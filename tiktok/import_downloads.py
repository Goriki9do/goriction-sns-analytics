"""
Downloadsフォルダにある、TikTok StudioからダウンロードしたZIPファイルを探して
展開し、中のCSVを exports/inbox/ にコピーする。TikTokには一切アクセスしない、
ローカルのファイル操作のみ。

対象にするZIPファイル名（TikTok Studioのダウンロード時の命名規則）:
    Content_*.zip / Overview_*.zip / Followers_*.zip / Viewers_*.zip

使い方:
    python import_downloads.py                  # ~/Downloads を対象にする
    python import_downloads.py D:/path/to/dir    # フォルダを指定する

処理済みのZIPは exports/downloads_processed/ に移動する（二重取り込み防止）。
"""

import re
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

EXPORTS_DIR = Path(__file__).parent / "exports"
INBOX_DIR = EXPORTS_DIR / "inbox"
DOWNLOADS_PROCESSED_DIR = EXPORTS_DIR / "downloads_processed"

# TikTok Studioのダウンロードファイル名の先頭部分。
TARGET_PREFIX_PATTERN = re.compile(r"^(Content|Overview|Followers|Viewers)", re.IGNORECASE)


def find_target_zips(downloads_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in downloads_dir.glob("*.zip")
        if TARGET_PREFIX_PATTERN.match(path.name)
    )


def extract_csvs_from_zip(zip_path: Path) -> int:
    count = 0
    with TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        for csv_path in tmp_dir.rglob("*.csv"):
            dest = INBOX_DIR / csv_path.name
            if dest.exists():
                # 同名ファイルがある場合は上書きせず、日時を付けて退避
                dest = INBOX_DIR / f"{csv_path.stem}_{zip_path.stem}{csv_path.suffix}"
            dest.write_bytes(csv_path.read_bytes())
            count += 1

    return count


def main() -> None:
    downloads_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads"

    if not downloads_dir.exists():
        print(f"{downloads_dir} が見つからんわ。パスを指定してもう一回実行してな。")
        sys.exit(1)

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    zip_files = find_target_zips(downloads_dir)
    if not zip_files:
        print(f"{downloads_dir} にTikTok Studioのダウンロードzipが見つからんかった。")
        return

    total_csv = 0
    for zip_path in zip_files:
        try:
            n = extract_csvs_from_zip(zip_path)
        except zipfile.BadZipFile:
            print(f"警告: {zip_path.name} はzipとして読めんかった。スキップする。")
            continue

        print(f"{zip_path.name} -> CSV {n}件を exports/inbox/ にコピー")
        total_csv += n
        zip_path.rename(DOWNLOADS_PROCESSED_DIR / zip_path.name)

    print(f"完了。zip {len(zip_files)}件からCSV {total_csv}件を取り込んだで。")
    print("次は normalize_export.py を実行してな。")


if __name__ == "__main__":
    main()
