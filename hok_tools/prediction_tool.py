import csv
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


DEFAULT_CONFIG = Path("data/prediction_round.json")
DEFAULT_OUTPUT = Path("list_html/predictions")


def load_hero_options(path="names.csv", image_dir="list_html/hok_pics"):
    with Path(path).open(newline="", encoding="utf-8") as file:
        options = [
            {"name": row["Japanese"], "asset": row["English"]}
            for row in csv.DictReader(file)
            if row.get("Japanese") and row.get("English")
        ]

    names = [option["name"] for option in options]
    if len(names) != len(set(names)):
        raise ValueError("Japanese hero names must be unique")
    missing_icons = [
        option["asset"]
        for option in options
        if not (Path(image_dir) / f"{option['asset']}.png").exists()
    ]
    if missing_icons:
        raise ValueError(f"Missing hero icons: {', '.join(missing_icons)}")
    return options


def _normalized_html(content):
    return "\n".join(line.rstrip() for line in content.splitlines()) + "\n"


def load_prediction_round(config_path=DEFAULT_CONFIG):
    with Path(config_path).open("r", encoding="utf-8") as file:
        prediction_round = json.load(file)

    prediction_ids = [item["id"] for item in prediction_round["predictions"]]
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("Prediction IDs must be unique")

    for prediction in prediction_round["predictions"]:
        probability = prediction["probability"]
        if not 0 <= probability <= 100:
            raise ValueError(f"Invalid probability for {prediction['id']}: {probability}")
        if prediction["direction"] not in {"buff", "nerf"}:
            raise ValueError(f"Invalid direction for {prediction['id']}")

    return prediction_round


def generate_prediction_page(
    config_path=DEFAULT_CONFIG,
    output_dir=DEFAULT_OUTPUT,
    template_path="hok_tools/template_prediction.html",
):
    prediction_round = load_prediction_round(config_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader("."), autoescape=True)
    template = env.get_template(template_path)
    hero_options = load_hero_options()
    html = template.render(round=prediction_round, hero_options=hero_options)

    (output_dir / "index.html").write_text(_normalized_html(html), encoding="utf-8")
    (output_dir / "round.json").write_text(
        json.dumps(prediction_round, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "hero_assets.json").write_text(
        json.dumps(
            {option["name"]: option["asset"] for option in hero_options},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Generated prediction page in {output_dir}")
