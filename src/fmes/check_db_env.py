import os
import sys

from Database import validate_database_environment


def main():
    try:
        status = validate_database_environment()
    except RuntimeError as exc:
        print(f"Database environment check failed: {exc}")
        print("Tip: copy .env.example values into your local environment before running.")
        return 1

    if status["mode"] == "connection_string":
        print("Database environment check passed using DB_CONNECTION_STRING.")
    else:
        print("Database environment check passed using separate DB_* variables.")

    print(f"Configured driver: {os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())