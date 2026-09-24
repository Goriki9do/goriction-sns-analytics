# 初回設定

**保存フォルダーはruntime.local.batのSNS_DATA_HOMEで指定します。このPCでは `C:\Users\81801\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\GorikushonSNS` です。** 以下のsecrets、vendorはこのフォルダー内を指します。open_data.batで開けます。Codexからの保存がWindowsによって専用領域に振り分けられたため、通常の起動でも読める実際のパスに統一しました。保護設定は変更していません。Codexをアンインストール・リセットする前にはこの保存フォルダーをバックアップしてください。

1. Google Cloud Consoleで専用プロジェクトを作成。課金アカウントや無料トライアル登録は不要な構成です。もし請求登録を要求されたらそこで止めて確認してください。
2. APIとサービス → ライブラリで **YouTube Data API v3** と **YouTube Analytics API** を有効化。
3. Google Auth Platformのブランディングを設定。名前はGorikushon SNS Analytics、連絡先は自分のメール。
4. 個人Googleアカウントなら対象はExternalを選び、公開ステータスはTestingのまま。Externalという対象種別はアプリ一般公開とは別です。Test usersに自分だけを登録。Publish appは押しません。
5. データアクセスは `youtube.readonly`、`yt-analytics.readonly`、`youtube.force-ssl`。コメント一覧のOAuth取得にはforce-sslが必要で、動画・評価・コメント・字幕の編集と削除も含む広い権限です。2026-09-24にユーザー承認を得て追加しました。プログラムが使うAPIは取得のみです。
6. OAuthクライアントを **デスクトップアプリ** として作成。ダウンロードしたJSONを保存フォルダーの `secrets/client_secret.json` に保存。JSONをチャットに貼らないでください。
7. run_youtube.batを開く。Google公式認証先への送信を許可した場合だけ認証を開始します。認証でゴリクションのチャンネルを選択。ブランドアカウントを使う場合は対象チャンネルの選択を確認。
8. 完了時のチャンネル名・動画数・日別行数を確認し、exports配下のCSVを開く。0行の場合は実データ検証完了とは扱いません。

## 認証情報

secretsにはOAuthクライアント情報とrefresh tokenが保存されます。ローカル認証時、認証コード・トークン・クライアント情報をGoogle公式OAuthエンドポイントへ送信する必要があります。API要求もGoogleへ送ります。それ以外への認証情報送信はありません。認証の返信を受けるローカルサーバーは127.0.0.1のみで一時的に起動します。

Testing状態のExternalアプリでは通常refresh tokenが7日で期限切れになり、ブラウザーで再認証が必要です。期限回避のためにアプリを一般公開することはしません。PCの通常ユーザー権限でファイルを保護し、secretsを共有/同期先へ移さないでください。利用終了時はGoogleアカウントの接続済みアプリで権限を取り消せます。

## 実行環境

このPCではruntime.local.batに指定したCodex同梱Pythonを使い、依存ライブラリはvendorにローカル保存します。PythonやCodexの移動後に起動できなくなったら、Python 3.12以上を公式サイトから入れ、runtime.local.batのSNS_PYTHONをそのpython.exeへ変更してください。新しいPythonへ移す際は対応するライブラリを別vendorフォルダーに再インストールしてください。

## 問題の対処

- client_secret.jsonなし: 手順6を完了。
- HTTP 403: 両APIの有効化、テストユーザー、チャンネル所有権、取得上限を確認。上限の場合は翌日の再実行。課金を有効にして解決しようとしない。
- HTTP 400: APIの指標/軸の組み合わせ、日付、認証設定を確認。
- RefreshError/認証拒否: 再認証、テストユーザー、対象チャンネルを確認。
- PermissionError/OSError: 同時実行中、ExcelでCSVを開いている、またはファイルのアクセス権を確認。
- 通信失敗: インターネット接続確認後に再実行。通常の一時的HTTP失敗は最大4回再試行します。

テストは一時フォルダーの架空データのみを使用し、本番DBに混在しません。
