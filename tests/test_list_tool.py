import unittest

from hok_tools.list_tool import extract_hero_data


class ListToolTests(unittest.TestCase):
    def test_extracts_legacy_hokcamp_row(self):
        html = """
        <tr>
          <td><div class="hero-intro-name">不知火舞</div></td>
          <td><div class="table-text table-trank-text">A</div></td>
          <td><div class="table-text table-normal-text">50.12%</div></td>
          <td><div class="table-text table-normal-text">1.23%</div></td>
          <td><div class="table-text table-normal-text">0.45%</div></td>
        </tr>
        """

        self.assertEqual(
            [
                {
                    "name": "不知火舞",
                    "win_rate": "50.12%",
                    "pick_rate": "1.23%",
                    "ban_rate": "0.45%",
                }
            ],
            extract_hero_data(html),
        )

    def test_extracts_current_hashed_hokcamp_row(self):
        html = """
        <tr>
          <td><div class="heroIntroName-t0A5a">不知火舞</div></td>
          <td><div class="tableText-bMQb1 tableTrankText-z0zuU">A</div></td>
          <td><div class="tableText-bMQb1 tableNormalText-PY8EQ">50.12%</div></td>
          <td><div class="tableText-bMQb1 tableNormalText-PY8EQ">1.23%</div></td>
          <td><div class="tableText-bMQb1 tableNormalText-PY8EQ">0.45%</div></td>
        </tr>
        """

        self.assertEqual(
            [
                {
                    "name": "不知火舞",
                    "win_rate": "50.12%",
                    "pick_rate": "1.23%",
                    "ban_rate": "0.45%",
                }
            ],
            extract_hero_data(html),
        )


if __name__ == "__main__":
    unittest.main()
