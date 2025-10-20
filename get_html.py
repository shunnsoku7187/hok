import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ターゲットとなるURL
# ユーザーが指定したURL: https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list
TARGET_URL = "https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list"

# 出力ファイル名
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

if __name__ == "__main__":
    # スクリプトを実行
    fetch_and_extract_tbody(TARGET_URL, OUTPUT_FILENAME)
