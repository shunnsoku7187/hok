# 必要なパッケージをインポート
import os
import pandas as pd
from hok_tools import (
    add_info_to_heroes,
    html_to_heroes,
    generate_meta_list_image,
    save_heroes_to_csv,
    load_hero_categories,
    generate_pick_up_html
)
import matplotlib.pyplot as plt
#import japanize_matplotlib

# 作業ディレクトリの指定
# 例: プロジェクトがリポジトリ内にある場合
os.chdir('/path/to/your/project')  # 作業ディレクトリを指定

# 必要なパッケージをインストール
# requirements.txtを使って、以下のパッケージが自動でインストールされます
# matplotlib
# japanize-matplotlib
# pandas

# main部分
def generate_html():
    file_path = 'html.txt'  # 解析するhtmlを張り付けたテキストファイルのパス

    # リストheroesの準備
    heroes = html_to_heroes(file_path)
    heroes = add_info_to_heroes(heroes)

    # heroesをcsvに書き込み(過去データとして参照するとき用)
    save_heroes_to_csv(heroes)

    # ロール名の管理用
    hero_categories = load_hero_categories()

    # 出力先ディレクトリの指定
    graph_path = "graph_images/"  # 画像の出力先ディレクトリ
    html_path = "list_html/"  # HTMLの出力先ディレクトリ

    # 各ロールごとにイメージを出力
    for category_name, hero_set in hero_categories.items():
        # 画像の生成
        g_filename = f"{graph_path}{category_name}_Meta_List.png"
        generate_meta_list_image(category_name, hero_set, heroes, filename=g_filename)

        # PC用HTML生成
        h_pc_filename = f"{html_path}/for_pc/{category_name}_pc_table.html"
        generate_pick_up_html(category_name, filename=h_pc_filename, device='pc')

        # モバイル用HTML生成
        h_mb_filename = f"{html_path}/for_mobile/{category_name}_mb_table.html"
        generate_pick_up_html(category_name, filename=h_mb_filename, device='mobile')

if __name__ == "__main__":
    generate_html()