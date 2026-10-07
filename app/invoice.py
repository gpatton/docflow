import re
from datetime import date
from decimal import Decimal


def extract_invoice(text: str) -> dict:
    """Extract labelled fields without guessing missing values."""

    def find(pattern: str):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    def iso_date(label: str):
        value = find(rf"^{label}:\s*(\d{{4}}-\d{{2}}-\d{{2}})\s*$")
        if value is None:
            return None
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None

    def amount(label: str):
        value = find(
            rf"^{label}:\s*EUR[ \t]+(\d+(?:\.\d{{2}})?)\s*$"
        )
        return Decimal(value) if value is not None else None

    subtotal = amount("Subtotal")
    vat = amount(r"VAT[ \t]*\(\d+(?:\.\d+)?%\)")
    total = amount("Total due")

    fields = {
        "supplier": find(r"^Supplier[ \t]*\n([^\n]+)"),
        "invoice_number": find(r"^Invoice number:[ \t]*([^\n]+)"),
        "invoice_date": iso_date("Invoice date"),
        "due_date": iso_date("Due date"),
        "currency": find(r"^Currency:[ \t]*([A-Z]{3})[ \t]*$"),
        "subtotal": str(subtotal) if subtotal is not None else None,
        "vat": str(vat) if vat is not None else None,
        "total": str(total) if total is not None else None,
    }

    missing = [name for name, value in fields.items() if value is None]

    totals_match = None
    if all(value is not None for value in (subtotal, vat, total)):
        totals_match = subtotal + vat == total

    return {
        "method": "labelled_text_rules_v1",
        "fields": fields,
        "validation": {
            "missing_fields": missing,
            "subtotal_plus_vat_matches_total": totals_match,
            "human_review_required": True,
        },
    }
