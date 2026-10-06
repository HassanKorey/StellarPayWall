def calculate_dynamic_price(endpoint: str) -> str:
    """
    Calculate dynamic pricing based on endpoint, load, or query complexity.
    """
    base_prices = {
        "/protected-resource": "0.05",
        "/verify-payment": "0.01",
    }
    return base_prices.get(endpoint, "0.10")

def generate_402_header(asset: str = "XLM", amount: str = "0.05") -> dict:
    return {
        "WWW-Authenticate": f'Stellar asset="{asset}", amount="{amount}"'
    }
