import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sns.storage import connect, save, export, next_start
from sns.providers.youtube import YouTube, METRICS


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = connect(self.root / 'test.sqlite3')
        self.video = dict(video_id='v1',title='=危険,タイトル\nテスト',published_at='2026-01-01T00:00:00Z',
            duration_iso8601='PT30S',privacy_status='public',views=10,likes=2,comments=None)
        self.row = dict(day='2026-09-01',creatorContentType='SHORTS',**{m:1 for m in METRICS})

    def tearDown(self):
        self.db.close(); self.temp.cleanup()

    def store(self, stamp, rows=None):
        save(self.db,'channel',[self.video],[('v1','2026-09-01',[self.row] if rows is None else rows)],
             stamp,'2026-09-01','2026-09-20')

    def test_repeat_corrects_and_exports_deltas(self):
        self.store('2026-09-21')
        self.video['views']=17
        self.row['views']=8
        self.store('2026-09-22')
        self.assertEqual(self.db.execute('SELECT count(*) FROM daily').fetchone()[0],1)
        self.assertEqual(json.loads(self.db.execute('SELECT payload FROM daily').fetchone()[0])['views'],8)
        path=export(self.db,self.root / 'exports','channel')
        with (path/'snapshots.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(rows[-1]['views_delta'],'7')
        self.assertEqual(rows[0]['views_delta'],'')
        with (path/'videos.csv').open(encoding='utf-8-sig',newline='') as f:
            self.assertEqual(next(csv.DictReader(f))['title'],"'"+self.video['title'])

    def test_transaction_rolls_back_on_bad_duplicate(self):
        self.store('one')
        self.video['views']=999
        with self.assertRaises(Exception): self.store('two',[self.row,self.row])
        self.assertEqual(self.db.execute('SELECT views FROM videos').fetchone()[0],10)
        self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)

    def test_commenter_history_unknown_then_refresh_and_decrease(self):
        self.store('one')
        self.video.update(unique_commenters=2,commenter_status='complete',unidentified_comments=0,own_comments_excluded=3)
        self.store('two')
        self.video['unique_commenters']=1
        self.store('three')
        path=export(self.db,self.root/'exports','channel')
        with (path/'videos.csv').open(encoding='utf-8-sig',newline='') as f:
            row=next(csv.DictReader(f))
        self.assertEqual(row['unique_commenters'],'1')
        self.assertNotIn('comments',row)
        with (path/'snapshots.csv').open(encoding='utf-8-sig',newline='') as f:
            rows={r['fetched_at']:r for r in csv.DictReader(f)}
        self.assertEqual(rows['one']['unique_commenters'],'')
        self.assertEqual(rows['two']['unique_commenters'],'2')

    def test_missing_is_removed_not_zero_and_channel_isolation(self):
        self.store('one'); self.store('two',[])
        self.assertEqual(self.db.execute('SELECT count(*) FROM daily').fetchone()[0],0)
        self.assertEqual(next_start(self.db,'other','v1','2026-01-01','2026-09-20'),'2026-01-01')

    def test_overlap_and_full(self):
        self.row['day']='2026-09-20'; self.store('one')
        self.assertEqual(next_start(self.db,'channel','v1','2026-09-01','2026-09-22'),'2026-09-01')
        self.assertEqual(next_start(self.db,'channel','v1','2026-01-01','2026-09-22',True),'2026-01-01')


class QueryTests(unittest.TestCase):
    def test_commenters_include_all_replies_and_exclude_owner(self):
        def comment(id, author):
            return {'id':id,'snippet':{'authorChannelId':{'value':author}} if author else {}}
        calls=[]
        class Fake:
            def commentThreads(self): self.kind='threads'; return self
            def comments(self): self.kind='replies'; return self
            def list(self,**kwargs): self.args=kwargs; calls.append((self.kind,kwargs)); return self
            def execute(self,**kwargs):
                if self.kind=='threads':
                    if self.args['pageToken']:
                        return {'items':[{'snippet':{'topLevelComment':comment('t2','a')}}]}
                    return {'items':[{'snippet':{'topLevelComment':comment('t1','a'),'totalReplyCount':4}}], 'nextPageToken':'next'}
                if self.args['pageToken']:
                    return {'items':[comment('r2','a'),comment('r3','b'),comment('r4',None)]}
                return {'items':[comment('r1','owner'),comment('r2','a')],'nextPageToken':'next'}
        provider=YouTube.__new__(YouTube); provider.data=Fake()
        result=provider.commenters('owner','v')
        self.assertEqual(result,dict(unique_commenters=2,commenter_status='partial_missing_author_id',
            unidentified_comments=1,own_comments_excluded=1))
        self.assertEqual(len(calls),4)

    def test_comments_disabled_is_unknown_and_other_errors_propagate(self):
        class ApiError(Exception):
            content=b'{"error":{"errors":[{"reason":"commentsDisabled"}]}}'
        class Fake:
            def commentThreads(self): return self
            def list(self,**kwargs): return self
            def execute(self,**kwargs): raise ApiError()
        provider=YouTube.__new__(YouTube); provider.data=Fake()
        self.assertIsNone(provider.commenters('owner','v')['unique_commenters'])
        ApiError.content=b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}'
        with self.assertRaises(ApiError): provider.commenters('owner','v')

    def test_pagination_keeps_every_row(self):
        calls=[]
        headers=['day','creatorContentType',*METRICS]
        class Fake:
            def reports(self): return self
            def query(self,**kwargs): calls.append(kwargs); return self
            def execute(self,**kwargs):
                count=200 if len(calls)==1 else 1
                return {'columnHeaders':[{'name':h} for h in headers],
                        'rows':[['2026-01-01','SHORTS',*([1]*len(METRICS))] for _ in range(count)]}
        provider=YouTube.__new__(YouTube); provider.analytics=Fake()
        rows=provider.daily('c','v','2026-01-01','2026-01-01')
        self.assertEqual(len(rows),201)
        self.assertEqual(calls[1]['startIndex'],201)

    def test_filtered_time_report_and_month_chunks(self):
        calls=[]
        class Fake:
            def reports(self): return self
            def query(self,**kwargs): calls.append(kwargs); return self
            def execute(self,**kwargs): return {'rows':[]}
        provider=YouTube.__new__(YouTube); provider.analytics=Fake()
        self.assertEqual(provider.daily('c','v','2026-01-01','2026-02-02'),[])
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['filters'],'video==v')
        self.assertEqual(calls[0]['dimensions'],'day,creatorContentType')
        self.assertEqual(calls[1]['startDate'],'2026-02-01')


if __name__ == '__main__': unittest.main()
