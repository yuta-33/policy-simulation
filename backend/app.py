from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import traceback
import time
from datetime import datetime
from config import Config
from data_processor import DataProcessor
from budget_predictor import BudgetPredictor
from models import DatabaseManager

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flaskアプリケーションの初期化
app = Flask(__name__)

# CORS設定
CORS(app, origins=Config.CORS_ORIGINS, methods=['GET', 'POST', 'OPTIONS'])

# グローバル変数
data_processor = None
budget_predictor = None
db_manager = None

def initialize_services():
    """サービスを初期化"""
    global data_processor, budget_predictor, db_manager
    
    try:
        logger.info("サービスを初期化中...")
        
        # データプロセッサーを初期化
        data_processor = DataProcessor()
        
        # ベクトルデータベースを準備（CSVファイルを使用）
        data_processor.prepare_vector_database(use_sample_data=False)
        
        # 予算予測器を初期化
        budget_predictor = BudgetPredictor(data_processor)
        
        # データベースマネージャーを初期化
        db_manager = DatabaseManager()
        
        logger.info("サービス初期化完了")
        
    except Exception as e:
        logger.error(f"サービス初期化エラー: {e}")
        logger.error(traceback.format_exc())
        raise

@app.before_first_request
def before_first_request():
    """初回リクエスト前に実行"""
    initialize_services()

@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'policy-budget-simulator-api'
    })

@app.route('/analyze', methods=['POST'])
def analyze_project():
    """
    新規事業計画の分析エンドポイント
    
    リクエスト形式:
    {
        "issue_text": "現状・目的（課題）のテキスト",
        "summary_text": "事業概要（課題解決策）のテキスト"
    }
    
    レスポンス形式:
    {
        "predicted_budget": 予測予算額,
        "average_budget": 類似事業平均予算,
        "case_count": 類似事業件数,
        "similar_cases": [類似事業のリスト],
        "message": "処理結果メッセージ"
    }
    """
    start_time = time.time()
    
    try:
        # リクエストデータを取得
        request_data = request.get_json()
        
        if not request_data:
            return jsonify({
                'error': 'リクエストデータが不正です',
                'message': 'JSONデータが必要です'
            }), 400
        
        # 必須フィールドのチェック
        issue_text = request_data.get('issue_text', '').strip()
        summary_text = request_data.get('summary_text', '').strip()
        
        if not issue_text or not summary_text:
            return jsonify({
                'error': '必須フィールドが不足しています',
                'message': 'issue_text と summary_text は必須です'
            }), 400
        
        logger.info(f"分析リクエスト受信: issue_text='{issue_text[:50]}...', summary_text='{summary_text[:50]}...'")
        
        # 予算予測器が初期化されているかチェック
        if budget_predictor is None:
            logger.error("予算予測器が初期化されていません")
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # 分析を実行
        analysis_result = budget_predictor.analyze_query(issue_text, summary_text)
        
        processing_time = time.time() - start_time
        
        logger.info(f"分析完了: 予測予算={analysis_result['predicted_budget']:,.0f}, 類似事業数={analysis_result['case_count']}")
        
        # ログを保存
        if db_manager and not analysis_result.get('error'):
            try:
                log_data = {
                    'issue_text': issue_text,
                    'summary_text': summary_text,
                    'proposed_budget': None,  # フロントエンドから送信されていない場合
                    'predicted_budget': analysis_result.get('predicted_budget'),
                    'average_budget': analysis_result.get('average_budget'),
                    'case_count': analysis_result.get('case_count'),
                    'similar_cases': analysis_result.get('similar_cases', []),
                    'user_ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'processing_time': processing_time,
                    'status': 'success'
                }
                
                log_id = db_manager.save_analysis_log(log_data)
                logger.info(f"分析ログを保存しました。ID: {log_id}")
                
            except Exception as log_error:
                logger.error(f"ログ保存エラー: {log_error}")
                # ログ保存エラーは分析結果には影響しない
        
        # レスポンスを返す
        return jsonify(analysis_result)
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        logger.error(f"分析処理中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        # エラーログを保存
        if db_manager:
            try:
                log_data = {
                    'issue_text': issue_text if 'issue_text' in locals() else '',
                    'summary_text': summary_text if 'summary_text' in locals() else '',
                    'proposed_budget': None,
                    'predicted_budget': None,
                    'average_budget': None,
                    'case_count': 0,
                    'similar_cases': [],
                    'user_ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'processing_time': processing_time,
                    'status': 'error',
                    'error_message': str(e)
                }
                
                log_id = db_manager.save_analysis_log(log_data)
                logger.info(f"エラーログを保存しました。ID: {log_id}")
                
            except Exception as log_error:
                logger.error(f"エラーログ保存エラー: {log_error}")
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'分析処理中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/projects', methods=['GET'])
def get_projects():
    """
    全プロジェクト一覧を取得するエンドポイント
    
    レスポンス形式:
    {
        "projects": [プロジェクトのリスト],
        "total_count": 総件数
    }
    """
    try:
        if data_processor is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # メタデータを取得
        embeddings, metadata = data_processor.load_vector_database()
        
        # プロジェクト情報を整形
        projects = []
        for _, row in metadata.iterrows():
            project = {
                'id': int(row['id']),
                'name': str(row['project_name']),
                'year': int(row['year']),
                'budget': int(row['budget']),
                'rating': str(row['rating']),
                'description': str(row['description']),
                'outcomes': str(row['outcomes'])
            }
            projects.append(project)
        
        return jsonify({
            'projects': projects,
            'total_count': len(projects)
        })
        
    except Exception as e:
        logger.error(f"プロジェクト一覧取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'プロジェクト一覧取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/projects/<int:project_id>', methods=['GET'])
def get_project_detail(project_id):
    """
    特定のプロジェクトの詳細を取得するエンドポイント
    
    Args:
        project_id: プロジェクトID
        
    レスポンス形式:
    {
        "id": プロジェクトID,
        "name": プロジェクト名,
        "year": 年度,
        "budget": 予算,
        "rating": 評価,
        "description": 説明,
        "outcomes": 成果・課題
    }
    """
    try:
        if data_processor is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # メタデータを取得
        embeddings, metadata = data_processor.load_vector_database()
        
        # 指定されたIDのプロジェクトを検索
        project_data = metadata[metadata['id'] == project_id]
        
        if len(project_data) == 0:
            return jsonify({
                'error': 'プロジェクトが見つかりません',
                'message': f'ID {project_id} のプロジェクトは存在しません'
            }), 404
        
        # プロジェクト情報を整形
        row = project_data.iloc[0]
        project = {
            'id': int(row['id']),
            'name': str(row['project_name']),
            'year': int(row['year']),
            'budget': int(row['budget']),
            'rating': str(row['rating']),
            'description': str(row['description']),
            'outcomes': str(row['outcomes']),
            'issue_text': str(row['issue_text']),
            'summary_text': str(row['summary_text'])
        }
        
        return jsonify(project)
        
    except Exception as e:
        logger.error(f"プロジェクト詳細取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'プロジェクト詳細取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/stats', methods=['GET'])
def get_statistics():
    """
    統計情報を取得するエンドポイント
    
    レスポンス形式:
    {
        "total_projects": 総プロジェクト数,
        "budget_stats": {
            "min": 最小予算,
            "max": 最大予算,
            "mean": 平均予算,
            "median": 中央値予算
        },
        "rating_distribution": {
            "A": A評価の件数,
            "B": B評価の件数,
            "C": C評価の件数,
            "D": D評価の件数
        }
    }
    """
    try:
        if data_processor is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # メタデータを取得
        embeddings, metadata = data_processor.load_vector_database()
        
        # 統計情報を計算
        budget_stats = {
            'min': int(metadata['budget'].min()),
            'max': int(metadata['budget'].max()),
            'mean': int(metadata['budget'].mean()),
            'median': int(metadata['budget'].median())
        }
        
        rating_distribution = metadata['rating'].value_counts().to_dict()
        
        stats = {
            'total_projects': len(metadata),
            'budget_stats': budget_stats,
            'rating_distribution': rating_distribution
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"統計情報取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'統計情報取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/logs', methods=['GET'])
def get_analysis_logs():
    """
    分析ログ一覧を取得するエンドポイント
    
    クエリパラメータ:
    - limit: 取得件数（デフォルト: 50）
    - offset: オフセット（デフォルト: 0）
    - status: ステータスでフィルタリング
    - date_from: 開始日（YYYY-MM-DD形式）
    - date_to: 終了日（YYYY-MM-DD形式）
    
    レスポンス形式:
    {
        "logs": [ログのリスト],
        "total_count": 総件数,
        "limit": 取得件数,
        "offset": オフセット
    }
    """
    try:
        if db_manager is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # クエリパラメータを取得
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # パラメータの検証
        if limit < 1 or limit > 100:
            limit = 50
        if offset < 0:
            offset = 0
        
        # ログを取得
        logs = db_manager.get_analysis_logs(
            limit=limit,
            offset=offset,
            status=status,
            date_from=date_from,
            date_to=date_to
        )
        
        return jsonify({
            'logs': logs,
            'total_count': len(logs),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"ログ一覧取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'ログ一覧取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/logs/<int:log_id>', methods=['GET'])
def get_analysis_log_detail(log_id: int):
    """
    特定の分析ログの詳細を取得するエンドポイント
    
    Args:
        log_id: ログID
        
    レスポンス形式:
    {
        "id": ログID,
        "issue_text": 現状・目的テキスト,
        "summary_text": 事業概要テキスト,
        "predicted_budget": 予測予算,
        "similar_cases": [類似事業のリスト],
        "analysis_date": 分析日時,
        "processing_time": 処理時間,
        "status": ステータス
    }
    """
    try:
        if db_manager is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # ログを取得
        log = db_manager.get_analysis_log_by_id(log_id)
        
        if log is None:
            return jsonify({
                'error': 'ログが見つかりません',
                'message': f'ID {log_id} のログは存在しません'
            }), 404
        
        return jsonify(log)
        
    except Exception as e:
        logger.error(f"ログ詳細取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'ログ詳細取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/logs/stats', methods=['GET'])
def get_log_statistics():
    """
    ログの統計情報を取得するエンドポイント
    
    レスポンス形式:
    {
        "total_count": 総件数,
        "status_counts": {ステータス別件数},
        "daily_counts": {日別件数},
        "avg_processing_time": 平均処理時間,
        "budget_stats": {予算統計}
    }
    """
    try:
        if db_manager is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # 統計情報を取得
        stats = db_manager.get_log_statistics()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"ログ統計情報取得中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'ログ統計情報取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/logs/cleanup', methods=['POST'])
def cleanup_old_logs():
    """
    古いログを削除するエンドポイント
    
    クエリパラメータ:
    - days: 何日前のログを削除するか（デフォルト: 90）
    
    レスポンス形式:
    {
        "deleted_count": 削除されたログの件数,
        "message": "処理完了メッセージ"
    }
    """
    try:
        if db_manager is None:
            return jsonify({
                'error': 'サービスが初期化されていません',
                'message': 'しばらく待ってから再試行してください'
            }), 503
        
        # クエリパラメータを取得
        days = request.args.get('days', 90, type=int)
        
        if days < 1:
            return jsonify({
                'error': '無効なパラメータ',
                'message': 'daysは1以上の値を指定してください'
            }), 400
        
        # 古いログを削除
        deleted_count = db_manager.delete_old_logs(days=days)
        
        # データベースを最適化
        db_manager.cleanup_database()
        
        return jsonify({
            'deleted_count': deleted_count,
            'message': f'{days}日前のログを{deleted_count}件削除しました'
        })
        
    except Exception as e:
        logger.error(f"ログクリーンアップ中にエラーが発生: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': '内部サーバーエラー',
            'message': f'ログクリーンアップ中にエラーが発生しました: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return jsonify({
        'error': 'Not Found',
        'message': '指定されたエンドポイントが見つかりません'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    return jsonify({
        'error': 'Internal Server Error',
        'message': '内部サーバーエラーが発生しました'
    }), 500

if __name__ == '__main__':
    try:
        # サービスを初期化
        initialize_services()
        
        # Flaskアプリケーションを起動
        logger.info(f"APIサーバーを起動中: {Config.HOST}:{Config.PORT}")
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG
        )
        
    except Exception as e:
        logger.error(f"サーバー起動エラー: {e}")
        logger.error(traceback.format_exc())
        exit(1)
