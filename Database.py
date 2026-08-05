"""
Database connectivity helpers.

Builds an ODBC connection string from environment variables and returns a
pyodbc connection.  Credentials are never hard-coded; they must be supplied
through the environment before calling connect().

Required environment variables (when DB_CONNECTION_STRING is not set):
    DB_SERVER   – SQL Server hostname or IP
    DB_NAME     – Target database name
    DB_USER     – SQL login username
    DB_PASSWORD – SQL login password

Optional:
    DB_DRIVER           – ODBC driver name (default: 'ODBC Driver 17 for SQL Server')
    DB_CONNECTION_STRING – Full ODBC connection string; overrides all component variables
"""

import os


REQUIRED_DB_ENV_VARS = (
    "DB_SERVER",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


def _missing_required_env_vars():
    return [name for name in REQUIRED_DB_ENV_VARS if not os.getenv(name)]


def validate_database_environment():
    """
    Confirm that enough environment variables are set to build a connection string.

    Accepts either a single DB_CONNECTION_STRING or all four component variables.

    Returns:
        dict with 'mode' ('connection_string' or 'components') and 'missing' (always []).

    Raises:
        RuntimeError: If required component variables are absent and no full string is set.
    """
    full_connection = os.getenv("DB_CONNECTION_STRING")
    if full_connection and full_connection.strip():
        return {
            "mode": "connection_string",
            "missing": [],
        }

    missing = _missing_required_env_vars()
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "Database configuration is incomplete. "
            "Set DB_CONNECTION_STRING or provide all required variables: "
            f"{missing_list}."
        )

    return {
        "mode": "components",
        "missing": [],
    }


def build_connection_string():
    """
    Build and return the ODBC connection string from environment variables.

    If DB_CONNECTION_STRING is set it is returned unchanged.  Otherwise the
    string is assembled from DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, and the
    optional DB_DRIVER (defaulting to ODBC Driver 17 for SQL Server).
    """
    status = validate_database_environment()

    if status["mode"] == "connection_string":
        full_connection = os.getenv("DB_CONNECTION_STRING", "")
        return full_connection

    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", "")
    database = os.getenv("DB_NAME", "")
    username = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
    )


def connect():
    """
    Open and return an active pyodbc database connection.

    Raises:
        RuntimeError: If pyodbc is not installed or the connection attempt fails.
    """
    try:
        import pyodbc
    except Exception as exc:
        raise RuntimeError(
            "pyodbc is not available. Install it in your active environment before "
            "attempting a database connection."
        ) from exc

    try:
        return pyodbc.connect(build_connection_string())
    except Exception as exc:
        raise RuntimeError(
            "Database connection failed. Verify DB settings, credentials, and ODBC "
            "driver availability."
        ) from exc