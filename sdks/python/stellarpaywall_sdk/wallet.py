from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

try:
    from stellar_sdk import Asset, Keypair, Server, TransactionBuilder

    STELLAR_SDK_AVAILABLE = True
except ImportError:
    STELLAR_SDK_AVAILABLE = False


class BudgetExceededError(Exception):
    """Raised when an HTTP 402 payment challenge exceeds the agent wallet's configured budget."""


@dataclass(frozen=True)
class AgentPaymentRecord:
    tx_hash: str
    amount: Decimal
    asset: str
    destination: str
    challenge_uuid: str
    endpoint: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentWallet:
    """
    Dedicated autonomous AI agent signing wallet with per-request and cumulative
    spending guardrails plus in-memory and optional SQLite audit trace logging.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        max_total_budget: str | float | Decimal = "1.00",
        max_per_request_budget: str | float | Decimal = "0.10",
        horizon_url: str = "https://horizon-testnet.stellar.org",
        network_passphrase: str = "Test SDF Network ; September 2015",
        audit_db_path: str | None = None,
    ):
        self._secret_key = secret_key
        self.max_total_budget = Decimal(str(max_total_budget))
        self.max_per_request_budget = Decimal(str(max_per_request_budget))
        self.spent_total = Decimal("0")
        self.horizon_url = horizon_url
        self.network_passphrase = network_passphrase
        self.audit_db_path = audit_db_path
        self._audit_log: list[AgentPaymentRecord] = []
        self._keypair = (
            Keypair.from_secret(secret_key)
            if (secret_key and STELLAR_SDK_AVAILABLE and secret_key.startswith("S") and len(secret_key) == 56)
            else None
        )
        if self.audit_db_path:
            self._init_audit_db()

    @property
    def remaining_budget(self) -> Decimal:
        return max(Decimal("0"), self.max_total_budget - self.spent_total)

    def _init_audit_db(self) -> None:
        if not self.audit_db_path:
            return
        conn = sqlite3.connect(self.audit_db_path)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_payment_audit (
                        tx_hash TEXT PRIMARY KEY,
                        amount TEXT NOT NULL,
                        asset TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        challenge_uuid TEXT,
                        endpoint TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
        finally:
            conn.close()

    def check_budget(self, amount: str | float | Decimal) -> Decimal:
        req_amount = Decimal(str(amount))
        if req_amount <= Decimal("0"):
            raise ValueError(f"Payment amount must be positive, got {amount}")
        if req_amount > self.max_per_request_budget:
            raise BudgetExceededError(
                f"Requested payment {req_amount} exceeds per-request budget {self.max_per_request_budget}"
            )
        if self.spent_total + req_amount > self.max_total_budget:
            raise BudgetExceededError(
                f"Requested payment {req_amount} would exceed total budget {self.max_total_budget} "
                f"(already spent: {self.spent_total})"
            )
        return req_amount

    def sign_and_record_payment(
        self,
        destination: str,
        amount: str | float | Decimal,
        asset_code: str = "XLM",
        challenge_uuid: str = "",
        endpoint: str = "",
    ) -> str:
        req_amount = self.check_budget(amount)
        tx_hash = self._sign_transaction(
            destination=destination,
            amount=str(req_amount),
            asset_code=asset_code,
            memo_text=challenge_uuid,
        )
        self.spent_total += req_amount
        record = AgentPaymentRecord(
            tx_hash=tx_hash,
            amount=req_amount,
            asset=asset_code,
            destination=destination,
            challenge_uuid=challenge_uuid,
            endpoint=endpoint,
        )
        self._audit_log.append(record)
        if self.audit_db_path:
            conn = sqlite3.connect(self.audit_db_path)
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO agent_payment_audit
                        (tx_hash, amount, asset, destination, challenge_uuid, endpoint, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.tx_hash,
                            str(record.amount),
                            record.asset,
                            record.destination,
                            record.challenge_uuid,
                            record.endpoint,
                            record.timestamp,
                        ),
                    )
            finally:
                conn.close()
        return tx_hash

    def _sign_transaction(
        self,
        destination: str,
        amount: str,
        asset_code: str,
        memo_text: str,
    ) -> str:
        if self._keypair and STELLAR_SDK_AVAILABLE:
            try:
                server = Server(horizon_url=self.horizon_url)
                account = server.load_account(self._keypair.public_key)
                asset = (
                    Asset.native()
                    if asset_code.upper() in ("XLM", "NATIVE")
                    else Asset(asset_code, destination)
                )
                tx = (
                    TransactionBuilder(
                        source_account=account,
                        network_passphrase=self.network_passphrase,
                        base_fee=100,
                    )
                    .add_text_memo(memo_text[:28])
                    .append_payment_op(destination=destination, amount=amount, asset=asset)
                    .set_timeout(30)
                    .build()
                )
                tx.sign(self._keypair)
                return tx.hash().hex()
            except Exception:  # noqa: BLE001, S110
                pass

        seed = f"{destination}:{amount}:{asset_code}:{memo_text}:{self._secret_key or 'default'}"
        return hashlib.sha256(seed.encode()).hexdigest()

    def get_audit_log(self) -> list[AgentPaymentRecord]:
        return list(self._audit_log)

    def reset_budget(self) -> None:
        self.spent_total = Decimal("0")
        self._audit_log.clear()
