"""Tests for demand parameter provider plumbing."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from examples.vending_bench import demand as demand_module
from examples.vending_bench.demand import (
    DemandModel,
    GeneratedDemandParameters,
    create_parameter_provider,
    generate_parameters,
)
from examples.vending_bench.state import DemandProfile, Product, Slot


@dataclass
class _StubProvider:
    reference_price: float
    base_sales: float
    elasticity: float
    calls: list[tuple[str, int]] = field(default_factory=list)

    def generate(self, product: Product, *, seed: int) -> GeneratedDemandParameters:
        self.calls.append((product.sku, seed))
        return GeneratedDemandParameters(
            reference_price=self.reference_price,
            base_sales=self.base_sales,
            elasticity=self.elasticity,
        )


def _build_product(*, sku: str = "sku") -> Product:
    return Product(
        sku=sku,
        name="Test",
        size="small",
        slot_capacity=12,
        unit_cost=1.0,
        base_price=2.0,
        base_daily_demand=10.0,
        price_elasticity=-1.0,
        variety_class="snack",
    )


@pytest.fixture(autouse=True)
def _reset_provider_cache(monkeypatch):
    monkeypatch.setattr(demand_module, "_DEFAULT_PROVIDER", None, raising=False)


def test_generate_parameters_uses_explicit_provider():
    product = _build_product()
    provider = _StubProvider(reference_price=3.0, base_sales=7.0, elasticity=-1.2)

    params = generate_parameters(product, seed=42, provider=provider)

    assert params.reference_price == pytest.approx(3.0)
    assert params.base_sales == pytest.approx(7.0)
    assert params.elasticity == pytest.approx(-1.2)
    assert provider.calls == [(product.sku, 42)]


def test_demand_model_caches_provider_results_across_days():
    product = _build_product(sku="cache")
    profile = DemandProfile(product=product)
    provider = _StubProvider(reference_price=2.5, base_sales=9.0, elasticity=-1.1)

    model = DemandModel(
        seed=11,
        skus=[product.sku],
        profiles={product.sku: profile},
        parameter_provider=provider,
    )

    assert len(provider.calls) == 1
    call_sku, _ = provider.calls[0]
    assert call_sku == product.sku

    machine = [[Slot(sku=product.sku, quantity=10, price=2.5, capacity=product.slot_capacity)]]

    model.simulate_day(day=0, demand_profiles={product.sku: profile}, machine_inventory=machine)
    model.simulate_day(day=1, demand_profiles={product.sku: profile}, machine_inventory=machine)

    assert len(provider.calls) == 1
    assert profile.reference_price == pytest.approx(2.5)
    assert profile.base_daily_sales == pytest.approx(9.0)
    assert profile.price_elasticity == pytest.approx(-1.1)


def test_create_parameter_provider_honours_env(monkeypatch):
    monkeypatch.setenv("DEMAND_PROVIDER", "deterministic")
    provider = create_parameter_provider()
    assert isinstance(provider, demand_module.DeterministicDemandParameterProvider)
