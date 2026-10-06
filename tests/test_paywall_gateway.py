import pytest
from httpx import ASGITransport, AsyncClient

from stellarpaywall.cache.replay_guard import _used_hashes
from stellarpaywall.main import app
from stellarpaywall.services.verifier import reset_replay_db


@pytest.fixture(autouse=True)
def clean_cache():
    _used_hashes.clear()
    reset_replay_db()

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_protected_resource_no_payment():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/protected-resource")
    assert response.status_code == 402
    assert "WWW-Authenticate" in response.headers
    assert response.json() == {"detail": "Payment Required"}

@pytest.mark.asyncio
async def test_protected_resource_with_invalid_payment():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": "invalid_hash"})
    assert response.status_code == 402
    assert response.json() == {"detail": "Invalid Payment"}

@pytest.mark.asyncio
async def test_replay_prevention():
    valid_hash = "valid_test_hash"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response1 = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": valid_hash})
        assert response1.status_code in (200, 402)
        
        response2 = await ac.get("/protected-resource", headers={"X-Stellar-Tx-Hash": valid_hash})
        assert response2.status_code == 400
        assert response2.json() == {"detail": "Transaction already spent"}
