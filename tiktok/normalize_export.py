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

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

EXPORTS_DIR = Path(__file__).parent / "exports"
INBOX_DIR = EXPORTS_DIR / "inbox"
PROCESSED_DIR = EXPORTS_DIR / "processed"
JST = timezone(timedelta(hours=9))
TEXT_COLUMNS = {"date", "post_date", "video_url", "title"}


def _month_day(value) -> tuple[int, int] | None:
    m = re.match(r"(\d+)月(\d+)日", str(value))
    return (int(m.group(1)), int(m.group(2))) if m else None


def infer_daily_iso_dates(values: pd.Series, anchor: date) -> list[str | None]:
    """日別CSVの「9月16日」(年なし)に年を補って「2026-09-16」にする。
    TikTok Studioの日別データは古い順に1日ずつ連続で並び、最後の行が
    ダウンロード時点以前の最新日という前提で、後ろから遡りながら
    月日が増えたところ(=年をまたいだところ)で年を1つ戻す。"""
    result: list[str | None] = [None] * len(values)
    year = None
    later = None
    for i in range(len(values) - 1, -1, -1):
        md = _month_day(values.iloc[i])
        if md is None:
            continue
        if year is None:
            year = anchor.year if md <= (anchor.month, anchor.day) else anchor.year - 1
        elif md > later:
            year -= 1
        result[i] = f"{year:04d}-{md[0]:02d}-{md[1]:02d}"
        later = md
    return result


def infer_post_iso_date(value, anchor: date) -> str | None:
    """動画一覧の投稿日(年なし)に年を補う。TikTok Studioは最大365日までしか
    遡れないので、ダウンロード日以前で最も近い日付と解釈すれば確定できる。"""
    md = _month_day(value)
    if md is None:
        return None
    year = anchor.year if md <= (anchor.month, anchor.day) else anchor.year - 1
    return f"{year:04d}-{md[0]:02d}-{md[1]:02d}"

# ファイル名の先頭部分 -> (出力先CSV, 列のリネーム対応表)
# TikTok Studio側の列名は言語・仕様変更で変わりうるため、
# 見つからなかった場合は警告を出して空欄で埋める。
FILE_TYPES = {
    "Content": {
        "output": "videos.csv",
        "key_column": "video_url",
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
        "key_column": "date_iso",
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
        "key_column": "date_iso",
        "columns": {
            "Date": "date",
            "Followers": "followers",
            "Difference in followers from previous day": "followers_diff",
        },
    },
    "Viewers": {
        "output": "viewers_daily.csv",
        "key_column": "date_iso",
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

    # TikTok Studioは、データが無い日や集計待ちの日を0ではなく"undefined"という
    # 文字列で書き出すことがある(Viewers.csvで確認)。0とは意味が違うので欠損にする。
    for target_col in spec["columns"].values():
        if target_col not in TEXT_COLUMNS:
            normalized[target_col] = pd.to_numeric(normalized[target_col], errors="coerce")

    # 年なしの日付に年を補う。重複排除のキーにもなるので、年をまたいでも
    # 「2025年9月25日」が「2026年9月25日」に上書きされることがない。
    anchor = datetime.now(JST).date()
    if "date" in normalized.columns:
        normalized["date_iso"] = infer_daily_iso_dates(normalized["date"], anchor)
    if "post_date" in normalized.columns:
        normalized["post_date_iso"] = [infer_post_iso_date(v, anchor) for v in normalized["post_date"]]

    normalized["fetched_at"] = datetime.now(timezone.utc).isoformat()
    normalized["source_file"] = raw_path.name

    return normalized


def append_csv(output_path: Path, new_rows: pd.DataFrame, key_column: str) -> None:
    """同じキー(video_url/date)の行は、後から取り込んだ方(new_rows)で上書きする。
    TikTok Studioの再ダウンロードで同じ日付・同じ動画が何度も来るため、
    キーで重複排除しないとexportsファイルが実行のたびに膨らんでしまう。"""
    if output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    if key_column in combined.columns:
        combined = combined.drop_duplicates(subset=key_column, keep="last")
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
            path.replace(PROCESSED_DIR / path.name)
            continue

        normalized = normalize(path, file_type)
        if normalized is not None:
            output_path = EXPORTS_DIR / FILE_TYPES[file_type]["output"]
            append_csv(output_path, normalized, FILE_TYPES[file_type]["key_column"])
            print(f"{path.name} -> {output_path.name} に{len(normalized)}行追加")
            processed_count += 1

        # 同名ファイルが前回分として残っていることがあるため上書きで移動する。
        path.replace(PROCESSED_DIR / path.name)

    print(f"完了。{processed_count}ファイルを取り込んだで。処理済みは {PROCESSED_DIR} に移動した。")


if __name__ == "__main__":
    main()
