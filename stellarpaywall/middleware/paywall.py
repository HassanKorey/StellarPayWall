from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from stellarpaywall.core.http402 import (
    DEFAULT_MERCHANT_DESTINATION,
    calculate_dynamic_price,
    generate_402_header,
)
from stellarpaywall.services.payment_verifier import verify_payment


class HTTP402Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Allow payment hash via either X-PayWall-Tx-Hash or X-Stellar-Tx-Hash
        tx_hash = request.headers.get("X-PayWall-Tx-Hash") or request.headers.get("X-Stellar-Tx-Hash")
        challenge_uuid = request.headers.get("X-PayWall-Challenge-UUID")
        
        amount = calculate_dynamic_price(request.url.path)

        if not tx_hash:
            headers = generate_402_header(amount=amount)
            return JSONResponse(status_code=402, content={"detail": "Payment Required"}, headers=headers)
        
        # Verify payment
        is_valid = await verify_payment(
            tx_hash=tx_hash,
            expected_amount=amount,
            destination=DEFAULT_MERCHANT_DESTINATION,
            expected_asset="XLM",
            challenge_uuid=challenge_uuid,
        )
        if not is_valid:
            headers = generate_402_header(amount=amount)
            return JSONResponse(status_code=402, content={"detail": "Invalid Payment"}, headers=headers)

        response = await call_next(request)
        return response
