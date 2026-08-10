import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Database import validate_database_environment
from DB_IO import list_columns, list_tables


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

		# Iterate through the tables and print the first 10 columns for each table
		# then look for matching columns in main and orders reports
		for table in tables:
			table_name = table["name"]
			columns = list_columns(table_name, schema="dbo")

			self.assertIsInstance(columns, list)
			self.assertGreater(len(columns), 0, f"No columns found for table {table_name}.")

			print(f"\nColumns for dbo.{table_name}:")
			for column in columns[:10]:
				print(
					f"- {column['ordinal']}: {column['name']} "
					f"({column['type']}, nullable={column['nullable']})"
				)

	def test_list_oe_header_and_detail_columns(self):
		"""
		Integration test: print all column names of dbo.OEHEader and dbo.OEDetail.

		Skipped when DB_* environment variables are not configured.
		"""
		try:
			validate_database_environment()
		except RuntimeError as exc:
			self.skipTest(f"Database environment not configured: {exc}")

		for table_name in ["OEHEader", "OEDetail"]:
			columns = list_columns(table_name, schema="dbo")

			self.assertGreater(len(columns), 0, f"No columns found for dbo.{table_name}.")

			print(f"\nColumns for dbo.{table_name} ({len(columns)} total):")
			for column in columns:
				print(
					f"- {column['ordinal']}: {column['name']} "
					f"({column['type']}, nullable={column['nullable']})"
				)

if __name__ == "__main__":
	unittest.main()

