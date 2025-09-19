"""Elastic demand model with deterministic randomness."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from .state import DemandProfile, Slot


@dataclass
class DemandOutcome:
    units_sold: dict[str, int]
    slot_sales: dict[tuple[int, int], SlotSale]
    revenue: float


@dataclass
class SlotSale:
    quantity: int = 0
    revenue: float = 0.0


class DemandModel:
    def __init__(self, seed: int, skus: Iterable[str]) -> None:
        self._seed = seed
        self._sku_index: dict[str, int] = {sku: idx for idx, sku in enumerate(sorted(set(skus)))}
        self._weather_cache: dict[int, float] = {}
        self._noise_cache: dict[tuple[int, str], float] = {}

    def _ensure_index(self, sku: str) -> int:
        if sku not in self._sku_index:
            self._sku_index[sku] = len(self._sku_index)
        return self._sku_index[sku]

    def _weather_factor(self, day: int, sensitivity: float) -> float:
        if day not in self._weather_cache:
            seed = (self._seed + day * 1_048_576) & 0xFFFFFFFFFFFFFFFF
            rng = random.Random(seed)
            delta = rng.uniform(-1.0, 1.0)
            self._weather_cache[day] = 1.0 + sensitivity * delta
        return max(0.5, min(1.5, self._weather_cache[day]))

    @staticmethod
    def _weekday_multiplier(day: int) -> float:
        weekday = day % 7
        multipliers = {
            0: 0.95,  # Monday slower after weekend
            1: 1.0,
            2: 1.05,
            3: 1.1,
            4: 1.15,
            5: 1.2,
            6: 0.9,
        }
        return multipliers.get(weekday, 1.0)

    @staticmethod
    def _seasonal_multiplier(day: int, amplitude: float) -> float:
        # 365 day sinusoid centred at 1.0
        return 1.0 + amplitude * math.sin((2.0 * math.pi * day) / 365.0)

    def _noise(self, day: int, sku: str, scale: float) -> float:
        key = (day, sku)
        if key not in self._noise_cache:
            idx = self._ensure_index(sku)
            seed = (self._seed * 6364136223846793005 + day * 1315423911 + idx * 2654435761) & 0xFFFFFFFFFFFFFFFF
            rng = random.Random(seed)
            sample = rng.gauss(1.0, scale)
            self._noise_cache[key] = max(0.5, min(1.5, sample))
        return self._noise_cache[key]

    @staticmethod
    def _variety_penalty(stocked_classes: Iterable[str]) -> float:
        unique_classes = {cls for cls in stocked_classes if cls}
        if not unique_classes:
            return 0.5  # empty machine – effectively zero demand
        target = 4
        deficit = max(0, target - len(unique_classes))
        penalty = 1.0 - 0.5 * (deficit / target)
        return max(0.5, penalty)

    def simulate_day(
        self,
        *,
        day: int,
        demand_profiles: dict[str, DemandProfile],
        machine_inventory: list[list[Slot | None]],
    ) -> DemandOutcome:
        sku_slots: dict[str, list[tuple[int, int, Slot]]] = {}
        stocked_classes: list[str] = []
        for row_idx, row in enumerate(machine_inventory):
            for col_idx, slot in enumerate(row):
                if slot is None or slot.sku is None or slot.quantity <= 0:
                    continue
                sku = slot.sku
                sku_slots.setdefault(sku, []).append((row_idx, col_idx, slot))
                profile = demand_profiles.get(sku)
                if profile:
                    stocked_classes.append(profile.product.variety_class)
        variety_factor = self._variety_penalty(stocked_classes)
        units_sold: dict[str, int] = {}
        slot_sales: dict[tuple[int, int], SlotSale] = {}
        revenue = 0.0

        for sku, profile in demand_profiles.items():
            slots = sku_slots.get(sku, [])
            available = sum(slot.quantity for _, _, slot in slots)
            if available <= 0:
                units_sold[sku] = 0
                continue

            product = profile.product
            prices_for_sku = [slot.price for _, _, slot in slots if slot.price is not None]
            if prices_for_sku:
                price = min(prices_for_sku)
            else:
                price = product.base_price
            base_demand = product.base_daily_demand
            if product.base_price <= 0:
                price_factor = 1.0
            else:
                ratio = max(0.01, price / product.base_price)
                price_factor = ratio**product.price_elasticity

            weekday_factor = self._weekday_multiplier(day)
            seasonal_factor = self._seasonal_multiplier(day, profile.seasonal_amplitude)
            weather_factor = self._weather_factor(day, profile.weather_sensitivity)
            noise = self._noise(day, sku, profile.noise_scale)

            demand = base_demand
            demand *= price_factor
            demand *= weekday_factor
            demand *= seasonal_factor
            demand *= weather_factor
            demand *= variety_factor
            demand *= noise

            demand = max(0.0, demand)
            sold = min(available, int(round(demand)))
            units_sold[sku] = sold

            remaining = sold
            for row_idx, col_idx, slot in sorted(slots, key=lambda item: (item[0], item[1])):
                if remaining <= 0:
                    break
                sell_qty = min(slot.quantity, remaining)
                if sell_qty <= 0:
                    continue
                slot_price = slot.price if slot.price is not None else product.base_price
                key = (row_idx, col_idx)
                sale = slot_sales.setdefault(key, SlotSale())
                sale.quantity += sell_qty
                sale.revenue += sell_qty * slot_price
                revenue += sell_qty * slot_price
                remaining -= sell_qty

        return DemandOutcome(units_sold=units_sold, slot_sales=slot_sales, revenue=revenue)
