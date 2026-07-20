import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = (
    "https://camp.honorofkings.com/h5/app/index.html"
    "?lang=ja&lang_type=ja#/adjustment-detail?heroId=172"
)
SOURCE_URL = "https://camp.honorofkings.com/h5/app/index.html#/adjustment-detail"
ADJUSTMENT_API = "/api/game/adjust/adjustheroinfo"
OUTPUT_FILE = Path("data/hero_adjustments.json")


def _chrome_options():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=ja-JP")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0 Safari/537.36"
    )
    options.add_experimental_option(
        "prefs", {"intl.accept_languages": "ja-JP,ja,en-US,en"}
    )
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return options


def _performance_messages(driver):
    for entry in driver.get_log("performance"):
        try:
            yield json.loads(entry["message"])["message"]
        except (KeyError, TypeError, json.JSONDecodeError):
            continue


def _wait_for_adjustment_response(driver, timeout=15):
    request_ids = {}
    response_ids = set()
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        for message in _performance_messages(driver):
            method = message.get("method")
            params = message.get("params", {})
            request_id = params.get("requestId")

            if method == "Network.requestWillBeSent":
                request = params.get("request", {})
                if ADJUSTMENT_API not in request.get("url", ""):
                    continue
                post_data = json.loads(request.get("postData", "{}"))
                request_ids[request_id] = int(post_data["heroId"])
            elif method == "Network.responseReceived" and request_id in request_ids:
                response_ids.add(request_id)
            elif method == "Network.loadingFinished" and request_id in response_ids:
                body = driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": request_id}
                )
                payload = json.loads(body["body"])
                if payload.get("code") != 0:
                    raise RuntimeError(
                        f"HOKCAMP adjustment API failed for hero {request_ids[request_id]}: "
                        f"{payload.get('msg', payload.get('code'))}"
                    )
                return request_ids[request_id], payload.get("data")

        time.sleep(0.05)

    raise TimeoutError("HOKCAMP adjustment response timed out")


def _date_key(value):
    digits = "".join(char for char in str(value) if char.isdigit())
    return digits[:8].ljust(8, "0")


def merge_adjustments(current, previous):
    merged = {}
    for adjustment in previous:
        content = adjustment.get("adjustContent") or {}
        key = (adjustment.get("versionName", ""), content.get("shortDesc", ""))
        merged[key] = adjustment
    for adjustment in current:
        content = adjustment.get("adjustContent") or {}
        key = (adjustment.get("versionName", ""), content.get("shortDesc", ""))
        merged[key] = adjustment
    return sorted(
        merged.values(),
        key=lambda adjustment: _date_key(adjustment.get("versionName", "")),
        reverse=True,
    )


def load_cached_heroes(path=OUTPUT_FILE):
    if not Path(path).exists():
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        hero["hero_name"]: hero
        for hero in payload.get("heroes", [])
        if hero.get("hero_name")
    }


def fetch_adjustments():
    driver = webdriver.Chrome(options=_chrome_options())
    try:
        driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "ja-JP"})
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(TARGET_URL)

        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".hero-card")))
        wait.until(
            lambda current_driver: len(
                current_driver.find_elements(By.CSS_SELECTOR, ".hero-card")
            )
            >= 100
        )
        time.sleep(1)

        hero_count = len(driver.find_elements(By.CSS_SELECTOR, ".hero-card"))
        if hero_count < 100:
            raise RuntimeError(f"Only {hero_count} hero cards were loaded")

        # Discard initial page-load traffic. Selecting a different card always creates
        # one fresh adjustment request, so process the initially selected card last.
        list(_performance_messages(driver))
        cached = load_cached_heroes()
        heroes = []

        for processed, index in enumerate(list(range(1, hero_count)) + [0], 1):
            cards = driver.find_elements(By.CSS_SELECTOR, ".hero-card")
            card = cards[index]
            hero_name = card.find_element(By.CSS_SELECTOR, ".title").text.strip()
            driver.execute_script("arguments[0].click();", card)
            hero_id, data = _wait_for_adjustment_response(driver)

            if data:
                api_name = data["heroInfo"]["heroName"].strip()
                if api_name != hero_name:
                    raise RuntimeError(
                        f"Hero selection mismatch: card={hero_name}, response={api_name}"
                    )
                current_adjustments = data.get("adjustInfo") or []
            else:
                current_adjustments = []

            previous_adjustments = cached.get(hero_name, {}).get("adjustments", [])
            heroes.append(
                {
                    "hero_id": hero_id,
                    "hero_name": hero_name,
                    "adjustments": merge_adjustments(
                        current_adjustments, previous_adjustments
                    ),
                }
            )
            print(
                f"[{processed:03d}/{hero_count}] {hero_name}: "
                f"{len(current_adjustments)} records"
            )

        if len({hero["hero_id"] for hero in heroes}) != hero_count:
            raise RuntimeError("Duplicate or missing hero IDs in adjustment data")
        if len({hero["hero_name"] for hero in heroes}) != hero_count:
            raise RuntimeError("Duplicate or missing hero names in adjustment data")

        heroes.sort(key=lambda hero: hero["hero_id"])
        all_adjustments = [
            adjustment
            for hero in heroes
            for adjustment in hero["adjustments"]
        ]
        latest_version = max(
            (adjustment.get("versionName", "") for adjustment in all_adjustments),
            key=_date_key,
            default="",
        )
        return {
            "source": SOURCE_URL,
            "hero_count": len(heroes),
            "adjustment_count": len(all_adjustments),
            "latest_version": latest_version,
            "heroes": heroes,
        }
    finally:
        driver.quit()


def save_adjustments(payload, path=OUTPUT_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    try:
        payload = fetch_adjustments()
        save_adjustments(payload)
        print(
            "Hero adjustment sync complete: "
            f"{payload['hero_count']} heroes, "
            f"{payload['adjustment_count']} adjustments"
        )
    except Exception as exc:
        if OUTPUT_FILE.exists():
            print(
                f"Hero adjustment sync warning: {exc}. Existing cache retained.",
                file=sys.stderr,
            )
            return
        raise


if __name__ == "__main__":
    main()
