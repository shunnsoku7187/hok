import csv
import os
import pandas as pd
import datetime
from hok_tools.categories_tool import get_heroes_by_tag

BASE_PATH = "csv/"
IMAGE_PATH = "../hok_pics"

def get_period(previous=False):
    today = datetime.date.today()

    days_to_friday = (today.weekday() - 4) % 7
    last_friday = today - datetime.timedelta(days=days_to_friday)

    # `previous` が指定されていれば、さらにその前の金曜日を計算
    if previous:
        last_friday -= datetime.timedelta(days=7)

    return last_friday.year, last_friday.month, last_friday.day

def save_heroes_to_csv(heroes, filename="heroes.csv"):
    year,month,day = get_period()
    if not os.path.exists(BASE_PATH):
        os.makedirs(BASE_PATH)

    # CSVファイルに書き込む
    with open(f"{BASE_PATH}{year}{month}{day}_{filename}", mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=heroes[0].keys())
        writer.writeheader()  # ヘッダー（キー）を書き込む
        writer.writerows(heroes)  # ヒーロー情報を行ごとに書き込む
        
def find_heroes_by_roll(previous_csv, current_csv, roll="All"):
    # 前回と今回のデータを読み込む
    prev_df = pd.read_csv(previous_csv)
    curr_df = pd.read_csv(current_csv)

    roll_names = get_heroes_by_tag(tag = roll)
    
    # ヒーロー名でデータを結合
    merged_df = pd.merge(prev_df, curr_df, on="name", suffixes=("_prev", "_curr"))
    merged_df = merged_df[merged_df["name"].isin(roll_names)]
    
    # meta_score の差分を計算
    merged_df["meta_score_diff"] = merged_df["meta_score_curr"] - merged_df["meta_score_prev"]
    
    # 必要なデータを抽出
    result = merged_df[[ 
        "name",
        "win_rate_curr",
        "pick_rate_curr",
        "ban_rate_curr",
        "meta_score_curr",
        "tier_curr",
        "meta_score_diff",
        "win_rate_prev",
        "pick_rate_prev",
        "ban_rate_prev",
        "tier_prev",
    ]].to_dict(orient="records")
    
    return result
    
def format_hero_data(data):
    formatted_data = []
    
    for hero in data:
        win_rate_curr = float(hero['win_rate_curr'].strip('%'))
        pick_rate_curr = float(hero['pick_rate_curr'].strip('%'))
        ban_rate_curr = float(hero['ban_rate_curr'].strip('%'))
        win_rate_prev = float(hero['win_rate_prev'].strip('%'))
        pick_rate_prev = float(hero['pick_rate_prev'].strip('%'))
        ban_rate_prev = float(hero['ban_rate_prev'].strip('%'))
        meta_score_curr = float(hero['meta_score_curr']) 
        meta_score_diff = float(hero['meta_score_diff']) 
        formatted_data.append({
            "name": hero["name"],
            "score": f"{meta_score_curr:.2f}({meta_score_diff:+.2f})",
            "tier": f"{hero['tier_prev']} → {hero['tier_curr']}",
            "data": f"【{win_rate_prev:.2f}%/{pick_rate_prev:.2f}%/{ban_rate_prev:.2f}%】→" + 
                    f"【{win_rate_curr:.2f}%/{pick_rate_curr:.2f}%/{ban_rate_curr:.2f}%】"
        })
    
    return formatted_data
    
def csv_to_list(filename="heroes.csv",roll = "All"):
    yc,mc,dc = get_period()
    yp,mp,dp = get_period(previous=True)
    
    current_csv = f"{BASE_PATH}{yc}{mc}{dc}_{filename}"
    previous_csv = f"{BASE_PATH}{yp}{mp}{dp}_{filename}"
    
    pick_up_list = find_heroes_by_roll(previous_csv, current_csv,roll = roll)
    pick_up_list = sorted(pick_up_list, key=lambda hero:hero['meta_score_curr'], reverse=True)
    pick_up_list = format_hero_data(pick_up_list)
    
    return pick_up_list

#デバッグ用のリストの表示
def display_diff_list(roll = "All"):
    
    results = csv_to_list(roll = roll)
    for hero in formated_results:
        print(
            f"{hero['name']} -- {hero['score']}/ {hero['tier']} / {hero['data']}"
        )
        
def load_name_dict(csv_file='names.csv'):
    name_dict = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # ヘッダー読み飛ばし
        for row in reader:
            if len(row) >= 2:
                japanese, english = row[0], row[1]
                name_dict[japanese] = english
    return name_dict

def transrate_name(japanese_name, name_dict=None):
    if name_dict is None:
        name_dict = load_name_dict()

    if japanese_name in name_dict:
        return name_dict[japanese_name]
    else:
        return None
        
def generate_pick_up_html(roll, image_folder=IMAGE_PATH, filename="sample.html", author="ぴかち", device="pc"):
    name_dict = load_name_dict()
    data = csv_to_list(roll=roll)
    y, m, d = get_period()

    # PC/モバイル共通部分
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{y}{m}{d} Score List</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f9f9f9;
                color: #333;
            }}
            h1 {{
                font-size: 1.5em;
                text-align: center;
            }}
            .hero-name {{
                font-weight: bold;
                color: #333;
            }}
            .highlight {{
                font-weight: bold;
                color: #4CAF50;
            }}
    """

    if device == "pc":
        # PC向けのスタイル
        html_content += """
            .supplementary {
                color: #666;
            }
            .scrollable {
                overflow-x: auto;
                width: 100%;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background: #fff;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
                word-break: break-word;
                max-width: 200px;
            }
            th {
                background-color: #4CAF50;
                color: white;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            td:first-child {
                width: 120px;
            }
            img {
                max-width: 100px;
                height: auto;
            }
        """
    elif device == "mobile":
        # モバイル向けのスタイル（縦長・シンプル化）
        html_content += """
            .supplementary {
                border-bottom: 2px solid #4CAF50;
                color: #666;
                font-size: 0.6em
            }
            table {
                width: 100%;
                border-collapse: collapse;
                background: #fff;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            th, td {
                border: 1px solid #ddd;
                padding: 5px;
                text-align: center;
                font-size: 0.9em;
            }
            th {
                background-color: #4CAF50;
                color: white;
            }
            img {
                max-width: 70px;
                height: auto;
            }
            td:first-child {
                width: 70px;
            }
            .hero-block:nth-of-type(odd) {
                background-color: #f2f2f2;
            }
            .hero-block:nth-of-type(even) {
                background-color: #ffffff;
            }
        """

    # PCまたはモバイルで異なるHTML構造
    if device == "pc":
        html_content += f"""
        </style>
    </head>
    <body>
        <h1>～{y}/{m}/{d}'s Score List (created by {author})</h1>
        <div class="scrollable">
            <table>
                <thead>
                    <tr>
                        <th>image</th>
                        <th>name</th>
                        <th>score</th>
                        <th>Tier</th>
                        <th>data</th>
                    </tr>
                </thead>
                <tbody>
        """
    elif device == "mobile":
        html_content += f"""
        </style>
    </head>
    <body>
        <h1>～{y}/{m}/{d}'s Score List (created by {author})</h1>
        <div class="scrollable">
            <table>
                <thead>
                    <tr>
                        <th colspan="2">Hero Data</th>
                    </tr>
                </thead>
                <tbody>
        """

    for idx, hero in enumerate(data):
        hero_name = hero["name"]
        eng_name = transrate_name(hero_name, name_dict)
        image_path = os.path.join(image_folder, f"{eng_name}.png")
        img_tag = f'<img src="{image_path}" alt="{hero_name}" />'

        if device == "pc":
            html_content += f"""
            <tr class="hero-row">
                <td>{img_tag}</td>
                <td class="hero-name">{hero_name}</td>
                <td class="highlight">{hero['score']}</td>
                <td class="highlight">{hero['tier']}</td>
                <td class="supplementary">{hero['data']}</td>
            </tr>
            """
        elif device == "mobile":
            html_content += f"""
            <tbody class="hero-block">
                <tr　class="hero-row">
                    <td rowspan="3">{img_tag}</td>
                    <td class="hero-name">{hero_name}</td>
                </tr>
                <tr class="hero-row">
                    <td class="highlight">{hero['score']}</td>
                </tr>
                <tr class="hero-row">
                    <td class="highlight">{hero['tier']}</td>
                </tr>
                <tr class="hero-row">
                    <td colspan="2" class="supplementary">{hero['data']}</td>
                </tr>
            </tbody>
            """

    html_content += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    with open(filename, "w", encoding="utf-8") as file:
        file.write(html_content)

    print(f"HTMLファイルを生成しました: {filename}")