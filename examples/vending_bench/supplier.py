"""Deterministic supplier fixtures for the vending simulator."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from .state import Order, Product


@dataclass(frozen=True)
class SupplierConfig:
    min_lead_time_days: int = 1
    max_lead_time_days: int = 4

    def validate(self) -> None:
        if self.min_lead_time_days < 0:
            raise ValueError("min_lead_time_days must be >= 0")
        if self.max_lead_time_days < self.min_lead_time_days:
            raise ValueError("max_lead_time_days must be >= min_lead_time_days")


class SupplierModel:
    """Pseudo-random but seedable supplier that returns deterministic lead times."""

    def __init__(self, seed: int, config: SupplierConfig | None = None) -> None:
        self._rng = random.Random(seed)
        self.config = config or SupplierConfig()
        self.config.validate()

    def quote_unit_cost(self, product: Product) -> float:
        """Return the deterministic unit cost (can be extended for markups)."""

        return product.unit_cost

    def draw_lead_time(self, product: Product) -> int:
        """Sample a deterministic lead time based on the RNG sequence."""

        span = self.config.max_lead_time_days - self.config.min_lead_time_days
        if span == 0:
            return self.config.min_lead_time_days
        return self.config.min_lead_time_days + self._rng.randint(0, span)

    def create_order(self, *, product: Product, quantity: int, day_ordered: int) -> Order:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        lead_time = self.draw_lead_time(product)
        delivery_day = day_ordered + max(1, lead_time)
        unit_cost = self.quote_unit_cost(product)
        return Order(
            sku=product.sku,
            quantity=quantity,
            unit_cost=unit_cost,
            day_ordered=day_ordered,
            delivery_day=delivery_day,
        )

    @staticmethod
    def split_deliveries(orders: Iterable[Order], current_day: int) -> tuple[list[Order], list[Order]]:
        """Partition orders into delivered vs pending based on the current day."""

        delivered: list[Order] = []
        pending: list[Order] = []
        for order in orders:
            if order.delivery_day <= current_day:
                delivered.append(order)
            else:
                pending.append(order)
        return delivered, pending
