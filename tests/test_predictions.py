import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from hok_tools.csv_tool import hero_page_slug
from hok_tools.hero_history_tool import load_hero_histories
from hok_tools.prediction_tool import (
    build_prediction_evidence,
    generate_prediction_page,
    load_prediction_round,
    load_prediction_rounds,
)


class PredictionPageTests(unittest.TestCase):
    def test_builds_weekly_evidence_for_prediction_cards(self):
        history = []
        scores = [50, 51, 50, 53, 54]
        for index, score in enumerate(scores, 1):
            history.append({
                "date_label": f"2026/01/{index:02d}",
                "score": score,
                "score_label": f"{score:.2f}",
                "tier": "B",
                "rank": 10,
                "hero_count": 100,
            })

        evidence = build_prediction_evidence("テスト", history)

        self.assertEqual("+4.00", evidence["four_week"]["label"])
        self.assertEqual("--", evidence["thirteen_week"]["label"])
        self.assertEqual(3, evidence["up_count"])
        self.assertEqual(1, evidence["down_count"])
        self.assertEqual("+1.00", evidence["average_change_label"])
        self.assertEqual("1.41", evidence["volatility_label"])

    def test_weekly_direction_uses_practical_flat_threshold(self):
        history = []
        scores = [50.00, 50.19, 50.39, 50.20, 50.00]
        for index, score in enumerate(scores, 1):
            history.append({
                "date_label": f"2026/01/{index:02d}",
                "score": score,
                "score_label": f"{score:.2f}",
                "tier": "B",
                "rank": 10,
                "hero_count": 100,
            })

        evidence = build_prediction_evidence("Test", history)

        self.assertEqual(1, evidence["up_count"])
        self.assertEqual(1, evidence["down_count"])
        self.assertEqual(2, evidence["flat_count"])
        self.assertEqual("0.20", evidence["flat_threshold_label"])

    def test_prediction_round_has_unique_valid_markets(self):
        prediction_round = load_prediction_round()
        predictions = prediction_round["predictions"]

        self.assertEqual(10, len(predictions))
        self.assertEqual(len(predictions), len({item["id"] for item in predictions}))
        self.assertEqual(
            ["鉄板", "大本命", "本命", "対抗", "対抗", "単穴", "穴", "穴", "大穴", "大穴"],
            [item["rank"] for item in predictions],
        )
        self.assertIsInstance(prediction_round["result"]["ready"], bool)

    def test_generated_page_contains_predictions_and_round_config(self):
        expected_latest_date = load_hero_histories()["李信"][-1]["date_label"]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            generate_prediction_page(output_dir=output_dir)

            html = (output_dir / "index.html").read_text(encoding="utf-8")
            deployed_round = json.loads((output_dir / "round.json").read_text(encoding="utf-8"))
            hero_assets = json.loads((output_dir / "hero_assets.json").read_text(encoding="utf-8"))
            archived_round_exists = (output_dir / "rounds" / "balance-2026-07-30.json").exists()

        self.assertIn("次回バランス調整予想", html)
        self.assertIn("data-prediction-id=\"lixin-nerf\"", html)
        self.assertIn("最新判断材料", html)
        self.assertIn("詳しい判断材料", html)
        self.assertIn("直近13週", html)
        self.assertIn("連動傾向", html)
        self.assertIn("../hok_pics/lixin.png", html)
        self.assertIn("id=\"comment-form\"", html)
        self.assertIn("value=\"匿名希望\"", html)
        self.assertIn("予想される修正", html)
        self.assertIn('value="妲己" data-asset="daji"', html)
        self.assertIn('href="prediction.css?v=', html)
        self.assertIn('src="comments.js?v=', html)
        self.assertEqual("balance-2026-07-30", deployed_round["round_id"])
        self.assertEqual("7/29 23:59", deployed_round["closes_label"])
        self.assertEqual("daji", hero_assets["妲己"])
        self.assertIn("evidence", deployed_round["predictions"][0])
        self.assertEqual(
            expected_latest_date,
            deployed_round["predictions"][0]["evidence"]["latest_date_label"],
        )
        self.assertTrue(archived_round_exists)

    def test_comment_hero_links_resolve_for_every_asset(self):
        comments_js = Path("list_html/predictions/comments.js").read_text(encoding="utf-8")
        self.assertIn("function heroPageUrl(asset)", comments_js)
        self.assertIn('heroIdentity.className = "comment-hero-link"', comments_js)

        with Path("names.csv").open(newline="", encoding="utf-8") as file:
            assets = [row["English"] for row in csv.DictReader(file)]

        for asset in assets:
            page = Path("list_html/heroes") / f"{hero_page_slug(asset)}.html"
            self.assertTrue(page.exists(), f"Missing comment hero link target: {page}")

    def test_completed_round_is_kept_as_result_history(self):
        with Path("data/prediction_round.json").open(encoding="utf-8") as file:
            current = json.load(file)["rounds"][0]
        previous = copy.deepcopy(current)
        previous["round_id"] = "balance-2026-07-01"
        previous["target_label"] = "2026/07/01"
        previous["published_at"] = "2026-06-20T00:00:00+09:00"
        previous["closes_at"] = "2026-06-30T23:59:59+09:00"
        previous["result_after"] = "2026/07/01"
        current = copy.deepcopy(current)
        current["round_id"] = "balance-2099-01-01"
        current["published_at"] = "2098-12-20T00:00:00+09:00"
        current["closes_at"] = "2098-12-31T23:59:59+09:00"
        current["result_after"] = "2099/01/01"
        manifest = {"current_round_id": current["round_id"], "rounds": [previous, current]}
        adjustments = {
            "heroes": [
                {
                    "hero_id": 163,
                    "hero_name": "李信",
                    "adjustments": [
                        {
                            "versionName": "2026/07/02",
                            "adjustContent": {"contentTag": {"text": "数値弱体化"}},
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "rounds.json"
            adjustment_path = temp_path / "adjustments.json"
            output_dir = temp_path / "output"
            config_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            adjustment_path.write_text(json.dumps(adjustments, ensure_ascii=False), encoding="utf-8")

            loaded_current, previous_rounds, _ = load_prediction_rounds(config_path, adjustment_path)
            generate_prediction_page(
                config_path=config_path,
                adjustment_path=adjustment_path,
                output_dir=output_dir,
            )
            html = (output_dir / "index.html").read_text(encoding="utf-8")

        self.assertEqual("balance-2099-01-01", loaded_current["round_id"])
        self.assertEqual(1, len(previous_rounds))
        self.assertEqual("2026/07/02", previous_rounds[0]["result"]["version"])
        self.assertEqual("hit", previous_rounds[0]["predictions"][0]["result"]["outcome"])
        self.assertIn('data-result-round-id="balance-2026-07-01"', html)
        self.assertIn("過去の予想結果", html)


if __name__ == "__main__":
    unittest.main()
