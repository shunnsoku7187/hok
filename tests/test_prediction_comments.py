import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUND_ID = "balance-2026-07-30"
ADMIN_TOKEN = "test-comment-admin-token"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(shutil.which("php"), "PHP is not installed")
class PredictionCommentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.web_root = Path(cls.temp_dir.name) / "public_html"
        (cls.web_root / "api").mkdir(parents=True)
        (cls.web_root / "predictions").mkdir()
        shutil.copy2(
            ROOT / "list_html" / "api" / "prediction_comments.php",
            cls.web_root / "api" / "prediction_comments.php",
        )
        shutil.copy2(
            ROOT / "list_html" / "predictions" / "round.json",
            cls.web_root / "predictions" / "round.json",
        )

        cls.port = _free_port()
        environment = os.environ.copy()
        environment["HOK_COMMENT_ADMIN_HASH"] = hashlib.sha256(ADMIN_TOKEN.encode()).hexdigest()
        cls.server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{cls.port}", "-t", str(cls.web_root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        for _ in range(30):
            try:
                cls._request("GET", query={"round_id": ROUND_ID})
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.1)
        else:
            raise RuntimeError("PHP test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.temp_dir.cleanup()

    @classmethod
    def _request(cls, method, query=None, payload=None, admin_token=None):
        query_string = f"?{urllib.parse.urlencode(query)}" if query else ""
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if admin_token:
            headers["X-Admin-Token"] = admin_token
        request = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}/api/prediction_comments.php{query_string}",
            data=body,
            method=method,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def test_create_reply_like_toggle_and_admin_delete(self):
        created = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "create",
                "nickname": "予想屋A",
                "hero": "ルナ",
                "direction": "buff",
                "body": "勝率が低いため上方修正されると思います。",
                "parent_id": None,
                "voter_token": "comment-voter-token-0001",
            },
        )
        root = created["comments"][-1]
        self.assertEqual(1, root["id"])
        self.assertEqual("予想屋A", root["nickname"])
        self.assertEqual("ルナ", root["hero"])
        self.assertEqual("buff", root["direction"])

        replied = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "create",
                "nickname": "予想屋B",
                "body": "私も賛成です。",
                "parent_id": root["id"],
                "voter_token": "comment-voter-token-0002",
            },
        )
        reply = replied["comments"][-1]
        self.assertEqual(root["id"], reply["parent_id"])
        self.assertIsNone(reply["hero"])
        self.assertIsNone(reply["direction"])

        liked = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "like",
                "comment_id": root["id"],
                "voter_token": "comment-voter-token-0003",
            },
        )
        self.assertEqual(1, liked["comments"][0]["like_count"])
        self.assertTrue(liked["comments"][0]["liked_by_me"])

        unliked = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "like",
                "comment_id": root["id"],
                "voter_token": "comment-voter-token-0003",
            },
        )
        self.assertEqual(0, unliked["comments"][0]["like_count"])

        deleted = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "admin_delete",
                "comment_id": root["id"],
            },
            admin_token=ADMIN_TOKEN,
        )
        self.assertTrue(deleted["comments"][0]["deleted"])
        self.assertEqual("管理者により削除されました", deleted["comments"][0]["body"])
        self.assertEqual(root["id"], deleted["comments"][1]["parent_id"])

        reply_deleted = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "admin_delete",
                "comment_id": reply["id"],
            },
            admin_token=ADMIN_TOKEN,
        )
        self.assertNotIn(reply["id"], [item["id"] for item in reply_deleted["comments"]])

        root_deleted = self._request(
            "POST",
            payload={
                "round_id": ROUND_ID,
                "action": "admin_delete",
                "comment_id": root["id"],
            },
            admin_token=ADMIN_TOKEN,
        )
        self.assertEqual([], root_deleted["comments"])


if __name__ == "__main__":
    unittest.main()
