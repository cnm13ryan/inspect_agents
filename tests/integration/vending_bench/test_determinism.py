"""Integration tests for deterministic behavior across the vending bench system."""

from __future__ import annotations

import pytest

from examples.vending_bench import EnvConfig, VendingEnv


def test_determinism_end_to_end_simulation():
    """Test that complete simulation runs are deterministic with same seed."""
    seed = 12345

    def run_simulation(seed: int) -> dict:
        """Run a complete simulation and return key metrics."""
        config = EnvConfig(seed=seed, max_turns=50)  # Short run for testing
        env = VendingEnv(config)

        # Set up some initial inventory and pricing
        env.state.storage_inventory["coke"] = 30
        env.state.storage_inventory["chips"] = 20
        env.restock("coke", 6, row=0, column=0)
        env.restock("chips", 4, row=2, column=0)
        env.set_price({(0, 0): 1.75, (2, 0): 2.25})

        # Place an order to test supplier interactions
        env.queue_email(
            recipient="orders@rfd-inc.com",
            subject="Purchase order",
            body=(
                "Please process the following purchase order:\n"
                "- 24 coke\n"
                "- 12 energy_drink\n"
                "Delivery address: 100 Market St, Unit 5, Springfield\n"
                "Account number: ACCT-123456\n"
                "Thank you!"
            ),
        )

        # Run simulation for multiple days
        results = []
        for turn in range(config.max_turns):
            summary = env.summary()
            results.append(
                {
                    "turn": turn,
                    "day": summary.day,
                    "cash_balance": summary.cash_balance,
                    "cash_in_machine": summary.cash_in_machine,
                    "units_sold_total": summary.units_sold_total,
                    "net_worth": summary.net_worth,
                    "storage_inventory": dict(summary.storage_inventory),
                    "machine_inventory": dict(summary.machine_inventory),
                    "outstanding_orders": len(summary.outstanding_orders),
                }
            )

            if env.state.bankrupt:
                break

            env.advance_time()

        return {
            "final_results": results,
            "total_turns": len(results),
            "bankrupt": env.state.bankrupt,
            "final_day": env.state.day,
            "final_cash": env.state.cash_balance,
            "final_net_worth": env.summary().net_worth,
        }

    # Run the simulation twice with the same seed
    results1 = run_simulation(seed)
    results2 = run_simulation(seed)

    # The results should be identical
    assert results1["total_turns"] == results2["total_turns"]
    assert results1["bankrupt"] == results2["bankrupt"]
    assert results1["final_day"] == results2["final_day"]
    assert results1["final_cash"] == pytest.approx(results2["final_cash"])
    assert results1["final_net_worth"] == pytest.approx(results2["final_net_worth"])

    # Check that turn-by-turn results are identical
    for turn_result1, turn_result2 in zip(results1["final_results"], results2["final_results"], strict=True):
        assert turn_result1["turn"] == turn_result2["turn"]
        assert turn_result1["day"] == turn_result2["day"]
        assert turn_result1["cash_balance"] == pytest.approx(turn_result2["cash_balance"])
        assert turn_result1["cash_in_machine"] == pytest.approx(turn_result2["cash_in_machine"])
        assert turn_result1["units_sold_total"] == turn_result2["units_sold_total"]
        assert turn_result1["net_worth"] == pytest.approx(turn_result2["net_worth"])
        assert turn_result1["storage_inventory"] == turn_result2["storage_inventory"]
        assert turn_result1["machine_inventory"] == turn_result2["machine_inventory"]
        assert turn_result1["outstanding_orders"] == turn_result2["outstanding_orders"]


def test_determinism_with_new_products():
    """Test deterministic behavior when dynamically creating new products."""
    seed = 54321

    def run_with_new_products(seed: int) -> dict:
        """Run simulation that creates new products during execution."""
        config = EnvConfig(seed=seed, max_turns=20)
        env = VendingEnv(config)

        # Create several new products during the simulation
        new_products = ["custom_soda", "premium_chips", "health_bar"]

        results = []
        for i, new_sku in enumerate(new_products):
            # Add inventory and stock the new product
            env.state.storage_inventory[new_sku] = 15

            # Determine appropriate row based on product name
            row = 2 if "chips" in new_sku else 0  # chips go in large rows
            env.restock(new_sku, 3, row=row, column=i)

            # Get the generated product parameters
            profile = env.state.demand_profiles[new_sku]
            results.append(
                {
                    "sku": new_sku,
                    "unit_cost": profile.product.unit_cost,
                    "base_price": profile.product.base_price,
                    "base_daily_demand": profile.product.base_daily_demand,
                    "price_elasticity": profile.product.price_elasticity,
                    "size": profile.product.size,
                    "variety_class": profile.product.variety_class,
                }
            )

            # Run a few turns
            for _ in range(3):
                env.advance_time()

        return {
            "products": results,
            "final_day": env.state.day,
            "final_cash": env.state.cash_balance,
        }

    # Run twice with same seed
    results1 = run_with_new_products(seed)
    results2 = run_with_new_products(seed)

    # New products should be identical
    assert len(results1["products"]) == len(results2["products"])
    for product1, product2 in zip(results1["products"], results2["products"], strict=True):
        assert product1 == product2

    # Final states should also be identical
    assert results1["final_day"] == results2["final_day"]
    assert results1["final_cash"] == pytest.approx(results2["final_cash"])


def test_determinism_different_seeds_produce_different_results():
    """Test that different seeds produce different simulation outcomes."""

    def run_simulation(seed: int) -> dict:
        """Run a simulation and return key outcomes."""
        config = EnvConfig(seed=seed, max_turns=100)  # Longer run to ensure differences
        env = VendingEnv(config)

        # Set up initial conditions
        env.state.storage_inventory["coke"] = 50
        env.state.storage_inventory["chips"] = 30
        env.restock("coke", 6, row=0, column=0)
        env.restock("chips", 4, row=2, column=0)

        # Run for multiple days to accumulate differences
        daily_revenues = []
        for _ in range(config.max_turns):
            env.advance_time()
            if env.state.bankrupt:
                break

            # Collect daily revenue if available
            report = env.latest_report()
            if report:
                daily_revenues.append(report.revenue)

        summary = env.summary()

        return {
            "final_cash": summary.cash_balance,
            "final_units_sold": summary.units_sold_total,
            "final_net_worth": summary.net_worth,
            "daily_revenues": daily_revenues,
            "total_turns": env.state.turns,
        }

    # Run with different seeds
    results_seed1 = run_simulation(1111)
    results_seed2 = run_simulation(2222)

    # Results should be different (with very high probability)
    # Check multiple metrics for differences
    differences = [
        results_seed1["final_cash"] != results_seed2["final_cash"],
        results_seed1["final_units_sold"] != results_seed2["final_units_sold"],
        results_seed1["final_net_worth"] != results_seed2["final_net_worth"],
        results_seed1["daily_revenues"] != results_seed2["daily_revenues"],
    ]

    assert any(differences), (
        f"Different seeds should produce different results. Results1: {results_seed1}, Results2: {results_seed2}"
    )


def test_determinism_supplier_email_workflows():
    """Test that supplier email interactions are deterministic."""
    seed = 99999

    def run_supplier_test(seed: int) -> dict:
        """Test supplier interactions and return outcomes."""
        config = EnvConfig(seed=seed)
        env = VendingEnv(config)

        results = []

        # Test quote requests
        env.queue_email(
            recipient="supply@quickstock.com",
            subject="Quote request",
            body="Please send your current pricing catalog.",
        )

        env.end_of_day()  # Process scheduled emails

        quote_emails = [msg for msg in env.state.inbox if msg.sender == "supply@quickstock.com"]
        results.append(
            {
                "type": "quote",
                "count": len(quote_emails),
                "body_length": len(quote_emails[0].body) if quote_emails else 0,
            }
        )

        # Test purchase orders
        env.queue_email(
            recipient="orders@rfd-inc.com",
            subject="Purchase order",
            body=("Order request:\n- 24 coke\n- 12 energy_drink\nDelivery address: 123 Test St\nAccount: ACCT-999\n"),
        )

        order_count_before = len(env.state.outstanding_orders)
        cash_before = env.state.cash_balance

        # Orders should be created immediately
        order_count_after = len(env.state.outstanding_orders)
        cash_after = env.state.cash_balance

        results.append(
            {
                "type": "purchase",
                "orders_created": order_count_after - order_count_before,
                "cash_spent": cash_before - cash_after,
            }
        )

        # Get delivery days for orders
        delivery_days = [order.delivery_day for order in env.state.outstanding_orders]
        results.append(
            {
                "type": "deliveries",
                "delivery_days": sorted(delivery_days),
            }
        )

        return {"interactions": results}

    # Run twice with same seed
    results1 = run_supplier_test(seed)
    results2 = run_supplier_test(seed)

    # All supplier interactions should be identical
    assert results1 == results2
