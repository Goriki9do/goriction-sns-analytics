"""
X API v2 の OAuth 2.0 (Authorization Code + PKCE, confidential client) 認証。

初回のみブラウザでの許可操作が必要。以後はrefresh_tokenで自動更新する。
アクセストークン・リフレッシュトークンは secrets/token_cache.json に保存し、
コミットしない。
"""

import base64
import hashlib
import http.server
import json
import secrets as secrets_mod
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

HERE = Path(__file__).parent
SECRETS_DIR = HERE / "secrets"
CLIENT_ID_PATH = SECRETS_DIR / "client_id.txt"
CLIENT_SECRET_PATH = SECRETS_DIR / "client_secret.txt"
TOKEN_CACHE_PATH = SECRETS_DIR / "token_cache.json"

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "tweet.read users.read offline.access"

# refresh前にこの秒数以上余裕を持たせる
EXPIRY_MARGIN_SEC = 120


def _read_secret(path: Path, label: str) -> str:
    if not path.exists():
        print(f"{path} が見つからんわ。X Developer Consoleで発行した{label}を保存してな。")
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
    TOKEN_CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result["code"] = params.get("code", [None])[0]
        _CallbackHandler.result["state"] = params.get("state", [None])[0]
        _CallbackHandler.result["error"] = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("認証完了。このタブは閉じてええで。".encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # 標準出力を汚さない


def _run_authorization_flow(client_id: str, client_secret: str) -> dict:
    code_verifier = base64.urlsafe_b64encode(secrets_mod.token_bytes(64)).decode("ascii").rstrip("=")
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    state = secrets_mod.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    _CallbackHandler.result = {}
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print("ブラウザで認証画面を開くで。許可したらこのスクリプトに自動で戻ってくる。")
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

    resp = requests.post(
        TOKEN_URL,
        headers=_basic_auth_header(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"トークン交換に失敗: HTTP {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()


def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers=_basic_auth_header(client_id, client_secret),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"リフレッシュに失敗: HTTP {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()


def get_access_token() -> str:
    client_id = _read_secret(CLIENT_ID_PATH, "Client ID")
    client_secret = _read_secret(CLIENT_SECRET_PATH, "Client Secret")
    cache = _load_cache()

    if cache.get("access_token") and time.time() < cache.get("expires_at", 0) - EXPIRY_MARGIN_SEC:
        return cache["access_token"]

    if cache.get("refresh_token"):
        try:
            token_data = _refresh_access_token(client_id, client_secret, cache["refresh_token"])
        except requests.HTTPError:
            print("refresh_tokenが無効になってたみたい。初回認証をやり直すで。")
            token_data = _run_authorization_flow(client_id, client_secret)
    else:
        token_data = _run_authorization_flow(client_id, client_secret)

    cache["access_token"] = token_data["access_token"]
    cache["refresh_token"] = token_data.get("refresh_token", cache.get("refresh_token"))
    cache["expires_at"] = time.time() + token_data.get("expires_in", 7200)
    _save_cache(cache)

    return cache["access_token"]
