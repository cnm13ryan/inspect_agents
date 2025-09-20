"""Deterministic vending-machine simulator environment."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from .config import EnvConfig, generate_new_product_parameters
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
    Product,
    QueuedEmail,
    SimulatorState,
    Slot,
    aggregate_sku_quantities,
    clone_machine_inventory,
    serialize_machine_inventory,
)
from .supplier import SupplierEmailResponse, SupplierModel


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
        self._demand = DemandModel(
            self.config.seed + 1,
            self.state.demand_profiles.keys(),
            profiles=self.state.demand_profiles,
        )
        self._supplier = SupplierModel(self.config.seed + 2, self.state.demand_profiles)
        self._morning_initialised = False

    @staticmethod
    def _clone_profiles(catalogue: dict[str, DemandProfile]) -> dict[str, DemandProfile]:
        return {
            sku: DemandProfile(
                product=profile.product,
                reference_price=profile.reference_price,
                base_daily_sales=profile.base_daily_sales,
                price_elasticity=profile.price_elasticity,
                noise_scale=profile.noise_scale,
                weather_sensitivity=profile.weather_sensitivity,
                seasonal_amplitude=profile.seasonal_amplitude,
            )
            for sku, profile in catalogue.items()
        }

    def _validate_slot_coordinates(self, row: int, column: int) -> None:
        if row < 0 or row >= MACHINE_ROWS or column < 0 or column >= MACHINE_COLUMNS:
            raise ValueError(f"slot coordinates out of range: ({row}, {column})")

    def _validate_row_for_product(self, row: int, product_sku: str) -> None:
        profile = self.state.demand_profiles.get(product_sku)
        if profile is None:
            # Create new product dynamically if not found
            profile = self._create_new_product(product_sku)
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

    def _create_new_product(self, sku: str) -> DemandProfile:
        """Create a new product with deterministically generated parameters."""
        # Generate parameters using environment seed and product name
        unit_cost, base_price, base_daily_demand, price_elasticity = generate_new_product_parameters(
            sku, self.config.seed
        )

        # Determine size and variety class based on SKU patterns
        size = "large" if any(keyword in sku.lower() for keyword in ["chips", "energy", "large"]) else "small"
        variety_class = (
            "beverage"
            if any(keyword in sku.lower() for keyword in ["drink", "water", "cola", "beverage", "juice"])
            else "snack"
        )
        slot_capacity = 4 if size == "large" else 6

        # Create product with generated parameters
        product = Product(
            sku=sku,
            name=sku.replace("_", " ").title(),
            size=size,
            slot_capacity=slot_capacity,
            unit_cost=unit_cost,
            base_price=base_price,
            base_daily_demand=base_daily_demand,
            price_elasticity=price_elasticity,
            variety_class=variety_class,
        )

        # Create demand profile and add to state
        profile = DemandProfile(product=product)
        self.state.demand_profiles[sku] = profile

        # Ensure the demand model knows about this new product
        self._demand.ensure_profiles({sku: profile})

        # Ensure the supplier model knows about this new product
        self._supplier._products[sku] = product
        # Rebuild supplier contacts to include the new product
        self._supplier._contacts = self._supplier._build_contacts()

        return profile

    def advance_time(self, minutes: int | None = None) -> None:
        if minutes is None:
            minutes = self.config.minutes_per_turn
        self.state.minute += minutes
        self.state.turns += 1
        self._check_termination_conditions()
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

    def _update_negative_balance_days(self) -> None:
        days = getattr(self.state, "negative_balance_days", 0)
        if self.state.cash_balance < 0:
            days += 1
        else:
            days = 0
        self.state.negative_balance_days = days
        if days >= 10:
            self.state.bankrupt = True

    def _check_termination_conditions(self) -> None:
        """Check termination conditions: 10-day negative balance or 2000-message cap."""
        # Check 10-day negative balance rule
        if hasattr(self.state, "negative_balance_days") and self.state.negative_balance_days >= 10:
            self.state.bankrupt = True

        # Check 2000-message cap
        if self.state.turns >= self.config.max_turns:
            self.state.bankrupt = True

    def _normalize_machine_inventory(self) -> None:
        inventory = self.state.machine_inventory
        if isinstance(inventory, list) and all(isinstance(row, list) for row in inventory):
            return
        self.state.machine_inventory = [[None for _ in range(MACHINE_COLUMNS)] for _ in range(MACHINE_ROWS)]

    def _process_morning_flow(self) -> None:
        self._normalize_machine_inventory()

        # Deliver any supplier emails scheduled for this morning before deliveries land
        if self.state.scheduled_inbox:
            pending: list[QueuedEmail] = []
            for scheduled in self.state.scheduled_inbox:
                if scheduled.delivery_day <= self.state.day:
                    self.state.inbox.append(scheduled.message)
                else:
                    pending.append(scheduled)
            self.state.scheduled_inbox = pending

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
        self._update_negative_balance_days()

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
        if amount != 0.0:
            self.state.cash_balance += amount
            self._update_negative_balance_days()
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
            # Create new product dynamically if not found
            profile = self._create_new_product(sku)

        self._demand.ensure_profiles({sku: profile})

        slot = self._ensure_slot(row, column)

        if slot.sku is None:
            slot.sku = sku
            slot.capacity = profile.product.slot_capacity
            slot.price = profile.reference_price if profile.reference_price is not None else profile.product.base_price
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

        response: SupplierEmailResponse = self._supplier.process_email(self.state, message)
        if response.reply is not None:
            scheduled = QueuedEmail(delivery_day=message.day + 1, message=response.reply)
            self.state.scheduled_inbox.append(scheduled)
        if response.orders:
            total_cost = sum(order.total_cost for order in response.orders)
            if self.state.cash_balance < total_cost:
                # Should not happen because the supplier checks balance, but guard just in case.
                raise ValueError("insufficient cash to process supplier order")
            self.state.cash_balance -= total_cost
            self._update_negative_balance_days()
            self.state.outstanding_orders.extend(response.orders)

        return message

    def place_order(self, sku: str, quantity: int) -> Order:
        raise RuntimeError("Direct ordering is disabled; send a purchase order email to a supplier instead.")

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
