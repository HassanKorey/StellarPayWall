from __future__ import annotations

from typing import Any, Callable

import requests

from ..wallet import AgentWallet
from .langchain import StellarPaywallRequestsWrapper

try:
    from crewai.tools import BaseTool as _CrewAIBaseTool
except ImportError:

    class _CrewAIBaseTool:  # type: ignore[no-redef]
        name: str = "CrewAI StellarPayWall Tool"
        description: str = ""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

        def run(self, *args: Any, **kwargs: Any) -> Any:
            return self._run(*args, **kwargs)


class CrewAIStellarPaywallTool(_CrewAIBaseTool):
    """
    CrewAI tool adapter with a dedicated AgentWallet and configurable spending
    guardrails for autonomous HTTP 402 micropayment negotiation.
    """

    name: str = "CrewAI StellarPayWall Tool"
    description: str = (
        "Autonomously fetch premium resources from StellarPayWall HTTP 402 endpoints "
        "with per-request and cumulative Stellar micropayment budget guardrails."
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
