"""Core dataclasses for the deterministic vending simulator."""

from __future__ import annotations

from dataclasses import dataclass, field

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class Product:
    """Static descriptor for a vending SKU."""

    sku: str
    name: str
    size: str  # "small" or "large"
    unit_cost: float
    base_price: float
    base_daily_demand: float
    price_elasticity: float
    variety_class: str


@dataclass
class DemandProfile:
    """Runtime demand parameters for a SKU."""

    product: Product
    noise_scale: float = 0.08
    weather_sensitivity: float = 0.05
    seasonal_amplitude: float = 0.1


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
class DailyReport:
    day: int
    units_sold: dict[str, int]
    revenue: float
    cash_balance: float
    cash_in_machine: float
    storage_inventory: dict[str, int]
    machine_inventory: dict[str, int]
    deliveries: dict[str, int]


@dataclass
class SimulatorState:
    day: int = 0
    minute: int = 0
    turns: int = 0
    cash_balance: float = 0.0
    cash_in_machine: float = 0.0
    storage_inventory: dict[str, int] = field(default_factory=dict)
    machine_inventory: dict[str, int] = field(default_factory=dict)
    prices: dict[str, float] = field(default_factory=dict)
    demand_profiles: dict[str, DemandProfile] = field(default_factory=dict)
    outstanding_orders: list[Order] = field(default_factory=list)
    inbox: list[EmailMessage] = field(default_factory=list)
    outbox: list[EmailMessage] = field(default_factory=list)
    units_sold_today: dict[str, int] = field(default_factory=dict)
    daily_reports: list[DailyReport] = field(default_factory=list)
    bankrupt: bool = False

    def reset_daily_counters(self) -> None:
        self.units_sold_today = {sku: 0 for sku in self.demand_profiles.keys()}
