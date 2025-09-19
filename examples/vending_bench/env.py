"""Deterministic vending-machine simulator environment."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from .config import EnvConfig
from .demand import DemandModel
from .metrics import compute_net_worth, cumulative_units_sold, daily_report
from .state import (
    MINUTES_PER_DAY,
    DailyReport,
    DemandProfile,
    EmailMessage,
    Order,
    SimulatorState,
)
from .supplier import SupplierModel


@dataclass
class EnvSummary:
    day: int
    cash_balance: float
    cash_in_machine: float
    storage_inventory: dict[str, int]
    machine_inventory: dict[str, int]
    outstanding_orders: Iterable[Order]
    net_worth: float
    units_sold_total: int


class VendingEnv:
    def __init__(self, config: EnvConfig | None = None) -> None:
        self.config = config or EnvConfig()
        self.config.validate()
        self.state = SimulatorState(
            cash_balance=self.config.starting_cash,
            demand_profiles=self._clone_profiles(self.config.catalogue),
        )
        self.state.reset_daily_counters()
        self._rng = random.Random(self.config.seed)
        self._demand = DemandModel(self.config.seed + 1, self.state.demand_profiles.keys())
        self._supplier = SupplierModel(self.config.seed + 2)
        self._morning_initialised = False

    @staticmethod
    def _clone_profiles(catalogue: dict[str, DemandProfile]) -> dict[str, DemandProfile]:
        return {
            sku: DemandProfile(product=profile.product, noise_scale=profile.noise_scale)
            for sku, profile in catalogue.items()
        }

    def advance_time(self, minutes: int | None = None) -> None:
        if minutes is None:
            minutes = self.config.minutes_per_turn
        self.state.minute += minutes
        self.state.turns += 1
        if self.state.minute >= MINUTES_PER_DAY:
            self.state.minute %= MINUTES_PER_DAY
            self.end_of_day()

    def end_of_day(self) -> None:
        self.state.day += 1
        self.morning_update()

    def morning_update(self) -> None:
        self._process_morning_flow()
        self.state.reset_daily_counters()
        self._morning_initialised = True

    def _process_morning_flow(self) -> None:
        # Deliver orders
        delivered, pending = self._supplier.split_deliveries(self.state.outstanding_orders, self.state.day)
        self.state.outstanding_orders = pending
        deliveries = {}
        for order in delivered:
            deliveries[order.sku] = deliveries.get(order.sku, 0) + order.quantity
        for sku, qty in deliveries.items():
            self.state.storage_inventory[sku] = self.state.storage_inventory.get(sku, 0) + qty

        outcome = self._demand.simulate_day(
            day=self.state.day,
            demand_profiles=self.state.demand_profiles,
            prices=self.state.prices,
            machine_inventory=self.state.machine_inventory,
        )
        revenue = outcome.revenue
        for sku, sold in outcome.units_sold.items():
            self.state.units_sold_today[sku] = sold
            current = self.state.machine_inventory.get(sku, 0)
            self.state.machine_inventory[sku] = max(0, current - sold)
            self.state.cash_in_machine += sold * self.state.prices.get(
                sku, self.state.demand_profiles[sku].product.base_price
            )

        self.state.cash_balance -= self.config.daily_fee
        if self.state.cash_balance < 0:
            self.state.bankrupt = True

        self.state.cash_balance += self.collect_machine_cash()

        report = DailyReport(
            day=self.state.day,
            units_sold=dict(self.state.units_sold_today),
            revenue=revenue,
            cash_balance=self.state.cash_balance,
            cash_in_machine=self.state.cash_in_machine,
            storage_inventory=dict(self.state.storage_inventory),
            machine_inventory=dict(self.state.machine_inventory),
            deliveries=deliveries,
        )
        self.state.daily_reports.append(report)
        summary_email = EmailMessage(
            day=self.state.day,
            subject=f"Daily summary day={self.state.day}",
            body=self._format_report(report),
            sender="simulator@vending-bench",
            recipient="agent@sim",
        )
        self.state.inbox.append(summary_email)

    def collect_machine_cash(self) -> float:
        amount = self.state.cash_in_machine
        self.state.cash_in_machine = 0.0
        return amount

    def restock(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        available = self.state.storage_inventory.get(sku, 0)
        if available < quantity:
            raise ValueError("insufficient storage inventory for restock")
        self.state.storage_inventory[sku] = available - quantity
        self.state.machine_inventory[sku] = self.state.machine_inventory.get(sku, 0) + quantity

    def set_price(self, sku: str, price: float) -> None:
        if sku not in self.state.demand_profiles:
            raise ValueError(f"Unknown SKU {sku}")
        if price <= 0:
            raise ValueError("price must be positive")
        self.state.prices[sku] = price

    def queue_email(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        sender: str = "agent@sim",
    ) -> EmailMessage:
        message = EmailMessage(
            day=self.state.day,
            subject=subject,
            body=body,
            sender=sender,
            recipient=recipient,
        )
        self.state.outbox.append(message)
        return message

    def place_order(self, sku: str, quantity: int) -> Order:
        if sku not in self.state.demand_profiles:
            raise ValueError(f"Unknown SKU {sku}")
        product = self.state.demand_profiles[sku].product
        order = self._supplier.create_order(product=product, quantity=quantity, day_ordered=self.state.day)
        total_cost = order.total_cost
        if self.state.cash_balance < total_cost:
            raise ValueError("insufficient cash to place order")
        self.state.cash_balance -= total_cost
        self.state.outstanding_orders.append(order)
        self.queue_email(
            recipient="supplier@sim",
            subject=f"Purchase order {order.sku}",
            body=f"Ordered {order.quantity} units for ${total_cost:.2f}, delivery day {order.delivery_day}",
            sender="agent@sim",
        )
        return order

    def summary(self) -> EnvSummary:
        return EnvSummary(
            day=self.state.day,
            cash_balance=self.state.cash_balance,
            cash_in_machine=self.state.cash_in_machine,
            storage_inventory=dict(self.state.storage_inventory),
            machine_inventory=dict(self.state.machine_inventory),
            outstanding_orders=list(self.state.outstanding_orders),
            net_worth=compute_net_worth(self.state),
            units_sold_total=cumulative_units_sold(self.state),
        )

    def latest_report(self) -> DailyReport | None:
        return daily_report(self.state)

    def _format_report(self, report: DailyReport) -> str:
        return (
            f"Day {report.day} summary\n"
            f"Revenue: ${report.revenue:.2f}\n"
            f"Cash balance: ${report.cash_balance:.2f}\n"
            f"Cash in machine: ${report.cash_in_machine:.2f}\n"
            f"Storage: {report.storage_inventory}\n"
            f"Machine: {report.machine_inventory}\n"
            f"Deliveries: {report.deliveries}\n"
            f"Units sold: {report.units_sold}\n"
        )
