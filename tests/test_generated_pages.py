import html
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERO_DIR = ROOT / "list_html" / "heroes"
LEGAL_DIR = ROOT / "list_html" / "legal"


class GeneratedPageTests(unittest.TestCase):
    def test_all_score_list_hero_links_resolve(self):
        list_pages = list((ROOT / "list_html" / "for_pc").glob("*_table.html"))
        list_pages += list((ROOT / "list_html" / "for_mobile").glob("*_table.html"))
        self.assertEqual(len(list_pages), 12)

        all_links = set()
        for page in list_pages:
            content = page.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'(?:href|src)="[^"]*\\')
            self.assertNotIn("created by", content.lower(), page.name)
            self.assertIn('href="../legal/terms.html"', content, page.name)
            links = re.findall(r'href="\.\./heroes/([^"]+\.html)"', content)
            self.assertTrue(links, page.name)
            for link in links:
                self.assertTrue((HERO_DIR / link).is_file(), f"Broken link in {page.name}: {link}")
            all_links.update(links)

        generated_hero_pages = {path.name for path in HERO_DIR.glob("*.html")} - {"index.html"}
        self.assertTrue(all_links.issubset(generated_hero_pages))

        index_content = (HERO_DIR / "index.html").read_text(encoding="utf-8")
        index_links = set(re.findall(r'class="hero-row" href="([^"]+\.html)"', index_content))
        self.assertEqual(index_links, generated_hero_pages)

    def test_each_hero_page_contains_chart_and_existing_icon(self):
        hero_pages = list(HERO_DIR.glob("*.html"))
        self.assertGreater(len(hero_pages), 1)

        for page in hero_pages:
            content = page.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'(?:href|src)="[^"]*\\')
            self.assertIn('href="../legal/terms.html"', content, page.name)
            if page.name == "index.html":
                continue
            self.assertIn('class="score-chart"', content, page.name)
            image_match = re.search(r'class="hero-icon" src="\.\./hok_pics/([^"]+)"', content)
            self.assertIsNotNone(image_match, page.name)
            image_name = html.unescape(image_match.group(1))
            self.assertTrue((ROOT / "list_html" / "hok_pics" / image_name).is_file(), image_name)

    def test_hero_pages_contain_adjustment_history(self):
        chicha = (HERO_DIR / "chicha.html").read_text(encoding="utf-8")
        garuda = (HERO_DIR / "garuda.html").read_text(encoding="utf-8")

        self.assertIn("能力調整履歴", chicha)
        self.assertIn("2026/07/16", chicha)
        self.assertIn("調整前", chicha)
        self.assertIn("調整後", chicha)
        self.assertIn('<details class="adjustment-item">', chicha)
        self.assertIn('<summary class="adjustment-summary">', chicha)
        self.assertNotIn('<details class="adjustment-item" open>', chicha)
        self.assertIn("上方修正", chicha)
        self.assertLess(chicha.index('id="score-trend-title"'), chicha.index('id="adjustment-title"'))
        self.assertLess(chicha.index('id="adjustment-title"'), chicha.index('id="history-title"'))
        self.assertIn('<details class="history-disclosure">', chicha)
        self.assertIn('<summary class="history-summary">', chicha)
        self.assertNotIn('<details class="history-disclosure" open>', chicha)
        self.assertIn("週次履歴を表示", chicha)
        self.assertIn("週次履歴を非表示", chicha)
        self.assertGreater(chicha.index("<table>"), chicha.index('<details class="history-disclosure">'))
        self.assertEqual(chicha.count('class="chart-adjustment '), 3)
        self.assertIn('<title>2026/07/16 上方修正</title>', chicha)
        self.assertIn('class="chart-adjustment-line"', chicha)
        self.assertIn("HOKCAMPに掲載された能力調整はありません。", garuda)

    def test_policy_pages_and_footer_links_exist(self):
        expected = {
            "terms.html": "利用規約",
            "privacy.html": "プライバシーポリシー",
            "disclaimer.html": "免責事項",
            "community-guidelines.html": "投稿ガイドライン",
        }
        for filename, heading in expected.items():
            content = (LEGAL_DIR / filename).read_text(encoding="utf-8")
            self.assertIn(f"<h1>{heading}</h1>", content)
            for linked_file in expected:
                self.assertIn(f'href="{linked_file}"', content, filename)

        for filename in ["index.html", "for_mobile.html"]:
            content = (ROOT / "list_html" / filename).read_text(encoding="utf-8")
            self.assertIn('href="legal/terms.html"', content, filename)

        prediction = (ROOT / "list_html" / "predictions" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="../legal/terms.html"', prediction)


if __name__ == "__main__":
    unittest.main()
