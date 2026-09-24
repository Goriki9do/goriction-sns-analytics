"""
TikTok Studioから手動でダウンロードしたCSVを読み込み、他SNS（YouTube等）と並べやすい
列名に正規化して exports/videos.csv に追記する。

前提（このスクリプトはTikTokには一切アクセスしない。ローカルのファイル処理のみ）:
    TikTok Studio（studio.tiktok.com、またはアプリ内Analytics）で
    Analytics > Content を開き、「データをダウンロード」でCSVを保存したら、
    そのファイルを exports/inbox/ フォルダに置く。

重要:
    TikTok Studioのエクスポートにあるコメント数は「件数」であり、
    YouTube版の unique_commenters（本人除外・返信込みのユニーク投稿者数）
    とは意味が異なる。安易に同じ指標として比較しない。
    TikTokの公式APIではユニーク投稿者数は取得できない（Research APIは研究者限定）。

使い方:
    python normalize_export.py
    exports/inbox/ にある未処理のCSVをすべて処理し、videos.csvに追記したうえで
    exports/processed/ に移動する（二重取り込み防止）。
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

EXPORTS_DIR = Path(__file__).parent / "exports"
INBOX_DIR = EXPORTS_DIR / "inbox"
PROCESSED_DIR = EXPORTS_DIR / "processed"
NORMALIZED_PATH = EXPORTS_DIR / "videos.csv"

# TikTok Studio側の列名は言語・仕様変更で揺れるため、複数候補から拾う。
# 実際にダウンロードしたCSVのヘッダーを見て、ここに列名を足していくこと。
COLUMN_CANDIDATES = {
    "post_date": ["Post time", "投稿日時", "Post date"],
    "title": ["Video title", "動画タイトル", "Title"],
    "views": ["Video views", "再生数", "Views"],
    "likes": ["Likes", "いいね数"],
    "comment_count_raw": ["Comments", "コメント数"],
    "shares": ["Shares", "シェア数"],
}


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
            print(f"警告: 列 '{target_col}' に対応する列が {raw_path.name} に見つからんかった（空欄で埋める）")

    normalized["fetched_at"] = datetime.now(timezone.utc).isoformat()
    normalized["source_file"] = raw_path.name
    normalized["unique_commenters"] = pd.NA  # TikTokでは取得不可。空欄のまま維持。

    return normalized


def main() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(INBOX_DIR.glob("*.csv"))
    if not raw_files:
        print(f"{INBOX_DIR} に未処理のCSVが見つからんわ。")
        print("TikTok Studioでダウンロードしたファイルをこのフォルダに置いてから実行してな。")
        return

    normalized_batches = [normalize(path) for path in raw_files]
    new_rows = pd.concat(normalized_batches, ignore_index=True)

    if NORMALIZED_PATH.exists():
        existing = pd.read_csv(NORMALIZED_PATH)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows

    combined.to_csv(NORMALIZED_PATH, index=False, encoding="utf-8-sig")
    print(f"追記したで: {NORMALIZED_PATH}（{len(new_rows)}行追加、{len(raw_files)}ファイル分）")

    for path in raw_files:
        path.rename(PROCESSED_DIR / path.name)
    print(f"処理済みのファイルは {PROCESSED_DIR} に移動したで。")


if __name__ == "__main__":
    main()
