import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


HTML_FILE = Path("html.txt")
NAMES_FILE = Path("names.csv")
CATEGORIES_FILE = Path("hero_categories.json")
IMAGE_DIR = Path("list_html") / "hok_pics"

ROLE_MAP = {
    "メイジ": ["Mid"],
    "Mage": ["Mid"],
    "アサシン": ["Jg"],
    "Assassin": ["Jg"],
    "マークスマン": ["Farm"],
    "Marksman": ["Farm"],
    "ファイター": ["Clash"],
    "Fighter": ["Clash"],
    "タンク": ["Clash"],
    "Tank": ["Clash"],
    "サポート": ["Roam"],
    "Support": ["Roam"],
}


def normalize_name(value):
    return re.sub(r"\s+", "", value).lower()


def extract_hero_id(img_tag):
    if not img_tag:
        return None

    params = img_tag.get("dt-params", "")
    match = re.search(r"hero_id=(\d+)", params)
    if match:
        return match.group(1)
    return None


def make_asset_name(hero_name, hero_id=None):
    ascii_name = re.sub(r"\s+", "", hero_name).lower()
    ascii_name = re.sub(r'[<>:"/\\|?*]', "-", ascii_name)
    ascii_name = ascii_name.strip(".-")

    if ascii_name and ascii_name.isascii():
        return ascii_name
    if hero_id:
        return f"hero_{hero_id}"

    digest = hashlib.sha1(hero_name.encode("utf-8")).hexdigest()[:10]
    return f"hero_{digest}"


def load_names():
    rows = []
    japanese_to_english = {}
    normalized_english_to_japanese = {}

    if not NAMES_FILE.exists():
        return rows, japanese_to_english, normalized_english_to_japanese

    with NAMES_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            japanese = row.get("Japanese", "").strip()
            english = row.get("English", "").strip()
            if not japanese or not english:
                continue

            rows.append({"Japanese": japanese, "English": english})
            japanese_to_english[japanese] = english
            normalized_english_to_japanese[normalize_name(english)] = japanese

    return rows, japanese_to_english, normalized_english_to_japanese


def save_names(rows):
    with NAMES_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Japanese", "English"])
        writer.writeheader()
        writer.writerows(rows)


def load_categories():
    with CATEGORIES_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_categories(categories):
    with CATEGORIES_FILE.open("w", encoding="utf-8") as file:
        json.dump(categories, file, ensure_ascii=False, indent=4)
        file.write("\n")


def append_unique(values, value):
    if value not in values:
        values.append(value)
        return True
    return False


def infer_roles(career_text):
    roles = []
    for career, mapped_roles in ROLE_MAP.items():
        if career in career_text:
            for role in mapped_roles:
                if role not in roles:
                    roles.append(role)
    return roles


def parse_html_heroes():
    if not HTML_FILE.exists():
        raise FileNotFoundError(f"{HTML_FILE} が見つかりません。先に get_html.py を実行してください。")

    soup = BeautifulSoup(HTML_FILE.read_text(encoding="utf-8"), "html.parser")
    heroes = []

    for row in soup.find_all("tr"):
        name_tag = row.find("div", class_="hero-intro-name")
        if not name_tag:
            continue

        career_tag = row.find("div", class_="hero-intro-career")
        img_tag = row.find("img", class_="hero-icon") or row.find("img")
        image_url = img_tag.get("src") if img_tag else None

        heroes.append(
            {
                "name": name_tag.get_text(strip=True),
                "career": career_tag.get_text(strip=True) if career_tag else "",
                "image_url": image_url,
                "hero_id": extract_hero_id(img_tag),
            }
        )

    return heroes


def download_icon(image_url, asset_name):
    if not image_url:
        return False, "画像URLなし"

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = IMAGE_DIR / f"{asset_name}.png"
    if image_path.exists():
        return False, "既存"

    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        image_path.write_bytes(response.read())

    return True, str(image_path)


def sync_new_heroes():
    rows, japanese_to_english, normalized_english_to_japanese = load_names()
    categories = load_categories()
    heroes = parse_html_heroes()

    added_names = []
    added_categories = []
    downloaded_icons = []
    warnings = []

    for hero in heroes:
        raw_name = hero["name"]
        normalized_raw_name = normalize_name(raw_name)

        display_name = normalized_english_to_japanese.get(normalized_raw_name, raw_name)
        asset_name = japanese_to_english.get(display_name)
        is_new_hero = display_name not in categories.get("All", [])

        if not asset_name:
            asset_name = make_asset_name(raw_name, hero["hero_id"])
            rows.append({"Japanese": display_name, "English": asset_name})
            japanese_to_english[display_name] = asset_name
            normalized_english_to_japanese[normalize_name(asset_name)] = display_name
            added_names.append((display_name, asset_name))

        if "All" not in categories:
            categories["All"] = []

        if append_unique(categories["All"], display_name):
            added_categories.append((display_name, "All"))

        inferred_roles = infer_roles(hero["career"]) if is_new_hero else []
        if is_new_hero and not inferred_roles:
            warnings.append(f"{display_name}: career='{hero['career']}' からロール推定不可")

        for role in inferred_roles:
            if role not in categories:
                categories[role] = []
            if append_unique(categories[role], display_name):
                added_categories.append((display_name, role))

        try:
            downloaded, result = download_icon(hero["image_url"], asset_name)
            if downloaded:
                downloaded_icons.append((display_name, result))
        except Exception as exc:
            warnings.append(f"{display_name}: アイコン取得失敗 ({exc})")

    if added_names:
        save_names(rows)
    if added_categories:
        save_categories(categories)

    print("New hero sync summary")
    print(f"- names.csv additions: {len(added_names)}")
    for name, asset in added_names:
        print(f"  - {name},{asset}")

    print(f"- hero_categories.json additions: {len(added_categories)}")
    for name, role in added_categories:
        print(f"  - {name} -> {role}")

    print(f"- downloaded icons: {len(downloaded_icons)}")
    for name, path in downloaded_icons:
        print(f"  - {name}: {path}")

    if warnings:
        print("- warnings:")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    try:
        sync_new_heroes()
    except Exception as exc:
        print(f"sync_new_heroes failed: {exc}", file=sys.stderr)
        sys.exit(1)
