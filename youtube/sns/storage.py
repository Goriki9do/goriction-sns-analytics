import csv
import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .providers.youtube import METRICS


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE IF NOT EXISTS videos(platform TEXT, channel_id TEXT, video_id TEXT,
      title TEXT, published_at TEXT, duration_iso8601 TEXT, privacy_status TEXT,
      views INTEGER, likes INTEGER, comments INTEGER, fetched_at TEXT, available INTEGER,
      PRIMARY KEY(platform,channel_id,video_id));
    CREATE TABLE IF NOT EXISTS snapshots(platform TEXT,channel_id TEXT,video_id TEXT,
      fetched_at TEXT,views INTEGER,likes INTEGER,comments INTEGER,
      PRIMARY KEY(platform,channel_id,video_id,fetched_at));
    CREATE TABLE IF NOT EXISTS daily(platform TEXT,channel_id TEXT,video_id TEXT,
      day TEXT,content_type TEXT,payload TEXT,fetched_at TEXT,
      PRIMARY KEY(platform,channel_id,video_id,day,content_type));
    CREATE TABLE IF NOT EXISTS coverage(platform TEXT,channel_id TEXT,video_id TEXT,
      start_date TEXT,end_date TEXT, PRIMARY KEY(platform,channel_id,video_id));
    CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,channel_id TEXT,start_date TEXT,
      end_date TEXT,video_count INTEGER,daily_rows INTEGER);
    CREATE TABLE IF NOT EXISTS commenter_snapshots(channel_id TEXT,video_id TEXT,fetched_at TEXT,
      unique_commenters INTEGER,commenter_status TEXT,unidentified_comments INTEGER,own_comments_excluded INTEGER,
      PRIMARY KEY(channel_id,video_id,fetched_at));
    ''')
    return db


def next_start(db, channel, video, initial, end, full=False):
    row = db.execute('SELECT start_date,end_date FROM coverage WHERE platform=? AND channel_id=? AND video_id=?',
                     ('youtube', channel, video)).fetchone()
    if full or not row or initial < row['start_date'] or end < row['start_date']:
        return initial
    overlap = (date.fromisoformat(row['end_date']) - timedelta(days=28)).isoformat()
    return max(initial, min(overlap, end))


def save(db, channel, videos, reports, stamp, requested_start, end):
    with db:
        db.execute('UPDATE videos SET available=0 WHERE platform=? AND channel_id=?', ('youtube', channel))
        for v in videos:
            if 'commenter_status' in v:
                db.execute('INSERT INTO commenter_snapshots VALUES(?,?,?,?,?,?,?)',
                    (channel,v['video_id'],stamp,v['unique_commenters'],v['commenter_status'],
                     v['unidentified_comments'],v['own_comments_excluded']))
            db.execute('INSERT OR REPLACE INTO videos VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                ('youtube', channel, v['video_id'], v['title'], v['published_at'], v['duration_iso8601'],
                 v['privacy_status'], v['views'], v['likes'], v['comments'], stamp, 1))
            db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',
                ('youtube',channel,v['video_id'],stamp,v['views'],v['likes'],v['comments']))
        for video, start, rows in reports:
            # Replace successful requested windows; omitted rows remain missing, never fabricated zeros.
            db.execute('DELETE FROM daily WHERE platform=? AND channel_id=? AND video_id=? AND day BETWEEN ? AND ?',
                       ('youtube',channel,video,start,end))
            for r in rows:
                db.execute('INSERT INTO daily VALUES(?,?,?,?,?,?,?)',
                    ('youtube',channel,video,r['day'],r['creatorContentType'],json.dumps(r),stamp))
            old = db.execute('SELECT start_date,end_date FROM coverage WHERE platform=? AND channel_id=? AND video_id=?',
                             ('youtube',channel,video)).fetchone()
            actual_end = max((r['day'] for r in rows), default=start)
            earliest = min(start,old['start_date']) if old else start
            latest = max(actual_end,old['end_date']) if old else actual_end
            db.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?,?,?)', ('youtube',channel,video,earliest,latest))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',
                   (stamp,channel,requested_start,end,len(videos),sum(len(r) for _,_,r in reports)))


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def write_csv(path, fields, rows):
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_cell(row.get(key)) for key in fields})
    os.replace(temp,path)


def export(db, directory, channel):
    directory = Path(directory) / channel
    directory.mkdir(parents=True, exist_ok=True)
    videos = [dict(r) for r in db.execute('SELECT * FROM videos WHERE channel_id=? ORDER BY published_at', (channel,))]
    people = {(r['video_id'],r['fetched_at']):dict(r) for r in db.execute(
        'SELECT * FROM commenter_snapshots WHERE channel_id=?',(channel,))}
    people_fields = ['unique_commenters','commenter_status','unidentified_comments','own_comments_excluded']
    for v in videos:
        v.update({k:people.get((v['video_id'],v['fetched_at']),{}).get(k) for k in people_fields})
        v['comment_count_raw'] = v['comments']
    fields = ['platform','channel_id','video_id','title','published_at','duration_iso8601','privacy_status',
              'views','likes',*people_fields,'comment_count_raw','fetched_at','available']
    write_csv(directory / 'videos.csv', fields, videos)
    titles = {v['video_id']:v['title'] for v in videos}
    daily = []
    for r in db.execute('SELECT * FROM daily WHERE channel_id=? ORDER BY day,video_id,content_type', (channel,)):
        item = dict(r)
        payload = json.loads(item.pop('payload'))
        item.update({m:payload.get(m) for m in METRICS})
        item['comment_events_raw'] = item.pop('comments')
        item['title'] = titles.get(item['video_id'], '')
        gained, lost = item['subscribersGained'], item['subscribersLost']
        item['subscribers_net'] = gained-lost if gained is not None and lost is not None else None
        daily.append(item)
    fields = ['platform','channel_id','video_id','title','day','content_type',
              *[m if m != 'comments' else 'comment_events_raw' for m in METRICS],'subscribers_net','fetched_at']
    write_csv(directory / 'video_daily.csv', fields, [r for r in daily if r['video_id']])
    write_csv(directory / 'channel_daily.csv', fields, [r for r in daily if not r['video_id']])
    snapshots = [dict(r) for r in db.execute('SELECT * FROM snapshots WHERE channel_id=? ORDER BY video_id,fetched_at', (channel,))]
    previous = {}
    for r in snapshots:
        r.update({k:people.get((r['video_id'],r['fetched_at']),{}).get(k) for k in people_fields})
        r['comment_count_raw'] = r['comments']
        old = previous.get(r['video_id'])
        r['previous_fetched_at'] = old['fetched_at'] if old else None
        for m in ('views','likes','comments'):
            r[m+'_delta'] = r[m]-old[m] if old and r[m] is not None and old[m] is not None else None
        previous[r['video_id']] = r
        r['comment_count_raw_delta'] = r['comments_delta']
    write_csv(directory / 'snapshots.csv', ['platform','channel_id','video_id','fetched_at','views','likes',
        *people_fields,'comment_count_raw','previous_fetched_at','views_delta','likes_delta','comment_count_raw_delta'], snapshots)
    metadata = dict(channel_id=channel,platform='youtube',analytics_timezone='America/Los_Angeles',
        missing_values='Unknown or unreported, not zero', video_daily_rows=sum(bool(r['video_id']) for r in daily),
        observed_analytics_start=min((r['day'] for r in daily),default=None),
        observed_analytics_end=max((r['day'] for r in daily),default=None),
        latest_run=dict(db.execute('SELECT * FROM runs WHERE channel_id=? ORDER BY run_id DESC LIMIT 1',(channel,)).fetchone()))
    temp = directory / 'manifest.tmp'
    temp.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,directory / 'manifest.json')
    return directory
