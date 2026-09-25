"""
Instagram Graph API（Instagramログイン版）から、自分のアカウントの投稿一覧・
コメントを取得してCSVに保存する。

YouTube版と同じ方針で、コメントは「件数」ではなく「返信を含む・本人除外・
重複排除後のユニーク投稿者数」を主指標(unique_commenters)として記録する。
Instagramのコメントには投稿者のusernameが付くため、TikTokと違いこの集計が
再現できる。

事前準備:
    secrets/access_token.txt に、Meta for Developersで発行した
    Instagramアクセストークンを1行だけ保存しておく。

使い方:
    python fetch.py
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
TOKEN_PATH = HERE / "secrets" / "access_token.txt"
EXPORTS_DIR = HERE / "exports"

GRAPH_BASE = "https://graph.instagram.com"
API_VERSION = "v21.0"

REQUEST_DELAY_SEC = 0.3  # レート制限を避けるための最低限のウェイト


def read_token() -> str:
    if not TOKEN_PATH.exists():
        print(f"{TOKEN_PATH} が見つからんわ。Meta for Developersで発行したアクセストークンを保存してな。")
        sys.exit(1)
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token:
        print(f"{TOKEN_PATH} が空やわ。")
        sys.exit(1)
    return token


def api_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{GRAPH_BASE}/{API_VERSION}/{path}" if not path.startswith("http") else path
    query = dict(params or {})
    query["access_token"] = token
    resp = requests.get(url, params=query, timeout=30)
    time.sleep(REQUEST_DELAY_SEC)
    if resp.status_code != 200:
        print(f"警告: {path} の取得でHTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    return resp.json()


def paginate(first_page: dict, token: str) -> list[dict]:
    items = list(first_page.get("data", []))
    next_url = first_page.get("paging", {}).get("next")
    while next_url:
        resp = requests.get(next_url, timeout=30)
        time.sleep(REQUEST_DELAY_SEC)
        if resp.status_code != 200:
            print(f"警告: ページング取得でHTTP {resp.status_code}: {resp.text[:300]}")
            break
        page = resp.json()
        items.extend(page.get("data", []))
        next_url = page.get("paging", {}).get("next")
    return items


def get_own_account(token: str) -> dict:
    return api_get("me", token, {"fields": "id,username,account_type,media_count"})


def get_all_media(user_id: str, token: str) -> list[dict]:
    first = api_get(
        f"{user_id}/media",
        token,
        {
            "fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
            "limit": 50,
        },
    )
    return paginate(first, token)


def get_all_comments_with_replies(media_id: str, token: str) -> list[dict]:
    """トップレベルコメント + 各コメントの返信を、全ページ取得してフラットなリストで返す。"""
    first = api_get(
        f"{media_id}/comments",
        token,
        {"fields": "id,text,username,timestamp", "limit": 50},
    )
    top_level = paginate(first, token)

    all_comments = list(top_level)
    for comment in top_level:
        try:
            reply_first = api_get(
                f"{comment['id']}/replies",
                token,
                {"fields": "id,text,username,timestamp", "limit": 50},
            )
        except requests.HTTPError:
            # 返信が無い/権限が無いコメントはスキップ
            continue
        replies = paginate(reply_first, token)
        all_comments.extend(replies)

    return all_comments


def summarize_media(media_list: list[dict], own_username: str, token: str) -> pd.DataFrame:
    rows = []
    for media in media_list:
        media_id = media["id"]
        comment_count_raw = media.get("comments_count", 0)

        if comment_count_raw and comment_count_raw > 0:
            comments = get_all_comments_with_replies(media_id, token)
        else:
            comments = []

        own_comments = [c for c in comments if c.get("username") == own_username]
        others_usernames = {
            c.get("username") for c in comments if c.get("username") and c.get("username") != own_username
        }

        rows.append(
            {
                "media_id": media_id,
                "permalink": media.get("permalink"),
                "caption": (media.get("caption") or "")[:200],
                "media_type": media.get("media_type"),
                "media_product_type": media.get("media_product_type"),
                "timestamp": media.get("timestamp"),
                "like_count": media.get("like_count"),
                "comment_count_raw": comment_count_raw,
                "unique_commenters": len(others_usernames) if comment_count_raw else 0,
                "own_comments_excluded": len(own_comments),
                "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        )
        print(f"取得: {media_id} / コメント{comment_count_raw}件 / ユニーク{len(others_usernames)}人")

    return pd.DataFrame(rows)


def main() -> None:
    token = read_token()
    EXPORTS_DIR.mkdir(exist_ok=True)

    account = get_own_account(token)
    own_username = account["username"]
    print(f"アカウント: {own_username} / {account['id']} / 投稿{account.get('media_count')}件")

    media_list = get_all_media(account["id"], token)
    print(f"投稿一覧を{len(media_list)}件取得したで。コメントも順番に取得していくわ...")

    df = summarize_media(media_list, own_username, token)

    output_path = EXPORTS_DIR / "media.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"完了。{len(df)}件を {output_path} に保存したで。")


if __name__ == "__main__":
    main()
