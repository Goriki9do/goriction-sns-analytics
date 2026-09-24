import json
import os
import threading
import webbrowser
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly',
          'https://www.googleapis.com/auth/youtube.force-ssl',
          'https://www.googleapis.com/auth/yt-analytics.readonly']


def credentials(root, allow_google_auth=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.exceptions import RefreshError
    folder = Path(root) / 'secrets'
    token, client = folder / 'token.json', folder / 'client_secret.json'
    if not client.exists():
        raise ValueError(f'認証ファイルを確認できません: {client} / ユーザー: {os.environ.get("USERNAME", "unknown")}。設定を作り直さず、この表示をCodexに伝えてください。')
    config = json.loads(client.read_text(encoding='utf-8-sig'))
    installed = config.get('installed', {})
    if (installed.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
            or installed.get('token_uri') != 'https://oauth2.googleapis.com/token'):
        raise ValueError('Google公式のデスクトップ用OAuth JSONを指定してください。')
    if not allow_google_auth:
        raise ValueError('GoogleへのOAuth認証情報送信は未許可です。説明を確認後、--allow-google-auth を指定してください。')
    creds = Credentials.from_authorized_user_file(str(token)) if token.exists() else None
    if creds and not creds.has_scopes(SCOPES):
        creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(config, SCOPES)
        manual = os.environ.get('SNS_AUTH_MANUAL') == '1'
        original = flow.authorization_url
        pending = folder / 'pending_auth_url.txt'
        def capture_url(**kwargs):
            url, state = original(**kwargs)
            pending.write_text(url, encoding='utf-8')
            print(f'認証画面が開かない場合は {pending} 内のURLをブラウザーで開いてください。',flush=True)
            if not manual:
                # Browser launch must not block the local OAuth callback server.
                threading.Thread(target=webbrowser.open,args=(url,),daemon=True).start()
            return url, state
        flow.authorization_url = capture_url
        try:
            creds = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=600,
                authorization_prompt_message='ブラウザーでGoogle認証を完了してください。',
                success_message='認証が完了しました。このタブを閉じて実行画面に戻ってください。',
                access_type='offline', prompt='consent', open_browser=False)
        finally:
            pending.unlink(missing_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    temp = token.with_suffix('.tmp')
    temp.write_text(creds.to_json(), encoding='utf-8')
    os.replace(temp, token)
    return creds
