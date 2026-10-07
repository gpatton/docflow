import re
from datetime import date
from decimal import Decimal


def extract_invoice(text: str) -> dict:
    """Extract labelled fields from PDF text or OCR output."""

    def find(pattern: str):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    def iso_date(label: str):
        value = find(
            rf"\b{label}:[ \t]*(\d{{4}}-\d{{2}}-\d{{2}})\b"
        )
        if value is None:
            return None
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None

    def amount(label: str):
        value = find(
            rf"\b{label}:\s*EUR[ \t]+"
            rf"(\d+(?:\.\d{{2}})?)(?![\d.,])"
        )
        return Decimal(value) if value is not None else None

    # This layout places the supplier name below the Supplier heading.
    supplier = find(
        r"^Supplier\b[^\n]*\n(?:[ \t]*\n)*([^\n]+)"
    )
    if supplier:
        supplier = re.split(
            r"\b(?:Invoice number|Invoice date|Due date|Currency):",
            supplier,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip() or None

    subtotal = amount("Subtotal")
    vat = amount(r"VAT[ \t]*\(\d+(?:\.\d+)?%\)")
    total = amount("Total due")

    fields = {
        "supplier": supplier,
        "invoice_number": find(
            r"\bInvoice number:[ \t]*([A-Z0-9][A-Z0-9._/-]*)"
        ),
        "invoice_date": iso_date("Invoice date"),
        "due_date": iso_date("Due date"),
        "currency": find(r"\bCurrency:[ \t]*([A-Z]{3})\b"),
        "subtotal": str(subtotal) if subtotal is not None else None,
        "vat": str(vat) if vat is not None else None,
        "total": str(total) if total is not None else None,
    }

    missing = [name for name, value in fields.items() if value is None]

    totals_match = None
    if all(value is not None for value in (subtotal, vat, total)):
        totals_match = subtotal + vat == total

    return {
        "method": "labelled_text_rules_v2",
        "fields": fields,
        "validation": {
            "missing_fields": missing,
            "subtotal_plus_vat_matches_total": totals_match,
            "human_review_required": True,
        },
    }
