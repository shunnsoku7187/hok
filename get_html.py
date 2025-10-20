import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import os
import re

# ターゲットとなるURL
# ユーザーが指定したURL: https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list
TARGET_URL = "https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list"

# ファイル名
INPUT_HTML_FILE = "html.txt"
INPUT_CSV_FILE = "names.csv"
OUTPUT_HTML_FILE = "html.txt"
OUTPUT_FILENAME = "html.txt" # 抽出された<tbody>タグの中身のみを保存するファイル名

def fetch_and_extract_tbody(url, filename):
    """
    Seleniumでウェブサイトのコンテンツを取得し、ランキングデータの<tbody>タグの中身のみを抽出して保存する関数。
    """
    print(f"ターゲットURL: {url} から動的にレンダリングされたコンテンツの取得を開始します...")

    # --- 1. WebDriverのセットアップ ---
    chrome_options = Options()
    # ヘッドレスモードで実行 (GUIなしで高速に動作)
    chrome_options.add_argument("--headless")
    # Docker/Linux環境などで必要になる可能性のあるオプション
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ja-JP")
    # ユーザーエージェントを設定
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36")
    
    try:
        # WebDriverの初期化
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"❌ WebDriverの初期化に失敗しました。ChromeDriverが正しく設定されているか確認してください: {e}")
        return

    try:
        # --- 2. ウェブサイトへのアクセス ---
        driver.get(url)
        print("ウェブサイトを開きました。動的コンテンツのロードを待機しています...")

        # --- 3. 動的コンテンツのロードを待機 ---
        # ランキングテーブルの親要素（ID: 'table-container'）が可視化されるまで最大20秒待機
        wait = WebDriverWait(driver, 20)
        
        # テーブル全体を含むコンテナがロードされるのを待つ
        table_container_locator = (By.ID, "table-container")
        wait.until(EC.visibility_of_element_located(table_container_locator))
        
        # さらに時間差でコンテンツが完全にレンダリングされるのを待つ（必要に応じて調整）
        time.sleep(2) 

        # --- 4. レンダリングされたHTMLの取得 ---
        rendered_html_content = driver.page_source

        # --- 5. Beautiful Soupによる<tbody>データの抽出 ---
        soup = BeautifulSoup(rendered_html_content, 'html.parser')
        
        # テーブルコンテナを取得
        table_container = soup.find('div', id='table-container')

        if not table_container:
            print("❌ 抽出エラー: ランキングテーブルのコンテナ（ID: 'table-container'）が見つかりませんでした。")
            return

        # table-containerの中から<tbody>タグを探す
        tbody = table_container.find('tbody')
        
        if not tbody:
            print("❌ 抽出エラー: ヒーローデータを含むテーブル本体（<tbody>）が見つかりませんでした。")
            return

        # <tbody>タグとその中身全体を抽出して整形
        extracted_tbody_html = tbody.prettify(encoding='utf-8', formatter="html").decode('utf-8')

        # --- 6. ファイルへの書き込み ---
        with open(filename, 'w', encoding='utf-8') as f:
            # 抽出した<tbody>タグのみを書き込み
            f.write(extracted_tbody_html.strip())

        print(f"✅ <tbody>タグの中身（ヒーローデータ）をファイル '{filename}' に正常に抽出・保存しました。")
        print("これで、データ解析に集中できる純粋なHTMLデータが取得されました。")

    except Exception as e:
        print(f"❌ データの取得または抽出中にエラーが発生しました: {e}")
        
    finally:
        # 必ずブラウザを閉じる
        if 'driver' in locals():
            driver.quit()
            print("WebDriverを終了しました。")

def load_translation_map(csv_file):
    """
    CSVファイルを読み込み、正規化された英名（小文字、空白なし）をキーに、
    日本語名を値とする辞書を作成する。
    """
    try:
        # CSVを読み込む。
        df = pd.read_csv(csv_file, encoding='utf-8')
        
        # 必要な列 'Japanese' と 'English' が存在するか確認
        if 'Japanese' not in df.columns or 'English' not in df.columns:
            print("❌ エラー: CSVファイルに 'Japanese' または 'English' の列が見つかりません。")
            return None
        
        # 1. English名を正規化（空白除去、小文字化）した新しい列を追加
        # 例: "Ukyo Tachibana" -> "ukyotachibana"
        df['Normalized_English'] = df['English'].str.replace(r'\s+', '', regex=True).str.lower()
        
        # 辞書を {正規化された英名: 日本語名} の形式で作成
        translation_map = df.set_index('Normalized_English')['Japanese'].to_dict()
        
        return translation_map
        
    except FileNotFoundError:
        print(f"❌ エラー: 翻訳ファイル '{csv_file}' が見つかりません。")
        return None
    except Exception as e:
        print(f"❌ エラー: CSVファイルの読み込み中に問題が発生しました: {e}")
        return None

def translate_hero_names(html_file, translation_map, output_file):
    """
    HTMLファイル内のヒーロー名（英名）を正規化して辞書と照合し、
    対応する日本語名に置き換えて新しいファイルに保存する。
    """
    if not translation_map:
        return
        
    try:
        # HTMLファイルを読み込む
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
    except FileNotFoundError:
        print(f"❌ エラー: 入力HTMLファイル '{html_file}' が見つかりません。")
        return
    except Exception as e:
        print(f"❌ エラー: HTMLファイルの読み込み中に問題が発生しました: {e}")
        return

    # Beautiful Soupで解析
    # Beautiful SoupはHTMLの解析エラーを許容するため、try/exceptブロックは省略
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # ヒーロー名を含む全ての要素（<div class="hero-intro-name">）を探す
    name_divs = soup.find_all('div', class_='hero-intro-name')
    
    if not name_divs:
        print("⚠️ 警告: ヒーロー名を含む要素（class='hero-intro-name'）がHTML内から見つかりませんでした。")
        # 見つからない場合は、元のコンテンツをそのまま出力します
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ 翻訳はスキップされましたが、元のHTMLを '{output_file}' に保存しました。")
        return

    translation_count = 0
    for name_div in name_divs:
        # 要素内のテキスト（例: "Ukyo Tachibana"）を取得
        original_english_name = name_div.text.strip()
        
        # 照合用に正規化（空白除去、小文字化）
        normalized_name = re.sub(r'\s+', '', original_english_name).lower()
        
        # 正規化された名前をキーに、日本語名を探す
        translated_name = translation_map.get(normalized_name)
        
        if translated_name:
            # 翻訳名が見つかった場合、テキストを日本語に置き換え
            name_div.string = translated_name
            translation_count += 1
        # 翻訳名が見つからない場合（例: 既に日本語名、またはデータ不足）、そのまま保持
        
    
    # 変換後のHTMLコンテンツを取得し、新しいファイルに書き出し
    # prettify()はHTML構造を整形し、可読性を高めます
    translated_html = soup.prettify(encoding='utf-8', formatter="html").decode('utf-8')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(translated_html.strip())

    print(f"✅ 翻訳完了: {translation_count}個のヒーロー名を翻訳し、'{output_file}' に保存しました。")


if __name__ == "__main__":
    # スクリプトを実行
    fetch_and_extract_tbody(TARGET_URL, OUTPUT_FILENAME)
    translation_map = load_translation_map(INPUT_CSV_FILE)
    if translation_map:
        translate_hero_names(INPUT_HTML_FILE, translation_map, OUTPUT_HTML_FILE)
