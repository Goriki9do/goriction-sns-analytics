# ゴリクション SNS分析 v0.1

YouTube公式API → このPCのSQLite・CSV。Python 3.12以上。投稿・削除・公開設定の変更は行いません。

**このPCの実データ保存先は `C:\Users\81801\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\GorictionSNS`（open_data.batで開く）です。以下のdata/exports/secrets/config.jsonはすべてこの保存先を基準にしています。** Codexからの保存がWindowsによって専用領域に振り分けられていたため、通常起動でも同じ実体を使えるようruntime.local.batに実際のパスを指定しています。Codexをアンインストール・リセットする前には、このフォルダーをローカルでバックアップしてください。

## 実行

初回は **SETUP.md** の設定後、**run_youtube.bat** をダブルクリック。以後も同じファイルで更新します。

このPCでは2026-09-24に初回設定・実データ取得を完了済みです。接続先は **ゴリクション / UCYV5uFCKBYG1lRlA8TbAScw**。通常はrun_youtube.batだけで更新できます。最新CSVは **open_exports.bat** で開けます。analysis-exportは検証時点のコピーで、自動更新されません。
初回の標準取得範囲は90日前〜3日前。APIの日付は米国太平洋時間です。初回の開始日はconfig.jsonに保存します。

```
python run.py --allow-google-auth --start 2020-01-01 --full-refresh
python run.py --export-only
python -m unittest discover -s tests -v
```

`--full-refresh` は指定期間の再取得。日常の更新は保存済み最終分析日の28日前から重複して取得します。新動画は設定した開始日から取得。古い期間の修正は明示的な再取得で反映します。`--start` の指定はその実行に適用され、標準開始日を変える場合はconfig.jsonを編集してください。

## 保存先と分析方法

- `data/sns.sqlite3`: 全データ。チャンネルIDで分離。
- `exports/<チャンネルID>/videos.csv`: タイトル、ID、公開日時、動画時間、現在の累計再生・高評価・コメント人数（unique_commenters）。
- `video_daily.csv`: 動画×日×コンテンツ種別。再生数、engagedViews、総再生時間（分）、平均視聴時間（秒）、平均再生率（%）、登録増・減・差。
- `channel_daily.csv`: チャンネル全体の日別値。動画で直接発生しない登録増減も含み得るため、動画別合計と区別。
- `snapshots.csv`: 実行時点ごとの累計と前回差。差は日別再生数と同義ではなく、訂正で負になることもあります。
- `manifest.json`: 取得期間・実行日時・行数。

ChatGPTには必要なCSVとこのREADME、manifestを添付し、「Shortsの直近20本を平均再生率と登録者獲得で比較して」のように依頼できます。本アプリからChatGPTへ自動送信はしません。非公開動画のタイトルも含みます。

## 数字の読み方

コメント人数は `videos.csv` の **unique_commenters**。動画ごとにコメントと返信を全ページ取得し、投稿者のYouTubeチャンネルIDで重複を除き、ゴリクション自身のチャンネルIDを除外します。同じ相手と何度やり取りしても1人です。毎回数え直し、削除による減少も反映します。取得時点でAPIから見える既存コメント全体が対象で、Analyticsの指定期間には限定しません。人間の実人数ではなくアカウント単位で、動画間の単純合計はチャンネル全体の人数にはなりません。

`commenter_status=complete` は取得したコメントの投稿者IDを全件識別できた状態。ID不明がある場合は `partial_missing_author_id` とし、人数は識別できた範囲、`unidentified_comments` が不明コメント件数です。コメント無効時は `comments_disabled` と人数空欄。`own_comments_excluded` は除外した本人のコメント・返信件数です。削除済み・非表示などAPIで読めないコメントは数えられません。本文や相手のIDは保存しません。

従来の件数は比較用に `comment_count_raw`、日別Analyticsの件数は `comment_events_raw` と明記して残します。どちらも人数ではありません。変更前の履歴には人数がないため空欄です。SQLiteでは `commenter_snapshots` に取得時点ごとの人数を保存します。

空欄・API未返却行は未報告/不明であり、0として補完しません。Shorts種別はAPIのcreatorContentType（今回の実値はshorts、videoOnDemand、creatorContentTypeUnspecified）をそのまま保存します。分析行がなければ未判定です。集計遅れのため3日前でも未確定の可能性があります。平均値の日別単純平均は期間平均ではありません。ShortsのviewsとengagedViewsは定義が異なるため、平均再生率などと合わせて読みます。登録増減は動画別では当該動画に帰属する範囲です。Data APIの累計とAnalyticsの期間値は定義・時点が異なります。

取得成功後にSQLiteを一括更新。失敗時は既存データを保持し再実行できます。CSV出力だけが失敗した場合はExcelを閉じてexport_saved.batを実行してください。CSVはUTF-8 BOM付きで、数式扱いされる文字列には先頭にアポストロフィを付けます。元タイトルはSQLiteに保持します。削除などで一覧に出なくなった動画はavailable=0として履歴を残します。削除動画の新しい分析値は取得対象外です。

## 構成・拡張

`sns/providers/youtube.py`がAPI依存部分、`sns/auth.py`が認証、`sns/storage.py`が保存・出力、`run.py`が実行管理です。Instagram/TikTok/X追加時はprovidersに実装を追加し、各サービスの認証と指標を別定義で接続します。現在の実行・エクスポートはYouTube専用で、他SNS対応済みという意味ではありません。

## 公式資料

- https://developers.google.com/youtube/analytics/channel_reports
- https://developers.google.com/youtube/analytics/metrics
- https://developers.google.com/youtube/analytics/reference/reports/query
- https://developers.google.com/youtube/v3/docs/playlistItems/list
- https://developers.google.com/identity/protocols/oauth2/native-app
