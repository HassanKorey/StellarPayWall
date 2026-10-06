import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class HorizonConnectionError(Exception):
    pass

class RateLimitError(Exception):
    pass

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((HorizonConnectionError, RateLimitError))
)
async def fetch_transaction(tx_hash: str):
    """
    Fetch a transaction from Horizon RPC with exponential backoff.
    """
    # Mock implementation for the test
    if tx_hash == "rate_limit_hash":
        raise RateLimitError("Rate limit exceeded")
    
    if tx_hash == "invalid_hash":
        return None
        
    return {"hash": tx_hash, "successful": True, "amount": "0.05"}
