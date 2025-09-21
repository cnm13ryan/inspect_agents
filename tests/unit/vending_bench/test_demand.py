"""Unit tests for the vending demand model."""

from __future__ import annotations

import pytest

from examples.vending_bench import demand as demand_module
from examples.vending_bench.demand import DemandModel, generate_parameters
from examples.vending_bench.state import DemandProfile, Product, Slot


@pytest.fixture(autouse=True)
def _force_deterministic_provider(monkeypatch):
    """Ensure legacy deterministic provider for demand-model tests."""

    monkeypatch.setenv("DEMAND_PROVIDER", "deterministic")
    monkeypatch.setattr(demand_module, "_DEFAULT_PROVIDER", None, raising=False)


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


def test_new_product_parameter_generation_deterministic():
    """Test that new product parameters are deterministic with same seed."""
    from examples.vending_bench.config import generate_new_product_parameters

    seed = 12345
    product_name = "test_new_product"

    # Generate parameters multiple times with same seed
    params1 = generate_new_product_parameters(product_name, seed)
    params2 = generate_new_product_parameters(product_name, seed)
    params3 = generate_new_product_parameters(product_name, seed)

    assert params1 == params2 == params3

    # Verify parameters are within expected ranges
    unit_cost, base_price, base_daily_demand, price_elasticity = params1
    assert 0.30 <= unit_cost <= 2.00
    assert base_price >= unit_cost * 1.5
    assert base_price <= unit_cost * 3.0
    assert 2.0 <= base_daily_demand <= 8.0
    assert -1.5 <= price_elasticity <= -0.5


def test_new_product_parameter_generation_varies_by_name():
    """Test that different product names generate different parameters."""
    from examples.vending_bench.config import generate_new_product_parameters

    seed = 12345
    params_a = generate_new_product_parameters("product_a", seed)
    params_b = generate_new_product_parameters("product_b", seed)

    assert params_a != params_b


def test_new_product_parameter_generation_varies_by_seed():
    """Test that different seeds generate different parameters."""
    from examples.vending_bench.config import generate_new_product_parameters

    product_name = "test_product"
    params_seed1 = generate_new_product_parameters(product_name, 111)
    params_seed2 = generate_new_product_parameters(product_name, 222)

    assert params_seed1 != params_seed2


def test_demand_model_weather_caching_deterministic():
    """Test that weather factors are cached and deterministic."""
    model = DemandModel(seed=42, skus=[])

    # Weather should be the same for the same day
    weather1 = model._weather_factor(day=5, sensitivity=0.3)
    weather2 = model._weather_factor(day=5, sensitivity=0.3)
    assert weather1 == weather2

    # Different days should have different weather
    weather3 = model._weather_factor(day=6, sensitivity=0.3)
    assert weather1 != weather3


def test_demand_model_noise_caching_deterministic():
    """Test that noise factors are cached and deterministic."""
    model = DemandModel(seed=42, skus=["test_sku"])

    # Noise should be the same for the same day and SKU
    noise1 = model._noise(day=3, sku="test_sku", scale=0.2)
    noise2 = model._noise(day=3, sku="test_sku", scale=0.2)
    assert noise1 == noise2

    # Different days should have different noise
    noise3 = model._noise(day=4, sku="test_sku", scale=0.2)
    assert noise1 != noise3

    # Different SKUs should have different noise
    noise4 = model._noise(day=3, sku="other_sku", scale=0.2)
    assert noise1 != noise4


def test_demand_simulation_deterministic_multiple_runs():
    """Test that demand simulation produces identical results across multiple runs."""
    product = _build_product(sku="consistent_sku")
    profile = DemandProfile(
        product=product,
        reference_price=2.0,
        base_daily_sales=10.0,
        price_elasticity=-1.0,
        noise_scale=0.1,
        weather_sensitivity=0.1,
        seasonal_amplitude=0.05,
    )

    # Create two identical demand models
    model1 = DemandModel(seed=789, skus=[product.sku])
    model2 = DemandModel(seed=789, skus=[product.sku])

    # Set up identical machine state
    machine_inventory = [[None for _ in range(3)] for _ in range(4)]
    machine_inventory[0][0] = Slot(
        sku=product.sku,
        quantity=10,
        price=2.0,
        capacity=product.slot_capacity,
    )

    # Run simulation on both models
    outcome1 = model1.simulate_day(
        day=10,
        demand_profiles={product.sku: profile},
        machine_inventory=machine_inventory,
    )

    # Reset machine state for second run
    machine_inventory[0][0] = Slot(
        sku=product.sku,
        quantity=10,
        price=2.0,
        capacity=product.slot_capacity,
    )

    outcome2 = model2.simulate_day(
        day=10,
        demand_profiles={product.sku: profile},
        machine_inventory=machine_inventory,
    )

    # Results should be identical
    assert outcome1.units_sold == outcome2.units_sold
    assert outcome1.revenue == pytest.approx(outcome2.revenue)
    assert len(outcome1.slot_sales) == len(outcome2.slot_sales)
    for slot_key in outcome1.slot_sales:
        assert slot_key in outcome2.slot_sales
        assert outcome1.slot_sales[slot_key].quantity == outcome2.slot_sales[slot_key].quantity
        assert outcome1.slot_sales[slot_key].revenue == pytest.approx(outcome2.slot_sales[slot_key].revenue)
