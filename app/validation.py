"""Validate reviewed invoice fields before approval."""

import re
from datetime import date
from decimal import Decimal

REQUIRED_FIELDS = (
    "supplier",
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "vat",
    "total",
)


def validate_approval(fields: dict) -> list[str]:
    """Return validation errors; an empty list means approval is allowed."""
    errors = []

    for key in REQUIRED_FIELDS:
        value = fields.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} is required.")

    dates = {}
    for key in ("invoice_date", "due_date"):
        value = fields.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            dates[key] = date.fromisoformat(value)
        except ValueError:
            errors.append(f"{key} must be a valid YYYY-MM-DD date.")

    if (
        len(dates) == 2
        and dates["due_date"] < dates["invoice_date"]
    ):
        errors.append("Due date cannot be before invoice date.")

    currency = fields.get("currency")
    if isinstance(currency, str) and currency.strip():
        if currency.strip() != "EUR":
            errors.append("Only EUR invoices are supported.")

    amounts = {}
    for key in ("subtotal", "vat", "total"):
        value = fields.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value):
            errors.append(
                f"{key} must be a non-negative amount with "
                "at most 12 whole digits and two decimal places."
            )
            continue
        amounts[key] = Decimal(value)

    if len(amounts) == 3:
        if amounts["subtotal"] + amounts["vat"] != amounts["total"]:
            errors.append("Subtotal plus VAT must equal total.")

    return errors
