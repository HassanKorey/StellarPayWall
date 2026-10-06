import pytest
from httpx import AsyncClient
from stellarpaywall.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_protected_resource_no_payment():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/protected-resource")
    assert response.status_code == 402
    assert "WWW-Authenticate" in response.headers
    assert response.json() == {"detail": "Payment Required"}

@pytest.mark.asyncio
async def test_protected_resource_with_invalid_payment():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": "invalid_hash"})
    assert response.status_code == 402
    assert response.json() == {"detail": "Invalid Payment"}

@pytest.mark.asyncio
async def test_replay_prevention():
    # Use a valid hash to bypass the paywall middleware first
    valid_hash = "valid_test_hash"
    
    # We mock fetch_transaction behavior in horizon_client or just test replay logic
    # The replay middleware runs first if added second, wait... HTTP402 is added first in main.py, so it runs LAST in the request phase.
    # ReplayGuardMiddleware is added second, so it runs FIRST in request phase.
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response1 = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": valid_hash})
        # Mock payment_verifier will fail for "valid_test_hash" because we didn't mock it to return true
        # But replay guard should register it
        assert response1.status_code == 402
        
        response2 = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": valid_hash})
        assert response2.status_code == 400
        assert response2.json() == {"detail": "Transaction already spent"}
