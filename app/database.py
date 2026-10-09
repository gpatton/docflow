"""PostgreSQL connections and initial schema for DocFlow."""

import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def get_connection():
    """Open a database connection with dictionary results."""
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
        connect_timeout=5,
    )


def initialize_database():
    """Create the invoice table if it does not exist."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id UUID PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'approved')),
                fields JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ
            )
            """
        )


def initialize_history():
    """Create storage for invoice review history."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_history (
                id BIGSERIAL PRIMARY KEY,
                invoice_id UUID NOT NULL REFERENCES invoices(id),
                action TEXT NOT NULL
                    CHECK (action IN ('created', 'updated', 'approved')),
                changes JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS invoice_history_invoice_idx
            ON invoice_history (invoice_id, id)
            """
        )
