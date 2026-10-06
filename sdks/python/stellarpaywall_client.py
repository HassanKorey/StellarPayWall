import requests

class StellarPaywallClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, **kwargs)
        
        if response.status_code == 402:
            auth_header = response.headers.get("WWW-Authenticate")
            print(f"Payment required: {auth_header}")
            
            # Handle automatic payment logic here
            tx_hash = "mock_signed_tx_hash" # Placeholder
            
            headers = kwargs.get("headers", {})
            headers["X-Stellar-Tx-Hash"] = tx_hash
            kwargs["headers"] = headers
            
            # Retry
            response = requests.request(method, url, **kwargs)
            
        return response
