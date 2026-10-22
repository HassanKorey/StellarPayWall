import os
from decimal import Decimal

from stellarpaywall.ledger import (
    DEFAULT_TTL_SECONDS,
    init_replay_db,
    is_tx_spent,
    record_verified_tx,
    reset_replay_db,
)
from stellarpaywall.services.horizon_client import fetch_transaction

DB_PATH = os.environ.get("STELLAR_REPLAY_DB_PATH", "stellar_replay.db")

__all__ = [
    "DB_PATH",
    "init_replay_db",
    "is_tx_spent",
    "record_verified_tx",
    "reset_replay_db",
    "verify_stellar_payment",
]


async def verify_stellar_payment(
    tx_hash: str,
    expected_amount: str,
    destination: str,
    expected_asset: str = "XLM",
    challenge_uuid: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db_path: str = DB_PATH,
) -> bool:
    """
    Hardened payment verifier for Stellar Horizon transactions:
    1. Blocks transaction replay attacks via SQLite/Redis cache with TTL.
    2. Enforces exact asset matching (XLM or SAC/SEP-41 tokens).
    3. Enforces minimum payment amount validation.
    4. Validates that transaction memo strictly matches the HTTP 402 challenge UUID.
    """
    if not tx_hash or not expected_amount:
        return False

    # 1. Anti-Replay Check: If transaction hash was already spent, reject immediately
    if is_tx_spent(tx_hash, db_path=db_path):
        return False

    # 2. Fetch transaction details from Horizon RPC (with exponential backoff)
    try:
        tx = await fetch_transaction(tx_hash)
    except Exception:  # noqa: BLE001
        return False

    if not tx or not tx.get("successful", False):
        return False

    # 3. Minimum payment amount validation
    try:
        actual_amount = Decimal(str(tx.get("amount", "0")))
        required_amount = Decimal(str(expected_amount))
        if actual_amount < required_amount:
            return False
    except (ValueError, ArithmeticError):
        return False

    # 4. Exact asset matching (XLM / native vs SAC / issued assets)
    tx_asset = str(tx.get("asset", "XLM")).upper()
    req_asset = str(expected_asset).upper()

    # Normalize native representations
    if req_asset in ("XLM", "NATIVE") and tx_asset in ("XLM", "NATIVE"):
        pass
    elif tx_asset != req_asset:
        return False

    # 5. Destination address validation (if specified in tx)
    tx_dest = tx.get("destination")
    if tx_dest and destination and tx_dest != destination:
        return False

    # 6. Strict Challenge UUID / Memo validation
    if challenge_uuid is not None:
        tx_memo = tx.get("memo")
        if tx_memo != challenge_uuid:
            return False

    # 7. Record transaction hash into replay ledger to block duplicate spending
    recorded = record_verified_tx(
        tx_hash=tx_hash,
        amount=str(actual_amount),
        asset=tx_asset,
        memo=tx.get("memo"),
        destination=destination,
        ttl_seconds=ttl_seconds,
        db_path=db_path,
    )
    return recorded
