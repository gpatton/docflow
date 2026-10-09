"""Record invoice changes within the caller's transaction."""

from psycopg.types.json import Jsonb


def field_changes(before: dict, after: dict) -> dict:
    """Return only values that changed."""
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


def record_history(connection, invoice_id, action, changes):
    connection.execute(
        """
        INSERT INTO invoice_history (invoice_id, action, changes)
        VALUES (%s, %s, %s)
        """,
        (invoice_id, action, Jsonb(changes)),
    )
