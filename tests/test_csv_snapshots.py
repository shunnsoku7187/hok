import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from hok_tools.csv_tool import find_previous_snapshot


class SnapshotComparisonTests(unittest.TestCase):
    def test_missing_week_uses_latest_saved_legacy_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for filename in ("2026814_heroes.csv", "20260821_heroes.csv", "20261009_heroes.csv"):
                (Path(temp_dir) / filename).touch()
            with patch("hok_tools.csv_tool.BASE_PATH", temp_dir):
                path, previous_date = find_previous_snapshot(date(2026, 10, 9))
            self.assertEqual(previous_date, date(2026, 8, 21))
            self.assertEqual(Path(path).name, "20260821_heroes.csv")

    def test_normal_week_uses_previous_week(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for filename in ("20260814_heroes.csv", "20260821_heroes.csv"):
                (Path(temp_dir) / filename).touch()
            with patch("hok_tools.csv_tool.BASE_PATH", temp_dir):
                _, previous_date = find_previous_snapshot(date(2026, 8, 21))
            self.assertEqual(previous_date, date(2026, 8, 14))

    def test_no_previous_snapshot_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("hok_tools.csv_tool.BASE_PATH", temp_dir):
                with self.assertRaisesRegex(FileNotFoundError, "No snapshot before"):
                    find_previous_snapshot(date(2026, 10, 9))
