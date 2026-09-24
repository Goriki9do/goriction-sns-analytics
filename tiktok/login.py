"""
初回専用：手動でTikTokにログインし、ログイン状態（Cookie）をローカルに保存する。

パスワードやTikTokの認証情報はこのスクリプトにもファイルにも書かない。
ブラウザを開くので、その画面上であなた自身の手でログインする。

使い方:
    python login.py

ブラウザが開くので、TikTokに普段どおりログイン（2段階認証があればそれも）してから、
このターミナルに戻って Enter を押すとセッションが保存される。

保存先の .auth/ フォルダはログイン情報そのものなので、絶対にリポジトリにコミットしない
（.gitignoreで除外済み）。セッションが切れたら、もう一度このスクリプトを実行する。
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

AUTH_DIR = Path(__file__).parent / ".auth"
STORAGE_STATE_PATH = AUTH_DIR / "tiktok_storage_state.json"

TIKTOK_STUDIO_URL = "https://www.tiktok.com/tiktokstudio/analytics"


def main() -> None:
    AUTH_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(TIKTOK_STUDIO_URL)

        print()
        print("ブラウザが開いたで。TikTokに自分でログインしてから、")
        print("この画面（Analytics）が表示されてる状態でここに戻って Enter を押してな。")
        input()

        context.storage_state(path=str(STORAGE_STATE_PATH))
        browser.close()

    print(f"保存したで: {STORAGE_STATE_PATH}")
    print("次から export_studio_csv.py がこのセッションを再利用する。")


if __name__ == "__main__":
    main()
