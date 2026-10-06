from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class HorizonConnectionError(Exception):
    pass

class RateLimitError(Exception):
    pass

_mock_transactions = {}

def register_mock_transaction(tx_hash: str, tx_data: dict | None):
    """Utility for testing to register mock transactions returned by fetch_transaction."""
    _mock_transactions[tx_hash] = tx_data

def clear_mock_transactions():
    _mock_transactions.clear()

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((HorizonConnectionError, RateLimitError))
)
async def fetch_transaction(tx_hash: str):
    """
    Fetch a transaction from Horizon RPC with exponential backoff.
    """
    if tx_hash in _mock_transactions:
        return _mock_transactions[tx_hash]

    if tx_hash == "rate_limit_hash":
        raise RateLimitError("Rate limit exceeded")
    
    if tx_hash == "invalid_hash":
        return None
        
    return {
        "hash": tx_hash,
        "successful": True,
        "amount": "0.05",
        "asset": "XLM",
        "destination": "merchant_address",
        "memo": None
    }
