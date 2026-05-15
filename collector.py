"""
collector.py — RSS自動収集モジュール
"""
import feedparser
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup


def parse_date(entry):
    for attr in ('published_parsed', 'updated_parsed', 'created_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
    return datetime.utcnow()


def get_thumbnail(entry, feed_url):
    """Googleニュース系は画像なし、それ以外はメディアから取得"""
    if 'google' in str(feed_url):
        return ''
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url', '')
        if url and 'google' not in url and 'gstatic' not in url:
            return url
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image'):
                url = enc.get('url', '')
                if url and 'google' not in url:
                    return url
    return ''


def guess_category(text):
    text = text.lower()
    if any(w in text for w in ['パレード', 'parade', 'イベント', 'event', '祭', 'フェス', 'pride']):
        return 'event'
    if any(w in text for w in ['法律', '制度', '権利', '条例', '法案', '婚姻', '同性婚', 'rights']):
        return 'rights'
    if any(w in text for w in ['相談', 'サポート', '支援', '悩み', 'カウンセリング', 'support']):
        return 'support'
    if any(w in text for w in ['ニュース', '報道', '記事', 'news']):
        return 'news'
    return 'general'


def guess_area(text):
    if any(w in text for w in ['東京', '渋谷', '新宿', '池袋', '品川']):
        return '東京'
    if any(w in text for w in ['大阪', '梅田', '難波', '心斎橋']):
        return '大阪'
    if any(w in text for w in ['名古屋', '愛知']):
        return '名古屋'
    if any(w in text for w in ['福岡', '博多', '天神']):
        return '福岡'
    if any(w in text for w in ['オンライン', 'online', 'zoom', 'youtube', '配信']):
        return 'オンライン'
    return '全国'


def collect_all(app, db, Article, RssFeed):
    results = {'feeds_checked': 0, 'new_articles': 0, 'skipped': 0, 'errors': []}
    with app.app_context():
        feeds = RssFeed.query.filter_by(is_active=True).all()
        results['feeds_checked'] = len(feeds)
        for feed in feeds:
            try:
                parsed = feedparser.parse(feed.url)
                if parsed.bozo and not parsed.entries:
                    results['errors'].append(f'{feed.name}: パース失敗')
                    continue
                for entry in parsed.entries[:20]:
                    link = getattr(entry, 'link', '') or ''
                    title = getattr(entry, 'title', '').strip()
                    if not title:
                        results['skipped'] += 1
                        continue
                    if link and Article.query.filter_by(url=link).first():
                        results['skipped'] += 1
                        continue
                    summary = ''
                    for attr in ('summary', 'description', 'content'):
                        val = getattr(entry, attr, None)
                        if val:
                            if isinstance(val, list):
                                val = val[0].get('value', '')
                            summary = BeautifulSoup(val, 'html.parser').get_text()[:300]
                            break
                    full_text = title + ' ' + summary
                    article = Article(
                        title        = title[:200],
                        summary      = summary,
                        url          = link or None,
                        source_name  = feed.name,
                        source_type  = 'rss',
                        category     = feed.category or guess_category(full_text),
                        area         = feed.area or guess_area(full_text),
                        image_url    = get_thumbnail(entry, feed.url),
                        published_at = parse_date(entry),
                    )
                    db.session.add(article)
                    results['new_articles'] += 1
                feed.last_fetched = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                results['errors'].append(f'{feed.name}: {str(e)}')
                db.session.rollback()
    return results


if __name__ == '__main__':
    from app import app, db, Article, RssFeed
    result = collect_all(app, db, Article, RssFeed)
    print(f"✅ 収集完了: {result}")