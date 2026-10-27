from decimal import Decimal
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import requests

from sdks.python.stellarpaywall_sdk.agent_adapters.crewai import CrewAIStellarPaywallTool
from sdks.python.stellarpaywall_sdk.agent_adapters.langchain import (
    StellarPaywallRequestsWrapper,
    StellarPaywallTool,
)
from sdks.python.stellarpaywall_sdk.wallet import AgentWallet, BudgetExceededError


def _make_response(status_code: int, json_body: dict, headers: dict | None = None) -> requests.Response:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


class TestAgentPaymentAdapters(unittest.TestCase):
    def test_langchain_tool_negotiates_402_and_logs_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_db = Path(tmpdir) / "agent_audit.db"
            wallet = AgentWallet(
                secret_key="agent-test-secret",
                max_total_budget="0.50",
                max_per_request_budget="0.10",
                audit_db_path=str(audit_db),
            )

            calls = []

            def fake_transport(method: str, url: str, **kwargs):
                calls.append((method, url, kwargs.get("headers") or {}))
                if len(calls) == 1:
                    return _make_response(
                        402,
                        {"detail": "Payment Required"},
                        headers={
                            "X-PayWall-Amount": "0.05",
                            "X-PayWall-Asset": "XLM",
                            "X-PayWall-Destination": "GMERCHANT123",
                            "X-PayWall-Challenge-UUID": "uuid-langchain-001",
                        },
                    )
                return _make_response(200, {"message": "Premium content accessed successfully."})

            tool = StellarPaywallTool(
                base_url="http://paywall.local",
                wallet=wallet,
                transport_fn=fake_transport,
            )

            result = tool.invoke("/protected-resource")
            self.assertEqual(result, {"message": "Premium content accessed successfully."})
            self.assertEqual(len(calls), 2)

            retry_headers = calls[1][2]
            self.assertEqual(len(retry_headers["X-PayWall-Tx-Hash"]), 64)
            self.assertEqual(retry_headers["X-Stellar-Tx-Hash"], retry_headers["X-PayWall-Tx-Hash"])
            self.assertEqual(retry_headers["X-PayWall-Challenge-UUID"], "uuid-langchain-001")

            self.assertEqual(wallet.spent_total, Decimal("0.05"))
            self.assertEqual(wallet.remaining_budget, Decimal("0.45"))

            audit_log = wallet.get_audit_log()
            self.assertEqual(len(audit_log), 1)
            self.assertEqual(audit_log[0].destination, "GMERCHANT123")
            self.assertEqual(audit_log[0].amount, Decimal("0.05"))
            self.assertEqual(audit_log[0].challenge_uuid, "uuid-langchain-001")

            conn = sqlite3.connect(str(audit_db))
            try:
                rows = conn.execute("SELECT tx_hash, amount, destination FROM agent_payment_audit").fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][1], "0.05")
                self.assertEqual(rows[0][2], "GMERCHANT123")
            finally:
                conn.close()

    def test_crewai_tool_enforces_per_request_and_total_budget(self):
        wallet = AgentWallet(
            secret_key="crewai-secret",
            max_total_budget="0.08",
            max_per_request_budget="0.06",
        )

        def fake_transport_expensive(method: str, url: str, **kwargs):
            return _make_response(
                402,
                {"detail": "Payment Required"},
                headers={
                    "WWW-Authenticate": 'Stellar asset="XLM", amount="0.10", destination="GMERCHANT", challenge="c-1"',
                },
            )

        expensive_tool = CrewAIStellarPaywallTool(
            base_url="http://paywall.local",
            wallet=wallet,
            transport_fn=fake_transport_expensive,
        )

        with self.assertRaisesRegex(BudgetExceededError, "exceeds per-request budget"):
            expensive_tool.run("/api/v1/analyze")
        self.assertEqual(wallet.spent_total, Decimal("0"))

        step = 0

        def fake_transport_affordable(method: str, url: str, **kwargs):
            nonlocal step
            step += 1
            headers = kwargs.get("headers") or {}
            if "X-PayWall-Tx-Hash" not in headers:
                return _make_response(
                    402,
                    {"detail": "Payment Required"},
                    headers={
                        "X-PayWall-Amount": "0.05",
                        "X-PayWall-Asset": "XLM",
                        "X-PayWall-Destination": "GMERCHANT",
                        "X-PayWall-Challenge-UUID": f"uuid-{step}",
                    },
                )
            return _make_response(200, {"data": "ok"})

        affordable_tool = CrewAIStellarPaywallTool(
            base_url="http://paywall.local",
            wallet=wallet,
            transport_fn=fake_transport_affordable,
        )

        res = affordable_tool.run("/api/v1/generate")
        self.assertEqual(res, {"data": "ok"})
        self.assertEqual(wallet.spent_total, Decimal("0.05"))

        with self.assertRaisesRegex(BudgetExceededError, "would exceed total budget"):
            affordable_tool.run("/api/v1/generate")
        self.assertEqual(wallet.spent_total, Decimal("0.05"))

    def test_requests_wrapper_passthrough_on_200(self):
        def fake_transport(method: str, url: str, **kwargs):
            return _make_response(200, {"status": "ok"})

        wrapper = StellarPaywallRequestsWrapper(
            base_url="http://paywall.local",
            transport_fn=fake_transport,
        )
        resp = wrapper.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(wrapper.wallet.spent_total, Decimal("0"))
