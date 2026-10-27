from __future__ import annotations

import re
from typing import Any, Callable

import requests

from ..wallet import AgentWallet

try:
    from langchain_core.tools import BaseTool as _LangChainBaseTool
except ImportError:

    class _LangChainBaseTool:  # type: ignore[no-redef]
        name: str = "stellar_paywall_tool"
        description: str = ""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

        def invoke(self, tool_input: str | dict[str, Any], **kwargs: Any) -> Any:
            if isinstance(tool_input, dict):
                return self._run(**tool_input)
            return self._run(tool_input)

        async def ainvoke(self, tool_input: str | dict[str, Any], **kwargs: Any) -> Any:
            if isinstance(tool_input, dict):
                return await self._arun(**tool_input)
            return await self._arun(tool_input)


class StellarPaywallRequestsWrapper:
    """
    Drop-in HTTP wrapper for LangChain / LlamaIndex agents that transparently
    negotiates HTTP 402 challenges within the configured AgentWallet budget.
    """

    def __init__(
        self,
        base_url: str,
        wallet: AgentWallet | None = None,
        secret_key: str | None = None,
        max_total_budget: str | float = "1.00",
        max_per_request_budget: str | float = "0.10",
        transport_fn: Callable[..., requests.Response] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.wallet = wallet or AgentWallet(
            secret_key=secret_key,
            max_total_budget=max_total_budget,
            max_per_request_budget=max_per_request_budget,
        )
        self._transport_fn = transport_fn or requests.request

    @staticmethod
    def parse_challenge(response: requests.Response) -> dict[str, str]:
        headers = response.headers
        amount = headers.get("X-PayWall-Amount")
        asset = headers.get("X-PayWall-Asset")
        destination = headers.get("X-PayWall-Destination")
        challenge_uuid = headers.get("X-PayWall-Challenge-UUID")

        auth_header = headers.get("WWW-Authenticate", "")
        if not amount and "amount=" in auth_header:
            m = re.search(r'amount="([^"]+)"', auth_header)
            if m:
                amount = m.group(1)
        if not asset and "asset=" in auth_header:
            m = re.search(r'asset="([^"]+)"', auth_header)
            if m:
                asset = m.group(1)
        if not destination and "destination=" in auth_header:
            m = re.search(r'destination="([^"]+)"', auth_header)
            if m:
                destination = m.group(1)
        if not challenge_uuid and "challenge=" in auth_header:
            m = re.search(r'challenge="([^"]+)"', auth_header)
            if m:
                challenge_uuid = m.group(1)

        return {
            "amount": amount or "0.05",
            "asset": asset or "XLM",
            "destination": destination or "merchant_address",
            "challenge_uuid": challenge_uuid or "",
        }

    def request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        if endpoint.startswith(("http://", "https://")):
            url = endpoint
        elif endpoint.startswith("/"):
            url = f"{self.base_url}{endpoint}"
        else:
            url = f"{self.base_url}/{endpoint}"

        response = self._transport_fn(method, url, **kwargs)
        if response.status_code == 402:
            challenge = self.parse_challenge(response)
            tx_hash = self.wallet.sign_and_record_payment(
                destination=challenge["destination"],
                amount=challenge["amount"],
                asset_code=challenge["asset"],
                challenge_uuid=challenge["challenge_uuid"],
                endpoint=endpoint,
            )
            headers = dict(kwargs.get("headers") or {})
            headers["X-PayWall-Tx-Hash"] = tx_hash
            headers["X-Stellar-Tx-Hash"] = tx_hash
            if challenge["challenge_uuid"]:
                headers["X-PayWall-Challenge-UUID"] = challenge["challenge_uuid"]
            kwargs["headers"] = headers
            response = self._transport_fn(method, url, **kwargs)

        return response

    def get(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)


class StellarPaywallTool(_LangChainBaseTool):
    """
    LangChain tool binding that allows an autonomous agent to query endpoints
    protected by StellarPayWall HTTP 402 micropayments with budget guardrails.
    """

    name: str = "stellar_paywall_tool"
    description: str = (
        "Query a StellarPayWall-protected HTTP API endpoint, automatically negotiating "
        "HTTP 402 micropayment challenges within the configured Stellar agent budget."
    )
    requests_wrapper: StellarPaywallRequestsWrapper

    def __init__(
        self,
        base_url: str,
        wallet: AgentWallet | None = None,
        secret_key: str | None = None,
        max_total_budget: str | float = "1.00",
        max_per_request_budget: str | float = "0.10",
        transport_fn: Callable[..., requests.Response] | None = None,
        **kwargs: Any,
    ) -> None:
        wrapper = StellarPaywallRequestsWrapper(
            base_url=base_url,
            wallet=wallet,
            secret_key=secret_key,
            max_total_budget=max_total_budget,
            max_per_request_budget=max_per_request_budget,
            transport_fn=transport_fn,
        )
        super().__init__(requests_wrapper=wrapper, **kwargs)
        self.requests_wrapper = wrapper

    @property
    def wallet(self) -> AgentWallet:
        return self.requests_wrapper.wallet

    def _run(self, endpoint: str, method: str = "GET", **kwargs: Any) -> Any:
        resp = self.requests_wrapper.request(method, endpoint, **kwargs)
        try:
            return resp.json()
        except Exception:  # noqa: BLE001
            return resp.text

    async def _arun(self, endpoint: str, method: str = "GET", **kwargs: Any) -> Any:
        return self._run(endpoint=endpoint, method=method, **kwargs)
