import html
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERO_DIR = ROOT / "list_html" / "heroes"


class GeneratedPageTests(unittest.TestCase):
    def test_all_score_list_hero_links_resolve(self):
        list_pages = list((ROOT / "list_html" / "for_pc").glob("*_table.html"))
        list_pages += list((ROOT / "list_html" / "for_mobile").glob("*_table.html"))
        self.assertEqual(len(list_pages), 12)

        all_links = set()
        for page in list_pages:
            content = page.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'(?:href|src)="[^"]*\\')
            links = re.findall(r'href="\.\./heroes/([^"]+\.html)"', content)
            self.assertTrue(links, page.name)
            for link in links:
                self.assertTrue((HERO_DIR / link).is_file(), f"Broken link in {page.name}: {link}")
            all_links.update(links)

        generated_hero_pages = {path.name for path in HERO_DIR.glob("*.html")} - {"index.html"}
        self.assertTrue(all_links.issubset(generated_hero_pages))

        index_content = (HERO_DIR / "index.html").read_text(encoding="utf-8")
        index_links = set(re.findall(r'href="([^"]+\.html)"', index_content)) - {
            "../index.html",
            "../for_pc/All_pc_table.html",
        }
        self.assertEqual(index_links, generated_hero_pages)

    def test_each_hero_page_contains_chart_and_existing_icon(self):
        hero_pages = list(HERO_DIR.glob("*.html"))
        self.assertGreater(len(hero_pages), 1)

        for page in hero_pages:
            content = page.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'(?:href|src)="[^"]*\\')
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
        self.assertIn("HOKCAMPに掲載された能力調整はありません。", garuda)


if __name__ == "__main__":
    unittest.main()
