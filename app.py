import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lgbtq-news-auto-secret-2025'

# --- DB設定 ---
database_url = os.environ.get('DATABASE_URL', '')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lgbtq_news.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- モデル ---
class Article(db.Model):
    __tablename__ = 'articles'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    summary     = db.Column(db.Text)
    url         = db.Column(db.String(500), unique=True)   # 重複防止
    source_name = db.Column(db.String(100))                # サイト名
    source_type = db.Column(db.String(20), default='rss')  # 'rss' | 'user'
    category    = db.Column(db.String(50), default='general')
    area        = db.Column(db.String(50))
    image_url   = db.Column(db.String(500))
    published_at= db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)

class RssFeed(db.Model):
    __tablename__ = 'rss_feeds'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    url         = db.Column(db.String(500), nullable=False, unique=True)
    category    = db.Column(db.String(50), default='general')
    area        = db.Column(db.String(50))
    is_active   = db.Column(db.Boolean, default=True)
    last_fetched= db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    # 初期RSSフィードを登録
    if RssFeed.query.count() == 0:
        seeds = [
            RssFeed(name='虹色ダイバーシティ',     url='https://nijiirodiversity.jp/feed/',           category='rights',  area='全国'),
            RssFeed(name='Google News - LGBTQ',    url='https://news.google.com/rss/search?q=LGBTQ+イベント+日本&hl=ja&gl=JP&ceid=JP:ja', category='news', area='全国'),
            RssFeed(name='Google News - プライド',  url='https://news.google.com/rss/search?q=プライドパレード+2025&hl=ja&gl=JP&ceid=JP:ja', category='event', area='全国'),
            RssFeed(name='Google News - 性的少数者', url='https://news.google.com/rss/search?q=性的少数者+イベント&hl=ja&gl=JP&ceid=JP:ja', category='news', area='全国'),
        ]
        for s in seeds:
            db.session.add(s)
        db.session.commit()

# --- カテゴリ定義 ---
CATEGORIES = [
    {'id': 'all',     'label': 'すべて',     'emoji': '🌈', 'color': '#a855f7'},
    {'id': 'event',   'label': 'イベント',   'emoji': '🎉', 'color': '#ec4899'},
    {'id': 'news',    'label': 'ニュース',   'emoji': '📰', 'color': '#3b82f6'},
    {'id': 'rights',  'label': '権利・制度', 'emoji': '⚖️', 'color': '#10b981'},
    {'id': 'support', 'label': 'サポート',   'emoji': '🤝', 'color': '#f59e0b'},
    {'id': 'general', 'label': 'その他',     'emoji': '✨', 'color': '#6b7280'},
]

AREAS = ['全国', '東京', '大阪', '名古屋', '福岡', 'オンライン', 'その他']

# ===== ROUTES =====

@app.route('/')
def index():
    cat  = request.args.get('cat', 'all')
    area = request.args.get('area', '')
    q    = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    query = Article.query
    if cat and cat != 'all':
        query = query.filter_by(category=cat)
    if area:
        query = query.filter_by(area=area)
    if q:
        query = query.filter(
            Article.title.ilike(f'%{q}%') | Article.summary.ilike(f'%{q}%')
        )

    total    = query.count()
    articles = query.order_by(Article.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    featured = Article.query.filter_by(is_featured=True).order_by(Article.created_at.desc()).limit(3).all()

    return render_template('index.html',
        articles=articles, featured=featured,
        categories=CATEGORIES, areas=AREAS,
        active_cat=cat, active_area=area, q=q, total=total
    )

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    related = Article.query.filter_by(category=article.category).filter(Article.id != article_id).limit(4).all()
    return render_template('detail.html', article=article, related=related)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        url   = request.form.get('url', '').strip()
        title = request.form.get('title', '').strip()
        if not title:
            return render_template('submit.html', categories=CATEGORIES, areas=AREAS, error='タイトルは必須です')
        # URL重複チェック
        if url and Article.query.filter_by(url=url).first():
            return render_template('submit.html', categories=CATEGORIES, areas=AREAS, error='このURLはすでに登録されています')

        article = Article(
            title       = title,
            summary     = request.form.get('summary', ''),
            url         = url or None,
            source_name = request.form.get('source_name', '投稿者'),
            source_type = 'user',
            category    = request.form.get('category', 'general'),
            area        = request.form.get('area', '全国'),
            published_at= datetime.utcnow(),
        )
        db.session.add(article)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('submit.html', categories=CATEGORIES, areas=AREAS, error=None)

@app.route('/feeds')
def feeds_list():
    feeds = RssFeed.query.order_by(RssFeed.created_at.desc()).all()
    return render_template('feeds.html', feeds=feeds, categories=CATEGORIES, areas=AREAS)

@app.route('/feeds/add', methods=['POST'])
def feed_add():
    name = request.form.get('name', '').strip()
    url  = request.form.get('url', '').strip()
    if name and url:
        if not RssFeed.query.filter_by(url=url).first():
            feed = RssFeed(
                name    = name,
                url     = url,
                category= request.form.get('category', 'general'),
                area    = request.form.get('area', '全国'),
            )
            db.session.add(feed)
            db.session.commit()
    return redirect(url_for('feeds_list'))

@app.route('/feeds/delete/<int:feed_id>', methods=['POST'])
def feed_delete(feed_id):
    feed = RssFeed.query.get_or_404(feed_id)
    db.session.delete(feed)
    db.session.commit()
    return redirect(url_for('feeds_list'))

@app.route('/api/collect', methods=['POST'])
def api_collect():
    """RSS収集エンドポイント（Cron Jobから叩く）"""
    secret = request.headers.get('X-Cron-Secret', '')
    if secret != os.environ.get('CRON_SECRET', 'dev-secret'):
        return jsonify({'error': 'Unauthorized'}), 401
    from collector import collect_all
    result = collect_all(app, db, Article, RssFeed)
    return jsonify(result)

@app.route('/api/stats')
def api_stats():
    return jsonify({
        'total_articles': Article.query.count(),
        'rss_articles':   Article.query.filter_by(source_type='rss').count(),
        'user_articles':  Article.query.filter_by(source_type='user').count(),
        'active_feeds':   RssFeed.query.filter_by(is_active=True).count(),
        'categories':     {c['id']: Article.query.filter_by(category=c['id']).count() for c in CATEGORIES if c['id'] != 'all'}
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True)
