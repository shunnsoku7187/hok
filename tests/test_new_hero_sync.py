import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sync_new_heroes import parse_html_heroes


class NewHeroSyncTests(unittest.TestCase):
    def test_current_hokcamp_classes_are_detected(self):
        html = '''<tbody><tr>
        <td><div class="heroIntroName-build">New Hero</div>
        <div class="heroIntroCareer-build">Assassin</div>
        <img src="https://example.com/hero.png" dt-params="hero_id=999"></td>
        </tr></tbody>'''
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "html.txt"
            path.write_text(html, encoding="utf-8")
            with patch("sync_new_heroes.HTML_FILE", path):
                heroes = parse_html_heroes()
        self.assertEqual(len(heroes), 1)
        self.assertEqual(heroes[0]["name"], "New Hero")
        self.assertEqual(heroes[0]["career"], "Assassin")
        self.assertEqual(heroes[0]["hero_id"], "999")
