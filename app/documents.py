"""Store and retrieve original invoice PDFs."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response

from app.database import get_connection

router = APIRouter(prefix="/documents", tags=["Documents"])


def initialize_documents():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY,
                filename TEXT NOT NULL,
                content BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (octet_length(content) <= 10485760)
            )
            """
        )


def save_document(filename: str, content: bytes) -> UUID:
    document_id = uuid4()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO documents (id, filename, content)
            VALUES (%s, %s, %s)
            """,
            (document_id, filename, content),
        )
    return document_id


@router.get("/{document_id}/pdf")
def get_document_pdf(document_id: UUID):
    with get_connection() as connection:
        document = connection.execute(
            "SELECT content FROM documents WHERE id = %s",
            (document_id,),
        ).fetchone()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return Response(
        content=bytes(document["content"]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="invoice.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def initialize_document_links():
    """Allow invoices to reference their original PDF."""
    with get_connection() as connection:
        connection.execute(
            """
            ALTER TABLE invoices
            ADD COLUMN IF NOT EXISTS document_id UUID
                REFERENCES documents(id)
            """
        )
