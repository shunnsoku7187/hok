# HOK Score List

『Honor of Kings』のヒーロー環境を、HOKCAMPで公開されている勝率・使用率・BAN率から独自に算出したスコアで比較するWebサイトです。

公式データだけでは把握しにくい「現在どのヒーローが強いか」「能力調整後にスコアがどう変化したか」を、ロール別ランキングとヒーロー別の時系列ページで確認できます。初心者から中級者が環境を把握し、使用するヒーローを選ぶ際の補助情報として公開しています。

> [!NOTE]
> 本サイトのスコアとバランス調整予想は独自の集計・分析であり、Honor of KingsおよびHOKCAMPの公式評価ではありません。元データの出典はHOKCAMPです。

## 公開ページ

- [PC版トップページ](http://shunnsoku.s324.xrea.com/index.html)
- [モバイル版トップページ](http://shunnsoku.s324.xrea.com/for_mobile.html)
- [ヒーロー別スコア推移](http://shunnsoku.s324.xrea.com/heroes/index.html)
- [次回バランス調整予想](http://shunnsoku.s324.xrea.com/predictions/index.html)

## 主な機能

### ロール別スコア一覧

- `All`、`Mid`、`Clash`、`Jg`、`Farm`、`Roam`の6分類
- PC向け・モバイル向けレイアウト
- 前週からのスコア、Tier、勝率・使用率・BAN率の変化を表示
- 直近1週間に能力調整があったヒーローへ「調整あり」を表示
- ヒーロー名から個別ページへ移動

### ヒーロー個別ページ

- 保存済みの週次CSVを使ったスコア推移グラフ
- 能力調整日の縦線とマーカーをグラフ上に表示
- 直近13週のスコア変化から算出した同方向・逆方向の連動ヒーロー
- 日付と上方・下方修正を常時表示し、詳細を開閉できる能力調整履歴
- 表示・非表示を切り替えられる週次履歴
- 現在のスコア、Tier、全体順位、勝率・使用率・BAN率を表示

週次データを保存し始めた2025年1月24日以降がスコア推移の対象です。能力調整履歴はHOKCAMPから取得できた範囲をキャッシュへ蓄積します。

### 次回バランス調整予想

- 独自分析で選んだ10ヒーローについて、予想方向、確率、根拠を掲載
- 各候補の現在スコア、4週・13週変化、週間変動幅、上下回数、直近調整、連動傾向を週次CSVから自動表示
- 週次の上昇・下降回数はスコア差が±0.20以上、横ばいは±0.20未満として集計
- 各予想へ`DO`または`NOT`で投票し、集計をほぼリアルタイムに表示
- 候補外のヒーローは予想掲示板から投稿可能
- 掲示板の親投稿は「ユーザーネーム」「ヒーロー」「上方・下方修正」「予想理由」で構成
- 投稿されたヒーローのアイコンと正式名称からヒーロー個別ページへ移動可能
- ヒーローは候補から選択し、投稿後に対応するアイコンを表示
- 他ユーザーの投稿へ返信・賛成が可能
- ラウンド締切後に投票、投稿、返信、賛成を一括停止
- 次の能力調整を取得した後、予想の的中結果を自動判定
- 完了したラウンドを「過去の予想結果」として保存
- 利用規約、プライバシーポリシー、免責事項、投稿ガイドラインを全ページのフッターから確認可能

投票者の識別にはブラウザの`localStorage`で生成した匿名トークンを使います。アカウント機能や金銭・商品のやり取りはありません。

## 週次自動更新

[`.github/workflows/main.yml`](.github/workflows/main.yml)が次のタイミングでビルドを実行します。

- 毎週日曜日 6:00（日本時間）
- `main`または`codex/**`ブランチへのpush
- `main`を対象とするPull Request
- `repository_dispatch`の`trigger-from-discord`

処理順は次のとおりです。

1. Python、PHP、依存パッケージ、日本語フォントを準備
2. `get_html.py`でHOKCAMPのランキングHTMLを取得
3. `get_adjustments.py`で全ヒーローの能力調整履歴を取得
4. `sync_new_heroes.py`で新ヒーローの名前、ロール、アイコンを同期
5. `main.py`で週次CSV、一覧、ヒーロー個別ページ、予想ページを生成
6. PHP構文チェックとPythonテストを実行
7. `main`上の実行で生成物に変更があれば、GitHub Actionsが自動コミット
8. `list_html/`をFTPでXREAの`/public_html/`へアップロード

Pull Requestと`codex/**`ブランチではビルドとテストだけを行い、自動コミットとFTP公開は行いません。

### 能力調整データの扱い

`get_adjustments.py`はHOKCAMPの調整ページをSeleniumで開き、各ヒーローを選択した際のAPI応答を取得します。新しく取得した履歴は`data/hero_adjustments.json`の保存済み履歴とマージするため、HOKCAMP側から古い履歴が見えなくなっても、取得済みデータは保持されます。

一時的な通信失敗などが起きた場合、既存キャッシュがあればそのまま保持して週次更新を継続します。初回取得でキャッシュも存在しない場合はエラーになります。

### 新ヒーローの同期

`sync_new_heroes.py`はランキング内の未登録ヒーローを検出すると、次の情報を同期します。

- 日本語表示名と英語アセット名を`names.csv`へ追加
- 推定したロールを`hero_categories.json`へ追加
- 元サイズのアイコンを`list_html/hok_pics/<英語アセット名>.png`へ保存
- 取得HTML内の英名を日本語名へ置換

名前は初回検出時にHOKCAMPの日本語・英語表示から解決し、以後は`names.csv`の保存済み対応を使用します。自動解決できない名前やロール、画像はログの警告を確認し、必要に応じてCSVまたはJSONを修正します。

一覧は前週との差分を前提にしているため、新ヒーローがスコア一覧へ載るのは原則として登場翌週からです。

## 予想ラウンドの運用

予想ラウンドは`data/prediction_round.json`で管理します。各ラウンドには一意な`round_id`と、少なくとも次の項目が必要です。

- `published_at`: 公開日時（ISO 8601）
- `closes_at`: 投票と掲示板を締め切る日時（ISO 8601）
- `result_after`: 結果判定に使う能力調整の基準日
- `predictions`: 予想ヒーロー、方向、確率、理由の一覧

新ラウンド用JSONを作成したら、次のコマンドで履歴へ追加し、公開対象を切り替えます。

```bash
python tools/manage_prediction_rounds.py publish path/to/new_round.json
```

現在のラウンドと結果取得状況を確認します。

```bash
python tools/manage_prediction_rounds.py status
```

`closes_at`を過ぎるとPHP API側でも受付を拒否します。`result_after`以降で最初の能力調整データが取得されると、予想した方向と実際の上方・下方修正を照合し、次回のページ生成時に結果を掲載します。

投票数とコメントはラウンドごとにWeb公開ディレクトリの一つ上にある`hok_vote_data/`へ保存します。FTP更新で上書きされず、ラウンドを切り替えても投票データを分離して保持できます。

### コメント管理

コメントIDを確認します。

```bash
python tools/manage_prediction_comments.py list
```

指定したコメントを削除します。

```bash
python tools/manage_prediction_comments.py delete <comment_id>
```

管理トークンはGit管理外の`.comment-admin-token`、または環境変数`HOK_COMMENT_ADMIN_TOKEN`から読み込みます。管理トークンを送るAPI URLにはHTTPSが必要です。返信がある親コメントはスレッド構造を維持するため「削除済み」表示にし、返信がないコメントはデータから削除します。

## ローカル実行

Python 3、Google Chrome、PHP 8系を使用します。

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

HOKCAMPからの取得を含む一連の生成処理は次の順番で実行します。

```bash
python get_html.py
python get_adjustments.py
python sync_new_heroes.py
python main.py
```

保存済みの`html.txt`、CSV、調整キャッシュだけからページを再生成する場合は`python main.py`のみで実行できます。

テストは次のコマンドで実行します。

```bash
php -l list_html/api/prediction_votes.php
php -l list_html/api/prediction_comments.php
python -m unittest discover -s tests -v
```

`list_html/for_pc/`、`list_html/for_mobile/`、`list_html/heroes/`、`list_html/predictions/`の大部分は自動生成物です。恒久的な表示変更は`hok_tools/template_*.html`または生成処理へ加えてください。

## 主なファイル

| パス | 役割 |
| --- | --- |
| `.github/workflows/main.yml` | 週次ビルド、テスト、自動コミット、FTP公開 |
| `get_html.py` | HOKCAMPランキングHTMLの取得と日本語名への変換 |
| `get_adjustments.py` | 全ヒーローの能力調整履歴の取得とキャッシュ更新 |
| `sync_new_heroes.py` | 新ヒーローの名前、ロール、アイコンの同期 |
| `main.py` | CSV保存と全ページ生成のエントリーポイント |
| `names.csv` | 日本語名と英語アセット名の対応表 |
| `hero_categories.json` | ロール別ヒーロー分類 |
| `data/hero_adjustments.json` | 能力調整履歴のキャッシュ |
| `data/prediction_round.json` | 予想ラウンドの設定と履歴 |
| `csv/` | 日付別の週次スナップショット |
| `hok_tools/` | スコア計算、履歴集計、テンプレート、ページ生成処理 |
| `list_html/` | FTPで公開するHTML、API、画像、JavaScript |
| `list_html/legal/` | 利用規約、プライバシーポリシー、免責事項、投稿ガイドライン |
| `tools/` | 予想ラウンドとコメントの管理コマンド |
| `tests/` | ページ生成、調整履歴、予想、投票、コメントAPIのテスト |

## スコア計算

基本方針は、勝率・使用率・BAN率が高いヒーローほど高いスコアにすることです。高勝率でも使用率が極端に低い場合は、一部の熟練プレイヤーによるノイズの可能性を考慮します。

### 勝率基礎点

```python
diff = win_rate - average_win_rate
W = average_win_rate + kw * (math.exp(diff / 10) - 1)
```

高い勝率をさらに伸ばすほど難しいと考え、平均との差を指数関数で重み付けします。

### 使用率補正

```python
pick_correction = ku * sigmoid(pick_rate, alpha, c * average_pick_rate)
```

ロールごとのヒーロー数の差を考慮し、シグモイド関数で補正を頭打ちにします。

### BAN率加点

```python
B = kb * ban_rate / 100
```

BAN率は線形で加点します。

### 最終スコア

```python
total_score = W + pick_correction + B
baseline = 50 + ku * sigmoid(average_pick_rate, alpha, c * average_pick_rate)
correction = 50 - baseline
total_score += correction
```

勝率と使用率が平均、BAN率が0%のヒーローがスコア50になるように補正しています。
