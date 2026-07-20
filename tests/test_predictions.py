import json
import tempfile
import unittest
from pathlib import Path

from hok_tools.prediction_tool import generate_prediction_page, load_prediction_round


class PredictionPageTests(unittest.TestCase):
    def test_prediction_round_has_unique_valid_markets(self):
        prediction_round = load_prediction_round()
        predictions = prediction_round["predictions"]

        self.assertEqual(10, len(predictions))
        self.assertEqual(len(predictions), len({item["id"] for item in predictions}))
        self.assertEqual(
            ["鉄板", "大本命", "本命", "対抗", "対抗", "単穴", "穴", "穴", "大穴", "大穴"],
            [item["rank"] for item in predictions],
        )

    def test_generated_page_contains_predictions_and_round_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            generate_prediction_page(output_dir=output_dir)

            html = (output_dir / "index.html").read_text(encoding="utf-8")
            deployed_round = json.loads((output_dir / "round.json").read_text(encoding="utf-8"))

        self.assertIn("次回バランス調整予想", html)
        self.assertIn("data-prediction-id=\"lixin-nerf\"", html)
        self.assertIn("../hok_pics/lixin.png", html)
        self.assertEqual("balance-2026-07-30", deployed_round["round_id"])


if __name__ == "__main__":
    unittest.main()
