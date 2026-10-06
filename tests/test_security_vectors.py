import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from stellarpaywall.cache.replay_guard import _used_hashes
from stellarpaywall.main import app
from stellarpaywall.services.horizon_client import (
    clear_mock_transactions,
    register_mock_transaction,
)
from stellarpaywall.services.soroban_verifier import verify_sac_transfer
from stellarpaywall.services.verifier import (
    is_tx_spent,
    reset_replay_db,
    verify_stellar_payment,
)


@pytest.fixture(autouse=True)
def clean_environment():
    _used_hashes.clear()
    reset_replay_db()
    clear_mock_transactions()
    yield
    _used_hashes.clear()
    reset_replay_db()
    clear_mock_transactions()

@pytest.mark.asyncio
async def test_standard_valid_402_payment_flow():
    """
    Test standard valid HTTP 402 negotiation flow:
    1. Initial request without payment receives 402 with X-PayWall-* headers.
    2. Client signs transaction with challenge UUID memo.
    3. Retried request with X-PayWall-Tx-Hash succeeds with 200 OK.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Challenge
        res1 = await ac.get("/protected-resource")
        assert res1.status_code == 402
        assert "X-PayWall-Challenge-UUID" in res1.headers
        challenge_uuid = res1.headers["X-PayWall-Challenge-UUID"]
        amount = res1.headers["X-PayWall-Amount"]

        # 2. Simulate valid payment on ledger
        tx_hash = f"tx_valid_{uuid.uuid4().hex[:12]}"
        register_mock_transaction(tx_hash, {
            "hash": tx_hash,
            "successful": True,
            "amount": amount,
            "asset": "XLM",
            "destination": "merchant_address",
            "memo": challenge_uuid
        })

        # 3. Retry with X-PayWall-Tx-Hash
        res2 = await ac.get(
            "/protected-resource",
            headers={
                "X-PayWall-Tx-Hash": tx_hash,
                "X-PayWall-Challenge-UUID": challenge_uuid
            }
        )
        assert res2.status_code == 200

@pytest.mark.asyncio
async def test_replayed_transaction_hash_rejection():
    """
    Test that once a transaction hash is verified and spent,
    subsequent replay attempts are rejected.
    """
    tx_hash = "replay_attack_tx_hash_123"
    memo = "test_challenge_uuid"
    register_mock_transaction(tx_hash, {
        "hash": tx_hash,
        "successful": True,
        "amount": "0.05",
        "asset": "XLM",
        "destination": "merchant_address",
        "memo": memo
    })

    # First verification must succeed
    verified_first = await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_asset="XLM",
        challenge_uuid=memo
    )
    assert verified_first is True
    assert is_tx_spent(tx_hash) is True

    # Immediate replay must fail
    verified_second = await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_asset="XLM",
        challenge_uuid=memo
    )
    assert verified_second is False

    # Also verify middleware rejects replayed transaction
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/protected-resource",
            headers={"X-PayWall-Tx-Hash": tx_hash}
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Transaction already spent"}

@pytest.mark.asyncio
async def test_underpayment_rejection():
    """
    Test that payment with amount less than the required HTTP 402 price is rejected.
    """
    tx_hash = "underpayment_tx_456"
    register_mock_transaction(tx_hash, {
        "hash": tx_hash,
        "successful": True,
        "amount": "0.01",  # Required is 0.05
        "asset": "XLM",
        "destination": "merchant_address",
        "memo": "memo123"
    })

    result = await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_asset="XLM",
        challenge_uuid="memo123"
    )
    assert result is False

@pytest.mark.asyncio
async def test_invalid_memo_rejection():
    """
    Test that payment where transaction memo does not match challenge UUID is rejected.
    """
    tx_hash = "invalid_memo_tx_789"
    register_mock_transaction(tx_hash, {
        "hash": tx_hash,
        "successful": True,
        "amount": "0.05",
        "asset": "XLM",
        "destination": "merchant_address",
        "memo": "attacker_arbitrary_memo"
    })

    result = await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_asset="XLM",
        challenge_uuid="expected_challenge_uuid_xyz"
    )
    assert result is False

@pytest.mark.asyncio
async def test_asset_mismatch_rejection():
    """
    Test that payment made with unauthorized asset (e.g. USDT instead of XLM) is rejected.
    """
    tx_hash = "asset_mismatch_tx_000"
    register_mock_transaction(tx_hash, {
        "hash": tx_hash,
        "successful": True,
        "amount": "0.05",
        "asset": "USDT",  # Expected XLM
        "destination": "merchant_address",
        "memo": "uuid_match"
    })

    result = await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_asset="XLM",
        challenge_uuid="uuid_match"
    )
    assert result is False

@pytest.mark.asyncio
async def test_soroban_vault_verification_mocking():
    """
    Test Soroban Smart Contract SAC token transfer verification.
    """
    # Valid SAC invocation
    valid_sac_res = await verify_sac_transfer("valid_soroban_tx", expected_amount="0.05")
    assert valid_sac_res is True

    # Invalid SAC invocation
    invalid_sac_res = await verify_sac_transfer("invalid_soroban_tx", expected_amount="0.05")
    assert invalid_sac_res is False
