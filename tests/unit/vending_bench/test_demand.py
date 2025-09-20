"""Unit tests for the vending demand model."""

from __future__ import annotations

import pytest

from examples.vending_bench.demand import DemandModel, generate_parameters
from examples.vending_bench.state import DemandProfile, Product, Slot


def _build_product(*, sku: str = "test_sku") -> Product:
    return Product(
        sku=sku,
        name="Test Product",
        size="small",
        slot_capacity=12,
        unit_cost=1.0,
        base_price=2.0,
        base_daily_demand=10.0,
        price_elasticity=-1.0,
        variety_class="snack",
    )


def test_generate_parameters_deterministic():
    product = _build_product()

    params_a = generate_parameters(product, seed=1234)
    params_b = generate_parameters(product, seed=1234)

    assert params_a == params_b
    assert params_a.reference_price > 0
    assert params_a.base_sales > 0
    assert params_a.elasticity < 0


def test_ensure_profiles_populates_parameters():
    product = _build_product(sku="profile_sku")
    profile = DemandProfile(product=product)
    model = DemandModel(seed=21, skus=[product.sku])

    assert profile.reference_price is None
    assert profile.base_daily_sales is None
    assert profile.price_elasticity is None

    model.ensure_profiles({product.sku: profile})

    assert profile.reference_price is not None
    assert profile.base_daily_sales is not None
    assert profile.price_elasticity is not None

    before = (
        profile.reference_price,
        profile.base_daily_sales,
        profile.price_elasticity,
    )

    model.ensure_profiles({product.sku: profile})

    after = (
        profile.reference_price,
        profile.base_daily_sales,
        profile.price_elasticity,
    )

    assert after == before


def test_linear_price_elasticity_response():
    product = _build_product(sku="elastic_sku")
    profile = DemandProfile(
        product=product,
        reference_price=2.0,
        base_daily_sales=10.0,
        price_elasticity=-1.2,
        noise_scale=0.0,
        weather_sensitivity=0.0,
        seasonal_amplitude=0.0,
    )
    model = DemandModel(seed=7, skus=[product.sku])

    def simulate(price: float) -> int:
        machine_inventory = [[None for _ in range(3)] for _ in range(4)]
        machine_inventory[0][0] = Slot(
            sku=product.sku,
            quantity=200,
            price=price,
            capacity=product.slot_capacity,
        )
        outcome = model.simulate_day(
            day=1,
            demand_profiles={product.sku: profile},
            machine_inventory=machine_inventory,
        )
        return outcome.units_sold[product.sku]

    at_reference = simulate(2.0)
    discounted = simulate(1.8)
    premium = simulate(2.2)

    assert at_reference == 10
    assert discounted == 11
    assert premium == 9


def test_variety_penalty_excess_categories():
    penalty_low = DemandModel._variety_penalty(["snack", "beverage", "snack"])
    penalty_high = DemandModel._variety_penalty(["snack", "beverage", "hot", "cold", "gum", "candy"])

    assert penalty_low == pytest.approx(1.0)
    assert penalty_high == pytest.approx(0.75)
    assert 0.5 <= penalty_high < penalty_low
