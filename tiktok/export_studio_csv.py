"""
保存済みログインセッションを使って、TikTok StudioのAnalyticsからCSVを自動ダウンロードする。

事前に一度 login.py を実行してログインしておくこと。

使い方:
    python export_studio_csv.py

注意:
    TikTok Studioの画面構成は予告なく変わることがある。ダウンロードボタンが
    見つからずに失敗した場合は、下記 DOWNLOAD_BUTTON_TEXT_CANDIDATES に
    実際の画面のボタン文言を追加するか、--headed を付けて画面を見ながら
    どこで止まっているか確認すること。

    python export_studio_csv.py --headed
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

AUTH_DIR = Path(__file__).parent / ".auth"
STORAGE_STATE_PATH = AUTH_DIR / "tiktok_storage_state.json"
EXPORTS_DIR = Path(__file__).parent / "exports"

ANALYTICS_CONTENT_URL = "https://www.tiktok.com/tiktokstudio/analytics/content"

# 実際のボタン文言はTikTok側の言語設定・仕様変更で変わりうるため候補を複数持つ。
DOWNLOAD_BUTTON_TEXT_CANDIDATES = [
    "データをダウンロード",
    "Download data",
    "Download",
]


def run(headless: bool) -> Path:
    if not STORAGE_STATE_PATH.exists():
        print("ログインセッションが見つからんわ。先に `python login.py` を実行してな。")
        sys.exit(1)

    EXPORTS_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(STORAGE_STATE_PATH))
        page = context.new_page()
        page.goto(ANALYTICS_CONTENT_URL)

        # セッション切れだとログイン画面にリダイレクトされる想定。
        try:
            page.wait_for_url("**/login**", timeout=5000)
            print("セッションが切れてるみたい。`python login.py` をもう一度実行してな。")
            browser.close()
            sys.exit(1)
        except PlaywrightTimeoutError:
            pass  # ログイン画面に飛ばされなければ正常

        download_button = None
        for text in DOWNLOAD_BUTTON_TEXT_CANDIDATES:
            locator = page.get_by_text(text, exact=False)
            if locator.count() > 0:
                download_button = locator.first
                break

        if download_button is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_path = EXPORTS_DIR / f"debug_screenshot_{timestamp}.png"
            page.screenshot(path=str(debug_path))
            print(
                "ダウンロードボタンが見つからんかった。画面構成が変わってるかも。"
                f"スクリーンショットを {debug_path} に保存したので確認してな。"
            )
            browser.close()
            sys.exit(1)

        with page.expect_download() as download_info:
            download_button.click()
        download = download_info.value

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = EXPORTS_DIR / f"tiktok_studio_raw_{timestamp}.csv"
        download.save_as(str(saved_path))

        browser.close()

    print(f"保存したで: {saved_path}")
    return saved_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--headed",
        action="store_true",
        help="ブラウザ画面を表示して実行する（デバッグ用）",
    )
    args = parser.parse_args()
    run(headless=not args.headed)


if __name__ == "__main__":
    main()
