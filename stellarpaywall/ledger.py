import asyncio
import contextlib
import logging
import os
import sqlite3
import time

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = int(os.environ.get("STELLAR_NONCE_TTL", "3600"))
DB_PATH = os.environ.get("STELLAR_REPLAY_DB_PATH", "stellar_replay.db")
REDIS_URL = os.environ.get("REDIS_URL", None)


class NonceLedger:
    """
    High-throughput anti-replay nonce ledger enforcing single-use transaction verification.
    Features:
    - Configurable Time-To-Live (TTL) expiration per nonce entry.
    - Automatic lazy and explicit pruning of expired nonces.
    - In-process asyncio key-level mutexes for atomic double-spend prevention under concurrency.
    - Pluggable storage engine: SQLite with WAL journaling or Redis distributed backend.
    """

    def __init__(
        self,
        db_path: str = DB_PATH,
        redis_url: str | None = REDIS_URL,
        default_ttl: int = DEFAULT_TTL_SECONDS,
    ):
        self.db_path = db_path
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._locks_mutex = asyncio.Lock()
        self._mem_conn: sqlite3.Connection | None = None
        self._init_sqlite()

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self) -> None:
        if self.db_path == ":memory:" or not os.path.exists(self.db_path):
            pass
        with self._get_sqlite_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_nonces (
                    tx_hash TEXT PRIMARY KEY,
                    amount TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    memo TEXT,
                    destination TEXT,
                    expires_at INTEGER NOT NULL,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nonces_expires_at ON verified_nonces (expires_at);
            """)
            # Ensure legacy verified_transactions table is also available if needed
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_transactions (
                    tx_hash TEXT PRIMARY KEY,
                    amount TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    memo TEXT,
                    destination TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    @contextlib.asynccontextmanager
    async def lock_key(self, key: str):
        """
        Atomic lock primitive for a specific transaction hash or nonce key.
        Prevents race conditions between concurrent requests presenting the same payment hash.
        """
        async with self._locks_mutex:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            lock = self._key_locks[key]

        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
            # Clean up lock object if not currently contested
            async with self._locks_mutex:
                if key in self._key_locks and not self._key_locks[key].locked():
                    self._key_locks.pop(key, None)

    def is_spent(self, tx_hash: str) -> bool:
        """
        Check whether a transaction hash has already been recorded and has not expired.
        Purges the nonce if its TTL has elapsed.
        """
        if not tx_hash:
            return False

        # Redis backend check if configured
        if self.redis_url:
            try:
                import redis
                r = redis.from_url(self.redis_url)
                if r.exists(f"nonce:{tx_hash}"):
                    return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis check failed, falling back to SQLite: %s", exc)

        now = int(time.time())
        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()
            # Query verified_nonces with expiration check
            cursor.execute(
                "SELECT expires_at FROM verified_nonces WHERE tx_hash = ?",
                (tx_hash,),
            )
            row = cursor.fetchone()
            if row:
                expires_at = row[0]
                if expires_at > now:
                    return True
                # Expired nonce, remove it to allow re-use or cleanup
                cursor.execute("DELETE FROM verified_nonces WHERE tx_hash = ?", (tx_hash,))
                cursor.execute("DELETE FROM verified_transactions WHERE tx_hash = ?", (tx_hash,))
                return False

            # Check legacy verified_transactions table
            cursor.execute(
                "SELECT 1 FROM verified_transactions WHERE tx_hash = ?",
                (tx_hash,),
            )
            if cursor.fetchone():
                return True

        return False

    def record(
        self,
        tx_hash: str,
        amount: str,
        asset: str,
        memo: str | None = None,
        destination: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Record a verified transaction hash into the nonce ledger with TTL.
        Returns True if recorded successfully, False if already present (replay detected).
        """
        if not tx_hash:
            return False

        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = int(time.time())
        expires_at = now + effective_ttl

        # Redis backend record if configured
        if self.redis_url:
            try:
                import redis
                r = redis.from_url(self.redis_url)
                # SET key 1 NX EX ttl
                acquired = r.set(f"nonce:{tx_hash}", "1", ex=effective_ttl, nx=True)
                if not acquired:
                    return False
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis record failed, falling back to SQLite: %s", exc)

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()
            # Check if active unexpired nonce exists
            cursor.execute("SELECT expires_at FROM verified_nonces WHERE tx_hash = ?", (tx_hash,))
            row = cursor.fetchone()
            if row:
                if row[0] > now:
                    return False  # Already spent
                # Expired, update/replace
                cursor.execute("DELETE FROM verified_nonces WHERE tx_hash = ?", (tx_hash,))

            try:
                cursor.execute(
                    """
                    INSERT INTO verified_nonces (tx_hash, amount, asset, memo, destination, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tx_hash, amount, asset, memo, destination, expires_at),
                )
                # Also record in legacy table for backward compatibility
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO verified_transactions (tx_hash, amount, asset, memo, destination)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tx_hash, amount, asset, memo, destination),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    async def claim_atomic(
        self,
        tx_hash: str,
        amount: str,
        asset: str,
        memo: str | None = None,
        destination: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Atomically checks and claims a nonce using the key lock primitive.
        Eliminates race conditions between simultaneous requests.
        """
        async with self.lock_key(tx_hash):
            if self.is_spent(tx_hash):
                return False
            return self.record(
                tx_hash=tx_hash,
                amount=amount,
                asset=asset,
                memo=memo,
                destination=destination,
                ttl_seconds=ttl_seconds,
            )

    def cleanup_expired(self) -> int:
        """
        Remove all expired nonces from the SQLite ledger.
        Returns the number of deleted records.
        """
        now = int(time.time())
        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM verified_transactions WHERE tx_hash IN (SELECT tx_hash FROM verified_nonces WHERE expires_at <= ?)",
                (now,),
            )
            cursor.execute("DELETE FROM verified_nonces WHERE expires_at <= ?", (now,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def reset(self) -> None:
        """Clear all nonces from the ledger (primarily for test fixture cleanup)."""
        if self.redis_url:
            try:
                import redis
                r = redis.from_url(self.redis_url)
                keys = r.keys("nonce:*")
                if keys:
                    r.delete(*keys)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis reset failed: %s", exc)

        with self._get_sqlite_connection() as conn:
            conn.execute("DELETE FROM verified_nonces")
            conn.execute("DELETE FROM verified_transactions")
            conn.commit()


# Default singleton instance
default_ledger = NonceLedger()


def get_ledger() -> NonceLedger:
    return default_ledger


def is_tx_spent(tx_hash: str, db_path: str = DB_PATH) -> bool:
    """Convenience function delegating to the NonceLedger."""
    if db_path != DB_PATH:
        ledger = NonceLedger(db_path=db_path)
        return ledger.is_spent(tx_hash)
    return default_ledger.is_spent(tx_hash)


def record_verified_tx(
    tx_hash: str,
    amount: str,
    asset: str,
    memo: str | None = None,
    destination: str | None = None,
    ttl_seconds: int | None = None,
    db_path: str = DB_PATH,
) -> bool:
    """Convenience function delegating to the NonceLedger."""
    if db_path != DB_PATH:
        ledger = NonceLedger(db_path=db_path)
        return ledger.record(
            tx_hash=tx_hash,
            amount=amount,
            asset=asset,
            memo=memo,
            destination=destination,
            ttl_seconds=ttl_seconds,
        )
    return default_ledger.record(
        tx_hash=tx_hash,
        amount=amount,
        asset=asset,
        memo=memo,
        destination=destination,
        ttl_seconds=ttl_seconds,
    )


def reset_replay_db(db_path: str = DB_PATH) -> None:
    """Convenience function resetting the NonceLedger."""
    if db_path != DB_PATH:
        ledger = NonceLedger(db_path=db_path)
        ledger.reset()
    else:
        default_ledger.reset()


def init_replay_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Legacy helper returning SQLite connection with verified_transactions table initialized."""
    ledger = NonceLedger(db_path=db_path)
    return ledger._get_sqlite_connection()
