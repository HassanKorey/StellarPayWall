from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from stellarpaywall.cache.replay_guard import mark_hash_used

class ReplayGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tx_hash = request.headers.get("X-Stellar-Tx-Hash")
        
        if tx_hash:
            is_new = await mark_hash_used(tx_hash)
            if not is_new:
                return JSONResponse(status_code=400, content={"detail": "Transaction already spent"})
        
        response = await call_next(request)
        return response
