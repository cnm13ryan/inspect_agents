"""Environment configuration defaults for Vending-Bench."""

from __future__ import annotations

from dataclasses import dataclass, field

from .state import DemandProfile, Product


def default_catalogue() -> dict[str, DemandProfile]:
    products = {
        "coke": Product(
            sku="coke",
            name="Coca-Cola 12oz",
            size="small",
            slot_capacity=6,
            unit_cost=0.50,
            base_price=1.50,
            base_daily_demand=4.0,
            price_elasticity=-0.9,
            variety_class="beverage",
        ),
        "water": Product(
            sku="water",
            name="Spring Water 16oz",
            size="small",
            slot_capacity=6,
            unit_cost=0.25,
            base_price=1.00,
            base_daily_demand=5.0,
            price_elasticity=-0.7,
            variety_class="beverage",
        ),
        "energy_drink": Product(
            sku="energy_drink",
            name="Energy Drink 16oz",
            size="large",
            slot_capacity=4,
            unit_cost=1.20,
            base_price=2.50,
            base_daily_demand=3.0,
            price_elasticity=-1.2,
            variety_class="beverage",
        ),
        "chips": Product(
            sku="chips",
            name="Potato Chips",
            size="large",
            slot_capacity=4,
            unit_cost=0.70,
            base_price=1.80,
            base_daily_demand=3.5,
            price_elasticity=-0.9,
            variety_class="snack",
        ),
        "chocolate_bar": Product(
            sku="chocolate_bar",
            name="Chocolate Bar",
            size="small",
            slot_capacity=6,
            unit_cost=0.60,
            base_price=1.25,
            base_daily_demand=4.0,
            price_elasticity=-1.0,
            variety_class="snack",
        ),
    }
    return {sku: DemandProfile(product=prod) for sku, prod in products.items()}


@dataclass
class EnvConfig:
    seed: int = 7
    starting_cash: float = 500.0
    daily_fee: float = 2.0
    slots_small: int = 2 * 3
    slots_large: int = 2 * 3
    max_turns: int = 2000
    minutes_per_turn: int = 60
    catalogue: dict[str, DemandProfile] = field(default_factory=default_catalogue)

    def validate(self) -> None:
        if self.starting_cash < 0:
            raise ValueError("starting_cash must be non-negative")
        if self.daily_fee < 0:
            raise ValueError("daily_fee must be non-negative")
        if self.minutes_per_turn <= 0:
            raise ValueError("minutes_per_turn must be positive")
        if self.slots_small < 0 or self.slots_large < 0:
            raise ValueError("slot counts must be non-negative")
