import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


HTML_FILE = Path("html.txt")
NAMES_FILE = Path("names.csv")
CATEGORIES_FILE = Path("hero_categories.json")
IMAGE_DIR = Path("list_html") / "hok_pics"
HOKCAMP_URL = "https://camp.honorofkings.com/h5/app/index.html?heroId=510&lang=ja&lang_type=ja#/hero-hot-list"
HOKCAMP_ENGLISH_URL = "https://camp.honorofkings.com/h5/app/index.html?heroId=510&lang=en&lang_type=en#/hero-hot-list"

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


def has_non_ascii(value):
    return any(ord(char) > 127 for char in value)


def extract_hero_id(img_tag):
    if not img_tag:
        return None

    params = img_tag.get("dt-params", "")
    match = re.search(r"hero_id=(\d+)", params)
    if match:
        return match.group(1)
    return None


def make_asset_name(hero_name):
    ascii_name = re.sub(r"\s+", "", hero_name).lower()
    ascii_name = re.sub(r'[<>:"/\\|?*]', "-", ascii_name)
    ascii_name = ascii_name.strip(".-")

    if ascii_name and ascii_name.isascii():
        return ascii_name
    return None


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


def replace_category_name(categories, old_name, new_name):
    replacements = 0

    for category, values in categories.items():
        next_values = []
        changed = False
        for value in values:
            next_value = new_name if value == old_name else value
            if next_value != value:
                replacements += 1
                changed = True
            if next_value not in next_values:
                next_values.append(next_value)

        if changed:
            categories[category] = next_values

    return replacements


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


def load_lazy_table_content(driver):
    from selenium.webdriver.common.by import By

    rows = driver.find_elements(By.CSS_SELECTOR, "#table-container tr")
    for row in rows:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
        time.sleep(0.05)

    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def fetch_japanese_hero_names_by_id():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except Exception as exc:
        print(f"Japanese name resolver skipped: Selenium unavailable ({exc})")
        return {}

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ja-JP")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36"
    )
    chrome_options.add_experimental_option(
        "prefs", {"intl.accept_languages": "ja-JP,ja,en-US,en"}
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "ja-JP"})
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {"headers": {"Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"}},
        )

        driver.get(HOKCAMP_URL)
        driver.execute_script(
            """
            window.localStorage.setItem('CAMP_LANGUAGE', 'ja');
            window.sessionStorage.setItem('CAMP_LANGUAGE', 'ja');
            """
        )
        driver.get(HOKCAMP_URL)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.visibility_of_element_located((By.ID, "table-container")))
        time.sleep(2)
        load_lazy_table_content(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        names_by_hero_id = {}

        for row in soup.find_all("tr"):
            name_tag = row.find("div", class_="hero-intro-name")
            img_tag = row.find("img", class_="hero-icon") or row.find("img")
            hero_id = extract_hero_id(img_tag)
            if not name_tag or not hero_id:
                continue

            name = name_tag.get_text(strip=True)
            if name and has_non_ascii(name):
                names_by_hero_id[hero_id] = name

        print(f"Japanese name resolver: {len(names_by_hero_id)} hero names loaded")
        return names_by_hero_id
    except Exception as exc:
        print(f"Japanese name resolver failed: {exc}")
        return {}
    finally:
        if driver:
            driver.quit()


def fetch_english_asset_names_by_id():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except Exception as exc:
        print(f"English asset resolver skipped: Selenium unavailable ({exc})")
        return {}

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36"
    )
    chrome_options.add_experimental_option(
        "prefs", {"intl.accept_languages": "en-US,en,ja-JP,ja"}
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "en-US"})
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {"headers": {"Accept-Language": "en-US,en;q=0.9,ja-JP;q=0.8,ja;q=0.7"}},
        )

        driver.get(HOKCAMP_ENGLISH_URL)
        driver.execute_script(
            """
            window.localStorage.setItem('CAMP_LANGUAGE', 'en');
            window.sessionStorage.setItem('CAMP_LANGUAGE', 'en');
            """
        )
        driver.get(HOKCAMP_ENGLISH_URL)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.visibility_of_element_located((By.ID, "table-container")))
        time.sleep(2)
        load_lazy_table_content(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        assets_by_hero_id = {}

        for row in soup.find_all("tr"):
            name_tag = row.find("div", class_="hero-intro-name")
            img_tag = row.find("img", class_="hero-icon") or row.find("img")
            hero_id = extract_hero_id(img_tag)
            if not name_tag or not hero_id:
                continue

            asset_name = make_asset_name(name_tag.get_text(strip=True))
            if asset_name:
                assets_by_hero_id[hero_id] = asset_name

        print(f"English asset resolver: {len(assets_by_hero_id)} asset names loaded")
        return assets_by_hero_id
    except Exception as exc:
        print(f"English asset resolver failed: {exc}")
        return {}
    finally:
        if driver:
            driver.quit()


def rewrite_html_hero_names(names_by_hero_id, normalized_english_to_japanese):
    if not HTML_FILE.exists():
        return 0

    soup = BeautifulSoup(HTML_FILE.read_text(encoding="utf-8"), "html.parser")
    changed = 0

    for row in soup.find_all("tr"):
        name_tag = row.find("div", class_="hero-intro-name")
        if not name_tag:
            continue

        img_tag = row.find("img", class_="hero-icon") or row.find("img")
        hero_id = extract_hero_id(img_tag)
        current_name = name_tag.get_text(strip=True)
        translated_name = None

        if hero_id:
            translated_name = names_by_hero_id.get(hero_id)
        if not translated_name:
            translated_name = normalized_english_to_japanese.get(normalize_name(current_name))

        if translated_name and translated_name != current_name:
            name_tag.string = translated_name
            changed += 1

    if changed:
        HTML_FILE.write_text(
            soup.prettify(encoding="utf-8", formatter="html").decode("utf-8").strip(),
            encoding="utf-8",
        )

    return changed


def original_icon_url(image_url):
    return image_url.split("?imageMogr2/thumbnail/64x", 1)[0]


def download_icon(image_url, asset_name):
    if not image_url:
        return False, "画像URLなし"

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = IMAGE_DIR / f"{asset_name}.png"
    if image_path.exists():
        return False, "既存"

    request = urllib.request.Request(
        original_icon_url(image_url),
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

    missing_name_candidates = []
    for hero in heroes:
        normalized_name = normalize_name(hero["name"])
        known_japanese_name = normalized_english_to_japanese.get(normalized_name)
        if hero["name"] not in japanese_to_english and not known_japanese_name:
            missing_name_candidates.append(hero)
        elif known_japanese_name and not has_non_ascii(known_japanese_name):
            missing_name_candidates.append(hero)

    japanese_names_by_hero_id = {}
    if missing_name_candidates:
        japanese_names_by_hero_id = fetch_japanese_hero_names_by_id()

    missing_asset_candidates = []
    for hero in heroes:
        normalized_name = normalize_name(hero["name"])
        existing_display_name = normalized_english_to_japanese.get(normalized_name)
        display_name = existing_display_name or hero["name"]
        if display_name not in japanese_to_english:
            missing_asset_candidates.append(hero)

    english_assets_by_hero_id = {}
    if missing_asset_candidates:
        english_assets_by_hero_id = fetch_english_asset_names_by_id()

    added_names = []
    renamed_names = []
    added_categories = []
    renamed_categories = []
    downloaded_icons = []
    warnings = []
    html_names_by_hero_id = {}

    for hero in heroes:
        raw_name = hero["name"]
        normalized_raw_name = normalize_name(raw_name)

        resolved_japanese_name = japanese_names_by_hero_id.get(hero["hero_id"])
        existing_display_name = normalized_english_to_japanese.get(normalized_raw_name)
        display_name = existing_display_name or resolved_japanese_name or raw_name
        asset_name = japanese_to_english.get(display_name)

        if (
            existing_display_name
            and resolved_japanese_name
            and resolved_japanese_name != existing_display_name
        ):
            for row in rows:
                if row["Japanese"] == existing_display_name:
                    row["Japanese"] = resolved_japanese_name
                    break

            asset_name = japanese_to_english.pop(existing_display_name, asset_name)
            display_name = resolved_japanese_name
            japanese_to_english[display_name] = asset_name
            normalized_english_to_japanese[normalized_raw_name] = display_name
            if asset_name:
                normalized_english_to_japanese[normalize_name(asset_name)] = display_name
            renamed_names.append((existing_display_name, display_name))

            renamed_count = replace_category_name(
                categories, existing_display_name, display_name
            )
            if renamed_count:
                renamed_categories.append((existing_display_name, display_name, renamed_count))

        is_new_hero = display_name not in categories.get("All", [])

        if not asset_name:
            asset_name = None
            if not has_non_ascii(raw_name):
                asset_name = make_asset_name(raw_name)
            if not asset_name and hero["hero_id"]:
                asset_name = english_assets_by_hero_id.get(hero["hero_id"])
            if not asset_name:
                warnings.append(
                    f"{display_name}: asset name unresolved for hero_id={hero['hero_id']}; "
                    "add it to names.csv"
                )
                continue
            rows.append({"Japanese": display_name, "English": asset_name})
            japanese_to_english[display_name] = asset_name
            normalized_english_to_japanese[normalize_name(asset_name)] = display_name
            added_names.append((display_name, asset_name))
            if not has_non_ascii(display_name):
                warnings.append(f"{display_name}: 日本語名を解決できなかったため英名で追加")

        if hero["hero_id"] and display_name != raw_name:
            html_names_by_hero_id[hero["hero_id"]] = display_name

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

    if added_names or renamed_names:
        save_names(rows)
    if added_categories or renamed_categories:
        save_categories(categories)
    html_rewrites = rewrite_html_hero_names(
        html_names_by_hero_id, normalized_english_to_japanese
    )

    print("New hero sync summary")
    print(f"- names.csv additions: {len(added_names)}")
    for name, asset in added_names:
        print(f"  - {name},{asset}")

    print(f"- names.csv renames: {len(renamed_names)}")
    for old_name, new_name in renamed_names:
        print(f"  - {old_name} -> {new_name}")

    print(f"- hero_categories.json additions: {len(added_categories)}")
    for name, role in added_categories:
        print(f"  - {name} -> {role}")

    print(f"- hero_categories.json renames: {len(renamed_categories)}")
    for old_name, new_name, count in renamed_categories:
        print(f"  - {old_name} -> {new_name} ({count})")

    print(f"- downloaded icons: {len(downloaded_icons)}")
    for name, path in downloaded_icons:
        print(f"  - {name}: {path}")

    print(f"- html.txt name rewrites: {html_rewrites}")

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
