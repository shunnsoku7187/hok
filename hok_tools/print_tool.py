import matplotlib.pyplot as plt
#import japanize_matplotlib
import os
from hok_tools.csv_tool import get_period

plt.rcParams['font.family'] = 'Noto Sans CJK JP'

###  画像出力本体
def generate_meta_list_image(roll_name,roll, heroes, filename="meta_list.png",author = "ぴかち"):

    year,month,day = get_period()
    # 対象ロールのヒーローを抽出
    roll_heroes = [hero for hero in heroes if hero['name'] in roll]
    # Tierスコアでソート
    roll_sorted = sorted(roll_heroes, key=lambda hero:hero['meta_score'], reverse=True)

    # 色の設定
    tier_colors = {
        "S": "#FFD700",  # Gold
        "A": "#C0C0C0",  # Silver
        "B": "#CD7F32",  # Bronze
        "C": "#87CEEB",  # Light Blue
        "D": "#90EE90",  # Light Green
        "E": "#FF6347",  # Tomato
    }

    # プロットの準備
    if roll_name == "All":
      plt.figure(figsize=(20, 16))
    else:
      plt.figure(figsize=(10, 8))
    bars = plt.barh(
        [hero["name"] for hero in roll_sorted],
        [hero["meta_score"] for hero in roll_sorted],
        color=[tier_colors[hero["tier"]] for hero in roll_sorted],
    )

    # グラフの詳細設定
    font_size = 8
    font_weight='heavy'
    line_width = 2
    plt.xlim(25, 70)
    plt.xlabel("Meta Score",fontsize=font_size,fontweight=font_weight)
    plt.ylabel("Hero Name",fontsize= font_size,fontweight=font_weight)
    plt.xticks(fontsize=font_size)
    plt.yticks(fontsize=font_size)
    plt.title(f"～{year}/{month}/{day}'s {roll_name} Meta report (created by {author})", fontsize=font_size,fontweight=font_weight)
    plt.axvline(x=0, color="gray", linestyle="--", linewidth=line_width)
    plt.gca().invert_yaxis()  # 上位を上に表示
    plt.grid(axis="x", linestyle="--", alpha=0.6,linewidth = line_width)

    # スコアと詳細情報をラベルとして表示
    for bar, hero in zip(bars, roll_sorted):
        plt.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f"{hero['meta_score']:.2f} 【{hero['win_rate']}/{hero['pick_rate']}/{hero['ban_rate']}】",
            va="center",
            ha="right",
            fontsize=8,
            fontweight='heavy',
        )


    # 画像の保存
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.show()