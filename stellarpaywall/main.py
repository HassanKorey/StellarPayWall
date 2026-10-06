from fastapi import FastAPI
from stellarpaywall.routers.paywall import router as paywall_router
from stellarpaywall.middleware.paywall import HTTP402Middleware
from stellarpaywall.middleware.replay_guard import ReplayGuardMiddleware

app = FastAPI(
    title="StellarPayWall",
    description="A High-Throughput HTTP 402 Stellar Micropayment API Gateway",
    version="1.0.0"
)

# Add middlewares
app.add_middleware(HTTP402Middleware)
app.add_middleware(ReplayGuardMiddleware)

# Include routers
app.include_router(paywall_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
