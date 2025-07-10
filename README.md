# hok
# ●概要
HOK（Honer of Kings）の対戦データは公式にHOKCAMPにて公開されているが、直感的に「どのヒーローが強いか」が分かりにくい表示形式になっている。  
本アプリは公開されているデータ(勝率、使用率、禁止率)から独自の計算式にてスコアを算出しソートすることで、直感的な強さの序列を表現する。  
スコアは勝率が高く、使用率が高く、禁止率が高いヒーローほど高くなるようにしてあり、３パラメータを独自のバランスで足し合わせて算出している。  
主に初心者から中級者プレイヤーにとって、環境把握やヒーロー選択の補助となる情報を提供する目的で公開している。  
ページリンク：[スコア公開ページ(PC向けレイアウト)](http://shunnsoku.s324.xrea.com/index.html)

# ●使い方
html.txtにデータ公開ページ[HOK CAMP](https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list)の対象となる部分(tobody)をペースト  
上書保存きすれば自動的にhtmlの解析、データの加工(csv)、データの表示用ページ作成(html)、サーバーへのアップロードが実行される。  

# ●新ヒーロー実装時 
①hero_categories.jsonに日本語名で追加  
②names.csvに日本語名,英名を追加  
③list_html/hok_pics内に英名.pngでアイコン画像を追加  
＊差分を表示するので登場週の次週よりページに追加される。  
＊実装ペースが頻繁ではなかったため、自動スクリプト化できていない  

# ●フォルダ構成
- .github\workflows\main.yml　GitActions制御
- main.py アプリ本体  
- names.csv 日本語名⇔英名の管理用  
- hero_categories.json　各ヒーローのロール管理用  
- requirements.txt　必要な環境  
- html.txt　html貼り付け用  
- list_html  
  - for_mobile モバイル版ページ保管場所  
  - for_pc PC版ページ保管場所  
  - hok_pics アイコン画像保管場所（英名.png）  
- csv 加工後データ保存場所（過去分参照用）  
- graph_images　グラフ画像保管場所（自動でサーバーにはアップロードされない）  
- hok_tools　mainを動かすための自作のツール保管場所

# ●スコア計算について(25/07/10追記)
**基本的な指針**:勝率が高く使用率が高く禁止率が高いほど強い

⇔勝率は高いが使用率が低い⇒一部のプレイヤーの影響が強い

**🟩勝率基礎点**
```python
diff = win_rate - average_win_rate    
W = average_win_rate + kw * (math.exp(diff / 10) - 1)
```
高い勝率ほど更に勝率を上げるのは難しいため、指数関数で重みづけ

**🟩使用率補正**
```python
pick_correction = ku * (sigmoid(pick_rate,alpha,c*average_pick_rate))
```
ロールごとの種類数の差を考慮してシグモイド関数で補正を頭打ち

**🟩禁止率加点**
```python
B = kb * ban_rate/100
```
線形で評価する

**🟩スコアの算出**
 ```ptyhon   
total_score = W + pick_correction + B
baseline = 50 + ku * (sigmoid(average_pick_rate,alpha,c*average_pick_rate)) + kb * 0
correction = 50 - baseline
total_score += correction
```
【勝率/使用率/禁止率】が【平均値/平均値/0】のときにスコアが50になるように補正
