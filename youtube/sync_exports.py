"""
YouTube側の実データはCodexのAppData配下に保存されており見つけにくいため、
扱いやすいようこのリポジトリ内 youtube/exports_local/ へコピーする。
TikTok版の tiktok/exports/ と同じ並びで確認できるようにするのが目的。

runtime.local.bat の SNS_DATA_HOME を読み取って場所を特定する（標準ライブラリ
のみ使用、追加インストール不要）。コピー先の実データはリポジトリにコミット
しない（.gitignoreで除外）。

使い方:
    python sync_exports.py
"""

import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
RUNTIME_BAT = HERE / "runtime.local.bat"
LOCAL_EXPORTS_DIR = HERE / "exports_local"


def read_data_home() -> Path:
    if not RUNTIME_BAT.exists():
        print(f"{RUNTIME_BAT} が見つからんわ。runtime.local.batを用意してな。")
        sys.exit(1)

    text = RUNTIME_BAT.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'SNS_DATA_HOME=([^\r\n"]+)', text)
    if not m:
        print("runtime.local.batにSNS_DATA_HOMEが見つからんかった。")
        sys.exit(1)

    return Path(m.group(1).strip().strip('"'))


def main() -> None:
    data_home = read_data_home()
    exports_root = data_home / "exports"
    if not exports_root.exists():
        print(f"{exports_root} が見つからんわ。先にrun_youtube.batを実行してな。")
        sys.exit(1)

    channel_dirs = [p for p in exports_root.iterdir() if p.is_dir()]
    if not channel_dirs:
        print(f"{exports_root} にチャンネルフォルダが見つからんかった。")
        sys.exit(1)
    if len(channel_dirs) > 1:
        print("複数のチャンネルフォルダが見つかった。念のため全部コピーするで:")
        for d in channel_dirs:
            print(f"  - {d.name}")

    LOCAL_EXPORTS_DIR.mkdir(exist_ok=True)
    count = 0
    for channel_dir in channel_dirs:
        dest_dir = LOCAL_EXPORTS_DIR / channel_dir.name
        dest_dir.mkdir(exist_ok=True)
        for src in channel_dir.glob("*"):
            if src.is_file():
                shutil.copy2(src, dest_dir / src.name)
                count += 1

    print(f"{count}件のファイルを {LOCAL_EXPORTS_DIR} にコピーしたで。")


if __name__ == "__main__":
    main()
