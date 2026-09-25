"""
X API v2から、自分のアカウントの投稿一覧・リプライを取得してCSVに保存する。

YouTube/Instagram版と同じ方針で、コメント(リプライ)は「件数」ではなく
「本人除外・重複排除後のユニーク投稿者数」を主指標(unique_commenters)
として記録する。識別キーはusername(Instagram版と同じ制約: ユーザー名
変更で別人扱いになりうる)。

重要な制約:
    リプライの取得には search/recent エンドポイントを使うが、これは
    直近7日以内の投稿しか検索できない(標準の制約)。7日より前の投稿への
    リプライは、現状このスクリプトでは取得できない(unique_commentersが
    実際より少なく出る)。

事前準備:
    secrets/client_id.txt, secrets/client_secret.txt に
    X Developer Consoleで発行したOAuth 2.0のClient ID/Secretを
    1行だけ保存しておく(auth.pyが初回にブラウザ認証を行う)。

使い方:
    python fetch.py
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

from auth import get_access_token

HERE = Path(__file__).parent
EXPORTS_DIR = HERE / "exports"

API_BASE = "https://api.x.com/2"
REQUEST_DELAY_SEC = 0.3  # レート制限を避けるための最低限のウェイト

TWEET_FIELDS = "created_at,public_metrics"
REPLY_TWEET_FIELDS = "created_at,author_id,conversation_id"


def api_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{API_BASE}/{path}" if not path.startswith("http") else path
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
    time.sleep(REQUEST_DELAY_SEC)
    if resp.status_code != 200:
        print(f"警告: {path} の取得でHTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    return resp.json()


def get_own_account(token: str) -> dict:
    data = api_get("users/me", token, {"user.fields": "public_metrics"})
    return data["data"]


def get_all_own_tweets(user_id: str, token: str) -> list[dict]:
    tweets: list[dict] = []
    pagination_token = None
    while True:
        params = {"tweet.fields": TWEET_FIELDS, "max_results": 100}
        if pagination_token:
            params["pagination_token"] = pagination_token
        page = api_get(f"users/{user_id}/tweets", token, params)
        tweets.extend(page.get("data", []))
        pagination_token = page.get("meta", {}).get("next_token")
        if not pagination_token:
            break
    return tweets


def get_recent_replies(tweet_id: str, own_username: str, token: str) -> list[dict]:
    """直近7日以内のリプライのみ取得できる(search/recentの制約)。"""
    replies: list[dict] = []
    next_token = None
    while True:
        params = {
            "query": f"conversation_id:{tweet_id} -from:{own_username} is:reply",
            "tweet.fields": REPLY_TWEET_FIELDS,
            "expansions": "author_id",
            "user.fields": "username",
            "max_results": 100,
        }
        if next_token:
            params["next_token"] = next_token
        page = api_get("tweets/search/recent", token, params)

        users_by_id = {u["id"]: u["username"] for u in page.get("includes", {}).get("users", [])}
        for tweet in page.get("data", []):
            if tweet["id"] == tweet_id:
                continue  # 元投稿自体が混ざってきた場合は除外
            tweet["author_username"] = users_by_id.get(tweet.get("author_id"))
            replies.append(tweet)

        next_token = page.get("meta", {}).get("next_token")
        if not next_token:
            break
    return replies


def summarize_posts(tweets: list[dict], own_username: str, token: str) -> pd.DataFrame:
    rows = []
    for tweet in tweets:
        tweet_id = tweet["id"]
        metrics = tweet.get("public_metrics", {})
        reply_count_raw = metrics.get("reply_count", 0)

        replies = get_recent_replies(tweet_id, own_username, token) if reply_count_raw else []

        others_usernames = {
            r["author_username"] for r in replies if r.get("author_username") and r["author_username"] != own_username
        }

        rows.append(
            {
                "tweet_id": tweet_id,
                "permalink": f"https://x.com/{own_username}/status/{tweet_id}",
                "text": (tweet.get("text") or "")[:200],
                "created_at": tweet.get("created_at"),
                "like_count": metrics.get("like_count"),
                "retweet_count": metrics.get("retweet_count"),
                "quote_count": metrics.get("quote_count"),
                "impression_count": metrics.get("impression_count"),
                "reply_count_raw": reply_count_raw,
                "unique_commenters": len(others_usernames) if reply_count_raw else 0,
                "replies_search_window_days": 7,
                "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        )
        print(f"取得: {tweet_id} / リプライ{reply_count_raw}件 / 直近7日ユニーク{len(others_usernames)}人")

    return pd.DataFrame(rows)


def main() -> None:
    token = get_access_token()
    EXPORTS_DIR.mkdir(exist_ok=True)

    account = get_own_account(token)
    own_username = account["username"]
    tweet_total = account.get("public_metrics", {}).get("tweet_count")
    print(f"アカウント: {own_username} / {account['id']} / 累計投稿{tweet_total}件")

    tweets = get_all_own_tweets(account["id"], token)
    print(f"投稿一覧を{len(tweets)}件取得したで。リプライも順番に取得していくわ...")

    df = summarize_posts(tweets, own_username, token)

    output_path = EXPORTS_DIR / "posts.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"完了。{len(df)}件を {output_path} に保存したで。")
    print("注意: リプライは直近7日以内のみ検索対象。7日より前の投稿はunique_commentersが過小になる。")


if __name__ == "__main__":
    main()
