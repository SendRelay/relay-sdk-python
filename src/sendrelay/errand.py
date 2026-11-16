"""Builders for errand stages. Each returns the same plain dict you could write by hand; they only
save remembering which fields each type takes.

Example::

    from sendrelay import Errand

    relay.tasks.create({
        "taskType": "ERRAND",
        "stages": [
            Errand.queue(bank, instructions="Collect the hardware token", expectedMinutes=30, maxMinutes=90),
            Errand.purchase(shoprite, [{"name": "Peak milk 400g", "quantity": 2, "maxUnitPrice": 350_000}]),
            Errand.dropoff(home, contact={"name": "Ada", "phone": "+2348030000000"}),
        ],
    })

Extra keyword arguments are stage fields in the API's camelCase (``reference``, ``expectedMinutes``,
``maxMinutes``, ``openingHours``, ``spendLimit``, ``payWith``, ``contact``, ``simulate``...).
"""

from __future__ import annotations

from typing import Any, List, Mapping, cast

from .types import ErrandQuestion, Item, PurchaseItem, Stage


def _stage(type_: str, location: Mapping[str, Any], instructions: str, fields: Mapping[str, Any]) -> Stage:
    return cast(Stage, {"type": type_, "location": dict(location), "instructions": instructions, **fields})


class Errand:
    @staticmethod
    def pickup(location: Mapping[str, Any], items: List[Item], *, instructions: str = "", **fields: Any) -> Stage:
        """Collect items to carry, as on any delivery."""
        return _stage("PICKUP", location, instructions, {**fields, "items": items})

    @staticmethod
    def dropoff(location: Mapping[str, Any], *, instructions: str = "", **fields: Any) -> Stage:
        """Hand over what was collected or bought. Without ``deliverItems``, everything comes here."""
        return _stage("DROPOFF", location, instructions, fields)

    @staticmethod
    def queue(location: Mapping[str, Any], *, instructions: str = "", **fields: Any) -> Stage:
        """Wait in line or for a service, then report back."""
        return _stage("QUEUE", location, instructions, fields)

    @staticmethod
    def purchase(
        location: Mapping[str, Any], items: List[PurchaseItem], *, instructions: str = "", **fields: Any
    ) -> Stage:
        """Buy a shopping list, within the prices you set."""
        return _stage("PURCHASE", location, instructions, {**fields, "items": items})

    @staticmethod
    def payment(
        location: Mapping[str, Any], payee: str, amount: int, *, instructions: str = "", **fields: Any
    ) -> Stage:
        """Pay a bill or a fee and bring the receipt. ``amount`` is the bill you expect, in kobo."""
        return _stage("PAYMENT", location, instructions, {**fields, "payee": payee, "amount": amount})

    @staticmethod
    def inspection(
        location: Mapping[str, Any], questions: List[ErrandQuestion], *, instructions: str = "", **fields: Any
    ) -> Stage:
        """Look at something and answer your questions."""
        return _stage("INSPECTION", location, instructions, {**fields, "questions": questions})

    @staticmethod
    def custom(location: Mapping[str, Any], instructions: str, effort: str, **fields: Any) -> Stage:
        """Anything else, described in ``instructions``. ``effort`` ("S", "M" or "L") sets the stage fee."""
        return _stage("CUSTOM", location, instructions, {**fields, "effort": effort})
