import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from hok_tools import csv_tool
from hok_tools.csv_tool import hero_page_slug
from hok_tools.hero_history_tool import resolve_snapshot_dates


class HeroHistoryTests(unittest.TestCase):
    def test_resolves_legacy_ambiguous_dates_using_adjacent_weeks(self):
        paths = [
            Path("csv/20251031_heroes.csv"),
            Path("csv/2025117_heroes.csv"),
            Path("csv/20251114_heroes.csv"),
            Path("csv/2025124_heroes.csv"),
        ]

        resolved = resolve_snapshot_dates(paths)

        self.assertEqual(resolved[Path("csv/2025117_heroes.csv")], date(2025, 11, 7))

    def test_hero_page_slug_handles_asset_name_punctuation(self):
        self.assertEqual(hero_page_slug("ao'yin"), "ao-yin")
        self.assertEqual(hero_page_slug("gan&mo"), "gan-mo")
        self.assertEqual(hero_page_slug("flowborn (mage)"), "flowborn-mage")

    def test_save_reuses_legacy_snapshot_for_the_same_date(self):
        from tempfile import TemporaryDirectory

        heroes = [{
            "name": "カルラ",
            "win_rate": "51.16%",
            "pick_rate": "0.80%",
            "ban_rate": "0.03%",
            "meta_score": 52.36,
            "tier": "B",
        }]

        with TemporaryDirectory() as directory:
            base_path = f"{directory}/"
            legacy_path = Path(directory) / "2026710_heroes.csv"
            legacy_path.write_text("old", encoding="utf-8")
            with patch.object(csv_tool, "BASE_PATH", base_path), patch.object(
                csv_tool, "get_period", return_value=(2026, 7, 10)
            ):
                csv_tool.save_heroes_to_csv(heroes)

            self.assertTrue(legacy_path.read_text(encoding="utf-8").startswith("name,"))
            self.assertFalse((Path(directory) / "20260710_heroes.csv").exists())


if __name__ == "__main__":
    unittest.main()
