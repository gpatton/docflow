from app.validation import validate_approval


def valid_fields():
    return {
        "supplier": "Example Office Supplies Ltd",
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-10-07",
        "due_date": "2026-10-21",
        "currency": "EUR",
        "subtotal": "200.00",
        "vat": "46.00",
        "total": "246.00",
    }


def test_valid_invoice():
    assert validate_approval(valid_fields()) == []


def test_missing_supplier():
    fields = valid_fields()
    fields["supplier"] = " "
    assert "supplier is required." in validate_approval(fields)


def test_incorrect_total():
    fields = valid_fields()
    fields["total"] = "250.00"
    assert "Subtotal plus VAT must equal total." in validate_approval(fields)


def test_invalid_date():
    fields = valid_fields()
    fields["invoice_date"] = "2026-02-30"
    assert any("valid YYYY-MM-DD" in error for error in validate_approval(fields))


def test_due_date_before_invoice_date():
    fields = valid_fields()
    fields["due_date"] = "2026-10-01"
    assert "Due date cannot be before invoice date." in validate_approval(fields)


def test_unsupported_currency():
    fields = valid_fields()
    fields["currency"] = "USD"
    assert "Only EUR invoices are supported." in validate_approval(fields)


def test_invalid_amounts():
    for value in ("-1.00", "NaN", "Infinity", "1.234", "1e2"):
        fields = valid_fields()
        fields["total"] = value
        assert any("total must be" in error for error in validate_approval(fields))


def test_decimal_arithmetic():
    fields = valid_fields()
    fields.update(subtotal="0.10", vat="0.02", total="0.12")
    assert validate_approval(fields) == []
