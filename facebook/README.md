# Facebook連携（初期実装・未検証）

Meta Graph API (v26.0) を使い、Facebookページの投稿一覧・Reels一覧と、
可能な範囲でインサイト（再生数・視聴時間・リテンション等）を取得してCSV/JSONに保存する。

## セットアップ（初回のみ）

### Meta Developer App側の準備

Instagram連携で作成済みの`goriction-sns-analytics`というMeta appに、機能を追加する形で進める。

1. [developers.facebook.com](https://developers.facebook.com) のアプリ管理画面で`goriction-sns-analytics`を開く
2. 製品として「Facebook ログイン」を追加
3. 「Facebookログイン」の設定で、有効なOAuthリダイレクトURIに `http://localhost:8080/callback` を追加
4. アプリの「設定」→「ベーシック」から **App ID** と **App Secret** を控える
5. ゴリクションのFacebookページで、このアプリのテスターまたは管理者として自分自身を設定しておく（開発モードのアプリは、テスター/管理者に登録した本人のページに対してのみ、審査なしでpages系権限を使える）

### ローカル側の準備

1. `secrets/app_id.txt`, `secrets/app_secret.txt` にそれぞれApp ID / App Secretを保存（Gitにはコミットしない）
2. 管理しているFacebookページが複数ある場合のみ、`secrets/page_name.txt` に対象ページ名を1行書く（1つしか管理していなければ不要）
3. venv作成・依存インストール:
   ```
   cd facebook
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

## 使い方

```
update_facebook.bat
```

初回実行時のみ、ブラウザが自動で開いて認証(許可)画面が出る。許可すると
`http://localhost:8080/callback`にリダイレクトされ、スクリプトが自動で
続きを進める。ページアクセストークンは`secrets/token_cache.json`に保存
され(Gitにはコミットしない)、長期ユーザートークンから発行しているため
通常は期限切れしない。

## 出力ファイル

- `exports/posts.csv`：投稿ID・投稿日時・本文・URL・種類
- `exports/post_snapshots.csv`：投稿ごとのリアクション数・コメント数・シェア数(実行時点のスナップショット)
- `exports/reels.csv`：Reel ID・投稿日時・説明文・URL・長さ
- `exports/reel_snapshots.csv`：Reelごとの再生数・視聴時間等(取得できたものだけ。取得失敗した指標は`<指標名>_error`列にエラー内容を記録)
- `exports/reel_retention.json`：Reelごとの視聴維持率グラフ(区間データなのでJSON)
- `exports/page_daily.csv`：ページ全体Insights(取得できた場合のみ。100いいね未満のページでは失敗する可能性が高い)

## 重要な注意（実行前に必ず読むこと）

- **書き込み系操作は一切行わない**（投稿・削除・返信・リアクション等はしない。取得のみ）。
- **ページ全体のInsights（`page_daily.csv`）は、100いいね未満のページでは取得できない可能性が高い。** ゴリクションのFacebookページがこの条件を満たすかは未確認。失敗した場合はエラーメッセージをそのまま記録するので、それを見て次の判断をする。
- **Reel単体の`video_insights`は、ページ規模の下限が公式ドキュメントに明記されていない。** `fetch.py`は指標を1つずつ個別に叩いて、このページ規模で実際に何が取得できるかをテストする（`reel_snapshots.csv`の`<指標名>_error`列、および実行時のコンソール出力にある「指標ごとの取得可否」を参照）。
- 2026年にFacebook Insightsの指標が大きく変更されており、`page_impressions`・`post_impressions`等の古い指標名は使っていない（廃止済み）。現行の指標名（`page_follows`・`post_video_avg_time_watched`等）を使用しているが、Meta側の仕様変更で今後も名前が変わる可能性がある。
- `secrets/`以下（App ID・Secret・token_cache.json）は絶対にコミットしない（`.gitignore`で除外済み）。

## 実データでの検証結果（2026-09-27、実機）

ページ「ゴリクション goriction」（page_id: 1403366112859905）で実行しエラーなく完走。

- 投稿2件（Reel 1件・写真投稿1件）、Reel 1件を取得
- **`video_insights`は7指標中6指標が値を取得できた**：`blue_reels_play_count`（再生数182）・`fb_reels_replay_count`（リプレイ数6）・`post_video_avg_time_watched`（平均視聴時間2908ミリ秒）・`post_video_retention_graph`（区間ごとのリテンション率、`reel_retention.json`に保存）・`post_video_social_actions`・`post_video_followers`
  - `total_video_view_total_time`だけHTTP 200だが中身が空(`{"data": []}`)。この指標はReelではなく通常動画向けの可能性が高い（Reel向けの総視聴時間を取りたい場合は別の指標を要調査）
  - **ページ規模の下限が無いという想定通り、100いいね未満でもvideo_insightsは機能した**
- **ページ全体Insights（`page_follows`・`page_views_total`・`page_post_engagements`）も、エラーにはならず200 OKで返ってきた。** ただし値はいずれも0。ページが実際に0人フォロワー相当なのか、データ量不足でAPIが黙って0を返しているのかは、フォロワーが増えてから再実行して切り分ける必要がある（「100いいね未満は失敗する」という事前の想定ほど単純ではなさそう）

## 未検証・要確認事項

- ページ全体Insightsの値が「本当の0」か「データ不足による黙示的な0」かの切り分け（フォロワー増加後に再検証）
- Reel向けの総視聴時間に相当する正しい指標名の調査（`total_video_view_total_time`はReelでは空だった）
- 投稿・Reelsが増えた場合のページング動作

`update_facebook.bat`を実行してエラーが出たら、そのエラーメッセージを教えてもらえれば修正する。
