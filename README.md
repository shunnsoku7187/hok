# hok
## 使い方
html.txtにデータページ( https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list )の対象となる部分(tobody)をペースト  
上書きすれば自動的にhtmlの解析、データの加工(csv)、データの表示用ページ作成(html)、サーバーへのアップロードが実行される。  

## 新ヒーロー実装時 
①hero_categories.jsonに日本語名で追加  
②names.csvに日本語名,英名を追加  
③list_html/hok_pics内に英名.pngでアイコン画像を追加  
＊差分を表示するので登場週の次週よりページに追加される。  

## フォルダ構成
main.py アプリ本体  
names.csv 日本語名⇔英名の管理用  
hero_categories.json　各ヒーローのロール管理用  
requirements.txt　必要な環境  
html.txt　html貼り付け用  
list_html  
/for_mobile モバイル版ページ保管場所  
/for_pc PC版ページ保管場所  
/hok_pics アイコン画像保管場所（英名.png）  
csv 加工後データ保存場所（過去分参照用）  
graph_images　グラフ画像保管場所（自動でサーバーにはアップロードされない）  
hok_tools　mainを動かすための自作のツール保管場所。  
