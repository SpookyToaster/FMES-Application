import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Database import build_connection_string, validate_database_environment


class DatabaseConfigTests(unittest.TestCase):
    def test_validate_uses_full_connection_string(self):
        with patch.dict("os.environ", {"DB_CONNECTION_STRING": "SERVER=test;"}, clear=True):
            status = validate_database_environment()

        self.assertEqual(status["mode"], "connection_string")

    def test_validate_requires_all_component_vars(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as context:
                validate_database_environment()

        message = str(context.exception)
        self.assertIn("DB_SERVER", message)
        self.assertIn("DB_NAME", message)
        self.assertIn("DB_USER", message)
        self.assertIn("DB_PASSWORD", message)

    def test_build_connection_string_from_components(self):
        env = {
            "DB_DRIVER": "ODBC Driver 17 for SQL Server",
            "DB_SERVER": "my_server",
            "DB_NAME": "my_db",
            "DB_USER": "my_user",
            "DB_PASSWORD": "my_password",
        }

        with patch.dict("os.environ", env, clear=True):
            connection_string = build_connection_string()

        self.assertIn("DRIVER={ODBC Driver 17 for SQL Server};", connection_string)
        self.assertIn("SERVER=my_server;", connection_string)
        self.assertIn("DATABASE=my_db;", connection_string)
        self.assertIn("UID=my_user;", connection_string)
        self.assertIn("PWD=my_password;", connection_string)


if __name__ == "__main__":
    unittest.main()