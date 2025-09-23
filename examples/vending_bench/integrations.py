"""External service integrations for Vending-Bench suppliers."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


class PerplexityIntegrationError(RuntimeError):
    """Raised when the Perplexity integration cannot return usable search results."""


@dataclass(slots=True)
class SupplierSearchItem:
    """Structured item entry returned from supplier search."""

    sku: str
    min_order: int | None = None
    wholesale_price: float | None = None
    lead_time_days: tuple[int, int] | None = None
    notes: str | None = None


@dataclass(slots=True)
class SupplierSearchHit:
    """Supplier metadata produced by Perplexity search or deterministic stub."""

    name: str
    email: str
    catalog: list[SupplierSearchItem]
    website: str | None = None
    phone: str | None = None
    tags: tuple[str, ...] = ()
    notes: str | None = None
    source: str = "stub"
    raw: dict[str, Any] = field(default_factory=dict)

    def has_known_skus(self, known_skus: Sequence[str]) -> bool:
        """Return True if the hit references at least one known SKU."""

        valid = {sku.lower() for sku in known_skus}
        for item in self.catalog:
            if item.sku.lower() in valid:
                return True
        return False


class PerplexityClient:
    """Minimal client for Perplexity's chat completions API with structured output."""

    _ENDPOINT_DEFAULT = "https://api.perplexity.ai/chat/completions"

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must be provided")
        self._api_key = api_key
        self._model = model or os.getenv("PERPLEXITY_MODEL", "sonar-pro")
        self._timeout = timeout
        self._endpoint = os.getenv("PERPLEXITY_API_URL", self._ENDPOINT_DEFAULT)

    def search_suppliers(self, *, query: str, limit: int, known_skus: Sequence[str]) -> list[SupplierSearchHit]:
        if not query:
            raise ValueError("query must be non-empty")
        if limit <= 0:
            raise ValueError("limit must be positive")

        schema = self._build_json_schema()
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a procurement analyst compiling vending machine suppliers. "
                        "Return ONLY JSON that adheres to the provided schema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Research real wholesalers that can service vending machines. "
                        "Use the query verbatim, prefer North American suppliers, and map their catalog to the allowed SKUs. "
                        "Allowed SKUs: "
                        + ", ".join(sorted({sku.lower() for sku in known_skus}))
                        + f". Limit results to {limit}."
                    ),
                },
            ],
            "response_format": {"type": "json_schema", "json_schema": schema},
            "max_output_tokens": 800,
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            self._endpoint,
            json=payload,
            headers=headers,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise PerplexityIntegrationError(f"Perplexity API returned {response.status_code}: {response.text[:200]}")

        try:
            body = response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover - response contract violation
            raise PerplexityIntegrationError("Perplexity response was not valid JSON") from exc

        content = self._extract_content(body)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PerplexityIntegrationError("Perplexity did not return JSON matching the schema") from exc

        suppliers = parsed.get("suppliers", [])
        hits: list[SupplierSearchHit] = []
        for entry in suppliers[:limit]:
            try:
                hits.append(self._convert_entry(entry))
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Skipping malformed supplier entry: %s", exc)
                continue

        return hits

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not choices:
            raise PerplexityIntegrationError("Perplexity response missing choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            combined = "".join(text_parts).strip()
            if combined:
                return combined
        raise PerplexityIntegrationError("Perplexity message content missing text payload")

    @staticmethod
    def _convert_entry(entry: dict[str, Any]) -> SupplierSearchHit:
        catalog_data = entry.get("catalog") or []
        items: list[SupplierSearchItem] = []
        for item in catalog_data:
            sku = str(item.get("sku", "")).strip()
            if not sku:
                continue
            lead = item.get("lead_time_days")
            lead_tuple: tuple[int, int] | None = None
            if isinstance(lead, list) and lead:
                if len(lead) == 1:
                    lead_tuple = (int(lead[0]), int(lead[0]))
                elif len(lead) >= 2:
                    lead_tuple = (int(lead[0]), int(lead[1]))
            items.append(
                SupplierSearchItem(
                    sku=sku,
                    min_order=_coerce_int(item.get("min_order")),
                    wholesale_price=_coerce_float(item.get("wholesale_price")),
                    lead_time_days=lead_tuple,
                    notes=item.get("notes"),
                )
            )

        tags = entry.get("tags") or []
        return SupplierSearchHit(
            name=entry.get("name", "").strip(),
            email=entry.get("email", "").strip().lower(),
            website=_sanitize_url(entry.get("website")),
            phone=_sanitize_phone(entry.get("phone")),
            catalog=items,
            tags=tuple(tag.lower() for tag in tags if isinstance(tag, str)),
            notes=entry.get("summary"),
            source=entry.get("source", "perplexity"),
            raw=entry,
        )

    @staticmethod
    def _build_json_schema() -> dict[str, Any]:
        return {
            "name": "supplier_search_results",
            "schema": {
                "type": "object",
                "properties": {
                    "suppliers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "email", "catalog"],
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "website": {"type": "string"},
                                "phone": {"type": "string"},
                                "summary": {"type": "string"},
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "source": {"type": "string"},
                                "catalog": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["sku"],
                                        "properties": {
                                            "sku": {"type": "string"},
                                            "min_order": {"type": ["integer", "null"]},
                                            "wholesale_price": {"type": ["number", "null"]},
                                            "lead_time_days": {
                                                "type": "array",
                                                "items": {"type": "integer"},
                                                "minItems": 1,
                                                "maxItems": 2,
                                            },
                                            "notes": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    }
                },
                "required": ["suppliers"],
            },
        }


def deterministic_supplier_hits(*, env: Any, limit: int, source: str = "stub") -> list[SupplierSearchHit]:
    """Return deterministic supplier hits aligned with the current catalogue."""

    catalogue = env.state.demand_profiles
    hits: list[SupplierSearchHit] = []

    def build_items(
        skus: Iterable[str], *, multiplier: float, min_order: int, lead: tuple[int, int]
    ) -> list[SupplierSearchItem]:
        items: list[SupplierSearchItem] = []
        for sku in skus:
            profile = catalogue.get(sku)
            if profile is None:
                continue
            wholesale = round(profile.product.unit_cost * multiplier, 2)
            items.append(
                SupplierSearchItem(
                    sku=sku,
                    min_order=min_order,
                    wholesale_price=wholesale,
                    lead_time_days=lead,
                )
            )
        return items

    hits.append(
        SupplierSearchHit(
            name="Regional Food Distributors Inc.",
            email="orders@rfd-inc.com",
            website="https://example-supplier1.com",
            phone="+1-800-555-0110",
            catalog=build_items(
                ("coke", "water", "energy_drink"),
                multiplier=0.95,
                min_order=24,
                lead=(2, 5),
            ),
            tags=("beverage", "snack"),
            notes="Bulk beverage catalogue with predictable 2-5 day delivery windows across the Midwest.",
            source=source,
        )
    )
    hits.append(
        SupplierSearchHit(
            name="QuickStock Vending Solutions",
            email="supply@quickstock.com",
            website="https://example-supplier2.com",
            phone="+1-800-555-0148",
            catalog=build_items(
                ("chips", "chocolate_bar", "energy_drink"),
                multiplier=0.9,
                min_order=12,
                lead=(2, 4),
            ),
            tags=("snack", "impulse"),
            notes="Fast-turn snack distributor with local cross-dock for 2-4 day replenishment.",
            source=source,
        )
    )
    hits.append(
        SupplierSearchHit(
            name="Metro Wholesale Foods",
            email="sales@metrofoods.example",
            website="https://example-supplier3.com",
            phone="+1-800-555-0190",
            catalog=build_items(
                catalogue.keys(),
                multiplier=1.0,
                min_order=18,
                lead=(3, 6),
            ),
            tags=("balanced", "office"),
            notes="Balanced assortment for office routes with 3-6 day scheduled deliveries.",
            source=source,
        )
    )

    return hits[:limit]


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sanitize_url(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    return text or None


def _sanitize_phone(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    return text or None
