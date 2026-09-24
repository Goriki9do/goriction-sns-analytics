# TikTok連携（初期実装）

TikTok Studioのブラウザ画面から、手動ログイン＋自動CSVダウンロードでデータを取得する。

## 方式について

- TikTokの公式Display APIは自分の投稿一覧・基本統計は取れるが、コメントの
  ユニーク投稿者数（YouTube版の主指標）は取れない（Research APIは研究者限定のため利用不可）。
- そのため当面は **TikTok Studioの画面から手動でログインし、以降はそのログイン状態を
  再利用してCSVダウンロードだけ自動化する** 方式を採る。
- パスワードや認証情報は保存しない。保存するのはブラウザのログインセッション（Cookie）のみで、
  `.auth/` に置かれ、`.gitignore` でコミット対象から除外している。
- セッションは切れることがある。切れたら `login.py` をもう一度実行して手動で入り直す。
- ここはブラウザ操作の自動化であり、TikTok公式APIの範囲外。UI変更で壊れる前提で運用し、
  規約上のグレーさがある点は把握した上で使う。

## セットアップ（初回のみ）

```
cd tiktok
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

## 使い方

1. 初回、またはセッションが切れたとき:
   ```
   .venv/bin/python login.py
   ```
   ブラウザが開くので自分でTikTokにログインし、Analytics画面が表示された状態で
   ターミナルに戻ってEnterを押す。

2. 普段の更新:
   ```
   .venv/bin/python export_studio_csv.py
   .venv/bin/python normalize_export.py
   ```
   `exports/videos.csv` に正規化済みデータが追記される。生CSVは
   `exports/tiktok_studio_raw_*.csv` として残る。

## 未検証・要確認事項

- `export_studio_csv.py` のダウンロードボタンの探し方（`DOWNLOAD_BUTTON_TEXT_CANDIDATES`）は
  実際のTikTok Studio画面で検証していない。実行して見つからない場合は
  `--headed` を付けて画面を見ながら調整すること。
- `normalize_export.py` の列名候補（`COLUMN_CANDIDATES`）も同様に、実際にダウンロードした
  CSVのヘッダーを見て調整が必要。
- TikTok Studioの分析期間は最大60日までしか遡れない。定期的に実行して蓄積する前提。
