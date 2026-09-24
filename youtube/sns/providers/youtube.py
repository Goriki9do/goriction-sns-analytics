from datetime import date, timedelta
import json

METRICS = ['views', 'engagedViews', 'likes', 'comments', 'estimatedMinutesWatched',
           'averageViewDuration', 'averageViewPercentage', 'subscribersGained', 'subscribersLost']


def execute(request):
    return request.execute(num_retries=4)


class YouTube:
    platform = 'youtube'

    def __init__(self, credentials):
        from googleapiclient.discovery import build
        import httplib2
        import google_auth_httplib2
        def transport():
            return google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=60))
        self.data = build('youtube', 'v3', http=transport(), cache_discovery=False)
        self.analytics = build('youtubeAnalytics', 'v2', http=transport(), cache_discovery=False)

    def inventory(self):
        channels = execute(self.data.channels().list(part='snippet,contentDetails', mine=True))['items']
        if len(channels) != 1:
            raise ValueError('認証したチャンネルを一意に取得できません。YouTubeのチャンネル選択を確認してください。')
        channel = channels[0]
        playlist = channel['contentDetails']['relatedPlaylists']['uploads']
        ids, token = [], None
        while True:
            page = execute(self.data.playlistItems().list(part='contentDetails', playlistId=playlist,
                           maxResults=50, pageToken=token))
            ids.extend(x['contentDetails']['videoId'] for x in page.get('items', []))
            token = page.get('nextPageToken')
            if not token:
                break
        videos = []
        ids = list(dict.fromkeys(ids))
        for offset in range(0, len(ids), 50):
            page = execute(self.data.videos().list(part='snippet,contentDetails,statistics,status',
                           id=','.join(ids[offset:offset + 50])))
            for item in page.get('items', []):
                s, stats = item['snippet'], item.get('statistics', {})
                videos.append(dict(video_id=item['id'], title=s['title'], published_at=s['publishedAt'],
                    duration_iso8601=item['contentDetails']['duration'],
                    privacy_status=item['status']['privacyStatus'],
                    views=int(stats['viewCount']) if 'viewCount' in stats else None,
                    likes=int(stats['likeCount']) if 'likeCount' in stats else None,
                    comments=int(stats['commentCount']) if 'commentCount' in stats else None))
        return channel, videos

    def commenters(self, channel_id, video_id):
        authors, seen, unknown = set(), set(), set()
        own = 0
        def collect(item):
            nonlocal own
            if item['id'] in seen:
                return
            seen.add(item['id'])
            author = item['snippet'].get('authorChannelId', {}).get('value')
            if not author:
                unknown.add(item['id'])
            elif author == channel_id:
                own += 1
            else:
                authors.add(author)
        try:
            token = None
            while True:
                page = execute(self.data.commentThreads().list(part='snippet', videoId=video_id,
                    maxResults=100, pageToken=token, textFormat='plainText'))
                for thread in page.get('items', []):
                    snippet = thread['snippet']
                    top = snippet['topLevelComment']
                    collect(top)
                    if snippet.get('totalReplyCount', 0):
                        reply_token = None
                        while True:
                            replies = execute(self.data.comments().list(part='snippet',parentId=top['id'],
                                maxResults=100,pageToken=reply_token,textFormat='plainText'))
                            for reply in replies.get('items', []):
                                collect(reply)
                            reply_token = replies.get('nextPageToken')
                            if not reply_token:
                                break
                token = page.get('nextPageToken')
                if not token:
                    break
        except Exception as exc:
            try:
                reasons = {e.get('reason') for e in json.loads(exc.content).get('error',{}).get('errors',[])}
            except (AttributeError, ValueError, TypeError):
                reasons = set()
            if reasons == {'commentsDisabled'}:
                return dict(unique_commenters=None,commenter_status='comments_disabled',
                    unidentified_comments=None,own_comments_excluded=None)
            if reasons == {'insufficientPermissions'}:
                raise ValueError('コメント人数の取得権限が不足しています。追加権限の承認とGoogle再認証が必要です。保存済みデータは更新していません。') from None
            raise
        return dict(unique_commenters=len(authors),
            commenter_status='partial_missing_author_id' if unknown else 'complete',
            unidentified_comments=len(unknown),own_comments_excluded=own)

    def daily(self, channel_id, video_id, start, end):
        """One filtered video per query avoids top-video report's 200-video limit."""
        result = []
        first = date.fromisoformat(start)
        last = date.fromisoformat(end)
        while first <= last:
            stop = min(first + timedelta(days=30), last)
            index = 1
            while True:
                args = dict(ids=f'channel=={channel_id}', startDate=first.isoformat(),
                    endDate=stop.isoformat(), dimensions='day,creatorContentType',
                    metrics=','.join(METRICS), sort='day,creatorContentType',
                    maxResults=200, startIndex=index)
                if video_id:
                    args['filters'] = f'video=={video_id}'
                page = execute(self.analytics.reports().query(**args))
                headers = [h['name'] for h in page.get('columnHeaders', [])]
                rows = page.get('rows', [])
                if rows and not {'day', 'creatorContentType', *METRICS}.issubset(headers):
                    raise ValueError('Analyticsの応答列が想定と異なります。既存データは更新しません。')
                result.extend(dict(zip(headers, row)) for row in rows)
                if len(rows) < 200:
                    break
                index += len(rows)
            first = stop + timedelta(days=1)
        return result
