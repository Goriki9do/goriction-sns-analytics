"""
「自動化専用のブラウザ」を新しく起動するのではなく、あなたが普段使っている
Edge（launch_edge_debug.batでリモート操作モードにしたもの）に接続して、
TikTok Studioの分析画面からCSVをダウンロードする。

事前準備:
    1. launch_edge_debug.bat を実行してEdgeをリモート操作モードで開く
    2. そのEdgeでいつも通りTikTokにログインする（自動化はしない、人間が普通に操作する）
    3. TikTok Studioの分析画面（Content）まで開いておく
    4. このスクリプトを実行する

使い方:
    python export_studio_csv.py

注意:
    TikTok Studioの画面構成は予告なく変わることがある。ダウンロードボタンが
    見つからずに失敗した場合は、下記 DOWNLOAD_BUTTON_TEXT_CANDIDATES に
    実際の画面のボタン文言を追加すること。
"""

import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

EXPORTS_DIR = Path(__file__).parent / "exports"
CDP_URL = "http://localhost:9222"

ANALYTICS_CONTENT_URL = "https://www.tiktok.com/tiktokstudio/analytics/content"

# 実際のボタン文言はTikTok側の言語設定・仕様変更で変わりうるため候補を複数持つ。
DOWNLOAD_BUTTON_TEXT_CANDIDATES = [
    "データをダウンロード",
    "Download data",
    "Download",
]


def find_or_open_studio_page(context) -> "playwright.sync_api.Page":
    for page in context.pages:
        if "tiktokstudio/analytics" in page.url:
            return page

    page = context.new_page()
    page.goto(ANALYTICS_CONTENT_URL)
    return page


def run() -> Path:
    EXPORTS_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception:
            print(
                "Edgeに接続できんかったわ。先に launch_edge_debug.bat を実行して、"
                "Edgeをリモート操作モードで開いてからやり直してな。"
            )
            sys.exit(1)

        context = browser.contexts[0]
        page = find_or_open_studio_page(context)
        page.bring_to_front()

        if "login" in page.url:
            print("ログインできてへんみたい。Edge側で先にTikTokにログインしてな。")
            sys.exit(1)

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
            sys.exit(1)

        with page.expect_download() as download_info:
            download_button.click()
        download = download_info.value

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = EXPORTS_DIR / f"tiktok_studio_raw_{timestamp}.csv"
        download.save_as(str(saved_path))

        # ブラウザ自体は閉じない（あなたが普段使ってるEdgeやから）。接続だけ切る。
        browser.close()

    print(f"保存したで: {saved_path}")
    return saved_path


def main() -> None:
    run()


if __name__ == "__main__":
    main()
