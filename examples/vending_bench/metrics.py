"""Utility functions for simulator metrics."""

from __future__ import annotations

from .state import DailyReport, DemandProfile, SimulatorState


def inventory_value(inventory: dict[str, int], demand_profiles: dict[str, DemandProfile]) -> float:
    value = 0.0
    for sku, qty in inventory.items():
        profile = demand_profiles.get(sku)
        if not profile:
            continue
        value += qty * profile.product.unit_cost
    return value


def compute_net_worth(state: SimulatorState) -> float:
    storage_val = inventory_value(state.storage_inventory, state.demand_profiles)
    machine_val = inventory_value(state.machine_inventory, state.demand_profiles)
    outstanding = sum(order.total_cost for order in state.outstanding_orders)
    return state.cash_balance + state.cash_in_machine + storage_val + machine_val + outstanding


def cumulative_units_sold(state: SimulatorState) -> int:
    return sum(sum(report.units_sold.values()) for report in state.daily_reports)


def daily_report(state: SimulatorState) -> DailyReport | None:
    if not state.daily_reports:
        return None
    return state.daily_reports[-1]
