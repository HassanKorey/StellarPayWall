import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

try:
    import tenacity  # noqa: F401
except ModuleNotFoundError:
    _tenacity_stub = types.ModuleType("tenacity")
    _tenacity_stub.retry = lambda *a, **kw: (lambda f: f)  # type: ignore[attr-defined]
    _tenacity_stub.retry_if_exception_type = lambda *a, **kw: None  # type: ignore[attr-defined]
    _tenacity_stub.stop_after_attempt = lambda *a, **kw: None  # type: ignore[attr-defined]
    _tenacity_stub.wait_exponential = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["tenacity"] = _tenacity_stub

from fastapi.testclient import TestClient

from stellarpaywall.core.http402 import (
    calculate_dynamic_price,
    clear_challenge_ttl_registry,
    clear_paywall_registry,
    convert_asset_amount,
    generate_402_header,
    get_route_paywall_config,
    is_challenge_expired,
    negotiate_payment_protocol,
    paywall,
    register_challenge_ttl,
)
from stellarpaywall.main import app


class TestDynamicPricingAndProtocolNegotiator(unittest.TestCase):
    def setUp(self) -> None:
        clear_challenge_ttl_registry()
        self.client = TestClient(app)

    def test_decorator_registers_route_config(self) -> None:
        @paywall(price="0.25", asset="USDC", scheme="x402", expires_in=120, path="/custom-llm")
        async def custom_llm_route():
            return {"ok": True}

        cfg = get_route_paywall_config("/custom-llm")
        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(cfg.price, "0.25")
        self.assertEqual(cfg.asset, "USDC")
        self.assertEqual(cfg.scheme, "x402")
        self.assertEqual(cfg.expires_in, 120)
        self.assertEqual(calculate_dynamic_price("/custom-llm"), "0.25")

    def test_calculate_dynamic_price_complexity_and_conversion(self) -> None:
        # Base price for /api/v1/generate is 0.05 XLM
        self.assertEqual(calculate_dynamic_price("/api/v1/generate"), "0.05")

        # 2000 tokens (+0.02), depth=3 (+0.02), 200 rows (+0.01) => 0.05 + 0.05 = 0.10 XLM
        price_xlm = calculate_dynamic_price(
            "/api/v1/generate",
            query_params={"tokens": "2000", "depth": "3", "rows": "200"},
        )
        self.assertEqual(price_xlm, "0.10")

        # Convert 0.10 XLM to USDC (default rate: 1 XLM = 0.20 USDC => 0.02 USDC)
        price_usdc = calculate_dynamic_price(
            "/api/v1/generate",
            query_params={"tokens": "2000", "depth": "3", "rows": "200"},
            asset="USDC",
        )
        self.assertEqual(price_usdc, "0.02")
        self.assertEqual(convert_asset_amount("1.00", "USDC"), "0.20")

    def test_protocol_negotiation_headers(self) -> None:
        # Default fallback
        default_res = negotiate_payment_protocol({})
        self.assertEqual(default_res.scheme, "Stellar")
        self.assertEqual(default_res.asset, "XLM")

        # Prefer header negotiation
        prefer_res = negotiate_payment_protocol(
            {"Prefer": 'scheme="x402"; asset="USDC"'}
        )
        self.assertEqual(prefer_res.scheme, "x402")
        self.assertEqual(prefer_res.asset, "USDC")

        # Explicit X-PayWall-* headers
        explicit_res = negotiate_payment_protocol(
            {
                "X-PayWall-Scheme": "L402",
                "X-PayWall-Preferred-Asset": "USDC",
            }
        )
        self.assertEqual(explicit_res.scheme, "L402")
        self.assertEqual(explicit_res.asset, "USDC")

        # Accept vendor MIME type negotiation
        accept_res = negotiate_payment_protocol(
            {"Accept": "application/vnd.x402+json"}
        )
        self.assertEqual(accept_res.scheme, "x402")

    def test_challenge_expiration_tracking(self) -> None:
        challenge_id = "chal-ttl-test"
        expires_at = register_challenge_ttl(challenge_id, expires_in=60, now=1000)
        self.assertEqual(expires_at, 1060)
        self.assertFalse(is_challenge_expired(challenge_id, now=1059))
        self.assertTrue(is_challenge_expired(challenge_id, now=1061))

    def test_middleware_negotiates_and_enforces_dynamic_price_and_ttl(self) -> None:
        # 1. Request /api/v1/generate?tokens=3000 with USDC preference -> 0.05 + 0.03 = 0.08 XLM = 0.016 USDC
        response = self.client.get(
            "/api/v1/generate?tokens=3000",
            headers={
                "X-PayWall-Preferred-Asset": "USDC",
                "X-PayWall-Scheme": "x402",
            },
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.headers.get("X-PayWall-Asset"), "USDC")
        self.assertEqual(response.headers.get("X-PayWall-Scheme"), "x402")
        self.assertEqual(response.headers.get("X-PayWall-Amount"), "0.016")
        self.assertIn('x402 asset="USDC"', response.headers.get("WWW-Authenticate", ""))
        self.assertIn("X-PayWall-Expires-In", response.headers)
        self.assertIn("X-PayWall-Expires-At", response.headers)

        # 2. Expired challenge should return 402 Challenge Expired even before Horizon check
        expired_uuid = "expired-challenge-001"
        register_challenge_ttl(expired_uuid, expires_in=10, now=100)
        expired_resp = self.client.get(
            "/protected-resource",
            headers={
                "X-PayWall-Tx-Hash": "expired_tx_hash_001",
                "X-PayWall-Challenge-UUID": expired_uuid,
            },
        )
        self.assertEqual(expired_resp.status_code, 402)
        self.assertEqual(expired_resp.json().get("detail"), "Challenge Expired")

        # 3. Valid non-expired challenge passes through when verifier succeeds
        fresh_headers = generate_402_header(amount="0.05", asset="XLM")
        fresh_uuid = fresh_headers["X-PayWall-Challenge-UUID"]
        with patch(
            "stellarpaywall.middleware.paywall.verify_payment",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = True
            ok_resp = self.client.get(
                "/protected-resource",
                headers={
                    "X-PayWall-Tx-Hash": "fresh_valid_tx_hash_002",
                    "X-PayWall-Challenge-UUID": fresh_uuid,
                },
            )
            self.assertEqual(ok_resp.status_code, 200)
            mock_verify.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
