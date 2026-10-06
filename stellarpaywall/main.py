from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from stellarpaywall.middleware.paywall import HTTP402Middleware
from stellarpaywall.middleware.replay_guard import ReplayGuardMiddleware
from stellarpaywall.routers.paywall import router as paywall_router

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

STATIC_HTML = Path(__file__).resolve().parent.parent / "frontend-static" / "index.html"

@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    if STATIC_HTML.exists():
        return FileResponse(STATIC_HTML, media_type="text/html")
    return HTMLResponse(
        "<h1>StellarPayWall Gateway Online</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>"
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}
