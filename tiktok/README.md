# TikTok連携（初期実装）

普段使っているEdgeブラウザに外から接続して、TikTok Studioの画面からCSVを自動ダウンロードする。

## 方式について（重要）

最初はPlaywrightで新規に自動化専用ブラウザを立ち上げてログインまで自動化しようとしたが、
TikTok側に「自動化されたブラウザ」として検知され、認証コード入力が「試行回数の上限」で
弾かれてログインできなかった。

そのため方式を変更し、**ログインは今までどおり人間が普段のEdgeで行い、スクリプトは
「もうログイン済みの本物のEdge」に外部から接続してボタンを押すだけ**にしている。
新しい自動化用プロファイルは作らない。

- パスワードや認証情報はどこにも保存しない。
- ログインは自動化しない。あなたが普段どおりEdgeで行う。
- スクリプトが自動化するのは「ダウンロードボタンを押す」部分だけ。
- それでもボタンを自動で押している以上、TikTokの利用規約上のグレーさは残る。
  UI変更で壊れる前提で運用し、異常（大量のCAPTCHA表示やアカウント制限など）が
  出たらすぐ使用を止めること。

## 使い方

### 1. セットアップ（初回のみ）

```
cd tiktok
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
```

### 2. Edgeをリモート操作モードで開く

```
launch_edge_debug.bat
```

いったん今開いているEdgeを閉じて、外部から操作できるモードで開き直す
（プロファイル・ログイン状態・お気に入りはそのまま引き継がれる）。

### 3. Edge側でいつも通りTikTokにログイン

開いたEdgeで、普段どおり手動でTikTokにログインし、TikTok Studioの
分析（Content）画面まで開いておく。

### 4. ダウンロードを実行

```
.venv\Scripts\python export_studio_csv.py
.venv\Scripts\python normalize_export.py
```

`exports/videos.csv` に正規化済みデータが追記される。生CSVは
`exports/tiktok_studio_raw_*.csv` として残る。

## 重要な注意

- コメント数は「件数」であり、YouTube版の `unique_commenters`
  （本人除外・返信込みのユニーク投稿者数）とは意味が異なる。
  TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）。
  `videos.csv` の `unique_commenters` 列は常に空欄になる。
- TikTok Studioの分析期間は最大60日までしか遡れない。定期的に実行して蓄積する前提。
- `launch_edge_debug.bat` 内のEdgeのインストールパスは環境によって異なる場合がある。
  見つからなければ `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"` の
  部分を実際のパスに書き換えること。

## 未検証・要確認事項

- `export_studio_csv.py` のダウンロードボタンの探し方（`DOWNLOAD_BUTTON_TEXT_CANDIDATES`）は
  実際のTikTok Studio画面で検証していない。見つからない場合はエラーメッセージに従って
  保存されるスクリーンショットを確認し、候補文言を追加すること。
- `normalize_export.py` の列名候補（`COLUMN_CANDIDATES`）も同様に、実際にダウンロードした
  CSVのヘッダーを見て調整が必要。
