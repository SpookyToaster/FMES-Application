import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Database import validate_database_environment
from DB_IO import list_tables


class DBIOIntegrationTests(unittest.TestCase):
	def test_list_tables_in_database(self):
		"""
		Integration test: connect to SQL Server and print discovered table names.

		This test is skipped when DB_* environment variables are not configured
		for the current shell/session.
		"""
		try:
			validate_database_environment()
		except RuntimeError as exc:
			self.skipTest(f"Database environment not configured: {exc}")

		tables = list_tables(schema="dbo", include_views=False)

		self.assertIsInstance(tables, list)
		self.assertGreater(len(tables), 0, "No base tables found in dbo schema.")

		print("\nDiscovered dbo base tables:")
		for table in tables:
			print(f"- {table['schema']}.{table['name']} ({table['type']})")


if __name__ == "__main__":
	unittest.main()

