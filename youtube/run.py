import argparse
import json
import os
import sys
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_HOME = Path(os.environ['LOCALAPPDATA']) / 'GorikushonSNS' if sys.platform == 'win32' else Path(__file__).resolve().parent
if sys.platform == 'win32':
    packaged_home = Path(os.environ['LOCALAPPDATA']) / 'Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/GorikushonSNS'
    if (packaged_home / 'secrets/client_secret.json').is_file():
        DEFAULT_HOME = packaged_home
APP_HOME = Path(os.environ.get('SNS_DATA_HOME', str(DEFAULT_HOME)))
sys.path.insert(0, str(APP_HOME / 'vendor'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sns.storage import connect, next_start, save, export

ROOT = APP_HOME


def main():
    parser = argparse.ArgumentParser(description='ゴリクション SNS分析 v0.1 / YouTube')
    parser.add_argument('--start', type=date.fromisoformat, help='初回の開始日 YYYY-MM-DD。省略時90日前')
    parser.add_argument('--end', type=date.fromisoformat, help='終了日。省略時YouTube日付の3日前')
    parser.add_argument('--full-refresh', action='store_true', help='指定期間を全件再取得')
    parser.add_argument('--allow-google-auth', action='store_true', help='Google公式OAuthへの認証通信に同意')
    parser.add_argument('--export-only', action='store_true', help='通信せず保存済みデータをCSV出力')
    args = parser.parse_args()
    db = connect(ROOT / 'data' / 'sns.sqlite3')
    if args.export_only:
        for row in db.execute('SELECT DISTINCT channel_id FROM runs').fetchall():
            print(export(db,ROOT / 'exports',row[0]))
        return
    today = datetime.now(ZoneInfo('America/Los_Angeles')).date()
    end = args.end or today - timedelta(days=3)
    start = args.start or today - timedelta(days=90)
    # Keep initial history boundary stable on subsequent runs.
    if not args.start:
        config_path = ROOT / 'config.json'
        if config_path.exists():
            start = date.fromisoformat(json.loads(config_path.read_text(encoding='utf-8'))['start_date'])
    if start > end or end >= today:
        raise ValueError('開始日 <= 終了日 < YouTubeの今日、となる期間を指定してください。')
    from sns.auth import credentials
    from sns.providers.youtube import YouTube
    provider = YouTube(credentials(ROOT,args.allow_google_auth))
    channel, videos = provider.inventory()
    channel_id = channel['id']
    print(f"チャンネル: {channel['snippet']['title']} / {channel_id} / 動画 {len(videos)}本", flush=True)
    reports = []
    for v in videos:
        v.update(provider.commenters(channel_id,v['video_id']))
        print(f"コメント人数: {v['video_id']} / {v['unique_commenters']} / {v['commenter_status']}",flush=True)
    for i, video_id in enumerate([''] + [v['video_id'] for v in videos]):
        begin = next_start(db,channel_id,video_id,start.isoformat(),end.isoformat(),args.full_refresh)
        print(f'取得 {i}/{len(videos)}: {video_id or "チャンネル全体"} {begin} - {end}',flush=True)
        reports.append((video_id,begin,provider.daily(channel_id,video_id,begin,end.isoformat())))
    stamp = datetime.now(timezone.utc).isoformat()
    save(db,channel_id,videos,reports,stamp,start.isoformat(),end.isoformat())
    config_path = ROOT / 'config.json'
    if not config_path.exists():
        config_path.write_text(json.dumps({'start_date':start.isoformat()},indent=2),encoding='utf-8')
    destination = export(db,ROOT / 'exports',channel_id)
    print(f'完了: 動画 {len(videos)}本 / 今回の日別行 {sum(len(r) for _,_,r in reports)} / {destination}')
    if not any(rows for _,_,rows in reports):
        print('注意: Analyticsは0行でした。未集計・活動なし・権限などを確認してください。実データの分析値は未確認です。')


if __name__ == '__main__':
    # Windows file lock is released by the OS even after crashes.
    lock_file = None
    try:
        if sys.platform == 'win32':
            import msvcrt
            (ROOT / 'data').mkdir(parents=True, exist_ok=True)
            lock_file = (ROOT / 'data' / 'run.lock').open('a+b')
            lock_file.seek(0)
            if not lock_file.read(1):
                lock_file.write(b'0'); lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(),msvcrt.LK_NBLCK,1)
        main()
    except KeyboardInterrupt:
        print('中断しました。次回の実行で再取得できます。'); sys.exit(130)
    except Exception as exc:
        # Do not dump HTTP responses, OAuth URLs, tokens or credential payloads.
        if isinstance(exc, OSError):
            import traceback
            print(f'ファイル操作エラー: {type(exc).__name__} / Windows {getattr(exc,"winerror",None)} / errno {exc.errno}',file=sys.stderr)
            print(f'対象: {exc.filename!r}',file=sys.stderr)
            print(f'保存先: {str(ROOT)!r}',file=sys.stderr)
            print(f'実行ユーザー: {os.environ.get("USERNAME")} / PC: {os.environ.get("COMPUTERNAME")}',file=sys.stderr)
            for frame in traceback.extract_tb(exc.__traceback__):
                print(f'場所: {Path(frame.filename).name}:{frame.lineno} ({frame.name})',file=sys.stderr)
        elif isinstance(exc, ValueError):
            print(f'エラー: {exc}',file=sys.stderr)
        else:
            code = getattr(getattr(exc,'resp',None),'status',None)
            print(f'処理を停止しました: {type(exc).__name__} / HTTP {code or "-"}。SETUP.mdの対処を確認してください。',file=sys.stderr)
        sys.exit(1)
    finally:
        if lock_file:
            lock_file.close()
