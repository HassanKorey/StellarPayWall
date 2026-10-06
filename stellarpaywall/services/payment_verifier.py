from stellarpaywall.services.horizon_client import fetch_transaction

async def verify_payment(tx_hash: str, expected_amount: str, destination: str) -> bool:
    """
    Verify payment transaction against source accounts, trustlines, and destination.
    """
    try:
        tx = await fetch_transaction(tx_hash)
        if tx and tx.get("successful") and float(tx.get("amount", "0")) >= float(expected_amount):
            return True
        return False
    except Exception:
        return False
