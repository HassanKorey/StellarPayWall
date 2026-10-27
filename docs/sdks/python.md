# Python Client SDK 🐍

The StellarPayWall Python SDK provides an asynchronous HTTP client that transparently handles the `HTTP 402 Payment Required` challenge handshake, builds and signs Stellar transactions, and retries the request with proof-of-payment headers.

---

## 📦 Installation

```bash
pip install stellarpaywall-sdk
# Or directly from source:
pip install git+https://github.com/HassanKorey/StellarPayWall-app.git#subdirectory=sdks/python
```

---

## ⚡ Quick Start: Automatic 402 Interceptor

The `AsyncStellarPayWallClient` automatically detects 402 responses, parses the challenge headers, constructs a Stellar micropayment transaction, submits it to the Horizon or Soroban RPC network, and returns the successful `200 OK` response without requiring manual challenge handling.

```python
import asyncio
from stellarpaywall_client import AsyncStellarPayWallClient

async def main():
    client = AsyncStellarPayWallClient(
        secret_key="S...",          # Stellar account secret seed (funded via Friendbot on testnet)
        base_url="https://stellarpaywall.onrender.com",
        network_passphrase="Test SDF Network ; September 2015",
    )

    # Calling a protected resource automatically negotiates 402 payment:
    response = await client.get("/protected-resource")
    print("Status:", response.status_code)
    print("Content:", response.json())

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🤖 AI Agent Integration (LangChain & CrewAI)

StellarPayWall SDK provides drop-in tool wrappers for autonomous agent frameworks:

### LangChain Tool Adapter
```python
from langchain.tools import tool
from stellarpaywall_client import AsyncStellarPayWallClient

client = AsyncStellarPayWallClient(
    secret_key="S...",
    base_url="https://stellarpaywall.onrender.com",
)

@tool
async def query_premium_market_data(query: str) -> str:
    """Queries premium financial analytics behind a Stellar 402 paywall."""
    res = await client.get(f"/api/v1/analyze?q={query}")
    return res.text
```

### CrewAI Agent Integration
```python
from crewai import Agent, Task, Crew
from stellarpaywall_client import AsyncStellarPayWallClient

class MonetizedAPITool:
    def __init__(self, secret_key: str):
        self.client = AsyncStellarPayWallClient(secret_key=secret_key)

    def fetch_data(self, endpoint: str) -> dict:
        import asyncio
        return asyncio.run(self.client.get(endpoint)).json()

researcher = Agent(
    role="Web3 Financial Analyst",
    goal="Retrieve real-time market data through monetized API endpoints",
    backstory="Autonomous analyst funded with testnet XLM to query high-value paywalled APIs.",
    verbose=True,
)
```

---

## ⚙️ Configuration Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `secret_key` | `str` | *Required* | Stellar secret seed (`S...`) used to sign payments |
| `base_url` | `str` | `https://stellarpaywall.onrender.com` | Base URL of the gateway |
| `horizon_url` | `str` | `https://horizon-testnet.stellar.org` | Stellar Horizon RPC server URL |
| `max_price_per_call` | `Decimal` | `1.00` | Safety limit preventing accidental overpayment |
| `timeout` | `float` | `15.0` | HTTP request timeout in seconds |
