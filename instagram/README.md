# Instagram連携（初期実装・未検証）

Meta for Developersで発行したアクセストークンを使い、Instagram Graph API
（Instagramログイン版、graph.instagram.com）から自分の投稿一覧・コメントを
取得してCSVに保存する。

## セットアップの前提（すでに完了済み）

- Instagramアカウントをクリエイターアカウントに切り替え済み
- Meta for Developersでアプリ`goriction-sns-analytics`を作成済み
- Instagram Login（Facebookページ連携不要）でアクセス許可を設定済み
- 自分をInstagramテスターとして登録・承認済み
- アクセストークンを発行し、`secrets/access_token.txt`に保存済み（1行のみ、平文）

## セットアップ（初回のみ）

```
cd instagram
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 使い方

```
update_instagram.bat
```

`exports/media.csv` に、投稿ごとの一覧・いいね数・コメント人数などを出力する。

## 重要な注意

- **`unique_commenters` の計算方法はYouTube版と同じ方針**（トップレベルコメント＋
  全返信を取得し、投稿者のusernameで重複排除、自分自身を除外）。TikTokと違い
  Instagramのコメントにはusernameが付くため、この集計が可能。
- ただし識別に使っているのは**username**であり、YouTube版のような安定した
  ユーザーIDではない（ユーザー名の変更で別人扱いになる可能性がある）。
- `secrets/access_token.txt` は絶対にコミットしない（`.gitignore`で除外済み）。
  トークンはMeta for Developersのダッシュボードで再発行できる。

## 未検証・要確認事項（重要）

このスクリプトは実際のAPIレスポンスで動作確認できていない。TikTok版と同じく、
実際に実行してエラーが出たら、その内容を元に修正する前提。特に以下が不明:

- `media`エンドポイントのフィールド名（`media_product_type`等）が実際に
  返ってくるか
- コメントの`replies`取得方法（`/{comment-id}/replies`エンドポイント）が
  想定通りページングできるか
- レート制限（`REQUEST_DELAY_SEC`で簡易的に待機を入れているが、投稿数・
  コメント数が多い場合は調整が必要かもしれない）

`update_instagram.bat`を実行してエラーが出たら、そのエラーメッセージを
教えてもらえれば修正する。
