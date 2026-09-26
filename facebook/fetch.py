"""
Facebook Graph API から、ページの投稿一覧・Reels一覧・Reelsのインサイトを取得する。

このスクリプトは「第一段階」用:
1. ページにAPIから接続できるか確認
2. 投稿一覧を取得(posts.csv, post_snapshots.csv)
3. Reels一覧を取得(reels.csv)
4. Reelsのvideo_insightsが、このページ規模(100いいね未満の可能性がある)でも
   取得できるかを指標ごとに個別テストする(reel_snapshots.csv, reel_retention.json)
5. ページ全体のInsightsが取得できるかも試す(page_daily.csv)。
   100いいね未満のページでは失敗する可能性が高いが、エラーメッセージを
   そのまま記録して次回の判断材料にする。

書き込み系操作は一切行わない(取得のみ)。

事前準備:
    facebook/auth.py の説明を参照。secrets/app_id.txt, secrets/app_secret.txt が必要。

使い方:
    python fetch.py
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

from auth import get_page_context

HERE = Path(__file__).parent
EXPORTS_DIR = HERE / "exports"

API_VERSION = "v26.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"
REQUEST_DELAY_SEC = 0.3

POST_FIELDS = "id,created_time,message,permalink_url,attachments{media_type,type}"

# 2026年時点の現行メトリクス名(video_insights)。
# ページ規模の下限は公式ドキュメントに明記が無いため、実際に叩いて確認する。
REEL_METRICS = [
    "blue_reels_play_count",       # 再生数
    "fb_reels_replay_count",       # リプレイ数
    "post_video_avg_time_watched",  # 平均視聴時間(Reel、リプレイ込み)
    "total_video_view_total_time",  # 総視聴時間
    "post_video_retention_graph",   # 視聴維持率(区間ごと)
    "post_video_social_actions",    # コメント・シェア(Reel向け集計)
    "post_video_followers",         # Reel経由のフォロー数
]

# ページ全体Insightsの候補(2026年の指標改定でpage_fans/impressions系は廃止済み)。
PAGE_METRICS = ["page_follows", "page_views_total", "page_post_engagements"]


def api_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{GRAPH_BASE}/{path}" if not path.startswith("http") else path
    query = dict(params or {})
    query["access_token"] = token
    resp = requests.get(url, params=query, timeout=30)
    time.sleep(REQUEST_DELAY_SEC)
    if resp.status_code != 200:
        raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:500]}")
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


def get_all_posts(page_id: str, token: str) -> list[dict]:
    first = api_get(f"{page_id}/posts", token, {"fields": POST_FIELDS, "limit": 50})
    return paginate(first, token)


def get_post_snapshot(post_id: str, token: str) -> dict:
    data = api_get(
        post_id,
        token,
        {"fields": "reactions.summary(true).limit(0),comments.summary(true).limit(0),shares"},
    )
    return {
        "reactions": data.get("reactions", {}).get("summary", {}).get("total_count"),
        "comments": data.get("comments", {}).get("summary", {}).get("total_count"),
        "shares": data.get("shares", {}).get("count"),
    }


def get_all_reels(page_id: str, token: str) -> list[dict]:
    """/video_reels が使えなければ /videos にフォールバックする。"""
    try:
        first = api_get(
            f"{page_id}/video_reels",
            token,
            {"fields": "id,description,created_time,permalink_url,length", "limit": 50},
        )
        return paginate(first, token)
    except requests.HTTPError as e:
        print(f"video_reelsエッジが使えんかった({e})。videosエッジで代用するで。")
        first = api_get(
            f"{page_id}/videos",
            token,
            {"fields": "id,description,created_time,permalink_url,length", "limit": 50},
        )
        return paginate(first, token)


def test_reel_metrics(video_id: str, token: str) -> dict:
    """指標を1つずつ個別に叩いて、このページ規模で何が取得できるか確認する。"""
    results = {}
    for metric in REEL_METRICS:
        try:
            data = api_get(f"{video_id}/video_insights", token, {"metric": metric})
            values = data.get("data", [])
            results[metric] = {"ok": True, "data": values}
        except requests.HTTPError as e:
            results[metric] = {"ok": False, "error": str(e)}
    return results


def try_page_insights(page_id: str, token: str) -> dict:
    results = {}
    for metric in PAGE_METRICS:
        try:
            data = api_get(f"{page_id}/insights", token, {"metric": metric, "period": "day"})
            results[metric] = {"ok": True, "data": data.get("data", [])}
        except requests.HTTPError as e:
            results[metric] = {"ok": False, "error": str(e)}
    return results


def main() -> None:
    ctx = get_page_context()
    page_id, page_name, token = ctx["page_id"], ctx["page_name"], ctx["page_access_token"]
    print(f"ページ: {page_name} / {page_id}")
    EXPORTS_DIR.mkdir(exist_ok=True)

    # 1) 投稿一覧
    posts = get_all_posts(page_id, token)
    print(f"投稿を{len(posts)}件取得したで。")
    posts_rows = []
    snapshot_rows = []
    fetched_at = pd.Timestamp.now(tz="UTC").isoformat()
    for post in posts:
        attachments = post.get("attachments", {}).get("data", [])
        post_type = attachments[0].get("media_type") or attachments[0].get("type") if attachments else "status"
        posts_rows.append(
            {
                "post_id": post["id"],
                "published_at": post.get("created_time"),
                "message": (post.get("message") or "")[:500],
                "url": post.get("permalink_url"),
                "type": post_type,
            }
        )
        try:
            snap = get_post_snapshot(post["id"], token)
            snapshot_rows.append({"date": fetched_at, "post_id": post["id"], **snap})
        except requests.HTTPError as e:
            print(f"警告: 投稿{post['id']}のスナップショット取得に失敗: {e}")

    pd.DataFrame(posts_rows).to_csv(EXPORTS_DIR / "posts.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(snapshot_rows).to_csv(EXPORTS_DIR / "post_snapshots.csv", index=False, encoding="utf-8-sig")
    print(f"posts.csv({len(posts_rows)}件) / post_snapshots.csv({len(snapshot_rows)}件) を保存したで。")

    # 2) Reels一覧
    reels = get_all_reels(page_id, token)
    print(f"Reelsを{len(reels)}件取得したで。")
    reels_rows = [
        {
            "reel_id": r["id"],
            "published_at": r.get("created_time"),
            "title": (r.get("description") or "")[:200],
            "url": r.get("permalink_url"),
            "duration": r.get("length"),
        }
        for r in reels
    ]
    pd.DataFrame(reels_rows).to_csv(EXPORTS_DIR / "reels.csv", index=False, encoding="utf-8-sig")

    # 3) Reelsのvideo_insightsを指標ごとにテスト(このページ規模で何が取れるか確認)
    reel_snapshot_rows = []
    retention_by_reel = {}
    metric_availability: dict[str, int] = {m: 0 for m in REEL_METRICS}
    for reel in reels:
        results = test_reel_metrics(reel["id"], token)
        row = {"date": fetched_at, "reel_id": reel["id"]}
        for metric, result in results.items():
            if result["ok"]:
                metric_availability[metric] += 1
                values = result["data"]
                if metric == "post_video_retention_graph":
                    retention_by_reel[reel["id"]] = values
                elif values and "values" in values[0] and values[0]["values"]:
                    row[metric] = values[0]["values"][0].get("value")
            else:
                row[f"{metric}_error"] = result["error"][:200]
        reel_snapshot_rows.append(row)

    pd.DataFrame(reel_snapshot_rows).to_csv(EXPORTS_DIR / "reel_snapshots.csv", index=False, encoding="utf-8-sig")
    (EXPORTS_DIR / "reel_retention.json").write_text(
        json.dumps(retention_by_reel, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== video_insights 指標ごとの取得可否(このページ規模での実測) ===")
    for metric, ok_count in metric_availability.items():
        print(f"  {metric}: {ok_count}/{len(reels)} 件で取得成功")

    # 4) ページ全体Insightsも試す(100いいね未満だと失敗する可能性が高い)
    print("\n=== ページ全体Insightsのテスト ===")
    page_results = try_page_insights(page_id, token)
    page_rows = []
    for metric, result in page_results.items():
        if result["ok"]:
            print(f"  {metric}: OK")
            for point in result["data"]:
                for v in point.get("values", []):
                    page_rows.append({"date": v.get("end_time"), "metric": metric, "value": v.get("value")})
        else:
            print(f"  {metric}: 失敗 - {result['error'][:200]}")
    pd.DataFrame(page_rows).to_csv(EXPORTS_DIR / "page_daily.csv", index=False, encoding="utf-8-sig")

    print(f"\n完了。{EXPORTS_DIR} 以下に保存したで。")


if __name__ == "__main__":
    main()
