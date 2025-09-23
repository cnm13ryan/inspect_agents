"""Environment configuration defaults for Vending-Bench."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .state import DemandProfile, Product
from .supplier import SupplierConfig

DEMAND_PROVIDER_ENV = "DEMAND_PROVIDER"


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


def _default_demand_provider() -> str:
    return os.getenv(DEMAND_PROVIDER_ENV, "llm")


def generate_new_product_parameters(product_name: str, seed: int) -> tuple[float, float, float, float]:
    """Generate deterministic parameters for a new product based on name and seed.

    Returns:
        tuple: (unit_cost, base_price, base_daily_demand, price_elasticity)
    """
    import hashlib
    import random

    # Create deterministic seed from product name and environment seed
    combined_seed_data = f"{seed}:new_product:{product_name}".encode()
    digest = hashlib.sha256(combined_seed_data).digest()
    product_seed = int.from_bytes(digest[:8], "big")

    rng = random.Random(product_seed)

    # Generate parameters within reasonable ranges
    unit_cost = rng.uniform(0.30, 2.00)  # $0.30 to $2.00
    base_price = unit_cost * rng.uniform(1.5, 3.0)  # 50-200% markup
    base_daily_demand = rng.uniform(2.0, 8.0)  # 2-8 units per day base demand
    price_elasticity = -rng.uniform(0.5, 1.5)  # Negative elasticity between -0.5 and -1.5

    return unit_cost, base_price, base_daily_demand, price_elasticity


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
    demand_provider: str = field(default_factory=_default_demand_provider)
    supplier: SupplierConfig = field(default_factory=SupplierConfig)
    supplier_research_minutes: int = 60

    def validate(self) -> None:
        if self.starting_cash < 0:
            raise ValueError("starting_cash must be non-negative")
        if self.daily_fee < 0:
            raise ValueError("daily_fee must be non-negative")
        if self.minutes_per_turn <= 0:
            raise ValueError("minutes_per_turn must be positive")
        if self.slots_small < 0 or self.slots_large < 0:
            raise ValueError("slot counts must be non-negative")
        if self.demand_provider.lower() not in {"llm", "deterministic", "rng"}:
            raise ValueError("demand_provider must be 'llm' or 'deterministic'")
        if self.supplier_research_minutes <= 0:
            raise ValueError("supplier_research_minutes must be positive")
        self.supplier.validate()
