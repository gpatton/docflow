"""Save and retrieve invoice review drafts."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from app.database import get_connection

router = APIRouter(prefix="/invoices", tags=["Invoices"])


class InvoiceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier: str | None = Field(default=None, max_length=500)
    invoice_number: str | None = Field(default=None, max_length=200)
    invoice_date: str | None = Field(default=None, max_length=30)
    due_date: str | None = Field(default=None, max_length=30)
    currency: str | None = Field(default=None, max_length=10)
    subtotal: str | None = Field(default=None, max_length=50)
    vat: str | None = Field(default=None, max_length=50)
    total: str | None = Field(default=None, max_length=50)


class InvoiceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    fields: InvoiceFields


@router.post("", status_code=201)
def create_invoice(draft: InvoiceDraft):
    with get_connection() as connection:
        return connection.execute(
            """
            INSERT INTO invoices (id, filename, fields)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (
                uuid4(),
                draft.filename,
                Jsonb(draft.fields.model_dump()),
            ),
        ).fetchone()


@router.get("")
def list_invoices():
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM invoices
            ORDER BY created_at DESC, id DESC
            LIMIT 100
            """
        ).fetchall()


@router.get("/{invoice_id}")
def get_invoice(invoice_id: UUID):
    with get_connection() as connection:
        invoice = connection.execute(
            "SELECT * FROM invoices WHERE id = %s",
            (invoice_id,),
        ).fetchone()

    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    return invoice


@router.put("/{invoice_id}")
def update_invoice(invoice_id: UUID, draft: InvoiceDraft):
    with get_connection() as connection:
        invoice = connection.execute(
            "SELECT status FROM invoices WHERE id = %s FOR UPDATE",
            (invoice_id,),
        ).fetchone()

        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        if invoice["status"] != "draft":
            raise HTTPException(
                status_code=409,
                detail="Only draft invoices can be edited.",
            )

        return connection.execute(
            """
            UPDATE invoices
            SET filename = %s, fields = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                draft.filename,
                Jsonb(draft.fields.model_dump()),
                invoice_id,
            ),
        ).fetchone()


@router.post("/{invoice_id}/approve")
def approve_invoice(invoice_id: UUID):
    from app.validation import validate_approval

    with get_connection() as connection:
        invoice = connection.execute(
            "SELECT * FROM invoices WHERE id = %s FOR UPDATE",
            (invoice_id,),
        ).fetchone()

        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        if invoice["status"] != "draft":
            raise HTTPException(
                status_code=409,
                detail="Invoice is already approved.",
            )

        errors = validate_approval(invoice["fields"])
        if errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invoice cannot be approved.",
                    "errors": errors,
                },
            )

        return connection.execute(
            """
            UPDATE invoices
            SET status = 'approved',
                approved_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (invoice_id,),
        ).fetchone()
