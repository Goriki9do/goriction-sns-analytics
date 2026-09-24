"""
TikTok Studioで手動ダウンロードしたCSVを読み込み、種類ごとに正規化して
exports/ 配下の集計用CSVに追記する。

前提（このスクリプトはTikTokには一切アクセスしない。ローカルのファイル処理のみ）:
    TikTok Studio（studio.tiktok.com、またはアプリ内Analytics）でダウンロードした
    CSV（Content.csv、Overview.csv、FollowerHistory.csv など）を
    exports/inbox/ フォルダに置く。ファイル名はTikTokが付けたままでよい
    （ZIPでまとめてダウンロードした場合は展開してから置く）。

重要:
    Content.csvの「Total comments」は「件数」であり、YouTube版の
    unique_commenters（本人除外・返信込みのユニーク投稿者数）とは意味が異なる。
    TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）。

    日付列（「9月16日」のような表記）には年が含まれない。TikTok Studio側の
    仕様のため、そのまま文字列で保存する。年をまたぐ場合は取り違えに注意。

使い方:
    python normalize_export.py
    exports/inbox/ にある未処理のCSVをすべて種類判定して処理し、
    exports/processed/ に移動する（二重取り込み防止）。
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

EXPORTS_DIR = Path(__file__).parent / "exports"
INBOX_DIR = EXPORTS_DIR / "inbox"
PROCESSED_DIR = EXPORTS_DIR / "processed"

# ファイル名の先頭部分 -> (出力先CSV, 列のリネーム対応表)
# TikTok Studio側の列名は言語・仕様変更で変わりうるため、
# 見つからなかった場合は警告を出して空欄で埋める。
FILE_TYPES = {
    "Content": {
        "output": "videos.csv",
        "columns": {
            "Video link": "video_url",
            "Video title": "title",
            "Post time": "post_date",
            "Total views": "views",
            "Total likes": "likes",
            "Total comments": "comment_count_raw",
            "Total shares": "shares",
        },
        "extra_columns": {"unique_commenters": pd.NA},  # TikTokでは取得不可
    },
    "Overview": {
        "output": "channel_daily.csv",
        "columns": {
            "Date": "date",
            "Video Views": "views",
            "Profile Views": "profile_views",
            "Likes": "likes",
            "Comments": "comment_count_raw",
            "Shares": "shares",
        },
    },
    "FollowerHistory": {
        "output": "follower_daily.csv",
        "columns": {
            "Date": "date",
            "Followers": "followers",
            "Difference in followers from previous day": "followers_diff",
        },
    },
    "Viewers": {
        "output": "viewers_daily.csv",
        "columns": {
            "Date": "date",
            "Total Viewers": "total_viewers",
            "New Viewers": "new_viewers",
            "Returning Viewers": "returning_viewers",
        },
    },
}

# 上記のいずれにも該当しないファイル（FollowerGender.csv等、今のところ
# 使い道が定まっていないもの）はそのままprocessedへ移すだけにする。


def detect_file_type(filename: str) -> str | None:
    stem = Path(filename).stem
    for prefix in FILE_TYPES:
        if stem.startswith(prefix):
            return prefix
    return None


def normalize(raw_path: Path, file_type: str) -> pd.DataFrame | None:
    spec = FILE_TYPES[file_type]
    raw = pd.read_csv(raw_path)

    if raw.empty:
        print(f"{raw_path.name} は中身が空やったのでスキップ")
        return None

    normalized = pd.DataFrame()
    for source_col, target_col in spec["columns"].items():
        if source_col in raw.columns:
            normalized[target_col] = raw[source_col]
        else:
            normalized[target_col] = pd.NA
            print(f"警告: 列 '{source_col}' が {raw_path.name} に見つからんかった（空欄で埋める）")

    for target_col, value in spec.get("extra_columns", {}).items():
        normalized[target_col] = value

    normalized["fetched_at"] = datetime.now(timezone.utc).isoformat()
    normalized["source_file"] = raw_path.name

    return normalized


def append_csv(output_path: Path, new_rows: pd.DataFrame) -> None:
    if output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    combined.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(INBOX_DIR.glob("*.csv"))
    if not raw_files:
        print(f"{INBOX_DIR} に未処理のCSVが見つからんわ。")
        print("TikTok Studioでダウンロードしたファイルをこのフォルダに置いてから実行してな。")
        return

    processed_count = 0
    for path in raw_files:
        file_type = detect_file_type(path.name)
        if file_type is None:
            print(f"{path.name} は未対応の種類やから、整理せずそのままprocessedへ移すで。")
            path.rename(PROCESSED_DIR / path.name)
            continue

        normalized = normalize(path, file_type)
        if normalized is not None:
            output_path = EXPORTS_DIR / FILE_TYPES[file_type]["output"]
            append_csv(output_path, normalized)
            print(f"{path.name} -> {output_path.name} に{len(normalized)}行追加")
            processed_count += 1

        path.rename(PROCESSED_DIR / path.name)

    print(f"完了。{processed_count}ファイルを取り込んだで。処理済みは {PROCESSED_DIR} に移動した。")


if __name__ == "__main__":
    main()
