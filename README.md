# 🌈 Rainbow News — LGBTQ自動まとめサイト

日本のLGBTQニュース・イベント情報をRSSで自動収集するサイト。

## ローカル開発スタート

```bash
# 1. 依存インストール
pip install -r requirements.txt

# 2. 環境変数設定
cp .env.example .env

# 3. 起動
python app.py
# → http://localhost:5001

# 4. RSS収集テスト（別ターミナル）
python collector.py
```

## ファイル構成

```
lgbtq-news/
├── app.py          # Flaskメインアプリ
├── collector.py    # RSS収集モジュール
├── requirements.txt
├── render.yaml     # Renderデプロイ設定
├── .env.example
└── templates/
    ├── index.html  # トップページ
    ├── detail.html # 記事詳細
    ├── submit.html # 情報投稿
    └── feeds.html  # フィード管理
```

## 機能

- **自動収集**: RSSフィードから3時間ごとに自動取得（Render Cron）
- **手動収集**: フィード管理ページから即時収集可能
- **ユーザー投稿**: URL・タイトル・概要を手動投稿
- **カテゴリ**: イベント / ニュース / 権利・制度 / サポート / その他
- **エリア**: 東京 / 大阪 / 名古屋 / 福岡 / オンライン / 全国
- **検索・フィルター**: キーワード × カテゴリ × エリア
- **ページネーション**: 12件/ページ

## Renderデプロイ

1. GitHubにpush
2. Renderで「New Web Service」→ リポジトリ選択
3. `render.yaml` が自動検出される
4. 環境変数 `DATABASE_URL` を設定（PostgreSQL）

## Phase 2 以降の予定

- [ ] Peatix/Doorkeeperスクレイピング追加
- [ ] 管理者ログイン（記事承認・FEATURED設定）
- [ ] タグ機能
- [ ] OGP設定
- [ ] 既存LGBTQイベントボードとの連携
