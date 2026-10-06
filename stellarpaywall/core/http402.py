import uuid

DEFAULT_MERCHANT_DESTINATION = "merchant_address"

def calculate_dynamic_price(endpoint: str) -> str:
    """
    Calculate dynamic pricing based on endpoint, load, or query complexity.
    """
    base_prices = {
        "/protected-resource": "0.05",
        "/verify-payment": "0.01",
        "/api/v1/generate": "0.05",
        "/api/v1/search": "0.02",
        "/api/v1/analyze": "0.10",
        "/api/v1/embed": "0.01",
    }
    return base_prices.get(endpoint, "0.05")

def generate_402_header(
    asset: str = "XLM",
    amount: str = "0.05",
    destination: str = DEFAULT_MERCHANT_DESTINATION,
    challenge_uuid: str | None = None
) -> dict:
    if not challenge_uuid:
        challenge_uuid = str(uuid.uuid4())

    return {
        "WWW-Authenticate": f'Stellar asset="{asset}", amount="{amount}", destination="{destination}", challenge="{challenge_uuid}"',
        "X-PayWall-Amount": str(amount),
        "X-PayWall-Asset": str(asset),
        "X-PayWall-Destination": str(destination),
        "X-PayWall-Challenge-UUID": str(challenge_uuid),
    }
