"""Utility functions for simulator metrics."""

from __future__ import annotations

from .runtime import get_tool_counts
from .state import DailyReport, DemandProfile, SimulatorState, Slot, aggregate_sku_quantities


def inventory_value(
    inventory: dict[str, int] | list[list[Slot | None]],
    demand_profiles: dict[str, DemandProfile],
) -> float:
    value = 0.0
    if isinstance(inventory, dict):
        items = inventory.items()
    else:
        totals = aggregate_sku_quantities(inventory)  # type: ignore[arg-type]
        items = totals.items()

    for sku, qty in items:
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


class EpisodeMetrics(dict):
    """Container for harness metrics with convenience accessors."""

    def summary(self) -> dict[str, float | int]:
        return {"net_worth": self.get("net_worth", 0.0), "units_sold": self.get("units_sold", 0)}


def collect_episode_metrics(state: SimulatorState) -> EpisodeMetrics:
    """Aggregate key metrics and tool usage for the current run."""

    metrics = EpisodeMetrics(
        net_worth=compute_net_worth(state),
        units_sold=cumulative_units_sold(state),
        day=state.day,
        bankrupt=state.bankrupt,
        telemetry=dict(state.telemetry),
    )
    metrics["tool_counts"] = get_tool_counts()
    if state.daily_reports:
        latest = state.daily_reports[-1]
        metrics["last_daily_report"] = {
            "day": latest.day,
            "revenue": latest.revenue,
            "cash_balance": latest.cash_balance,
            "cash_in_machine": latest.cash_in_machine,
        }
    return metrics
