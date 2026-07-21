import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hok_tools.prediction_tool import DEFAULT_CONFIG, load_prediction_rounds


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_manifest(path, manifest):
    Path(path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def show_status(config_path):
    current, previous, rounds = load_prediction_rounds(config_path)
    print(f"現在: {current['round_id']} ({current['target_label']})")
    for prediction_round in reversed(rounds):
        result = prediction_round["result"]
        state = (
            f"結果発表済み {result['hit_count']}/{result['prediction_count']}"
            if result["ready"]
            else "投票中または結果待ち"
        )
        marker = "*" if prediction_round["round_id"] == current["round_id"] else " "
        print(f"{marker} {prediction_round['round_id']}: {state}")
    if previous:
        print(f"結果履歴: {len(previous)}件")


def publish_round(config_path, round_path):
    manifest = load_manifest(config_path)
    previous_current = manifest.get("current_round_id")
    prediction_round = json.loads(Path(round_path).read_text(encoding="utf-8"))
    round_id = prediction_round.get("round_id")
    if not round_id:
        raise ValueError("新ラウンドに round_id がありません")
    if any(item.get("round_id") == round_id for item in manifest.get("rounds", [])):
        raise ValueError(f"同じ round_id が既に存在します: {round_id}")

    manifest.setdefault("rounds", []).append(prediction_round)
    manifest["current_round_id"] = round_id
    save_manifest(config_path, manifest)
    try:
        load_prediction_rounds(config_path)
    except Exception:
        manifest["rounds"].pop()
        manifest["current_round_id"] = previous_current
        save_manifest(config_path, manifest)
        raise
    print(f"新ラウンドを公開設定にしました: {round_id}")


def main():
    parser = argparse.ArgumentParser(description="予想ラウンドの状態確認と公開設定")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="現在と過去ラウンドの状態を表示")
    publish = subparsers.add_parser("publish", help="新しいラウンドJSONを追記して公開対象にする")
    publish.add_argument("round_file")
    args = parser.parse_args()

    if args.command == "status":
        show_status(args.config)
    else:
        publish_round(args.config, args.round_file)


if __name__ == "__main__":
    main()
