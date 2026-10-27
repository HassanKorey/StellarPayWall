import asyncio
import time

import pytest

from stellarpaywall.cache.replay_guard import _used_hashes, mark_hash_used
from stellarpaywall.ledger import (
    NonceLedger,
    default_ledger,
    is_tx_spent,
    record_verified_tx,
    reset_replay_db,
)


@pytest.fixture(autouse=True)
def clean_ledger():
    _used_hashes.clear()
    reset_replay_db()
    yield
    _used_hashes.clear()
    reset_replay_db()


def test_nonce_ledger_record_and_spent():
    tx_hash = "test_ledger_hash_001"
    assert is_tx_spent(tx_hash) is False

    recorded = record_verified_tx(
        tx_hash=tx_hash,
        amount="0.05",
        asset="XLM",
        memo="test_memo",
        destination="merchant_1",
        ttl_seconds=3600,
    )
    assert recorded is True
    assert is_tx_spent(tx_hash) is True

    # Duplicate record must return False
    assert record_verified_tx(
        tx_hash=tx_hash,
        amount="0.05",
        asset="XLM",
    ) is False


def test_nonce_ledger_ttl_expiration():
    ledger = NonceLedger(db_path=":memory:", default_ttl=1)
    tx_hash = "test_expiring_hash_002"

    recorded = ledger.record(tx_hash=tx_hash, amount="1.0", asset="XLM", ttl_seconds=1)
    assert recorded is True
    assert ledger.is_spent(tx_hash) is True

    # Sleep slightly more than 1 second for TTL to expire
    time.sleep(1.1)

    # After TTL expiration, nonce should no longer be spent
    assert ledger.is_spent(tx_hash) is False

    # Cleanup expired nonces returns count
    ledger.record("expired_1", "1.0", "XLM", ttl_seconds=1)
    ledger.record("expired_2", "1.0", "XLM", ttl_seconds=1)
    time.sleep(1.1)
    deleted = ledger.cleanup_expired()
    assert deleted >= 2


@pytest.mark.asyncio
async def test_atomic_lock_prevents_concurrent_double_spend():
    """
    Simulate high-throughput concurrent requests with the exact same transaction hash.
    The atomic lock primitive ensures exactly one request acquires the nonce.
    """
    tx_hash = "race_condition_tx_hash_999"

    # Launch 10 concurrent tasks trying to mark the same hash as used
    results = await asyncio.gather(*[mark_hash_used(tx_hash) for _ in range(10)])

    # Exactly one request must succeed (True), all other 9 must fail (False)
    assert results.count(True) == 1
    assert results.count(False) == 9
    assert is_tx_spent(tx_hash) is False  # In-flight hash isn't committed until payment verified


@pytest.mark.asyncio
async def test_atomic_claim_concurrency():
    """Test claim_atomic under high concurrency on NonceLedger."""
    tx_hash = "atomic_claim_tx_777"
    ledger = default_ledger

    results = await asyncio.gather(
        *[ledger.claim_atomic(tx_hash, "0.05", "XLM", ttl_seconds=60) for _ in range(10)]
    )

    assert results.count(True) == 1
    assert results.count(False) == 9
    assert ledger.is_spent(tx_hash) is True
