import csv
import json
import unittest
from datetime import date
from pathlib import Path

from get_adjustments import merge_adjustments
from hok_tools.adjustment_tool import (
    adjustment_direction,
    format_adjustment_date,
    has_adjustment_between,
    html_to_text,
    load_adjustment_data,
    prepare_hero_adjustments,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "hero_adjustments.json"


class AdjustmentTests(unittest.TestCase):
    def test_supports_both_hokcamp_date_formats(self):
        self.assertEqual(format_adjustment_date("2026/07/16"), "2026/07/16")
        self.assertEqual(format_adjustment_date("20251030"), "2025/10/30")

    def test_converts_adjustment_html_to_plain_text(self):
        self.assertEqual(
            html_to_text("調整前：100<br>調整後：120"),
            "調整前：100\n調整後：120",
        )

    def test_normalizes_adjustment_direction_labels(self):
        self.assertEqual(adjustment_direction("数値強化"), "上方修正")
        self.assertEqual(adjustment_direction("制度レベルアップ"), "上方修正")
        self.assertEqual(adjustment_direction("数値弱体化"), "下方修正")
        self.assertEqual(adjustment_direction("制度調整"), "調整")

    def test_detects_adjustment_in_weekly_window(self):
        hero = {"adjustments": [{"versionName": "2026/07/16"}]}
        self.assertTrue(
            has_adjustment_between(hero, date(2026, 7, 10), date(2026, 7, 17))
        )
        self.assertFalse(
            has_adjustment_between(hero, date(2026, 7, 17), date(2026, 7, 24))
        )

    def test_merge_keeps_cached_history_and_prefers_current_record(self):
        previous = [
            {
                "versionName": "2026/07/02",
                "adjustContent": {"shortDesc": "調整", "desc": "old"},
            },
            {
                "versionName": "2026/06/17",
                "adjustContent": {"shortDesc": "過去調整"},
            },
        ]
        current = [
            {
                "versionName": "2026/07/02",
                "adjustContent": {"shortDesc": "調整", "desc": "new"},
            }
        ]

        merged = merge_adjustments(current, previous)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["adjustContent"]["desc"], "new")
        self.assertEqual(merged[1]["versionName"], "2026/06/17")

    def test_cached_data_covers_every_local_hero(self):
        adjustments = load_adjustment_data(DATA_FILE)
        with (ROOT / "names.csv").open("r", encoding="utf-8", newline="") as file:
            local_names = {row["Japanese"] for row in csv.DictReader(file)}

        self.assertEqual(set(adjustments), local_names)
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.assertEqual(payload["hero_count"], len(local_names))
        self.assertEqual(
            payload["adjustment_count"],
            sum(len(hero["adjustments"]) for hero in payload["heroes"]),
        )

    def test_prepares_detailed_adjustment_for_hero_page(self):
        adjustments = load_adjustment_data(DATA_FILE)
        prepared = prepare_hero_adjustments(adjustments["チーシャ"])

        self.assertTrue(prepared)
        self.assertEqual(prepared[0]["date_label"], "2026/07/16")
        self.assertEqual(prepared[0]["tag_text"], "数値強化")
        self.assertEqual(prepared[0]["direction_label"], "上方修正")
        self.assertIn("調整前", prepared[0]["attributes"][0]["description"])
        self.assertIn("調整後", prepared[0]["attributes"][0]["description"])


if __name__ == "__main__":
    unittest.main()
