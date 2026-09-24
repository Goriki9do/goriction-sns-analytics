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
2. Analytics > Content で期間を指定し、「データをダウンロード」をクリック
3. ダウンロードしたCSVファイルを `tiktok/exports/inbox/` フォルダに置く
   （ファイル名はTikTokが付けたままでよい）

### 3. 整理を実行

```
.venv\Scripts\python normalize_export.py
```

`exports/inbox/` にある未処理のCSVをすべて `exports/videos.csv` に正規化・追記し、
処理済みファイルは `exports/processed/` に移動する。このスクリプトはTikTokには
一切アクセスしない、純粋なローカルのファイル処理。

## 重要な注意

- コメント数は「件数」であり、YouTube版の `unique_commenters`
  （本人除外・返信込みのユニーク投稿者数）とは意味が異なる。
  TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）。
  `videos.csv` の `unique_commenters` 列は常に空欄になる。
- TikTok Studioの分析期間は最大60日までしか遡れない。定期的に手動ダウンロードして
  蓄積する運用が前提。

## 未検証・要確認事項

- `normalize_export.py` の列名候補（`COLUMN_CANDIDATES`）は、実際にダウンロードした
  CSVのヘッダーを見て調整が必要。列が見つからない場合は警告を出して空欄で埋めるので、
  実行結果を見て `normalize_export.py` 内の候補リストに実際の列名を追加すること。
