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