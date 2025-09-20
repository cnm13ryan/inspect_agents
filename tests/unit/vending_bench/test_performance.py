"""Performance tests for vending bench simulator."""

import time

from examples.vending_bench import EnvConfig, VendingEnv

SUPPLIER_EMAIL = "orders@rfd-inc.com"
PURCHASE_TEMPLATE = (
    "Please order 24 coke for next week delivery.\nDelivery address: 500 Commerce Way\nAccount number: PERF-ACCT-01."
)


def test_2000_step_performance():
    """Test that 2000-step simulation completes within reasonable time."""
    config = EnvConfig(
        seed=42,
        starting_cash=10000.0,  # High cash to avoid bankruptcy
        max_turns=2000,
        minutes_per_turn=60,
    )
    env = VendingEnv(config)
    slot_map = {"coke": (0, 0), "water": (0, 1), "chips": (2, 0)}

    start_time = time.time()

    # Run 2000 steps
    for step in range(2000):
        # Occasionally request supplier orders via email and restock
        if step % 50 == 0 and env.state.cash_balance > 200:
            try:
                env.queue_email(
                    recipient=SUPPLIER_EMAIL,
                    subject="Purchase Order",
                    body=PURCHASE_TEMPLATE,
                )
            except ValueError:
                pass  # May fail if cash falls below requirement mid-run

        if step % 30 == 0:
            # Restock from storage
            for sku in ["coke", "water", "chips"]:
                storage = env.state.storage_inventory.get(sku, 0)
                if storage > 0:
                    restock_qty = min(5, storage)
                    row, column = slot_map[sku]
                    slot = env.state.machine_inventory[row][column]
                    current_qty = slot.quantity if slot and slot.sku == sku else 0
                    capacity = env.state.demand_profiles[sku].product.slot_capacity
                    available_capacity = max(0, capacity - current_qty)
                    effective_qty = min(restock_qty, available_capacity)
                    if effective_qty > 0:
                        env.restock(sku, effective_qty, row=row, column=column)

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
