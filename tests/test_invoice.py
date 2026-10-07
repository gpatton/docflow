import pytest

from app.invoice import extract_invoice


PDF_TEXT = """Supplier
Example Office Supplies Ltd
Invoice number: INV-2026-001
Invoice date: 2026-10-07
Due date: 2026-10-21
Currency: EUR
Subtotal:
EUR 200.00
VAT (23%):
EUR 46.00
Total due:
EUR 246.00
"""

OCR_TEXT = """Supplier Invoice number: INV-2026-001

Example Office Supplies Ltd Invoice date: 2026-10-07
10 Example Street Due date: 2026-10-21
Example Town, Ireland Currency: EUR
Subtotal: EUR 200.00
VAT (23%): EUR 46.00
Total due: EUR 246.00
"""


@pytest.mark.parametrize("text", [PDF_TEXT, OCR_TEXT])
def test_extracts_expected_invoice(text):
    invoice = extract_invoice(text)

    assert invoice["fields"] == {
        "supplier": "Example Office Supplies Ltd",
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-10-07",
        "due_date": "2026-10-21",
        "currency": "EUR",
        "subtotal": "200.00",
        "vat": "46.00",
        "total": "246.00",
    }
    assert invoice["validation"]["missing_fields"] == []
    assert invoice["validation"]["subtotal_plus_vat_matches_total"] is True
    assert invoice["validation"]["human_review_required"] is True


def test_missing_amount_is_not_invented():
    invoice = extract_invoice("Invoice number: TEST-001")

    assert invoice["fields"]["total"] is None
    assert "total" in invoice["validation"]["missing_fields"]
    assert invoice["validation"]["subtotal_plus_vat_matches_total"] is None


def test_incorrect_total_is_flagged():
    invoice = extract_invoice(PDF_TEXT.replace("246.00", "250.00"))

    assert invoice["validation"]["subtotal_plus_vat_matches_total"] is False


def test_invalid_date_is_flagged():
    invoice = extract_invoice(
        PDF_TEXT.replace("2026-10-07", "2026-02-30")
    )

    assert invoice["fields"]["invoice_date"] is None
    assert "invoice_date" in invoice["validation"]["missing_fields"]


def test_decimal_arithmetic_is_exact():
    invoice = extract_invoice(
        "Subtotal: EUR 0.10\n"
        "VAT (20%): EUR 0.02\n"
        "Total due: EUR 0.12"
    )

    assert invoice["validation"]["subtotal_plus_vat_matches_total"] is True
