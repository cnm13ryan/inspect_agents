"""Performance tests for vending bench simulator."""

import time

from examples.vending_bench import EnvConfig, VendingEnv


def test_2000_step_performance():
    """Test that 2000-step simulation completes within reasonable time."""
    config = EnvConfig(
        seed=42,
        starting_cash=10000.0,  # High cash to avoid bankruptcy
        max_turns=2000,
        minutes_per_turn=60,
    )
    env = VendingEnv(config)

    start_time = time.time()

    # Run 2000 steps
    for step in range(2000):
        # Occasionally place orders and restock
        if step % 50 == 0 and env.state.cash_balance > 100:
            try:
                env.place_order("coke", 10)
            except ValueError:
                pass  # Might fail due to insufficient cash

        if step % 30 == 0:
            # Restock from storage
            for sku in ["coke", "water", "chips"]:
                storage = env.state.storage_inventory.get(sku, 0)
                if storage > 0:
                    restock_qty = min(5, storage)
                    env.restock(sku, restock_qty)

        # Advance time
        env.advance_time()

        # Stop if bankrupt
        if env.state.bankrupt:
            break

    end_time = time.time()
    duration = end_time - start_time

    print(f"2000-step simulation took {duration:.2f} seconds")
    print(f"Final state: Day {env.state.day}, Turn {env.state.turns}, Cash {env.state.cash_balance:.2f}")

    # Should complete within 30 seconds (reasonable for CI)
    assert duration < 30.0, f"Simulation took too long: {duration:.2f}s"

    # Verify we advanced time
    assert env.state.turns <= 2000
    assert env.state.day > 0
