# TikTok連携（初期実装）

TikTok Studioで手動ダウンロードしたCSVを、整理・蓄積するだけの仕組み。

## 経緯（なぜブラウザ自動化をやめたか）

最初はPlaywrightでブラウザ操作を自動化し、ログイン→ダウンロードまで一気通貫で
自動化しようとした。しかし:

1. 自動化専用のブラウザで自動ログインを試みたところ、TikTok側に
   「自動化されたブラウザ」として検知され、認証コード入力が
   「試行回数の上限」で弾かれてログインできなかった。
2. 「ログインは人間が普段のEdgeで行い、スクリプトはリモートデバッグモードで
   そのEdgeに接続してボタンを押すだけ」という方式に変更したが、
   リモートデバッグモードを有効にしただけで（何も自動操作していない段階で）
   TikTok側からHTTP 403で弾かれた。

つまりTikTokは、CDP（Chrome DevTools Protocol）で外部から操作可能な状態の
ブラウザそのものを検知してブロックしてくる。Selenium（WebDriverプロトコル）も
内部的には同種の痕跡を残すため、同じ壁にぶつかる可能性が高い。

これ以上、検知を回避する方向（フィンガープリント偽装など）に進むのは
TikTokの不正対策への正面突破になるため行わない。**ブラウザの自動操作は諦め、
「手動ダウンロード」＋「そのCSVの整理だけを自動化する」**方式に変更した。

## 使い方

### 1. セットアップ（初回のみ）

```
cd tiktok
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

（Playwrightは使わなくなったので、Chromiumのダウンロードは不要）

### 2. TikTok Studioで手動ダウンロード

1. 普段どおりEdgeでTikTok Studio（studio.tiktok.com、またはアプリ内Analytics）を開く
2. Analytics（Content / Overview / Followers / Viewers など各タブ）で期間を指定し、
   「データをダウンロード」をクリック。TikTok Studioの仕様でZIPファイルとして
   `Downloads` フォルダに保存される
3. ダウンロードしたZIPはそのままでよい（展開・移動は次のステップが自動でやる）

### 3. 更新を実行

```
update_tiktok.bat
```

をダブルクリックするだけでOK。内部では以下を順番に実行している。

1. `import_downloads.py` — `Downloads` フォルダにある
   `Content_*.zip` / `Overview_*.zip` / `Followers_*.zip` / `Viewers_*.zip` を探して展開し、
   中身を `exports/inbox/` にCSVとしてコピーする。TikTok Studioのダウンロード形式設定に
   よってZIPの中身がCSVの場合とExcel（`.xlsx`）の場合があるが、`.xlsx`の場合は自動で
   読み込んでCSVに変換するのでどちらでもよい。処理済みのZIPは
   `exports/downloads_processed/` に移動する（二重取り込み防止）。
2. `normalize_export.py` — `exports/inbox/` にある未処理のCSVをファイル名から種類判定し、
   それぞれ以下に正規化・追記する。処理済みファイルは `exports/processed/` に移動する。

どちらのスクリプトもTikTokには一切アクセスしない、純粋なローカルのファイル処理。
（コマンドプロンプトから個別に実行したい場合は `.venv\Scripts\python import_downloads.py`
→ `.venv\Scripts\python normalize_export.py` の順に実行してもよい）

| 入力ファイル | 出力先 | 内容 |
|---|---|---|
| `Content*.csv` | `exports/videos.csv` | 動画ごとの一覧・累計値 |
| `Overview*.csv` | `exports/channel_daily.csv` | チャンネル全体の日別値 |
| `FollowerHistory*.csv` | `exports/follower_daily.csv` | フォロワー数の日別推移 |
| `Viewers*.csv` | `exports/viewers_daily.csv` | 視聴者数の日別推移 |
| 上記以外（`FollowerGender.csv`等） | 未対応（整理せずprocessedへ） | 今後必要になれば対応を追加 |

## 重要な注意

- `videos.csv` の `comment_count_raw`（コメント数）は「件数」であり、YouTube版の
  `unique_commenters`（本人除外・返信込みのユニーク投稿者数）とは意味が異なる。
  TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）ため、
  `unique_commenters` 列は常に空欄になる。
- 日付列（「9月16日」のような表記）には年が含まれない。年をまたいで蓄積する場合、
  同じ月日が複数年分混在する可能性があるので注意する。
- TikTok Studioの分析期間は最大60日までしか遡れない。定期的に手動ダウンロードして
  蓄積する運用が前提。

## 動作確認済み

- 実際にTikTok Studioからダウンロードしたzip（`Content_goriction.zip` 等4件、CSV形式・
  Excel形式の両方）で、`import_downloads.py`（zip展開→CSV化、CSV7件）→
  `normalize_export.py`（動画15件・日別7行を取り込み）まで一気通貫で動作確認済み。
- `FollowerGender.csv`、`FollowerTopTerritories.csv`、`Viewers.csv` は今回中身が空
  （データがまだ少ないアカウントのため）だったので、実データでの整理は未確認。
