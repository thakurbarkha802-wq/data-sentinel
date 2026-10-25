"""Unit tests for DataSentinel Safe CSV Loader
"""

import tempfile
import unittest
from pathlib import Path

from core.loader import DataSentinelError, load_csv


class TestCSVLoader(unittest.TestCase):
    """Tests CSV loading, encoding handling, and structural edge cases."""

    def test_missing_file_raises_datasentinel_error(self):
        """Verifies that non-existent files raise user-friendly DataSentinelError."""
        fake_path = Path("non_existent_dataset_12345.csv")
        with self.assertRaises(DataSentinelError) as ctx:
            load_csv(fake_path)
        self.assertIn("does not exist", str(ctx.exception))

    def test_empty_file_zero_bytes(self):
        """Verifies that 0-byte files return is_empty=True without crashing."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as tmp:
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertTrue(result.is_empty)
            self.assertEqual(len(result.headers), 0)
            self.assertEqual(len(result.rows), 0)
            self.assertTrue(any("empty" in i.message.lower() for i in result.issues))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_empty_file_whitespace_only(self):
        """Verifies that whitespace-only files are treated as empty."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("   \n\n   \t\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertTrue(result.is_empty)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_headers_only_zero_data_rows(self):
        """Verifies CSV with headers but no data rows."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("name,age,city\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertTrue(result.is_empty)
            self.assertEqual(result.headers, ["name", "age", "city"])
            self.assertEqual(len(result.rows), 0)
            self.assertTrue(any("zero data rows" in i.message.lower() for i in result.issues))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_utf8_bom_and_non_ascii_characters(self):
        """Verifies that UTF-8 with BOM (\ufeff) and international characters parse properly."""
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".csv") as tmp:
            # Write UTF-8 BOM followed by international text
            content = "name,city,country\nÁlvaro,São Paulo,Brasil\n田中,東京,日本\nBarkha,Mathura,भारत\n"
            tmp.write(content.encode("utf-8-sig"))
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertFalse(result.is_empty)
            # Verify BOM did not attach to the first header
            self.assertEqual(result.headers[0], "name")
            self.assertEqual(len(result.rows), 3)
            # Verify non-ASCII characters preserved
            self.assertEqual(result.rows[0][1][0], "Álvaro")
            self.assertEqual(result.rows[1][1][0], "田中")
            self.assertEqual(result.rows[2][1][0], "Barkha")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_duplicate_column_headers(self):
        """Verifies that duplicate column names trigger a schema warning."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("id,name,email,name\n1,Alice,alice@example.com,Alice2\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            warnings = [i for i in result.issues if i.issue_type == "schema_warning" and "duplicate" in i.message.lower()]
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0].column, "name")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_malformed_row_normalized(self):
        """Verifies that rows with missing or extra columns are normalized without crashing."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            # Header has 3 columns, line 2 has 2, line 3 has 4
            tmp.write("col_a,col_b,col_c\nval1,val2\nval3,val4,val5,val6\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            malformed_issues = [i for i in result.issues if i.issue_type == "malformed_row"]
            self.assertEqual(len(malformed_issues), 2)
            # Line numbers should be 2 and 3
            self.assertEqual(malformed_issues[0].row_number, 2)
            self.assertEqual(malformed_issues[1].row_number, 3)
            # Rows must be normalized to len(headers)
            self.assertEqual(len(result.rows[0][1]), 3)
            self.assertEqual(result.rows[0][1][2], "")  # Padded with empty string
            self.assertEqual(len(result.rows[1][1]), 3)  # Truncated
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_duplicate_headers_disambiguation(self):
        """Verifies duplicate and empty column headers are disambiguated with stable names."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("id,name,email,name,\n1,Alice,alice@example.com,Alice2,extra\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertEqual(result.headers, ["id", "name", "email", "name_2", "Unnamed_5"])
            warnings = [i for i in result.issues if i.issue_type == "schema_warning"]
            self.assertTrue(any("duplicate" in i.message.lower() and i.column == "name" for i in warnings))
            self.assertTrue(any("empty" in i.message.lower() and i.column == "Unnamed_5" for i in warnings))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_blank_lines_skipped_without_synthesizing_records(self):
        """Verifies blank physical lines in CSV do not synthesize fake rows or spurious malformed warnings."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("col_a,col_b\nval1,val2\n\nval3,val4\n   \n\n")
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            # Only the 2 non-blank data rows should be parsed
            self.assertEqual(len(result.rows), 2)
            self.assertEqual(result.rows[0][1], ["val1", "val2"])
            self.assertEqual(result.rows[1][1], ["val3", "val4"])
            # Physical line numbers: header is 1, val1 is 2, blank is 3, val3 is 4
            self.assertEqual(result.rows[0][0], 2)
            self.assertEqual(result.rows[1][0], 4)
            # Zero malformed row issues
            malformed = [i for i in result.issues if i.issue_type == "malformed_row"]
            self.assertEqual(len(malformed), 0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_quoted_multiline_field_physical_line_numbers(self):
        """Verifies accurate physical line numbering when records contain quoted newlines."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write('col_a,col_b\nval1,val2\n"line3\nline4",val3\nval5,val6\n')
            tmp_path = Path(tmp.name)
        try:
            result = load_csv(tmp_path)
            self.assertEqual(len(result.rows), 3)
            # Row 1 is on physical line 2
            self.assertEqual(result.rows[0][0], 2)
            # Row 2 (multiline) starts on physical line 3
            self.assertEqual(result.rows[1][0], 3)
            # Row 3 is on physical line 5
            self.assertEqual(result.rows[2][0], 5)
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
