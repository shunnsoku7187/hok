import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "https://ss1.xrea.com/shunnsoku.s324.xrea.com/api/prediction_comments.php"


def default_round_id():
    with (ROOT / "data" / "prediction_round.json").open(encoding="utf-8") as file:
        return json.load(file)["round_id"]


def request_json(url, payload=None, admin_token=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            message = json.loads(error.read().decode("utf-8")).get("error", str(error))
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = str(error)
        raise RuntimeError(message) from error


def load_admin_token(path):
    token = os.environ.get("HOK_COMMENT_ADMIN_TOKEN", "").strip()
    if not token:
        try:
            token = Path(path).read_text(encoding="utf-8").strip()
        except FileNotFoundError as error:
            raise RuntimeError(
                f"管理トークンがありません: {path} または HOK_COMMENT_ADMIN_TOKEN を設定してください"
            ) from error
    return token


def list_comments(args):
    query = urllib.parse.urlencode({"round_id": args.round_id})
    data = request_json(f"{args.api_url}?{query}")
    if not data["comments"]:
        print("コメントはありません")
        return
    for comment in data["comments"]:
        parent = f" -> #{comment['parent_id']}" if comment["parent_id"] else ""
        deleted = " [削除済み]" if comment["deleted"] else ""
        body = comment["body"].replace("\n", " ")
        print(f"#{comment['id']}{parent} {comment['nickname']} 賛成:{comment['like_count']}{deleted}")
        print(f"  {body}")


def delete_comment(args):
    parsed_url = urllib.parse.urlparse(args.api_url)
    if parsed_url.scheme != "https" and parsed_url.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("管理トークンを送るAPI URLにはHTTPSを指定してください")
    token = load_admin_token(args.token_file)
    data = request_json(
        args.api_url,
        {
            "round_id": args.round_id,
            "action": "admin_delete",
            "comment_id": args.comment_id,
        },
        token,
    )
    deleted = next((item for item in data["comments"] if item["id"] == args.comment_id), None)
    if not deleted or not deleted["deleted"]:
        raise RuntimeError("削除結果を確認できませんでした")
    print(f"コメント #{args.comment_id} を削除しました")


def build_parser():
    parser = argparse.ArgumentParser(description="予想掲示板のコメントを管理します")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--round-id", default=default_round_id())
    parser.add_argument("--token-file", default=ROOT / ".comment-admin-token")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="コメントIDと本文を一覧表示します")
    delete_parser = subparsers.add_parser("delete", help="指定コメントを論理削除します")
    delete_parser.add_argument("comment_id", type=int)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "list":
            list_comments(args)
        else:
            delete_comment(args)
    except RuntimeError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
