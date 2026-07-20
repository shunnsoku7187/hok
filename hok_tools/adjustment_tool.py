import json
import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup


ADJUSTMENTS_FILE = Path("data/hero_adjustments.json")
SOURCE_URL = "https://camp.honorofkings.com/h5/app/index.html#/adjustment-detail"


def parse_adjustment_date(value):
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def format_adjustment_date(value):
    parsed = parse_adjustment_date(value)
    return parsed.strftime("%Y/%m/%d") if parsed else str(value)


def html_to_text(value):
    soup = BeautifulSoup(value or "", "html.parser")
    for break_tag in soup.find_all("br"):
        break_tag.replace_with("\n")
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def load_adjustment_data(path=ADJUSTMENTS_FILE):
    path = Path(path)
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    heroes = payload.get("heroes", [])
    result = {}
    for hero in heroes:
        hero_name = hero.get("hero_name", "").strip()
        if not hero_name:
            raise ValueError(f"Missing hero_name in {path}")
        if hero_name in result:
            raise ValueError(f"Duplicate hero adjustment entry: {hero_name}")
        result[hero_name] = hero
    return result


def adjustment_class(tag_text):
    if "弱体化" in tag_text:
        return "nerf"
    if "強化" in tag_text or "レベルアップ" in tag_text:
        return "buff"
    return "adjust"


def adjustment_direction(tag_text):
    direction = adjustment_class(tag_text)
    return {
        "buff": "上方修正",
        "nerf": "下方修正",
        "adjust": "調整",
    }[direction]


def prepare_hero_adjustments(hero_entry):
    if not hero_entry:
        return []

    prepared = []
    for adjustment in hero_entry.get("adjustments", []):
        content = adjustment.get("adjustContent") or {}
        tag_text = (content.get("contentTag") or {}).get("text") or "数値調整"
        attributes = []
        for attribute in content.get("attribute") or []:
            description = html_to_text(attribute.get("attributeDesc", ""))
            if not description:
                continue
            attributes.append(
                {
                    "title": attribute.get("title") or "調整内容",
                    "description": description,
                }
            )

        prepared.append(
            {
                "date_label": format_adjustment_date(adjustment.get("versionName", "")),
                "season_name": adjustment.get("seasonName", ""),
                "summary": content.get("shortDesc") or content.get("desc") or "能力調整",
                "tag_text": tag_text,
                "tag_class": adjustment_class(tag_text),
                "direction_label": adjustment_direction(tag_text),
                "attributes": attributes,
            }
        )
    return prepared


def has_adjustment_between(hero_entry, start_date, end_date):
    if not hero_entry:
        return False
    return any(
        parsed_date is not None and start_date < parsed_date <= end_date
        for parsed_date in (
            parse_adjustment_date(adjustment.get("versionName", ""))
            for adjustment in hero_entry.get("adjustments", [])
        )
    )


def hero_adjustment_url(hero_entry):
    if not hero_entry or not hero_entry.get("hero_id"):
        return SOURCE_URL
    return f"{SOURCE_URL}?heroId={hero_entry['hero_id']}"
