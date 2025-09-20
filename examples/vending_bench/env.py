"""Deterministic vending-machine simulator environment."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from .config import EnvConfig
from .demand import DemandModel
from .metrics import compute_net_worth, cumulative_units_sold, daily_report
from .state import (
    LARGE_ITEM_ROWS,
    MACHINE_COLUMNS,
    MACHINE_ROWS,
    MINUTES_PER_DAY,
    SMALL_ITEM_ROWS,
    DailyReport,
    DemandProfile,
    EmailMessage,
    Order,
    SimulatorState,
    Slot,
    aggregate_sku_quantities,
    clone_machine_inventory,
    serialize_machine_inventory,
)
from .supplier import SupplierModel


@dataclass
class EnvSummary:
    day: int
    cash_balance: float
    cash_in_machine: float
    storage_inventory: dict[str, int]
    machine_inventory: dict[str, int]
    machine_slots: list[list[Slot | None]]
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

    def _validate_slot_coordinates(self, row: int, column: int) -> None:
        if row < 0 or row >= MACHINE_ROWS or column < 0 or column >= MACHINE_COLUMNS:
            raise ValueError(f"slot coordinates out of range: ({row}, {column})")

    def _validate_row_for_product(self, row: int, product_sku: str) -> None:
        profile = self.state.demand_profiles.get(product_sku)
        if profile is None:
            raise ValueError(f"Unknown SKU {product_sku}")
        size = profile.product.size
        if size == "small" and row not in SMALL_ITEM_ROWS:
            raise ValueError(f"SKU {product_sku} ({size}) must be placed in rows {SMALL_ITEM_ROWS}")
        if size == "large" and row not in LARGE_ITEM_ROWS:
            raise ValueError(f"SKU {product_sku} ({size}) must be placed in rows {LARGE_ITEM_ROWS}")

    def _ensure_slot(self, row: int, column: int) -> Slot:
        slot = self.state.machine_inventory[row][column]
        if slot is None:
            slot = Slot()
            self.state.machine_inventory[row][column] = slot
        return slot

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
            machine_inventory=self.state.machine_inventory,
        )
        revenue = outcome.revenue
        for sku in self.state.demand_profiles.keys():
            self.state.units_sold_today[sku] = outcome.units_sold.get(sku, 0)

        for (row, column), sale in outcome.slot_sales.items():
            slot = self.state.machine_inventory[row][column]
            if slot is None:
                continue
            slot.quantity = max(0, slot.quantity - sale.quantity)
            if slot.quantity == 0:
                slot.sku = None
                slot.price = None
                slot.capacity = None

        self.state.cash_in_machine += revenue

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
            machine_inventory=clone_machine_inventory(self.state.machine_inventory),
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

    def restock(self, sku: str, quantity: int, *, row: int, column: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        self._validate_slot_coordinates(row, column)
        self._validate_row_for_product(row, sku)

        available = self.state.storage_inventory.get(sku, 0)
        if available < quantity:
            raise ValueError("insufficient storage inventory for restock")

        profile = self.state.demand_profiles.get(sku)
        if profile is None:
            raise ValueError(f"Unknown SKU {sku}")

        slot = self._ensure_slot(row, column)

        if slot.sku is None:
            slot.sku = sku
            slot.capacity = profile.product.slot_capacity
            slot.price = profile.product.base_price
        elif slot.sku != sku:
            raise ValueError(f"slot ({row}, {column}) currently holds SKU {slot.sku}")

        if slot.capacity is None:
            slot.capacity = profile.product.slot_capacity

        if slot.quantity + quantity > slot.capacity:
            raise ValueError(f"restock exceeds capacity {slot.capacity} for slot ({row}, {column})")

        self.state.storage_inventory[sku] = available - quantity
        slot.quantity += quantity

    def set_price(self, slot_prices: dict[tuple[int, int], float]) -> None:
        if not slot_prices:
            raise ValueError("slot_prices must not be empty")

        for (row, column), price in slot_prices.items():
            if price <= 0:
                raise ValueError("price must be positive")
            self._validate_slot_coordinates(row, column)
            slot = self.state.machine_inventory[row][column]
            if slot is None or slot.sku is None:
                raise ValueError(f"slot ({row}, {column}) is empty")
            slot.price = price

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
        machine_slots = clone_machine_inventory(self.state.machine_inventory)
        return EnvSummary(
            day=self.state.day,
            cash_balance=self.state.cash_balance,
            cash_in_machine=self.state.cash_in_machine,
            storage_inventory=dict(self.state.storage_inventory),
            machine_inventory=aggregate_sku_quantities(machine_slots),
            machine_slots=machine_slots,
            outstanding_orders=list(self.state.outstanding_orders),
            net_worth=compute_net_worth(self.state),
            units_sold_total=cumulative_units_sold(self.state),
        )

    def latest_report(self) -> DailyReport | None:
        return daily_report(self.state)

    def _format_report(self, report: DailyReport) -> str:
        slot_repr = serialize_machine_inventory(report.machine_inventory)
        sku_totals = aggregate_sku_quantities(report.machine_inventory)
        return (
            f"Day {report.day} summary\n"
            f"Revenue: ${report.revenue:.2f}\n"
            f"Cash balance: ${report.cash_balance:.2f}\n"
            f"Cash in machine: ${report.cash_in_machine:.2f}\n"
            f"Storage: {report.storage_inventory}\n"
            f"Machine (slots): {slot_repr}\n"
            f"Machine (totals): {sku_totals}\n"
            f"Deliveries: {report.deliveries}\n"
            f"Units sold: {report.units_sold}\n"
        )
