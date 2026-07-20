import json
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(shutil.which("php"), "PHP is not installed")
class PredictionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.web_root = Path(cls.temp_dir.name) / "public_html"
        (cls.web_root / "api").mkdir(parents=True)
        (cls.web_root / "predictions").mkdir()
        shutil.copy2(
            ROOT / "list_html" / "api" / "prediction_votes.php",
            cls.web_root / "api" / "prediction_votes.php",
        )
        shutil.copy2(
            ROOT / "list_html" / "predictions" / "round.json",
            cls.web_root / "predictions" / "round.json",
        )

        cls.port = _free_port()
        cls.server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{cls.port}", "-t", str(cls.web_root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            try:
                cls._request("GET", "?round_id=balance-2026-07-30")
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
    def _request(cls, method, query="", payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}/api/prediction_votes.php{query}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def test_vote_can_be_recorded_and_changed(self):
        base_payload = {
            "round_id": "balance-2026-07-30",
            "prediction_id": "lixin-nerf",
            "voter_token": "test-voter-token-0001",
        }

        voted_do = self._request("POST", payload={**base_payload, "choice": "do"})
        self.assertEqual({"do": 1, "not": 0}, voted_do["markets"]["lixin-nerf"])
        self.assertEqual("do", voted_do["own_votes"]["lixin-nerf"])

        voted_not = self._request("POST", payload={**base_payload, "choice": "not"})
        self.assertEqual({"do": 0, "not": 1}, voted_not["markets"]["lixin-nerf"])
        self.assertEqual("not", voted_not["own_votes"]["lixin-nerf"])


if __name__ == "__main__":
    unittest.main()
