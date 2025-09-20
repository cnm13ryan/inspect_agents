"""Core dataclasses for the deterministic vending simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MACHINE_ROWS = 4
MACHINE_COLUMNS = 3
SMALL_ITEM_ROWS = (0, 1)
LARGE_ITEM_ROWS = (2, 3)


@dataclass
class Slot:
    """Runtime state for a single vending machine slot."""

    sku: str | None = None
    quantity: int = 0
    price: float | None = None
    capacity: int | None = None

    def is_empty(self) -> bool:
        return self.sku is None or self.quantity == 0

    def available_capacity(self) -> int:
        if self.capacity is None:
            return 0
        return max(0, self.capacity - self.quantity)


MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class Product:
    """Static descriptor for a vending SKU."""

    sku: str
    name: str
    size: str  # "small" or "large"
    slot_capacity: int
    unit_cost: float
    base_price: float
    base_daily_demand: float
    price_elasticity: float
    variety_class: str


@dataclass
class DemandProfile:
    """Runtime demand parameters for a SKU."""

    product: Product
    reference_price: float | None = None
    base_daily_sales: float | None = None
    price_elasticity: float | None = None
    noise_scale: float = 0.08
    weather_sensitivity: float = 0.05
    seasonal_amplitude: float = 0.1


@dataclass
class SupplierProductOffer:
    """Static supplier offer data for a SKU."""

    product: Product
    wholesale_price: float
    min_order_quantity: int
    lead_time_days: tuple[int, int]
    keywords: tuple[str, ...]


@dataclass
class SupplierContact:
    """Supplier directory entry used for deterministic email responses."""

    name: str
    email: str
    categories: tuple[str, ...]
    products: dict[str, SupplierProductOffer]


@dataclass
class Order:
    sku: str
    quantity: int
    unit_cost: float
    day_ordered: int
    delivery_day: int

    @property
    def total_cost(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class EmailMessage:
    day: int
    subject: str
    body: str
    sender: str
    recipient: str


@dataclass
class QueuedEmail:
    """Scheduled email set to arrive on a future morning."""

    delivery_day: int
    message: EmailMessage


@dataclass
class DailyReport:
    day: int
    units_sold: dict[str, int]
    revenue: float
    cash_balance: float
    cash_in_machine: float
    storage_inventory: dict[str, int]
    machine_inventory: list[list[Slot | None]]
    deliveries: dict[str, int]


@dataclass
class SimulatorState:
    telemetry: dict[str, Any] = field(default_factory=dict)
    day: int = 0
    minute: int = 0
    turns: int = 0
    cash_balance: float = 0.0
    cash_in_machine: float = 0.0
    storage_inventory: dict[str, int] = field(default_factory=dict)
    machine_inventory: list[list[Slot | None]] = field(
        default_factory=lambda: [[None for _ in range(MACHINE_COLUMNS)] for _ in range(MACHINE_ROWS)]
    )
    demand_profiles: dict[str, DemandProfile] = field(default_factory=dict)
    outstanding_orders: list[Order] = field(default_factory=list)
    inbox: list[EmailMessage] = field(default_factory=list)
    outbox: list[EmailMessage] = field(default_factory=list)
    scheduled_inbox: list[QueuedEmail] = field(default_factory=list)
    units_sold_today: dict[str, int] = field(default_factory=dict)
    daily_reports: list[DailyReport] = field(default_factory=list)
    negative_balance_days: int = 0
    bankrupt: bool = False

    def reset_daily_counters(self) -> None:
        self.units_sold_today = {sku: 0 for sku in self.demand_profiles.keys()}


def clone_machine_inventory(inventory: list[list[Slot | None]]) -> list[list[Slot | None]]:
    """Deep copy the machine inventory grid."""

    from copy import deepcopy

    return deepcopy(inventory)


def iter_slots(inventory: list[list[Slot | None]]):
    """Yield (row, column, slot) tuples for populated slots."""

    for row_idx, row in enumerate(inventory):
        for col_idx, slot in enumerate(row):
            if slot is None:
                continue
            yield row_idx, col_idx, slot


def aggregate_sku_quantities(inventory: list[list[Slot | None]]) -> dict[str, int]:
    """Aggregate per-SKU quantities from the slot grid."""

    totals: dict[str, int] = {}
    for _, _, slot in iter_slots(inventory):
        if slot.sku is None or slot.quantity <= 0:
            continue
        totals[slot.sku] = totals.get(slot.sku, 0) + slot.quantity
    return totals


def serialize_slot(slot: Slot | None) -> dict[str, Any] | None:
    """Convert a slot to a JSON-serialisable dict."""

    if slot is None:
        return None
    return {
        "sku": slot.sku,
        "quantity": slot.quantity,
        "price": slot.price,
        "capacity": slot.capacity,
    }


def serialize_machine_inventory(inventory: list[list[Slot | None]]) -> list[list[dict[str, Any] | None]]:
    """Serialise the machine inventory grid."""

    return [[serialize_slot(slot) for slot in row] for row in inventory]
