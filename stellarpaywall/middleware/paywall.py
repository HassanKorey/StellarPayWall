from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from stellarpaywall.core.http402 import (
    DEFAULT_MERCHANT_DESTINATION,
    calculate_dynamic_price,
    generate_402_header,
    get_route_paywall_config,
    is_challenge_expired,
    negotiate_payment_protocol,
)
from stellarpaywall.services.payment_verifier import verify_payment


class HTTP402Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip health check, docs, and public dashboard
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc", "/", "/dashboard", "/favicon.ico"]:
            return await call_next(request)

        # Allow payment hash via either X-PayWall-Tx-Hash or X-Stellar-Tx-Hash
        tx_hash = request.headers.get("X-PayWall-Tx-Hash") or request.headers.get("X-Stellar-Tx-Hash")
        challenge_uuid = request.headers.get("X-PayWall-Challenge-UUID")

        route_config = get_route_paywall_config(request.url.path)
        negotiation = negotiate_payment_protocol(request.headers, route_config=route_config)

        content_length = 0
        raw_cl = request.headers.get("content-length")
        if raw_cl and raw_cl.isdigit():
            content_length = int(raw_cl)

        amount = calculate_dynamic_price(
            request.url.path,
            query_params=request.query_params,
            payload_bytes=content_length,
            asset=negotiation.asset,
        )

        if not tx_hash:
            headers = generate_402_header(
                asset=negotiation.asset,
                amount=amount,
                scheme=negotiation.scheme,
                expires_in=negotiation.expires_in,
            )
            return JSONResponse(status_code=402, content={"detail": "Payment Required"}, headers=headers)

        if is_challenge_expired(challenge_uuid):
            headers = generate_402_header(
                asset=negotiation.asset,
                amount=amount,
                scheme=negotiation.scheme,
                expires_in=negotiation.expires_in,
            )
            return JSONResponse(status_code=402, content={"detail": "Challenge Expired"}, headers=headers)

        # Verify payment
        is_valid = await verify_payment(
            tx_hash=tx_hash,
            expected_amount=amount,
            destination=DEFAULT_MERCHANT_DESTINATION,
            expected_asset=negotiation.asset,
            challenge_uuid=challenge_uuid,
        )
        if not is_valid:
            headers = generate_402_header(
                asset=negotiation.asset,
                amount=amount,
                scheme=negotiation.scheme,
                expires_in=negotiation.expires_in,
            )
            return JSONResponse(status_code=402, content={"detail": "Invalid Payment"}, headers=headers)

        response = await call_next(request)
        return response
