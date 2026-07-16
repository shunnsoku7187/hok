import unittest
from datetime import date
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
