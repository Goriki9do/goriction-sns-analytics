"""
unique_commenters（返信込み・本人除外・重複排除後のコメント人数）の
集計ロジックを、架空のAPIレスポンスでテストする。

実際のInstagram APIには接続しない。requests.getを差し替えて、
コメント・返信のパターンごとに正しく人数が数えられるか確認する。
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetch import summarize_media  # noqa: E402

OWN_USERNAME = "goriction"


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")


def comments_page(items):
    return {"data": items, "paging": {}}


class UniqueCommentersTests(unittest.TestCase):
    def _run(self, media, comments_by_media, replies_by_comment):
        def fake_get(url, params=None, timeout=30):
            params = params or {}
            if url.endswith("/comments"):
                media_id = url.split("/")[-2]
                return FakeResponse(comments_page(comments_by_media.get(media_id, [])))
            if url.endswith("/replies"):
                comment_id = url.split("/")[-2]
                return FakeResponse(comments_page(replies_by_comment.get(comment_id, [])))
            raise AssertionError(f"unexpected URL in test: {url}")

        with patch("fetch.requests.get", side_effect=fake_get):
            df = summarize_media([media], OWN_USERNAME, token="dummy-token")
        return df.iloc[0]

    def test_multiple_distinct_commenters(self):
        media = {"id": "m1", "comments_count": 3, "permalink": "", "caption": "",
                  "media_type": "IMAGE", "media_product_type": "FEED", "timestamp": "",
                  "like_count": 0}
        comments = {
            "m1": [
                {"id": "c1", "text": "hi", "username": "alice"},
                {"id": "c2", "text": "nice", "username": "bob"},
                {"id": "c3", "text": "again", "username": "alice"},  # aliceの2回目
            ]
        }
        row = self._run(media, comments, {})
        self.assertEqual(row["unique_commenters"], 2)  # alice, bob
        self.assertEqual(row["comment_count_raw"], 3)
        self.assertEqual(row["own_comments_excluded"], 0)

    def test_own_comments_excluded(self):
        media = {"id": "m2", "comments_count": 2, "permalink": "", "caption": "",
                  "media_type": "IMAGE", "media_product_type": "FEED", "timestamp": "",
                  "like_count": 0}
        comments = {
            "m2": [
                {"id": "c1", "text": "hi", "username": "alice"},
                {"id": "c2", "text": "thanks!", "username": OWN_USERNAME},
            ]
        }
        row = self._run(media, comments, {})
        self.assertEqual(row["unique_commenters"], 1)  # aliceのみ
        self.assertEqual(row["own_comments_excluded"], 1)

    def test_replies_count_new_commenter_and_dedupe_existing(self):
        media = {"id": "m3", "comments_count": 2, "permalink": "", "caption": "",
                  "media_type": "IMAGE", "media_product_type": "FEED", "timestamp": "",
                  "like_count": 0}
        comments = {
            "m3": [
                {"id": "c1", "text": "hi", "username": "alice"},
                {"id": "c2", "text": "cool", "username": "bob"},
            ]
        }
        replies = {
            "c1": [
                {"id": "r1", "text": "thanks", "username": OWN_USERNAME},  # 本人の返信
                {"id": "r2", "text": "+1", "username": "carol"},  # 新規
            ],
            "c2": [
                {"id": "r3", "text": "same here", "username": "alice"},  # 既出、重複排除される
            ],
        }
        row = self._run(media, comments, replies)
        self.assertEqual(row["unique_commenters"], 3)  # alice, bob, carol
        self.assertEqual(row["own_comments_excluded"], 1)

    def test_no_comments_skips_fetch(self):
        media = {"id": "m4", "comments_count": 0, "permalink": "", "caption": "",
                  "media_type": "IMAGE", "media_product_type": "FEED", "timestamp": "",
                  "like_count": 0}
        row = self._run(media, {}, {})
        self.assertEqual(row["unique_commenters"], 0)
        self.assertEqual(row["comment_count_raw"], 0)


if __name__ == "__main__":
    unittest.main()
