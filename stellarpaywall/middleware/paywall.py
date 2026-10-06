from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from stellarpaywall.core.http402 import calculate_dynamic_price, generate_402_header
from stellarpaywall.services.payment_verifier import verify_payment

class HTTP402Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        tx_hash = request.headers.get("X-Stellar-Tx-Hash")
        if not tx_hash:
            amount = calculate_dynamic_price(request.url.path)
            headers = generate_402_header(amount=amount)
            return JSONResponse(status_code=402, content={"detail": "Payment Required"}, headers=headers)
        
        # Verify payment
        amount = calculate_dynamic_price(request.url.path)
        is_valid = await verify_payment(tx_hash, amount, "merchant_address")
        if not is_valid:
            return JSONResponse(status_code=402, content={"detail": "Invalid Payment"}, headers=generate_402_header(amount=amount))

        response = await call_next(request)
        return response
