from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from stellarpaywall.cache.replay_guard import mark_hash_used
from stellarpaywall.services.verifier import is_tx_spent


class ReplayGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tx_hash = request.headers.get("X-PayWall-Tx-Hash") or request.headers.get("X-Stellar-Tx-Hash")
        
        if tx_hash and (is_tx_spent(tx_hash) or not await mark_hash_used(tx_hash)):
            return JSONResponse(status_code=400, content={"detail": "Transaction already spent"})
        
        response = await call_next(request)
        return response
