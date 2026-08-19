import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = (
    "https://camp.honorofkings.com/h5/app/index.html"
    "?lang=ja&lang_type=ja#/hero-homepage"
)
SOURCE_URL = "https://camp.honorofkings.com/h5/app/index.html#/adjustment-detail"
ADJUSTMENT_LIST_API = "/api/game/adjust/adjustforseason"
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
                if (
                    ADJUSTMENT_API not in request.get("url", "")
                    or request.get("method") != "POST"
                ):
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


def _wait_for_adjustment_list_response(driver, timeout=20):
    request_ids = set()
    response_ids = set()
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        for message in _performance_messages(driver):
            method = message.get("method")
            params = message.get("params", {})
            request_id = params.get("requestId")

            if method == "Network.requestWillBeSent":
                request = params.get("request", {})
                if (
                    ADJUSTMENT_LIST_API in request.get("url", "")
                    and request.get("method") == "POST"
                ):
                    request_ids.add(request_id)
            elif method == "Network.responseReceived" and request_id in request_ids:
                response_ids.add(request_id)
            elif method == "Network.loadingFinished" and request_id in response_ids:
                body = driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": request_id}
                )
                payload = json.loads(body["body"])
                if payload.get("code") != 0:
                    raise RuntimeError(
                        "HOKCAMP adjustment list API failed: "
                        f"{payload.get('msg', payload.get('code'))}"
                    )
                return (payload.get("data") or {}).get("adjustList") or []

        time.sleep(0.05)

    raise TimeoutError("HOKCAMP adjustment list response timed out")


def _date_key(value):
    digits = "".join(char for char in str(value) if char.isdigit())
    return digits[:8].ljust(8, "0")


def _fetch_hero_detail(hero_id, route_version, attempts=2):
    target_url = (
        "https://camp.honorofkings.com/h5/app/index.html"
        f"?lang=ja&lang_type=ja#/adjustment-detail?heroId={hero_id}"
        f"&versionName={route_version}"
    )
    last_error = None
    for attempt in range(1, attempts + 1):
        detail_driver = webdriver.Chrome(options=_chrome_options())
        try:
            detail_driver.execute_cdp_cmd(
                "Emulation.setLocaleOverride", {"locale": "ja-JP"}
            )
            detail_driver.execute_cdp_cmd("Network.enable", {})
            detail_driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
            detail_driver.get(target_url)
            return _wait_for_adjustment_response(detail_driver, timeout=25)
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                raise
        finally:
            detail_driver.quit()
    raise last_error


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
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '直近の調整')]")))
        latest_match = re.search(
            r"アップデート[：:]\s*(\d{4}/\d{2}/\d{2})",
            driver.find_element(By.TAG_NAME, "body").text,
        )
        if not latest_match:
            raise RuntimeError("HOKCAMP homepage has no latest adjustment date")
        latest_version = latest_match.group(1)
        list(_performance_messages(driver))
        more_links = driver.find_elements(
            By.XPATH, "//*[normalize-space(text())='もっと見る>']"
        )
        if not more_links:
            raise RuntimeError("HOKCAMP recent-adjustments link was not found")
        driver.execute_script("arguments[0].click();", more_links[0])
        wait.until(lambda current_driver: "#/adjustment-detail" in current_driver.current_url)
        adjustment_items = _wait_for_adjustment_list_response(driver)
        if not adjustment_items:
            raise RuntimeError("HOKCAMP returned an empty adjustment list")
        route_version = (
            datetime.strptime(latest_version, "%Y/%m/%d") - timedelta(days=1)
        ).strftime("%Y/%m/%d")
        print(
            f"HOKCAMP latest adjustment: {latest_version}; "
            f"route version: {route_version}; "
            f"season list: {len(adjustment_items)} heroes"
        )

        cached = load_cached_heroes()
        refreshed = {}

        for processed, item in enumerate(adjustment_items, 1):
            hero_info = item.get("heroInfo") or {}
            hero_name = hero_info.get("heroName", "").strip()
            expected_hero_id = int(hero_info.get("heroId"))
            if not hero_name:
                raise RuntimeError("HOKCAMP adjustment item has no hero name")
            hero_id, data = _fetch_hero_detail(expected_hero_id, route_version)
            if hero_id != expected_hero_id:
                raise RuntimeError(
                    f"Hero route mismatch: expected={expected_hero_id}, response={hero_id}"
                )

            if data:
                api_name = data["heroInfo"]["heroName"].strip()
                if api_name != hero_name:
                    raise RuntimeError(
                        f"Hero selection mismatch: card={hero_name}, response={api_name}"
                    )
                current_adjustments = data.get("adjustInfo") or []
            else:
                current_adjustments = []

            current_latest = max(
                (record.get("versionName", "") for record in current_adjustments),
                key=_date_key,
                default="",
            )
            if _date_key(current_latest) not in {
                _date_key(latest_version),
                _date_key(route_version),
            }:
                print(
                    f"Stopped at older adjustment: {hero_name} ({current_latest})"
                )
                break
            if _date_key(current_latest) == _date_key(route_version):
                for record in current_adjustments:
                    if _date_key(record.get("versionName", "")) == _date_key(route_version):
                        record["versionName"] = latest_version

            previous_adjustments = cached.get(hero_name, {}).get("adjustments", [])
            refreshed[hero_name] = {
                "hero_id": hero_id,
                "hero_name": hero_name,
                "adjustments": merge_adjustments(
                    current_adjustments, previous_adjustments
                ),
            }
            print(
                f"[{processed:03d}/{len(adjustment_items)}] {hero_name}: "
                f"{len(current_adjustments)} records"
            )

        heroes = [refreshed.get(name, hero) for name, hero in cached.items()]
        for name, hero in refreshed.items():
            if name not in cached:
                heroes.append(hero)

        hero_count = len(heroes)
        if hero_count < 100:
            raise RuntimeError(f"Only {hero_count} heroes were retained")
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
