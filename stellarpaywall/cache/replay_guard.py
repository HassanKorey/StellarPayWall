import logging

from stellarpaywall.ledger import default_ledger

logger = logging.getLogger(__name__)

# Backward-compatibility alias for test suites
_used_hashes: set[str] = set()


async def mark_hash_used(tx_hash: str) -> bool:
    """
    Marks a transaction hash as seen/in-flight for replay prevention.
    Returns False if already spent or currently in-flight.
    """
    if not tx_hash:
        return False

    async with default_ledger.lock_key(tx_hash):
        if tx_hash in _used_hashes or default_ledger.is_spent(tx_hash):
            return False
        _used_hashes.add(tx_hash)
        return True


def clear_replay_cache() -> None:
    _used_hashes.clear()
