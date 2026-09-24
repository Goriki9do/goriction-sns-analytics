# YouTube連携

Notionの記録上のオリジナルは
`C:\Users\81801\Documents\Codex\2026-09-23\referenced-chatgpt-conversation-this-is-an-2\outputs\gorikushon-sns`
にあった。TikTok版と同じ場所（このリポジトリ）にまとめるため、ここへコード一式を移した。

`secrets/`・`data/`・`exports/`（認証情報・実データ）はこのリポジトリには含まれない
（`.gitignore`で除外）。`runtime.local.bat`もPC固有のパスを含むためコミットしない。
新しいPCでセットアップする場合は、元のNotionページ「YouTube初回設定の流れ」を参照して
`runtime.local.bat`を手動で作成すること。

使い方はこのフォルダ内の `README.md`（元プロジェクトのもの）・`SETUP.md`・`TEST_RESULTS.md`
を参照。

## exports_local/ について

実データは `runtime.local.bat` の `SNS_DATA_HOME`（AppData配下）に保存される仕様のまま
変更していない（歴史的にこのパスまわりで一度不具合が出ているため、触らずそのままにした）。
見つけやすくするため、`sync_exports.py` を実行すると最新のCSVを `exports_local/` へ
コピーしてくる（このフォルダもコミットしない。あくまでローカルの確認用コピー）。

```
python sync_exports.py
```

リポジトリ直下の `update_all.bat` を実行すると、TikTok更新→YouTube更新→この
`exports_local/` へのコピーまで自動で行われる。
