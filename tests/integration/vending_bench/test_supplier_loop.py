"""Integration tests for supplier search and email workflows."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from examples.vending_bench.env import VendingEnv
from examples.vending_bench.integrations import SupplierSearchHit, SupplierSearchItem
from examples.vending_bench.state import EmailMessage
from examples.vending_bench.supplier import SupplierModel
from examples.vending_bench.tools import ai_web_search


@pytest.fixture
def vending_env(monkeypatch: pytest.MonkeyPatch) -> VendingEnv:
    env = VendingEnv()
    monkeypatch.setattr("examples.vending_bench.tools.get_env", lambda: env)
    return env


def test_live_quote_flow_with_mocked_integrations(monkeypatch: pytest.MonkeyPatch, vending_env: VendingEnv) -> None:
    """Perplexity + GPT integration should register suppliers and generate grounded quotes."""

    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.delenv("VENDING_SUPPLIER_FORCE_STUB", raising=False)
    vending_env._supplier._gpt_api_key = "test-openai"
    vending_env._supplier._force_stub = False

    hit = SupplierSearchHit(
        name="Delta Wholesale",
        email="sales@delta-wholesale.test",
        catalog=[
            SupplierSearchItem(sku="coke", min_order=30, wholesale_price=0.62, lead_time_days=(2, 4)),
            SupplierSearchItem(sku="water", min_order=40, wholesale_price=0.28, lead_time_days=(2, 4)),
        ],
        website="https://delta-wholesale.test",
        phone="+1-555-0100",
        tags=("beverage",),
        notes="Regional beverage wholesaler with two-day delivery.",
        source="perplexity",
    )

    with patch("examples.vending_bench.tools.PerplexityClient.search_suppliers", return_value=[hit]):
        generated_bodies: list[str] = []

        def fake_generate(
            self: SupplierModel,
            *,
            client: object,
            subject: str,
            sender: str,
            recipient: str,
            current_day: int,
            body_prompt: str,
            system_prompt: str,
        ) -> EmailMessage:
            generated_bodies.append(body_prompt)
            return EmailMessage(
                day=current_day + 1,
                subject=subject,
                body="Live GPT reply",
                sender=sender,
                recipient=recipient,
            )

        monkeypatch.setattr(SupplierModel, "_ensure_gpt_client", lambda self: object())
        monkeypatch.setattr(SupplierModel, "_generate_gpt_email", fake_generate)

        search_tool = ai_web_search()
        result = search_tool(query="vending machine suppliers", max_results=3)

    assert result.results, "Expected at least one supplier result"
    first = result.results[0]
    assert first["contact"]["email"] == "sales@delta-wholesale.test"
    assert first["catalog"][0]["sku"] == "coke"

    history = vending_env.state.telemetry.get("supplier_search_history", [])
    assert history, "Search history should be recorded"
    assert history[-1]["mode"] == "live"

    # Send a quote request and ensure GPT integration handled it
    vending_env.queue_email(
        recipient="sales@delta-wholesale.test",
        subject="Quote request",
        body="Hi Supplier, please share pricing for Coke and water.",
    )

    assert generated_bodies, "GPT generator should have been invoked for quote replies"
    scheduled = vending_env.state.scheduled_inbox
    assert scheduled, "Supplier reply should be scheduled for next morning"
    assert scheduled[0].message.body == "Live GPT reply"


def test_purchase_flow_requires_account_and_confirms_orders(vending_env: VendingEnv) -> None:
    """Purchase orders must include account/address and yield delayed deliveries."""

    # Missing account number triggers clarification
    response = vending_env.queue_email(
        recipient="orders@rfd-inc.com",
        subject="Purchase order",
        body="Ordering 48 units of Coke for next week delivery.",
    )
    assert response.day == vending_env.state.day
    assert vending_env.state.scheduled_inbox[-1].message.body.startswith("Hello, this is Regional Food")
    assert "account number" in vending_env.state.scheduled_inbox[-1].message.body.lower()

    # Provide complete information to receive confirmation and scheduled delivery
    vending_env.queue_email(
        recipient="orders@rfd-inc.com",
        subject="Purchase order",
        body=("Please process 48 units of Coke.\nAccount number 123-456.\nDeliver to 123 Main St, Springfield."),
    )

    assert vending_env.state.outstanding_orders, "Order should be recorded as outstanding"
    order = vending_env.state.outstanding_orders[-1]
    assert 2 <= order.delivery_day <= 5, "Delivery should be scheduled with 2-5 day lead"

    confirmation = vending_env.state.scheduled_inbox[-1].message
    assert "Thanks for your purchase order" in confirmation.body
    assert str(order.delivery_day) in confirmation.body
