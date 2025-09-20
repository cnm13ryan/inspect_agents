"""Unit tests for VendingEnv core functionality."""

import pytest

from examples.vending_bench import EnvConfig, VendingEnv
from examples.vending_bench.state import aggregate_sku_quantities

SUPPLIER_EMAIL = "orders@rfd-inc.com"


def _purchase_order_body() -> str:
    return (
        "Hello supplier,\n"
        "Please process the following purchase order:\n"
        "- 24 coke\n"
        "- 12 energy_drink\n"
        "Delivery address: 100 Market St, Unit 5, Springfield\n"
        "Account number: ACCT-123456\n"
        "Thank you!"
    )


def test_env_initialization():
    """Test basic environment initialization."""
    env = VendingEnv()

    assert env.state.day == 0
    assert env.state.minute == 0
    assert env.state.turns == 0
    assert env.state.cash_balance == 500.0
    assert env.state.cash_in_machine == 0.0
    assert not env.state.bankrupt
    assert len(env.state.demand_profiles) == 5  # Default catalogue


def test_deterministic_behavior_with_same_seed():
    """Test that same seed produces identical supplier responses."""
    config1 = EnvConfig(seed=42)
    config2 = EnvConfig(seed=42)

    env1 = VendingEnv(config1)
    env2 = VendingEnv(config2)

    body = _purchase_order_body()
    env1.queue_email(recipient=SUPPLIER_EMAIL, subject="Purchase order", body=body)
    env2.queue_email(recipient=SUPPLIER_EMAIL, subject="Purchase order", body=body)

    assert len(env1.state.outstanding_orders) == len(env2.state.outstanding_orders) == 2
    for order1, order2 in zip(env1.state.outstanding_orders, env2.state.outstanding_orders, strict=True):
        assert order1.delivery_day == order2.delivery_day
        assert order1.unit_cost == pytest.approx(order2.unit_cost)
        assert order1.quantity == order2.quantity


def test_advance_time():
    """Test time advancement."""
    env = VendingEnv()
    initial_turns = env.state.turns

    env.advance_time(60)

    assert env.state.minute == 60
    assert env.state.turns == initial_turns + 1


def test_day_rollover():
    """Test day rollover when minutes exceed 24 hours."""
    env = VendingEnv()

    # Advance close to end of day
    env.advance_time(23 * 60 + 30)  # 23.5 hours
    assert env.state.day == 0

    # Push over to next day
    env.advance_time(60)  # +1 hour
    assert env.state.day == 1
    assert env.state.minute == 30  # 30 minutes into new day


def test_restock():
    """Test restocking machine from storage with slot coordinates."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 10

    env.restock("coke", 5, row=0, column=0)

    slot = env.state.machine_inventory[0][0]
    assert slot is not None
    assert slot.sku == "coke"
    assert slot.quantity == 5
    assert env.state.storage_inventory["coke"] == 5


def test_restock_enforces_size_constraints():
    """Small products may not be stocked in large-item rows and vice versa."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 4
    with pytest.raises(ValueError):
        env.restock("coke", 2, row=2, column=0)

    env.state.storage_inventory["chips"] = 4
    with pytest.raises(ValueError):
        env.restock("chips", 2, row=0, column=0)


def test_restock_respects_capacity():
    """Restocking beyond slot capacity raises an error."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 10
    env.restock("coke", 6, row=0, column=0)

    with pytest.raises(ValueError):
        env.restock("coke", 1, row=0, column=0)


def test_demand_model_slot_sales_distribution():
    """Demand simulation tracks per-slot sales quantities."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 10
    env.restock("coke", 2, row=0, column=0)
    env.restock("coke", 4, row=0, column=1)

    outcome = env._demand.simulate_day(
        day=env.state.day,
        demand_profiles=env.state.demand_profiles,
        machine_inventory=env.state.machine_inventory,
    )

    total_slot_sales = sum(sale.quantity for sale in outcome.slot_sales.values())
    assert total_slot_sales == outcome.units_sold["coke"]
    assert (0, 0) in outcome.slot_sales
    # Slot (0,1) should contribute when demand exceeds first slot quantity
    if outcome.units_sold["coke"] > 2:
        assert (0, 1) in outcome.slot_sales


def test_email_purchase_creates_orders_and_deducts_cash():
    """Purchasing via email should create orders, deduct cash, and queue supplier confirmation."""
    env = VendingEnv()
    starting_cash = env.state.cash_balance

    body = _purchase_order_body()
    env.queue_email(recipient=SUPPLIER_EMAIL, subject="Purchase order", body=body)

    assert len(env.state.outstanding_orders) == 2
    total_order_cost = sum(order.total_cost for order in env.state.outstanding_orders)
    assert env.state.cash_balance == pytest.approx(starting_cash - total_order_cost)
    # Replies should be scheduled for the next day, not immediately delivered
    assert env.state.inbox == []
    assert env.state.scheduled_inbox

    env.end_of_day()

    # Reply arrives the following morning alongside the daily summary email
    supplier_messages = [msg for msg in env.state.inbox if msg.sender == SUPPLIER_EMAIL]
    assert supplier_messages, "Expected supplier confirmation in the inbox"


def test_supplier_quote_request_reply_next_day():
    """Supplier quote requests should produce next-day replies with catalog details."""
    env = VendingEnv()

    env.queue_email(
        recipient="supply@quickstock.com",
        subject="Need wholesale pricing",
        body="Please send your product list and pricing tiers.",
    )

    assert env.state.scheduled_inbox
    env.end_of_day()
    quote_messages = [msg for msg in env.state.inbox if msg.sender == "supply@quickstock.com"]
    assert len(quote_messages) == 1
    body_lower = quote_messages[0].body.lower()
    assert "moq" in body_lower or "min order" in body_lower


def test_unknown_email_gets_no_reply():
    """Emails to unknown recipients should not generate replies."""
    env = VendingEnv()

    env.queue_email(recipient="unknown@supplier.test", subject="Hello", body="Do you sell snacks?")

    assert env.state.scheduled_inbox == []


def test_set_price_updates_slot():
    """Setting price for a slot updates its stored price."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 6
    env.restock("coke", 3, row=0, column=0)

    slot = env.state.machine_inventory[0][0]
    assert slot is not None

    env.set_price({(0, 0): 2.0})

    assert slot.price == 2.0


def test_summary():
    """Test environment summary generation with email-based ordering."""
    env = VendingEnv()

    env.state.storage_inventory["coke"] = 5
    env.state.storage_inventory["chips"] = 3
    env.restock("chips", 3, row=2, column=0)
    env.queue_email(
        recipient="sales@metrofoods.example",
        subject="Order",
        body=(
            "Order 18 coke and 18 chocolate_bar for Springfield HQ.\n"
            "Delivery address: 200 Industrial Way\n"
            "Account: ACCT-999999"
        ),
    )

    summary = env.summary()

    assert summary.day == 0
    assert summary.cash_balance < 500.0  # Order cost deducted
    assert summary.storage_inventory["coke"] == 5
    assert summary.machine_inventory["chips"] == 3
    totals = aggregate_sku_quantities(summary.machine_slots)
    assert totals["chips"] == 3
    assert len(summary.outstanding_orders) == 2
    assert summary.net_worth > 0
    assert summary.units_sold_total == 0


def test_morning_update_preserves_machine_cash():
    """Machine cash should persist until explicitly collected."""

    env = VendingEnv()
    env.state.cash_in_machine = 50.0
    env.state.machine_inventory = {sku: 0 for sku in env.state.demand_profiles}

    starting_balance = env.state.cash_balance

    env.morning_update()

    assert env.state.cash_in_machine >= 50.0
    assert env.state.cash_balance == pytest.approx(starting_balance - env.config.daily_fee)


def test_bankruptcy_requires_grace_period():
    """Bankruptcy should only trigger after 10 consecutive negative days."""

    env = VendingEnv()
    env.state.cash_balance = -1.0
    env.state.machine_inventory = {sku: 0 for sku in env.state.demand_profiles}

    for day in range(9):
        env.end_of_day()

    assert not env.state.bankrupt

    env.end_of_day()

    assert env.state.bankrupt
