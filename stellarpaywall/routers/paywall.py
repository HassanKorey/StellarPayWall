from fastapi import APIRouter
from stellarpaywall.core.http402 import paywall

router = APIRouter(tags=["Paywall API"])


@router.get(
    "/protected-resource",
    summary="Access Protected Resource",
    description="Returns premium content if a valid HTTP 402 payment header is provided.",
)
@paywall(price="0.05", asset="XLM", path="/protected-resource")
async def protected_resource():
    """
    Access a premium resource that requires a Stellar micropayment.
    Requires `X-Stellar-Tx-Hash` or `Bearer` token representing a valid transaction.
    """
    return {"message": "Premium content accessed successfully."}


@router.post(
    "/verify-payment",
    summary="Verify Payment Explicitly",
    description="Verify a payment hash without accessing a resource.",
)
@paywall(price="0.01", asset="XLM", path="/verify-payment")
async def verify_payment(tx_hash: str):
    """
    Verify if a transaction hash represents a valid payment to the merchant.
    """
    return {"status": "verified", "tx_hash": tx_hash}
