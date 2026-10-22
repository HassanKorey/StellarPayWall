import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from stellarpaywall.cache.replay_guard import _used_hashes
from stellarpaywall.main import app
from stellarpaywall.services.horizon_client import (
    clear_mock_transactions,
    register_mock_transaction,
)
from stellarpaywall.services.soroban_verifier import (
    clear_mock_soroban_txs,
    register_mock_soroban_tx,
    verify_sac_transfer,
)
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
    clear_mock_soroban_txs()
    yield
    _used_hashes.clear()
    reset_replay_db()
    clear_mock_transactions()
    clear_mock_soroban_txs()

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
    Test Soroban Smart Contract SAC token transfer verification baseline.
    """
    # Valid SAC invocation
    valid_sac_res = await verify_sac_transfer("valid_soroban_tx", expected_amount="0.05")
    assert valid_sac_res is True

    # Invalid SAC invocation
    invalid_sac_res = await verify_sac_transfer("invalid_soroban_tx", expected_amount="0.05")
    assert invalid_sac_res is False


@pytest.mark.asyncio
async def test_soroban_sac_event_verifier_full_flow():
    """
    Test SEP-41 token transfer event parsing and validation:
    Validates contract ID, recipient address, amount, and challenge UUID.
    """
    tx_hash = "soroban_sac_tx_valid_001"
    contract_id = "CA5Q7TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJSEPQ"
    recipient = "GA7QYNF7SOWQ3GLR2BGMZEHXAVIRZA4KVWLTJJFC7MGXUA74P7UJVWAC"
    challenge_uuid = "challenge-uuid-sac-test-123"

    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": contract_id,
                "type": "contract",
                "topics": ["transfer", "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5", recipient],
                "data": "1000000",  # 0.10 tokens (scaled 10^7)
                "inSuccessfulContractCall": True,
                "memo": challenge_uuid,
            }
        ],
        "memo": challenge_uuid,
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.10",
        destination=recipient,
        expected_contract_id=contract_id,
        challenge_uuid=challenge_uuid,
    )
    assert verified is True

    # Verify anti-replay recorded the spent hash
    assert is_tx_spent(tx_hash) is True
    replayed = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.10",
        destination=recipient,
        expected_contract_id=contract_id,
        challenge_uuid=challenge_uuid,
    )
    assert replayed is False


@pytest.mark.asyncio
async def test_soroban_sac_contract_id_mismatch():
    """Test rejection when contract ID in event log does not match expected token contract."""
    tx_hash = "soroban_sac_tx_bad_contract"
    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": "C_WRONG_CONTRACT_ID",
                "type": "contract",
                "topics": ["transfer", "G_SENDER", "merchant_address"],
                "data": "500000",
                "inSuccessfulContractCall": True,
            }
        ],
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        expected_contract_id="C_EXPECTED_USDC_CONTRACT",
    )
    assert verified is False


@pytest.mark.asyncio
async def test_soroban_sac_recipient_mismatch():
    """Test rejection when recipient address in event log does not match merchant address."""
    tx_hash = "soroban_sac_tx_bad_recipient"
    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": "CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJSEPQ",
                "type": "contract",
                "topics": ["transfer", "G_SENDER", "G_SOME_OTHER_RECIPIENT"],
                "data": "500000",
                "inSuccessfulContractCall": True,
            }
        ],
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
    )
    assert verified is False


@pytest.mark.asyncio
async def test_soroban_sac_underpayment_rejection():
    """Test rejection when token amount transferred in event is less than required."""
    tx_hash = "soroban_sac_tx_underpaid"
    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": "CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJSEPQ",
                "type": "contract",
                "topics": ["transfer", "G_SENDER", "merchant_address"],
                "data": "100000",  # 0.01 tokens, but 0.05 required
                "inSuccessfulContractCall": True,
            }
        ],
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
    )
    assert verified is False


@pytest.mark.asyncio
async def test_soroban_sac_memo_challenge_mismatch():
    """Test rejection when transaction memo / challenge UUID does not match requirement."""
    tx_hash = "soroban_sac_tx_bad_memo"
    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": "CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJSEPQ",
                "type": "contract",
                "topics": ["transfer", "G_SENDER", "merchant_address"],
                "data": "500000",
                "inSuccessfulContractCall": True,
                "memo": "attacker_memo_123",
            }
        ],
        "memo": "attacker_memo_123",
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.05",
        destination="merchant_address",
        challenge_uuid="expected_challenge_uuid_xyz",
    )
    assert verified is False


@pytest.mark.asyncio
async def test_soroban_paywall_vault_event_verification():
    """Test parsing and verification of PaywallVault PaymentVerified events."""
    tx_hash = "soroban_vault_tx_001"
    contract_id = "CV67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJSEPQ"
    challenge_uuid = "req_payment_402_uuid"

    register_mock_soroban_tx(tx_hash, {
        "status": "SUCCESS",
        "events": [
            {
                "contractId": contract_id,
                "type": "contract",
                "topics": ["PaymentVerified", challenge_uuid],
                "data": "500000",  # 0.05
                "inSuccessfulContractCall": True,
            }
        ],
    })

    verified = await verify_sac_transfer(
        tx_hash=tx_hash,
        expected_amount="0.05",
        expected_contract_id=contract_id,
        challenge_uuid=challenge_uuid,
    )
    assert verified is True

