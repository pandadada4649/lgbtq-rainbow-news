import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lgbtq-rainbow-news-secret-2025')

# --- DB設定 ---
database_url = os.environ.get('DATABASE_URL', '')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lgbtq_news.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- ログイン管理 ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- モデル ---
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Article(db.Model):
    __tablename__ = 'articles'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    summary     = db.Column(db.Text)
    url         = db.Column(db.String(500), unique=True)
    source_name = db.Column(db.String(100))
    source_type = db.Column(db.String(20), default='rss')  # 'rss' | 'user'
    category    = db.Column(db.String(50), default='general')
    area        = db.Column(db.String(50))
    image_url   = db.Column(db.String(500))
    published_at= db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)
    user_id     = db.Column(db.Integer, nullable=True)

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 定数 ---
CATEGORIES = [
    {'id': 'all',     'label': 'すべて',     'emoji': '🌈'},
    {'id': 'event',   'label': 'イベント',   'emoji': '🎉'},
    {'id': 'news',    'label': 'ニュース',   'emoji': '📰'},
    {'id': 'rights',  'label': '権利・制度', 'emoji': '⚖️'},
    {'id': 'support', 'label': 'サポート',   'emoji': '🤝'},
    {'id': 'general', 'label': 'その他',     'emoji': '✨'},
]
AREAS = ['全国', '東京', '大阪', '名古屋', '福岡', 'オンライン', 'その他']

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        active_cat=cat, active_area=area, q=q, total=total,
        current_user=current_user
    )

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    related = Article.query.filter_by(category=article.category).filter(Article.id != article_id).limit(4).all()
    return render_template('detail.html', article=article, related=related, current_user=current_user)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        url   = request.form.get('url', '').strip()
        title = request.form.get('title', '').strip()
        if not title:
            return render_template('submit.html', categories=CATEGORIES, areas=AREAS,
                                   error='タイトルは必須です', current_user=current_user)
        if url and Article.query.filter_by(url=url).first():
            return render_template('submit.html', categories=CATEGORIES, areas=AREAS,
                                   error='このURLはすでに登録されています', current_user=current_user)

        image_url = None
        image_file = request.files.get('image')
        if image_file and image_file.filename and allowed_file(image_file.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_url = '/static/uploads/' + filename

        article = Article(
            title       = title,
            summary     = request.form.get('summary', ''),
            url         = url or None,
            source_name = request.form.get('source_name', '投稿者'),
            source_type = 'user',
            category    = request.form.get('category', 'general'),
            area        = request.form.get('area', '全国'),
            image_url   = image_url,
            published_at= datetime.utcnow(),
            user_id     = current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(article)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('submit.html', categories=CATEGORIES, areas=AREAS,
                           error=None, current_user=current_user)

# --- 認証 ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not username or not email or not password:
            error = 'すべて入力してください'
        elif len(password) < 8:
            error = 'パスワードは8文字以上にしてください'
        elif User.query.filter_by(email=email).first():
            error = 'このメールアドレスはすでに登録されています'
        elif User.query.filter_by(username=username).first():
            error = 'このユーザー名はすでに使われています'
        else:
            user = User(username=username, email=email,
                        password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    return render_template('auth.html', page_title='新規登録', is_signup=True,
                           error=error, current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        error = 'メールアドレスまたはパスワードが間違っています'
    return render_template('auth.html', page_title='ログイン', is_signup=False,
                           error=error, current_user=current_user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 管理者専用 ---
@app.route('/feeds')
@login_required
def feeds_list():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    feeds = RssFeed.query.order_by(RssFeed.created_at.desc()).all()
    return render_template('feeds.html', feeds=feeds, categories=CATEGORIES,
                           areas=AREAS, current_user=current_user)

@app.route('/feeds/add', methods=['POST'])
@login_required
def feed_add():
    if not current_user.is_admin:
        return redirect(url_for('index'))
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
@login_required
def feed_delete(feed_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    feed = RssFeed.query.get_or_404(feed_id)
    db.session.delete(feed)
    db.session.commit()
    return redirect(url_for('feeds_list'))

@app.route('/feeds/toggle/<int:feed_id>', methods=['POST'])
@login_required
def feed_toggle(feed_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    feed = RssFeed.query.get_or_404(feed_id)
    feed.is_active = not feed.is_active
    db.session.commit()
    return redirect(url_for('feeds_list'))

@app.route('/article/delete/<int:article_id>', methods=['POST'])
@login_required
def article_delete(article_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/article/feature/<int:article_id>', methods=['POST'])
@login_required
def article_feature(article_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    article = Article.query.get_or_404(article_id)
    article.is_featured = not article.is_featured
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

# --- API ---
@app.route('/api/collect', methods=['POST'])
def api_collect():
    secret = request.headers.get('X-Cron-Secret', '')
    if secret != os.environ.get('CRON_SECRET', 'dev-secret'):
        return jsonify({'error': 'Unauthorized'}), 401
    from collector import collect_all
    result = collect_all(app, db, Article, RssFeed)
    return jsonify(result)

@app.route('/api/stats')
def api_stats():
    is_admin = current_user.is_authenticated and current_user.is_admin
    data = {
        'total_articles': Article.query.count(),
        'user_articles':  Article.query.filter_by(source_type='user').count(),
        'active_feeds':   RssFeed.query.filter_by(is_active=True).count(),
    }
    if is_admin:
        data['rss_articles'] = Article.query.filter_by(source_type='rss').count()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True)
