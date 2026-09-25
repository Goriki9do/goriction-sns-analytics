# X連携（初期実装・未検証）

X API v2 (OAuth 2.0, Authorization Code + PKCE) を使い、自分の投稿一覧・
リプライを取得してCSVに保存する。

## セットアップの前提（すでに完了済み）

- X Developer Portal (console.x.com) で開発者アカウントを作成済み
- Pay-per-useのクレジットを$5チャージ済み
- アプリを作成し、User authentication settings (OAuth 2.0) を
  「Web App, Automated App or Bot」(confidential client) / Read only / 
  Callback URI `http://localhost:8080/callback` で設定済み
- Client ID・Client Secretを`secrets/client_id.txt`・
  `secrets/client_secret.txt`に保存済み

## セットアップ（初回のみ）

```
cd x
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 使い方

```
update_x.bat
```

初回実行時のみ、ブラウザが自動で開いて認証(許可)画面が出る。許可すると
`http://localhost:8080/callback`にリダイレクトされ、スクリプトが自動で
続きを進める。以後はrefresh_tokenで自動更新するため、通常は毎回の許可
操作は不要(`secrets/token_cache.json`に保存。Gitにはコミットしない)。

`exports/posts.csv` に、投稿ごとの一覧・いいね数・リツイート数・
インプレッション数・リプライ人数などを出力する。

## 料金について

pay-per-use。自分の投稿の読み取りはowned reads扱いで1件$0.001、
リプライ(他人の投稿)の検索・読み取りは1件$0.005。このアカウント規模
(投稿数十件、リプライ数件程度)なら月あたり数十〜数百円程度の想定。
チャージ残高は console.x.com > クレジット で確認できる。

## 重要な注意

- **リプライの取得は`search/recent`エンドポイントを使うため、直近7日
  以内の投稿しか対象にできない**(標準アクセスの制約)。7日より前の
  投稿は`unique_commenters`が実際より少なく出る、または0のまま。
  7日を超えた過去分もまとめて取りたい場合は、full-archive search
  エンドポイントの利用可否を別途確認する必要がある(未調査)。
- `unique_commenters`の識別キーは**username**であり、YouTube版のような
  安定したユーザーIDではない(ユーザー名変更で別人扱いになる可能性)。
- `secrets/`以下(Client ID・Secret・token_cache.json)は絶対にコミット
  しない(`.gitignore`で除外済み)。

## 未検証・要確認事項（重要）

このスクリプトは実際のAPIレスポンスで動作確認できていない。
Instagram版と同じく、実際に実行してエラーが出たら、その内容を元に
修正する前提。特に以下が不明:

- OAuth 2.0のトークン交換・リフレッシュが想定通り動くか
- `users/:id/tweets`・`tweets/search/recent`のフィールド名が実際に
  返ってくる形と一致しているか
- レート制限(`REQUEST_DELAY_SEC`で簡易的に待機を入れているが、投稿数・
  リプライ数が多い場合は調整が必要かもしれない)

`update_x.bat`を実行してエラーが出たら、そのエラーメッセージを教えて
もらえれば修正する。
