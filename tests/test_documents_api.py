"""API tests using an isolated, temporary PostgreSQL database."""

import os
from io import BytesIO
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pypdf import PdfWriter

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Database integration tests require RUN_DB_TESTS=1",
)


@pytest.fixture(scope="module")
def client():
    load_dotenv(".env")
    original_url = os.environ["DATABASE_URL"]
    parameters = conninfo_to_dict(original_url)
    parameters["dbname"] = "postgres"
    admin_url = make_conninfo(**parameters)
    database_name = f"docflow_test_{uuid4().hex}"
    created = False

    try:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(database_name)
                )
            )
        created = True

        parameters["dbname"] = database_name
        os.environ["DATABASE_URL"] = make_conninfo(**parameters)

        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
    finally:
        os.environ["DATABASE_URL"] = original_url
        if created:
            with psycopg.connect(admin_url, autocommit=True) as connection:
                connection.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )


def sample_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client, monkeypatch):
    # Exercise storage without requiring local OCR binaries.
    monkeypatch.setattr(
        "app.main.ocr_page",
        lambda data, number: "Invoice number: STORAGE-TEST",
    )
    content = sample_pdf()
    response = client.post(
        "/documents/extract",
        files={"file": ("test.pdf", content, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return content, response.json()["document_id"]


def draft(document_id=None):
    return {
        "filename": "test.pdf",
        "document_id": document_id,
        "fields": {
            "supplier": "Example Supplier",
            "invoice_number": "STORAGE-TEST",
            "invoice_date": "2026-10-07",
            "due_date": "2026-10-21",
            "currency": "EUR",
            "subtotal": "200.00",
            "vat": "46.00",
            "total": "246.00",
        },
    }


def test_pdf_round_trip_and_invoice_link(client, monkeypatch):
    content, document_id = upload(client, monkeypatch)

    pdf = client.get(f"/documents/{document_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content == content
    assert pdf.headers["content-type"] == "application/pdf"

    response = client.post("/invoices", json=draft(document_id))
    assert response.status_code == 201, response.text
    invoice_id = response.json()["id"]

    reopened = client.get(f"/invoices/{invoice_id}").json()
    assert reopened["document_id"] == document_id
    assert reopened["fields"]["total"] == "246.00"

    approval = client.post(f"/invoices/{invoice_id}/approve")
    assert approval.status_code == 200, approval.text
    assert approval.json()["document_id"] == document_id

    history = client.get(f"/invoices/{invoice_id}/history").json()
    assert history[0]["changes"]["document_id"]["after"] == document_id


def test_unknown_document_returns_404(client):
    response = client.get(f"/documents/{uuid4()}/pdf")
    assert response.status_code == 404


def test_unknown_document_link_rejected(client):
    response = client.post("/invoices", json=draft(str(uuid4())))
    assert response.status_code == 422


def test_original_document_cannot_be_replaced(client, monkeypatch):
    _, first_id = upload(client, monkeypatch)
    _, second_id = upload(client, monkeypatch)

    response = client.post("/invoices", json=draft(first_id))
    assert response.status_code == 201
    invoice_id = response.json()["id"]

    replacement = client.put(
        f"/invoices/{invoice_id}", json=draft(second_id)
    )
    assert replacement.status_code == 409

    reopened = client.get(f"/invoices/{invoice_id}").json()
    assert reopened["document_id"] == first_id

    history = client.get(f"/invoices/{invoice_id}/history").json()
    assert len(history) == 1


def test_invoice_without_document_still_supported(client):
    response = client.post("/invoices", json=draft())
    assert response.status_code == 201
    assert response.json()["document_id"] is None
