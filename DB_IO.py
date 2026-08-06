"""Database input/output functions."""

from Database import connect


def list_tables(schema="dbo", include_views=False):
    """
    Return table metadata from INFORMATION_SCHEMA for the target schema.

    Args:
        schema: SQL schema name (defaults to dbo).
        include_views: If True, includes views in addition to base tables.

    Returns:
        List of dictionaries with keys: schema, name, type.
    """
    table_types = ["BASE TABLE"]
    if include_views:
        table_types.append("VIEW")

    placeholders = ", ".join("?" for _ in table_types)
    sql = f"""
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_TYPE IN ({placeholders})
        ORDER BY TABLE_NAME;
    """

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, schema, *table_types)
        rows = cursor.fetchall()
    finally:
        connection.close()

    return [
        {
            "schema": row[0],
            "name": row[1],
            "type": row[2],
        }
        for row in rows
    ]


def print_tables(schema="dbo", include_views=False):
    """Print tables (and optionally views) in a readable list format."""
    entries = list_tables(schema=schema, include_views=include_views)

    if not entries:
        print(f"No objects found in schema '{schema}'.")
        return

    print(f"Objects in schema '{schema}':")
    for entry in entries:
        print(f"- {entry['name']} ({entry['type']})")


def get_connection():
    """Return an active SQL Server connection from the shared DB helper."""
    return connect()