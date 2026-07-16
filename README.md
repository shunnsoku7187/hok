# hok
# ●概要
HOK（Honer of Kings）の対戦データは公式にHOKCAMPにて公開されているが、直感的に「どのヒーローが強いか」が分かりにくい表示形式になっている。  
本アプリは公開されているデータ(勝率、使用率、禁止率)から独自の計算式にてスコアを算出しソートすることで、直感的な強さの序列を表現する。  
スコアは勝率が高く、使用率が高く、禁止率が高いヒーローほど高くなるようにしてあり、３パラメータを独自のバランスで足し合わせて算出している。  
各ヒーローの個別ページでは、保存済みの週次CSVを使ってスコア推移と勝率・使用率・禁止率の履歴を確認できる。
主に初心者から中級者プレイヤーにとって、環境把握やヒーロー選択の補助となる情報を提供する目的で公開している。  
ページリンク：[スコア公開ページ(PC向けレイアウト)](http://shunnsoku.s324.xrea.com/index.html)

# ●使い方
GitHub Actionsが毎週日曜日の午前6時に[HOK CAMP](https://camp.honorofkings.com/h5/app/index.html?heroId=510#/hero-hot-list)を取得する。
取得後、ヒーロー情報の同期、週次CSVの保存、ロール別一覧とヒーロー別推移ページの生成、FTPサーバーへのアップロードまで自動で実行される。
`main`ブランチへのpushでも同じ処理を実行できる。

# ●新ヒーロー実装時
`sync_new_heroes.py`がHOKCAMPの日本語名・英語アセット名・ロール・アイコンを取得し、`names.csv`、`hero_categories.json`、`list_html/hok_pics`へ自動追加する。
日本語名と英語アセット名は初回検出時に保存し、以後の週次更新では保存済みの対応を利用する。
自動判定できない場合はActionsを失敗させ、誤った名前や画像を追加しない。
＊一覧は前週との差分を表示するため、新ヒーローがスコア一覧に載るのは原則として登場翌週から。

# ●フォルダ構成
- .github\workflows\main.yml　GitActions制御
- main.py アプリ本体
- get_html.py 自動でのhtml取得用アプリ 
- names.csv 日本語名⇔英名の管理用  
- hero_categories.json　各ヒーローのロール管理用  
- requirements.txt　必要な環境  
- html.txt　html貼り付け用  
- list_html  
  - for_mobile モバイル版ページ保管場所  
  - for_pc PC版ページ保管場所  
  - heroes ヒーロー別スコア推移ページ保管場所
  - hok_pics アイコン画像保管場所（英名.png）  
- csv 加工後データ保存場所（過去分参照用）  
- graph_images　グラフ画像保管場所（自動でサーバーにはアップロードされない）  
- hok_tools　main.pyを動かすための自作のツール保管場所

# ●スコア計算について
**基本的な指針**:勝率が高く使用率が高く禁止率が高いほど強い

⇔勝率は高いが使用率が低い:一部の熟練プレイヤーの影響が強くノイズの可能性

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
