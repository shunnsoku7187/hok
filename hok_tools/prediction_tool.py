import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from .adjustment_tool import ADJUSTMENTS_FILE, SOURCE_URL, adjustment_class, parse_adjustment_date


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


def _validate_round(prediction_round):
    required = {"round_id", "title", "target_label", "published_at", "closes_at", "result_after", "predictions"}
    missing = sorted(required - prediction_round.keys())
    if missing:
        raise ValueError(f"Missing prediction round fields: {', '.join(missing)}")

    try:
        datetime.fromisoformat(prediction_round["published_at"])
        datetime.fromisoformat(prediction_round["closes_at"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid prediction round datetime: {prediction_round['round_id']}") from error
    if parse_adjustment_date(prediction_round["result_after"]) is None:
        raise ValueError(f"Invalid result_after: {prediction_round['round_id']}")

    prediction_ids = [item["id"] for item in prediction_round["predictions"]]
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("Prediction IDs must be unique")

    for prediction in prediction_round["predictions"]:
        probability = prediction["probability"]
        if not 0 <= probability <= 100:
            raise ValueError(f"Invalid probability for {prediction['id']}: {probability}")
        if prediction["direction"] not in {"buff", "nerf"}:
            raise ValueError(f"Invalid direction for {prediction['id']}")


def _load_adjustment_payload(path=ADJUSTMENTS_FILE):
    path = Path(path)
    if not path.exists():
        return {"heroes": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"heroes": []}


def _actual_direction(classes):
    if "buff" in classes and "nerf" in classes:
        return "上方・下方修正"
    if "buff" in classes:
        return "上方修正"
    if "nerf" in classes:
        return "下方修正"
    if "adjust" in classes:
        return "複合・数値調整"
    return "修正なし"


def _prepare_round_result(prediction_round, adjustment_payload):
    result_after = parse_adjustment_date(prediction_round["result_after"])
    versions = sorted(
        {
            parsed
            for hero in adjustment_payload.get("heroes", [])
            for adjustment in hero.get("adjustments", [])
            if (parsed := parse_adjustment_date(adjustment.get("versionName", ""))) is not None
            and parsed >= result_after
        }
    )
    if not versions:
        prediction_round["result"] = {"ready": False}
        for prediction in prediction_round["predictions"]:
            prediction["result"] = None
        return

    result_date = versions[0]
    result_version = result_date.strftime("%Y/%m/%d")
    adjustments_by_hero = {}
    for hero in adjustment_payload.get("heroes", []):
        matching = [
            adjustment
            for adjustment in hero.get("adjustments", [])
            if parse_adjustment_date(adjustment.get("versionName", "")) == result_date
        ]
        if matching:
            adjustments_by_hero[hero.get("hero_name", "")] = {
                "hero_id": hero.get("hero_id"),
                "adjustments": matching,
            }

    hit_count = 0
    for prediction in prediction_round["predictions"]:
        actual = adjustments_by_hero.get(prediction["hero_name"])
        classes = {
            adjustment_class(
                (((adjustment.get("adjustContent") or {}).get("contentTag") or {}).get("text") or "")
            )
            for adjustment in (actual or {}).get("adjustments", [])
        }
        classes.discard(None)
        if prediction["direction"] in classes:
            outcome = "hit"
            outcome_label = "的中"
            hit_count += 1
        elif "adjust" in classes:
            outcome = "partial"
            outcome_label = "調整あり"
        elif classes:
            outcome = "opposite"
            outcome_label = "逆方向"
        else:
            outcome = "miss"
            outcome_label = "修正なし"

        hero_id = (actual or {}).get("hero_id")
        source_url = SOURCE_URL
        if hero_id:
            source_url = f"{SOURCE_URL}?heroId={hero_id}&versionName={quote(result_version, safe='')}"
        prediction["result"] = {
            "outcome": outcome,
            "outcome_label": outcome_label,
            "actual_direction": _actual_direction(classes),
            "source_url": source_url,
        }

    prediction_round["result"] = {
        "ready": True,
        "version": result_version,
        "version_label": f"{result_date.year}/{result_date.month}/{result_date.day}",
        "hit_count": hit_count,
        "prediction_count": len(prediction_round["predictions"]),
        "source_url": SOURCE_URL,
    }


def load_prediction_rounds(config_path=DEFAULT_CONFIG, adjustment_path=ADJUSTMENTS_FILE):
    with Path(config_path).open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    if "rounds" not in manifest:
        manifest = {"current_round_id": manifest.get("round_id"), "rounds": [manifest]}
    rounds = copy.deepcopy(manifest.get("rounds") or [])
    round_ids = [prediction_round.get("round_id") for prediction_round in rounds]
    if not rounds or len(round_ids) != len(set(round_ids)):
        raise ValueError("Prediction round IDs must be present and unique")
    if manifest.get("current_round_id") not in round_ids:
        raise ValueError("current_round_id must reference a configured round")

    adjustment_payload = _load_adjustment_payload(adjustment_path)
    for prediction_round in rounds:
        _validate_round(prediction_round)
        closes_at = datetime.fromisoformat(prediction_round["closes_at"])
        prediction_round["closes_label"] = (
            f"{closes_at.month}/{closes_at.day} {closes_at.hour:02d}:{closes_at.minute:02d}"
        )
        _prepare_round_result(prediction_round, adjustment_payload)

    rounds.sort(key=lambda item: item["published_at"], reverse=True)
    current = next(item for item in rounds if item["round_id"] == manifest["current_round_id"])
    previous = [item for item in rounds if item["round_id"] != current["round_id"] and item["result"]["ready"]]
    return current, previous, rounds


def load_prediction_round(config_path=DEFAULT_CONFIG, adjustment_path=ADJUSTMENTS_FILE):
    current, _, _ = load_prediction_rounds(config_path, adjustment_path)
    return current


def generate_prediction_page(
    config_path=DEFAULT_CONFIG,
    output_dir=DEFAULT_OUTPUT,
    template_path="hok_tools/template_prediction.html",
    adjustment_path=ADJUSTMENTS_FILE,
):
    prediction_round, previous_rounds, all_rounds = load_prediction_rounds(config_path, adjustment_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader("."), autoescape=True)
    template = env.get_template(template_path)
    hero_options = load_hero_options()
    html = template.render(
        round=prediction_round,
        previous_rounds=previous_rounds,
        hero_options=hero_options,
    )

    (output_dir / "index.html").write_text(_normalized_html(html), encoding="utf-8")
    (output_dir / "round.json").write_text(
        json.dumps(prediction_round, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    for configured_round in all_rounds:
        (rounds_dir / f"{configured_round['round_id']}.json").write_text(
            json.dumps(configured_round, ensure_ascii=False, indent=2) + "\n",
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
