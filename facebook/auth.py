"""
Facebook Graph API の認証(OAuth 2.0, Authorization Code)。

Facebookページの投稿・Reelsを取得するには「ページアクセストークン」が要る。
取得の流れ:
1. ブラウザでFacebookログイン→権限許可(このスクリプトが自動で開く)
2. 短期ユーザートークンを取得
3. 短期→長期ユーザートークン(60日)に交換
4. 長期ユーザートークンから、自分が管理するページ一覧とページアクセストークンを取得
   (長期ユーザートークンから発行したページアクセストークンは、通常期限切れしない)
5. 対象ページのアクセストークンを secrets/token_cache.json に保存

事前準備:
    secrets/app_id.txt, secrets/app_secret.txt に
    Meta for Developersで発行したApp ID/App Secretを1行だけ保存しておく。
"""

import http.server
import json
import secrets as secrets_mod
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

HERE = Path(__file__).parent
SECRETS_DIR = HERE / "secrets"
APP_ID_PATH = SECRETS_DIR / "app_id.txt"
APP_SECRET_PATH = SECRETS_DIR / "app_secret.txt"
PAGE_NAME_PATH = SECRETS_DIR / "page_name.txt"  # 複数ページ管理者の場合、対象ページ名を指定
TOKEN_CACHE_PATH = SECRETS_DIR / "token_cache.json"

API_VERSION = "v26.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"
AUTHORIZE_URL = f"https://www.facebook.com/{API_VERSION}/dialog/oauth"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "pages_show_list,pages_read_engagement,read_insights,pages_read_user_content"


def _read_secret(path: Path, label: str) -> str:
    if not path.exists():
        print(f"{path} が見つからんわ。Meta for Developersで発行した{label}を保存してな。")
        sys.exit(1)
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        print(f"{path} が空やわ。")
        sys.exit(1)
    return value


def _load_cache() -> dict:
    if TOKEN_CACHE_PATH.exists():
        return json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    SECRETS_DIR.mkdir(exist_ok=True)
    TOKEN_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result["code"] = params.get("code", [None])[0]
        _CallbackHandler.result["state"] = params.get("state", [None])[0]
        _CallbackHandler.result["error"] = params.get("error_description", params.get("error", [None]))[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("認証完了。このタブは閉じてええで。".encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def _run_authorization_flow(app_id: str, app_secret: str) -> str:
    """ブラウザ許可→短期ユーザートークン取得までを行う。"""
    state = secrets_mod.token_urlsafe(16)
    params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "response_type": "code",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    _CallbackHandler.result = {}
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print("ブラウザでFacebookの認証画面を開くで。許可したらこのスクリプトに自動で戻ってくる。")
    webbrowser.open(auth_url)

    server_thread.join(timeout=180)
    if not _CallbackHandler.result:
        print("認証がタイムアウトしたわ。もう一回実行してみて。")
        sys.exit(1)
    if _CallbackHandler.result.get("error"):
        print(f"認証がエラーになったで: {_CallbackHandler.result['error']}")
        sys.exit(1)
    if _CallbackHandler.result.get("state") != state:
        print("state不一致。CSRF対策で弾いたで。もう一回実行してみて。")
        sys.exit(1)

    code = _CallbackHandler.result.get("code")
    if not code:
        print("認可コードを取得できんかったわ。")
        sys.exit(1)

    resp = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": app_id,
            "redirect_uri": REDIRECT_URI,
            "client_secret": app_secret,
            "code": code,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"短期トークン取得に失敗: HTTP {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()["access_token"]


def _exchange_for_long_lived_user_token(app_id: str, app_secret: str, short_lived_token: str) -> str:
    resp = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"長期トークンへの交換に失敗: HTTP {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()["access_token"]


def _select_page(long_lived_user_token: str) -> dict:
    resp = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={"access_token": long_lived_user_token, "fields": "id,name,access_token"},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"管理ページ一覧の取得に失敗: HTTP {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    pages = resp.json().get("data", [])
    if not pages:
        print("管理しているFacebookページが見つからんかった。pages_show_listの許可が出てるか確認してな。")
        sys.exit(1)

    if len(pages) == 1:
        return pages[0]

    if PAGE_NAME_PATH.exists():
        target_name = PAGE_NAME_PATH.read_text(encoding="utf-8").strip()
        for page in pages:
            if page["name"] == target_name:
                return page
        print(f"secrets/page_name.txt の「{target_name}」に一致するページが見つからんかった。")

    print("複数ページを管理してるみたいやから、secrets/page_name.txt にページ名を1行書いて指定してな。候補:")
    for page in pages:
        print(f"  - {page['name']}")
    sys.exit(1)


def get_page_context() -> dict:
    """{"page_id": ..., "page_name": ..., "page_access_token": ...} を返す。"""
    app_id = _read_secret(APP_ID_PATH, "App ID")
    app_secret = _read_secret(APP_SECRET_PATH, "App Secret")
    cache = _load_cache()

    if cache.get("page_access_token"):
        return cache

    short_lived = _run_authorization_flow(app_id, app_secret)
    long_lived_user_token = _exchange_for_long_lived_user_token(app_id, app_secret, short_lived)
    page = _select_page(long_lived_user_token)

    cache = {
        "page_id": page["id"],
        "page_name": page["name"],
        "page_access_token": page["access_token"],
    }
    _save_cache(cache)
    return cache
