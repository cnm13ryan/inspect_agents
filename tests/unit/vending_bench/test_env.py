"""Unit tests for VendingEnv core functionality."""

from examples.vending_bench import EnvConfig, VendingEnv


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
    """Test that same seed produces identical results."""
    config1 = EnvConfig(seed=42)
    config2 = EnvConfig(seed=42)

    env1 = VendingEnv(config1)
    env2 = VendingEnv(config2)

    # Place same orders
    order1 = env1.place_order("coke", 5)
    order2 = env2.place_order("coke", 5)

    assert order1.delivery_day == order2.delivery_day
    assert order1.unit_cost == order2.unit_cost


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
    """Test restocking machine from storage."""
    env = VendingEnv()

    # Add some items to storage
    env.state.storage_inventory["coke"] = 10

    # Restock machine
    env.restock("coke", 5)

    assert env.state.storage_inventory["coke"] == 5
    assert env.state.machine_inventory["coke"] == 5


def test_place_order():
    """Test placing orders."""
    env = VendingEnv()

    order = env.place_order("coke", 10)

    assert order.sku == "coke"
    assert order.quantity == 10
    assert order.day_ordered == 0
    assert order.delivery_day > 0
    assert env.state.cash_balance < 500.0  # Cost deducted
    assert len(env.state.outstanding_orders) == 1
    assert len(env.state.outbox) == 1  # Email sent


def test_summary():
    """Test environment summary generation."""
    env = VendingEnv()

    # Set up some state
    env.state.storage_inventory["coke"] = 5
    env.state.machine_inventory["chips"] = 3
    env.place_order("water", 5)

    summary = env.summary()

    assert summary.day == 0
    assert summary.cash_balance < 500.0  # Order cost deducted
    assert summary.storage_inventory["coke"] == 5
    assert summary.machine_inventory["chips"] == 3
    assert len(summary.outstanding_orders) == 1
    assert summary.net_worth > 0
    assert summary.units_sold_total == 0
