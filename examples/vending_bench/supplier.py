"""Deterministic supplier fixtures and email responders for the vending simulator."""

from __future__ import annotations

import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .state import (
    EmailMessage,
    Order,
    Product,
    SimulatorState,
    SupplierContact,
    SupplierProductOffer,
)

if TYPE_CHECKING:
    from .state import DemandProfile


@dataclass(frozen=True)
class SupplierConfig:
    min_lead_time_days: int = 1
    max_lead_time_days: int = 4

    def validate(self) -> None:
        if self.min_lead_time_days < 0:
            raise ValueError("min_lead_time_days must be >= 0")
        if self.max_lead_time_days < self.min_lead_time_days:
            raise ValueError("max_lead_time_days must be >= min_lead_time_days")


@dataclass
class SupplierEmailResponse:
    """Result of processing an outbound email to a supplier."""

    reply: EmailMessage | None
    orders: list[Order]


class SupplierModel:
    """Seeded supplier model that responds to emails and schedules orders."""

    QUOTE_KEYWORDS = ("quote", "pricing", "price list", "catalog", "product list", "availability")
    PURCHASE_KEYWORDS = ("order", "purchase", "buy")

    def __init__(
        self,
        seed: int,
        catalogue: dict[str, DemandProfile],
        config: SupplierConfig | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self.config = config or SupplierConfig()
        self.config.validate()

        # Copy base product data for deterministic offers
        self._products: dict[str, Product] = {sku: profile.product for sku, profile in catalogue.items()}
        self._contacts = self._build_contacts()

    def supplier_directory(self) -> dict[str, SupplierContact]:
        """Expose the supplier directory for inspection/testing."""

        return self._contacts.copy()

    def process_email(self, state: SimulatorState, message: EmailMessage) -> SupplierEmailResponse:
        """Return a reply and optional order(s) in response to an outbound email."""

        contact = self._contacts.get(message.recipient.lower())
        if contact is None:
            return SupplierEmailResponse(reply=None, orders=[])

        lower_subject = message.subject.lower()
        lower_body = message.body.lower()

        if self._is_quote_request(lower_subject, lower_body):
            reply = self._quote_response(contact, message, state.day)
            return SupplierEmailResponse(reply=reply, orders=[])

        if self._is_purchase_request(lower_subject, lower_body):
            requested = self._parse_purchase_quantities(contact, lower_body)
            if not requested:
                return SupplierEmailResponse(
                    reply=self._clarification_response(
                        contact, message, "Please specify quantities for each SKU you'd like to order.", state.day
                    ),
                    orders=[],
                )

            missing_requirements: list[str] = []
            for sku, qty in requested.items():
                offer = contact.products[sku]
                if qty < offer.min_order_quantity:
                    missing_requirements.append(
                        f"{offer.product.name} (SKU {sku}) requires a minimum order of {offer.min_order_quantity} units"
                    )

            if missing_requirements:
                return SupplierEmailResponse(
                    reply=self._clarification_response(
                        contact,
                        message,
                        "\n".join(missing_requirements),
                        state.day,
                    ),
                    orders=[],
                )

            if not self._has_account_info(lower_body):
                return SupplierEmailResponse(
                    reply=self._clarification_response(
                        contact,
                        message,
                        "Please include your account number so we can process the purchase order.",
                        state.day,
                    ),
                    orders=[],
                )

            if not self._has_delivery_address(lower_body):
                return SupplierEmailResponse(
                    reply=self._clarification_response(
                        contact,
                        message,
                        "Please confirm the delivery address to schedule shipment.",
                        state.day,
                    ),
                    orders=[],
                )

            offers = [contact.products[sku] for sku in requested.keys()]
            total_cost = sum(requested[offer.product.sku] * offer.wholesale_price for offer in offers)
            if state.cash_balance < total_cost:
                return SupplierEmailResponse(
                    reply=self._clarification_response(
                        contact,
                        message,
                        (
                            "We cannot process the order because your available cash ($"
                            f"{state.cash_balance:.2f}) is below the order total of ${total_cost:.2f}."
                        ),
                        state.day,
                    ),
                    orders=[],
                )

            orders = [self._create_order(offer, requested[offer.product.sku], state.day) for offer in offers]
            reply = self._order_confirmation(contact, message, orders, state.day)
            return SupplierEmailResponse(reply=reply, orders=orders)

        # Default response asking for clarification when the intent is unclear
        return SupplierEmailResponse(
            reply=self._clarification_response(
                contact,
                message,
                "Let us know if you need a price quote or want to place an order.",
                state.day,
            ),
            orders=[],
        )

    def split_deliveries(self, orders: Iterable[Order], current_day: int) -> tuple[list[Order], list[Order]]:
        """Partition orders into delivered vs pending based on the current day."""

        delivered: list[Order] = []
        pending: list[Order] = []
        for order in orders:
            if order.delivery_day <= current_day:
                delivered.append(order)
            else:
                pending.append(order)
        return delivered, pending

    # Internal helpers -----------------------------------------------------------------

    def _build_contacts(self) -> dict[str, SupplierContact]:
        """Construct deterministic supplier directory."""

        def make_offer(
            sku: str,
            *,
            wholesale_price: float | None = None,
            min_order: int,
            lead: tuple[int, int],
            extra_keywords: tuple[str, ...] = (),
        ) -> SupplierProductOffer:
            product = self._products[sku]
            price = wholesale_price if wholesale_price is not None else product.unit_cost
            keywords = {sku.lower(), product.name.lower()}
            keywords.add(product.name.lower().replace(" ", ""))
            keywords.update(extra_keywords)
            return SupplierProductOffer(
                product=product,
                wholesale_price=price,
                min_order_quantity=min_order,
                lead_time_days=lead,
                keywords=tuple(sorted(keywords)),
            )

        contacts = [
            SupplierContact(
                name="Regional Food Distributors Inc.",
                email="orders@rfd-inc.com",
                categories=("beverage", "snack"),
                products={
                    sku: make_offer(
                        sku,
                        wholesale_price=self._products[sku].unit_cost * 0.95,
                        min_order=24 if sku != "energy_drink" else 12,
                        lead=(2, 5),
                    )
                    for sku in ("coke", "water", "energy_drink")
                    if sku in self._products
                },
            ),
            SupplierContact(
                name="QuickStock Vending Solutions",
                email="supply@quickstock.com",
                categories=("snack", "impulse"),
                products={
                    sku: make_offer(
                        sku,
                        wholesale_price=self._products[sku].unit_cost * 0.9,
                        min_order=12,
                        lead=(1, 3),
                    )
                    for sku in ("chips", "chocolate_bar", "energy_drink")
                    if sku in self._products
                },
            ),
            SupplierContact(
                name="Metro Wholesale Foods",
                email="sales@metrofoods.example",
                categories=("balanced", "office"),
                products={
                    sku: make_offer(
                        sku,
                        wholesale_price=self._products[sku].unit_cost,
                        min_order=18,
                        lead=(3, 6),
                        extra_keywords=(self._products[sku].variety_class.lower(),),
                    )
                    for sku in self._products.keys()
                },
            ),
        ]

        return {contact.email.lower(): contact for contact in contacts if contact.products}

    def _is_quote_request(self, subject: str, body: str) -> bool:
        return any(keyword in subject or keyword in body for keyword in self.QUOTE_KEYWORDS)

    def _is_purchase_request(self, subject: str, body: str) -> bool:
        return any(keyword in subject or keyword in body for keyword in self.PURCHASE_KEYWORDS)

    def _parse_purchase_quantities(self, contact: SupplierContact, lower_body: str) -> dict[str, int]:
        requested: dict[str, int] = {}
        for sku, offer in contact.products.items():
            patterns = {re.escape(keyword) for keyword in offer.keywords}
            for pattern in patterns:
                regex = re.compile(rf"(\d+)\s+(?:units?\s+of\s+)?{pattern}\b")
                for match in regex.finditer(lower_body):
                    quantity = int(match.group(1))
                    requested[sku] = requested.get(sku, 0) + quantity
        return requested

    def _has_account_info(self, lower_body: str) -> bool:
        if "account" not in lower_body:
            return False
        return bool(re.search(r"account\s*(?:number|#|no\.?|acct)?\s*[:#]?\s*[a-z0-9-]{4,}", lower_body))

    def _has_delivery_address(self, lower_body: str) -> bool:
        if "address" in lower_body:
            return True
        return "deliver" in lower_body and "to" in lower_body

    def _quote_response(self, contact: SupplierContact, message: EmailMessage, current_day: int) -> EmailMessage:
        lines = [
            f"Hello, this is {contact.name}.",
            "Here are our current wholesale options:",
        ]
        for offer in sorted(contact.products.values(), key=lambda o: o.product.name):
            lead_min, lead_max = offer.lead_time_days
            lead_text = f"{lead_min} day" if lead_min == lead_max else f"{lead_min}-{lead_max} day"
            lines.append(
                f"- {offer.product.name} (SKU {offer.product.sku}): "
                f"${offer.wholesale_price:.2f} per unit, MOQ {offer.min_order_quantity}, "
                f"lead time {lead_text}s"
            )
        lines.append("Let us know if you'd like to place an order.")
        body = "\n".join(lines)
        return EmailMessage(
            day=current_day + 1,
            subject=f"Re: {message.subject or 'Supplier inquiry'}",
            body=body,
            sender=contact.email,
            recipient=message.sender,
        )

    def _clarification_response(
        self,
        contact: SupplierContact,
        message: EmailMessage,
        reason: str,
        current_day: int,
    ) -> EmailMessage:
        body = (
            f"Hello, this is {contact.name}.\n"
            f"{reason}\n"
            "Feel free to reply with the missing details or request an updated quote."
        )
        return EmailMessage(
            day=current_day + 1,
            subject=f"Re: {message.subject or 'Supplier request'}",
            body=body,
            sender=contact.email,
            recipient=message.sender,
        )

    def _order_confirmation(
        self,
        contact: SupplierContact,
        message: EmailMessage,
        orders: list[Order],
        current_day: int,
    ) -> EmailMessage:
        lines = [
            "Thanks for your purchase order. We've scheduled the following items:",
        ]
        for order in orders:
            lines.append(
                f"- {order.quantity} units of {self._products[order.sku].name} "
                f"(SKU {order.sku}) arriving day {order.delivery_day} at ${order.total_cost:.2f}."
            )
        total_cost = sum(order.total_cost for order in orders)
        lines.append(f"Total cost debited: ${total_cost:.2f}.")
        lines.append("Reach out if you need to adjust quantities or delivery timing.")
        body = "\n".join(lines)
        return EmailMessage(
            day=current_day + 1,
            subject=f"Order confirmation #{message.day}-{current_day + 1}",
            body=body,
            sender=contact.email,
            recipient=message.sender,
        )

    def _create_order(self, offer: SupplierProductOffer, quantity: int, day_ordered: int) -> Order:
        lead_min, lead_max = offer.lead_time_days
        if lead_min == lead_max:
            delivery_day = day_ordered + max(1, lead_min)
        else:
            delivery_day = day_ordered + max(1, self._rng.randint(lead_min, lead_max))
        return Order(
            sku=offer.product.sku,
            quantity=quantity,
            unit_cost=offer.wholesale_price,
            day_ordered=day_ordered,
            delivery_day=delivery_day,
        )
