# 政策立案支援アプリ バックエンドシステム

## 概要

本バックエンドシステムは、「政策立案支援アプリ」のフロントエンドからのリクエストに基づき、以下の主要な機能を提供するAPIサーバーです。

- ユーザーが入力した新規事業計画のテキストデータを**ベクトル化**
- 事前にベクトル化しておいた過去の行政レビューシートのデータと**類似度を比較**
- 類似度の高い過去の事業データを基に、新規事業の**参考予算額を予測**し、**類似事業のリスト**をフロントエンドに返す

## システム構成

```
backend/
├── app.py                 # Flask APIサーバー
├── config.py              # 設定管理
├── data_processor.py      # データ処理・ベクトル化
├── budget_predictor.py    # 予算予測ロジック
├── sample_data.py         # サンプルデータ生成
├── requirements.txt       # Python依存関係
└── README.md             # このファイル
```

## 技術スタック

- **言語**: Python 3.8+
- **フレームワーク**: Flask 2.3.3
- **主要ライブラリ**:
  - `pandas`: データハンドリング
  - `numpy`: 数値計算・ベクトル演算
  - `openai`: OpenAI APIの利用
  - `python-dotenv`: 環境変数の管理
  - `flask-cors`: CORS対応
- **API**: OpenAI Embedding API (`text-embedding-3-small`)

## セットアップ

### 1. 環境準備

```bash
# Python仮想環境を作成
python -m venv venv

# 仮想環境を有効化
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt
```

### 2. 環境変数設定

`.env`ファイルを作成し、以下の内容を設定してください：

```bash
# OpenAI API設定
OPENAI_API_KEY=your-openai-api-key-here

# アプリケーション設定
FLASK_ENV=development
FLASK_DEBUG=true

# サーバー設定
HOST=0.0.0.0
PORT=5000

# ログレベル
LOG_LEVEL=INFO
```

**注意**: OpenAI APIキーを取得するには、[OpenAI](https://platform.openai.com/)のアカウントが必要です。

### 3. CSVデータの準備

アプリケーションは `final_2024.csv` ファイルから実際の行政レビューシートデータを読み込みます。

```bash
# CSVデータの読み込みテスト
python test_csv.py
```

**CSVファイルの要件:**
- ファイル名: `final_2024.csv`
- 配置場所: プロジェクトルートディレクトリ
- 必要な列: 予算事業ID, 府省庁, 事業の概要, 当初予算, 事業名, 現状・課題, embedding_sum, 相対誤差% など

## 使用方法

### 1. サーバーの起動

```bash
# 開発モードで起動
python app.py

# または
flask run
```

サーバーは `http://localhost:5000` で起動します。

### 2. APIエンドポイント

#### ヘルスチェック
```bash
GET /health
```

#### 事業計画分析
```bash
POST /analyze
Content-Type: application/json

{
  "issue_text": "現状・目的（課題）のテキスト",
  "summary_text": "事業概要（課題解決策）のテキスト"
}
```

#### プロジェクト一覧取得
```bash
GET /projects
```

#### プロジェクト詳細取得
```bash
GET /projects/{project_id}
```

#### 統計情報取得
```bash
GET /stats
```

#### 分析ログ一覧取得
```bash
GET /logs?limit=50&offset=0&status=success&date_from=2024-01-01&date_to=2024-12-31
```

#### 特定ログの詳細取得
```bash
GET /logs/{log_id}
```

#### ログ統計情報取得
```bash
GET /logs/stats
```

#### 古いログの削除
```bash
POST /logs/cleanup?days=90
```

## 処理フロー

### 1. 事前準備（オフライン・バッチ処理）

1. CSVファイルからの実データ読み込み
2. データの前処理（テキストクリーニング、評価ランク生成）
3. 既存のベクトル埋め込みデータの処理
4. ベクトルDBとメタデータの作成・保存

### 2. API実行（オンライン・リアルタイム処理）

1. フロントエンドからリクエスト受信
2. 受信したテキストを結合し、ベクトル化
3. 事前準備で作成したベクトルDBを読込
4. 類似度計算・予算予測を実行
5. 予測結果と類似事業リストをJSON形式で整形
6. フロントエンドへレスポンスを送信

## 設定パラメータ

`config.py`で以下のパラメータを調整できます：

- **TOPK**: 類似度上位K件（デフォルト: 10）
- **TAU**: 類似度閾値（デフォルト: 0.1）
- **ALPHA**: 類似度重み（デフォルト: 0.7）
- **BETA**: 予算重み（デフォルト: 0.3）
- **BATCH_SIZE**: ベクトル化のバッチサイズ（デフォルト: 128）

## フロントエンドとの連携

### CORS設定

フロントエンドからのアクセスを許可するため、以下のオリジンが設定されています：

- `http://localhost:3000`
- `http://127.0.0.1:5000`
- `http://localhost:5000`

### レスポンス形式

分析APIのレスポンス例：

```json
{
  "predicted_budget": 155000000.0,
  "average_budget": 155000000.0,
  "case_count": 7,
  "similar_cases": [
    {
      "id": 4,
      "name": "サテライトオフィス誘致プロジェクト",
      "budget": "130000000",
      "eval": "C",
      "evalText": "C評価: 要改善、一部目標未達、改善が必要",
      "details": "誘致企業数が目標の6割に留まった。プロモーション戦略の見直しが必要。",
      "similarity": 0.885,
      "weight": 0.35,
      "year": 2022
    }
  ],
  "message": "分析が完了しました"
}
```

## 開発・テスト

### 個別モジュールのテスト

```bash
# CSVデータの読み込みテスト
python test_csv.py

# 予算予測のテスト
python budget_predictor.py

# データベースモデルのテスト
python models.py
```

### APIテスト

```bash
# ヘルスチェック
curl http://localhost:5000/health

# 分析APIテスト
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "issue_text": "地域の小規模事業者がデジタル化の波に取り残されている",
    "summary_text": "地域の小規模事業者のデジタル化を支援し、地域経済の活性化を図る"
  }'
```

## トラブルシューティング

### よくある問題

1. **OpenAI APIキーエラー**
   - `.env`ファイルに正しいAPIキーが設定されているか確認
   - APIキーの有効性を確認

2. **依存関係エラー**
   - 仮想環境が有効化されているか確認
   - `pip install -r requirements.txt`を再実行

3. **ポート競合**
   - `config.py`でポート番号を変更
   - 他のプロセスがポートを使用していないか確認

### ログ確認

アプリケーションのログは標準出力に表示されます。エラーが発生した場合は、ログメッセージを確認してください。

## 今後の拡張予定

- **グラフ表示**: 予算分布や評価の内訳を可視化
- **AI分析**: より高度な類似事業の検索・分析
- **データベース連携**: 外部データベースとの連携
- **ユーザー管理**: 複数ユーザーでの利用
- **履歴管理**: 分析履歴の保存・参照
- **CSVファイル対応**: 実際の行政レビューシートデータの読み込み

## ライセンス

このプロジェクトは教育・研究目的で作成されています。

## 注意事項

- このバージョンは実際の行政レビューシートデータ（final_2024.csv）を使用しています
- 3790件の実際の政策事業データを分析に活用
- 実際の政策立案では、より詳細な分析と専門家の判断が必要です
- OpenAI APIの利用には料金が発生する場合があります
- 本番環境での利用前に、セキュリティ設定の見直しが必要です
