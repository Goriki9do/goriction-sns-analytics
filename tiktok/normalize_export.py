"""
export_studio_csv.py が保存した生CSVを読み込み、他SNS（YouTube等）と並べやすい
列名に正規化して exports/videos.csv に追記する。

重要:
    TikTok Studioのエクスポートにあるコメント数は「件数」であり、
    YouTube版の unique_commenters（本人除外・返信込みのユニーク投稿者数）
    とは意味が異なる。安易に同じ指標として比較しない。
    TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）。

使い方:
    python normalize_export.py                 # exports/内の最新の生CSVを使う
    python normalize_export.py path/to/raw.csv  # ファイルを指定する
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

EXPORTS_DIR = Path(__file__).parent / "exports"
NORMALIZED_PATH = EXPORTS_DIR / "videos.csv"

# TikTok Studio側の列名は言語・仕様変更で揺れるため、複数候補から拾う。
# 実際にダウンロードしたCSVを見て、ここに列名を足していくこと。
COLUMN_CANDIDATES = {
    "post_date": ["Post time", "投稿日時", "Post date"],
    "title": ["Video title", "動画タイトル", "Title"],
    "views": ["Video views", "再生数", "Views"],
    "likes": ["Likes", "いいね数"],
    "comment_count_raw": ["Comments", "コメント数"],
    "shares": ["Shares", "シェア数"],
}


def find_latest_raw_csv() -> Path:
    candidates = sorted(EXPORTS_DIR.glob("tiktok_studio_raw_*.csv"))
    if not candidates:
        print("生CSVが exports/ に見つからんわ。先に export_studio_csv.py を実行してな。")
        sys.exit(1)
    return candidates[-1]


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def normalize(raw_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(raw_path)

    normalized = pd.DataFrame()
    for target_col, candidates in COLUMN_CANDIDATES.items():
        source_col = pick_column(raw, candidates)
        if source_col is not None:
            normalized[target_col] = raw[source_col]
        else:
            normalized[target_col] = pd.NA
            print(f"警告: 列 '{target_col}' に対応する列がCSVに見つからんかった（空欄で埋める）")

    normalized["fetched_at"] = datetime.now(timezone.utc).isoformat()
    normalized["source_file"] = raw_path.name
    normalized["unique_commenters"] = pd.NA  # TikTokでは取得不可。空欄のまま維持。

    return normalized


def main() -> None:
    raw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_raw_csv()
    normalized = normalize(raw_path)

    if NORMALIZED_PATH.exists():
        existing = pd.read_csv(NORMALIZED_PATH)
        combined = pd.concat([existing, normalized], ignore_index=True)
    else:
        combined = normalized

    combined.to_csv(NORMALIZED_PATH, index=False, encoding="utf-8-sig")
    print(f"追記したで: {NORMALIZED_PATH}（{len(normalized)}行追加）")


if __name__ == "__main__":
    main()
