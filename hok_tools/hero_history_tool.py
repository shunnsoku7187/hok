import csv
import html
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from jinja2 import Environment, FileSystemLoader

from hok_tools.adjustment_tool import (
    load_adjustment_data,
    prepare_hero_adjustments,
)
from hok_tools.categories_tool import load_hero_categories
from hok_tools.csv_tool import hero_page_slug, load_name_dict, transrate_name


CSV_DIR = Path("csv")
OUTPUT_DIR = Path("list_html/heroes")
RELATIONSHIP_WINDOW = 13
MIN_RELATIONSHIP_SAMPLES = 8
RELATIONSHIP_LIMIT = 3


def _date_candidates(path):
    token = path.stem.split("_", 1)[0]
    if not token.isdigit() or len(token) < 6:
        raise ValueError(f"Unsupported snapshot filename: {path.name}")

    year = int(token[:4])
    month_day = token[4:]

    if len(token) == 8:
        return [date(year, int(token[4:6]), int(token[6:8]))]

    candidates = []
    for month in range(1, 13):
        for day in range(1, 32):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if f"{month}{day}" == month_day:
                candidates.append(candidate)

    if not candidates:
        raise ValueError(f"Could not parse snapshot date: {path.name}")
    friday_candidates = [candidate for candidate in candidates if candidate.weekday() == 4]
    return friday_candidates or candidates


def resolve_snapshot_dates(paths):
    candidates_by_path = {path: _date_candidates(path) for path in paths}
    known_dates = {
        candidates[0]
        for candidates in candidates_by_path.values()
        if len(candidates) == 1
    }
    resolved = {}

    for path, candidates in candidates_by_path.items():
        if len(candidates) == 1:
            resolved[path] = candidates[0]
            continue

        adjacency = {
            candidate: sum(
                neighbor in known_dates
                for neighbor in (
                    candidate - timedelta(days=7),
                    candidate + timedelta(days=7),
                )
            )
            for candidate in candidates
        }
        best_score = max(adjacency.values())
        best = [candidate for candidate, score in adjacency.items() if score == best_score]
        if len(best) != 1:
            choices = ", ".join(candidate.isoformat() for candidate in candidates)
            raise ValueError(f"Ambiguous snapshot date {path.name}: {choices}")
        resolved[path] = best[0]

    duplicate_dates = defaultdict(list)
    for path, snapshot_date in resolved.items():
        duplicate_dates[snapshot_date].append(path.name)
    duplicates = {
        snapshot_date: names
        for snapshot_date, names in duplicate_dates.items()
        if len(names) > 1
    }
    if duplicates:
        details = "; ".join(
            f"{snapshot_date.isoformat()}: {', '.join(names)}"
            for snapshot_date, names in sorted(duplicates.items())
        )
        raise ValueError(f"Duplicate hero snapshots: {details}")

    return resolved


def _percent(value):
    return float(value.strip().rstrip("%"))


def load_hero_histories(csv_dir=CSV_DIR):
    paths = sorted(Path(csv_dir).glob("*_heroes.csv"))
    if not paths:
        raise FileNotFoundError(f"No hero snapshots found in {csv_dir}")

    dated_paths = resolve_snapshot_dates(paths)
    histories = defaultdict(list)

    for path, snapshot_date in sorted(dated_paths.items(), key=lambda item: item[1]):
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

        ranked_rows = sorted(rows, key=lambda row: float(row["meta_score"]), reverse=True)
        rank_by_name = {row["name"].strip(): rank for rank, row in enumerate(ranked_rows, 1)}

        for row in rows:
            hero_name = row["name"].strip()
            histories[hero_name].append({
                "date": snapshot_date,
                "date_label": snapshot_date.strftime("%Y/%m/%d"),
                "score": float(row["meta_score"]),
                "score_label": f'{float(row["meta_score"]):.2f}',
                "tier": row["tier"].strip(),
                "win_rate": _percent(row["win_rate"]),
                "win_rate_label": f'{_percent(row["win_rate"]):.2f}%',
                "pick_rate": _percent(row["pick_rate"]),
                "pick_rate_label": f'{_percent(row["pick_rate"]):.2f}%',
                "ban_rate": _percent(row["ban_rate"]),
                "ban_rate_label": f'{_percent(row["ban_rate"]):.2f}%',
                "rank": rank_by_name[hero_name],
                "hero_count": len(rows),
            })

    return dict(histories)


def _chart_label_indices(point_count, max_labels=6):
    if point_count <= max_labels:
        return list(range(point_count))
    return sorted({round(index * (point_count - 1) / (max_labels - 1)) for index in range(max_labels)})


def build_score_chart(history, adjustments=None):
    width, height = 960, 360
    left, right, top, bottom = 62, 24, 26, 54
    plot_width = width - left - right
    plot_height = height - top - bottom
    scores = [item["score"] for item in history]

    y_min = math.floor((min(scores) - 2) / 5) * 5
    y_max = math.ceil((max(scores) + 2) / 5) * 5
    if y_min == y_max:
        y_min -= 5
        y_max += 5

    def x_position(index):
        if len(history) == 1:
            return left + plot_width / 2
        return left + plot_width * index / (len(history) - 1)

    def y_position(score):
        return top + (y_max - score) * plot_height / (y_max - y_min)

    def adjustment_x_position(adjustment_date):
        if not adjustment_date or not history[0]["date"] <= adjustment_date <= history[-1]["date"]:
            return None
        if len(history) == 1:
            return x_position(0)

        for index in range(1, len(history)):
            previous_date = history[index - 1]["date"]
            current_date = history[index]["date"]
            if adjustment_date > current_date:
                continue
            day_span = (current_date - previous_date).days
            fraction = (
                (adjustment_date - previous_date).days / day_span
                if day_span > 0
                else 1
            )
            return x_position(index - 1) + (x_position(index) - x_position(index - 1)) * fraction
        return x_position(len(history) - 1)

    grid = []
    for tick in range(y_min, y_max + 1, 5):
        y = y_position(tick)
        grid.append(
            f'<line class="chart-grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" />'
            f'<text class="chart-y-label" x="{left - 12}" y="{y + 4:.1f}">{tick}</text>'
        )

    x_labels = []
    for index in _chart_label_indices(len(history)):
        x = x_position(index)
        label = history[index]["date"].strftime("%y/%m/%d")
        x_labels.append(
            f'<text class="chart-x-label" x="{x:.1f}" y="{height - 18}">{label}</text>'
        )

    adjustment_markers = []
    visible_adjustments = []
    for adjustment in adjustments or []:
        x = adjustment_x_position(adjustment.get("date"))
        if x is not None:
            visible_adjustments.append((adjustment, x))
    visible_adjustments.sort(key=lambda item: item[0]["date"])

    for index, (adjustment, x) in enumerate(visible_adjustments):
        label_y = top + 15 + (index % 2) * 17
        if x < left + 34:
            anchor = "start"
            label_x = x + 5
        elif x > width - right - 34:
            anchor = "end"
            label_x = x - 5
        else:
            anchor = "middle"
            label_x = x
        title = html.escape(
            f'{adjustment["date_label"]} {adjustment["direction_label"]}'
        )
        marker_class = html.escape(adjustment["tag_class"])
        adjustment_markers.append(
            f'<g class="chart-adjustment {marker_class}"><title>{title}</title>'
            f'<line class="chart-adjustment-line" x1="{x:.1f}" y1="{top}" '
            f'x2="{x:.1f}" y2="{height - bottom}" />'
            f'<circle class="chart-adjustment-point" cx="{x:.1f}" '
            f'cy="{height - bottom}" r="4" />'
            f'<text class="chart-adjustment-label" x="{label_x:.1f}" y="{label_y}" '
            f'text-anchor="{anchor}">調整</text></g>'
        )

    points = [f'{x_position(index):.1f},{y_position(item["score"]):.1f}' for index, item in enumerate(history)]
    circles = []
    for index, item in enumerate(history):
        x = x_position(index)
        y = y_position(item["score"])
        circles.append(
            f'<circle class="chart-point" cx="{x:.1f}" cy="{y:.1f}" r="4">'
            f'<title>{item["date_label"]}: {item["score_label"]}</title></circle>'
        )

    latest = history[-1]
    latest_x = x_position(len(history) - 1)
    latest_y = y_position(latest["score"])
    latest_anchor = "end" if latest_x > width - 90 else "start"
    latest_label_x = latest_x - 10 if latest_anchor == "end" else latest_x + 10

    return (
        f'<svg class="score-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(history[-1].get("hero_name", "ヒーロー"))}のスコア推移">'
        f'<title>スコア推移</title>'
        f'{"".join(grid)}'
        f'<line class="chart-axis" x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" />'
        f'<line class="chart-axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" />'
        f'{"".join(adjustment_markers)}'
        f'<polyline class="chart-line" points="{" ".join(points)}" />'
        f'{"".join(circles)}'
        f'<circle class="chart-point chart-point-latest" cx="{latest_x:.1f}" cy="{latest_y:.1f}" r="6" />'
        f'<text class="chart-latest-label" x="{latest_label_x:.1f}" y="{latest_y - 12:.1f}" text-anchor="{latest_anchor}">{latest["score_label"]}</text>'
        f'{"".join(x_labels)}'
        '</svg>'
    )


def _role_map(hero_categories):
    result = defaultdict(list)
    for role, hero_names in hero_categories.items():
        if role == "All":
            continue
        for hero_name in hero_names:
            result[hero_name].append(role)
    return result


def _average_ranks(values):
    ranks = [0.0] * len(values)
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for index, _ in ordered[start:end]:
            ranks[index] = average_rank
        start = end
    return ranks


def _spearman_correlation(left, right):
    if len(left) != len(right) or len(left) < 2:
        return None

    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = sum(left_ranks) / len(left_ranks)
    right_mean = sum(right_ranks) / len(right_ranks)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_ranks, right_ranks)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left_ranks)
    right_variance = sum((value - right_mean) ** 2 for value in right_ranks)
    denominator = math.sqrt(left_variance * right_variance)
    return numerator / denominator if denominator else None


def build_market_adjusted_change_series(histories, window=RELATIONSHIP_WINDOW):
    snapshot_dates = sorted({item["date"] for history in histories.values() for item in history})
    transitions = list(zip(snapshot_dates, snapshot_dates[1:]))[-window:]
    scores_by_hero = {
        hero_name: {item["date"]: item["score"] for item in history}
        for hero_name, history in histories.items()
    }
    series = defaultdict(dict)

    for previous_date, current_date in transitions:
        changes = {
            hero_name: scores[current_date] - scores[previous_date]
            for hero_name, scores in scores_by_hero.items()
            if previous_date in scores and current_date in scores
        }
        if not changes:
            continue
        market_change = median(changes.values())
        for hero_name, change in changes.items():
            series[hero_name][current_date] = change - market_change

    return dict(series)


def calculate_hero_relationships(
    histories,
    window=RELATIONSHIP_WINDOW,
    min_samples=MIN_RELATIONSHIP_SAMPLES,
    limit=RELATIONSHIP_LIMIT,
):
    change_series = build_market_adjusted_change_series(histories, window)
    relationships = {}

    for hero_name, hero_series in change_series.items():
        candidates = []
        for candidate_name, candidate_series in change_series.items():
            if candidate_name == hero_name:
                continue
            shared_dates = sorted(set(hero_series) & set(candidate_series))
            if len(shared_dates) < min_samples:
                continue

            hero_changes = [hero_series[item_date] for item_date in shared_dates]
            candidate_changes = [candidate_series[item_date] for item_date in shared_dates]
            correlation = _spearman_correlation(hero_changes, candidate_changes)
            if correlation is None:
                continue

            comparable_pairs = [
                (hero_change, candidate_change)
                for hero_change, candidate_change in zip(hero_changes, candidate_changes)
                if hero_change != 0 and candidate_change != 0
            ]
            same_direction = sum(left * right > 0 for left, right in comparable_pairs)
            opposite_direction = sum(left * right < 0 for left, right in comparable_pairs)
            candidates.append({
                "name": candidate_name,
                "correlation": correlation,
                "correlation_label": f"{correlation:+.2f}",
                "sample_count": len(shared_dates),
                "direction_count": len(comparable_pairs),
                "same_direction_count": same_direction,
                "opposite_direction_count": opposite_direction,
            })

        positive = sorted(
            (item for item in candidates if item["correlation"] > 0),
            key=lambda item: (-item["correlation"], item["name"]),
        )[:limit]
        negative = sorted(
            (item for item in candidates if item["correlation"] < 0),
            key=lambda item: (item["correlation"], item["name"]),
        )[:limit]
        relationships[hero_name] = {
            "positive": positive,
            "negative": negative,
            "window": window,
        }

    return relationships


def _page_data(hero_name, english_name, history, roles, adjustment_entry=None):
    history = [dict(item, hero_name=hero_name) for item in history]
    latest = history[-1]
    previous = history[-2] if len(history) > 1 else None
    score_change = latest["score"] - previous["score"] if previous else 0
    change_class = "positive" if score_change > 0 else "negative" if score_change < 0 else "flat"
    role_label = " / ".join(sorted(roles)) if roles else "All"
    hero_adjustments = prepare_hero_adjustments(adjustment_entry)

    return {
        "name": hero_name,
        "english_name": english_name,
        "page_slug": hero_page_slug(english_name),
        "image_filename": f"{english_name}.png",
        "roles": sorted(roles),
        "role_label": role_label,
        "latest": latest,
        "score_change_label": f"{score_change:+.2f}",
        "change_class": change_class,
        "first_date_label": history[0]["date_label"],
        "period_count": len(history),
        "chart_svg": build_score_chart(history, hero_adjustments),
        "history": list(reversed(history)),
        "adjustments": hero_adjustments,
    }


def _normalized_html(content):
    return "\n".join(line.rstrip() for line in content.splitlines()) + "\n"


def generate_hero_history_pages(
    csv_dir=CSV_DIR,
    output_dir=OUTPUT_DIR,
    names_file="names.csv",
    categories_file="hero_categories.json",
    adjustments_file="data/hero_adjustments.json",
):
    histories = load_hero_histories(csv_dir)
    name_dict = load_name_dict(names_file)
    roles = _role_map(load_hero_categories(categories_file))
    adjustments = load_adjustment_data(adjustments_file)
    relationships = calculate_hero_relationships(histories)
    missing_names = sorted(name for name in histories if transrate_name(name, name_dict) is None)
    if missing_names:
        raise ValueError(f"Missing English hero names in {names_file}: {', '.join(missing_names)}")

    pages = [
        _page_data(
            hero_name,
            transrate_name(hero_name, name_dict),
            history,
            roles[hero_name],
            adjustments.get(hero_name),
        )
        for hero_name, history in histories.items()
    ]
    pages.sort(key=lambda hero: (-hero["latest"]["score"], hero["name"]))

    page_by_name = {hero["name"]: hero for hero in pages}
    for hero in pages:
        hero_relationships = relationships.get(hero["name"], {})
        hero["relationships"] = {
            "window": hero_relationships.get("window", RELATIONSHIP_WINDOW),
            "positive": [],
            "negative": [],
        }
        for direction in ("positive", "negative"):
            for relationship in hero_relationships.get(direction, []):
                related_hero = page_by_name[relationship["name"]]
                hero["relationships"][direction].append({
                    **relationship,
                    "page_slug": related_hero["page_slug"],
                    "image_filename": related_hero["image_filename"],
                    "role_label": related_hero["role_label"],
                    "direction_match_count": (
                        relationship["same_direction_count"]
                        if direction == "positive"
                        else relationship["opposite_direction_count"]
                    ),
                })

    page_slugs = [hero["page_slug"] for hero in pages]
    if len(page_slugs) != len(set(page_slugs)):
        raise ValueError("Duplicate hero page slugs generated from names.csv")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader("."), autoescape=True)
    hero_template = env.get_template("hok_tools/template_hero.html")
    index_template = env.get_template("hok_tools/template_hero_index.html")

    expected_files = {"index.html"}
    for hero in pages:
        filename = f'{hero["page_slug"]}.html'
        expected_files.add(filename)
        (output_dir / filename).write_text(
            _normalized_html(hero_template.render(hero=hero)),
            encoding="utf-8",
        )

    (output_dir / "index.html").write_text(
        _normalized_html(
            index_template.render(heroes=pages, latest_date=pages[0]["latest"]["date_label"])
        ),
        encoding="utf-8",
    )

    for old_page in output_dir.glob("*.html"):
        if old_page.name not in expected_files:
            old_page.unlink()

    print(f"Generated {len(pages)} hero history pages in {output_dir}")
