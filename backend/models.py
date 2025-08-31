import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import os
from config import Config

class DatabaseManager:
    """SQLiteデータベース管理クラス"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # データディレクトリ内にデータベースファイルを作成
            Config.ensure_data_dir()
            db_path = os.path.join(Config.DATA_DIR, 'policy_analysis.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """データベースとテーブルを初期化"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 分析ログテーブルの作成
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_text TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    proposed_budget INTEGER,
                    predicted_budget REAL,
                    average_budget REAL,
                    case_count INTEGER,
                    similar_cases TEXT,  -- JSON形式で保存
                    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_ip TEXT,
                    user_agent TEXT,
                    processing_time REAL,  -- 処理時間（秒）
                    status TEXT DEFAULT 'success',  -- success, error
                    error_message TEXT
                )
            ''')
            
            # インデックスの作成（検索パフォーマンス向上）
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_analysis_date 
                ON analysis_logs(analysis_date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON analysis_logs(status)
            ''')
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """データベース接続のコンテキストマネージャー"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能にする
        try:
            yield conn
        finally:
            conn.close()
    
    def save_analysis_log(self, log_data: Dict[str, Any]) -> int:
        """
        分析ログを保存
        
        Args:
            log_data: ログデータの辞書
            
        Returns:
            log_id: 保存されたログのID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # similar_casesをJSON文字列に変換
            similar_cases_json = json.dumps(log_data.get('similar_cases', []), ensure_ascii=False)
            
            cursor.execute('''
                INSERT INTO analysis_logs (
                    issue_text, summary_text, proposed_budget, predicted_budget,
                    average_budget, case_count, similar_cases, user_ip,
                    user_agent, processing_time, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_data.get('issue_text', ''),
                log_data.get('summary_text', ''),
                log_data.get('proposed_budget'),
                log_data.get('predicted_budget'),
                log_data.get('average_budget'),
                log_data.get('case_count'),
                similar_cases_json,
                log_data.get('user_ip'),
                log_data.get('user_agent'),
                log_data.get('processing_time'),
                log_data.get('status', 'success'),
                log_data.get('error_message')
            ))
            
            log_id = cursor.lastrowid
            conn.commit()
            return log_id
    
    def get_analysis_logs(self, 
                         limit: int = 50, 
                         offset: int = 0,
                         status: Optional[str] = None,
                         date_from: Optional[str] = None,
                         date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        分析ログを取得
        
        Args:
            limit: 取得件数
            offset: オフセット
            status: ステータスでフィルタリング
            date_from: 開始日（YYYY-MM-DD形式）
            date_to: 終了日（YYYY-MM-DD形式）
            
        Returns:
            logs: ログのリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # クエリの構築
            query = '''
                SELECT * FROM analysis_logs 
                WHERE 1=1
            '''
            params = []
            
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            if date_from:
                query += ' AND DATE(analysis_date) >= ?'
                params.append(date_from)
            
            if date_to:
                query += ' AND DATE(analysis_date) <= ?'
                params.append(date_to)
            
            query += ' ORDER BY analysis_date DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 結果を辞書のリストに変換
            logs = []
            for row in rows:
                log = dict(row)
                
                # similar_casesをJSONから復元
                try:
                    log['similar_cases'] = json.loads(log['similar_cases']) if log['similar_cases'] else []
                except (json.JSONDecodeError, TypeError):
                    log['similar_cases'] = []
                
                # 日時をISO形式に変換
                if log['analysis_date']:
                    log['analysis_date'] = log['analysis_date']
                
                logs.append(log)
            
            return logs
    
    def get_analysis_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        指定されたIDの分析ログを取得
        
        Args:
            log_id: ログID
            
        Returns:
            log: ログデータ（見つからない場合はNone）
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM analysis_logs WHERE id = ?', (log_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            log = dict(row)
            
            # similar_casesをJSONから復元
            try:
                log['similar_cases'] = json.loads(log['similar_cases']) if log['similar_cases'] else []
            except (json.JSONDecodeError, TypeError):
                log['similar_cases'] = []
            
            return log
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        ログの統計情報を取得
        
        Returns:
            stats: 統計情報の辞書
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 総件数
            cursor.execute('SELECT COUNT(*) FROM analysis_logs')
            total_count = cursor.fetchone()[0]
            
            # ステータス別件数
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM analysis_logs 
                GROUP BY status
            ''')
            status_counts = dict(cursor.fetchall())
            
            # 日別件数（過去30日）
            cursor.execute('''
                SELECT DATE(analysis_date) as date, COUNT(*) as count
                FROM analysis_logs 
                WHERE analysis_date >= DATE('now', '-30 days')
                GROUP BY DATE(analysis_date)
                ORDER BY date DESC
            ''')
            daily_counts = dict(cursor.fetchall())
            
            # 平均処理時間
            cursor.execute('''
                SELECT AVG(processing_time) as avg_time
                FROM analysis_logs 
                WHERE status = 'success' AND processing_time IS NOT NULL
            ''')
            avg_processing_time = cursor.fetchone()[0] or 0
            
            # 予算統計
            cursor.execute('''
                SELECT 
                    AVG(predicted_budget) as avg_predicted,
                    MIN(predicted_budget) as min_predicted,
                    MAX(predicted_budget) as max_predicted,
                    COUNT(DISTINCT proposed_budget) as unique_budgets
                FROM analysis_logs 
                WHERE status = 'success' AND predicted_budget IS NOT NULL
            ''')
            budget_stats = cursor.fetchone()
            
            return {
                'total_count': total_count,
                'status_counts': status_counts,
                'daily_counts': daily_counts,
                'avg_processing_time': round(avg_processing_time, 3),
                'budget_stats': {
                    'avg_predicted': budget_stats[0] or 0,
                    'min_predicted': budget_stats[1] or 0,
                    'max_predicted': budget_stats[2] or 0,
                    'unique_budgets': budget_stats[3] or 0
                }
            }
    
    def delete_old_logs(self, days: int = 90) -> int:
        """
        古いログを削除
        
        Args:
            days: 何日前のログを削除するか
            
        Returns:
            deleted_count: 削除されたログの件数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM analysis_logs 
                WHERE analysis_date < DATE('now', '-{} days')
            '''.format(days))
            
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
    
    def cleanup_database(self):
        """データベースの最適化"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # VACUUMでデータベースを最適化
            cursor.execute('VACUUM')
            
            # 統計情報を更新
            cursor.execute('ANALYZE')
            
            conn.commit()

if __name__ == "__main__":
    # データベースのテスト
    db_manager = DatabaseManager()
    
    # テストログの保存
    test_log = {
        'issue_text': 'テスト用の課題テキスト',
        'summary_text': 'テスト用の事業概要',
        'proposed_budget': 50000000,
        'predicted_budget': 55000000,
        'average_budget': 52000000,
        'case_count': 5,
        'similar_cases': [
            {'id': 1, 'name': 'テスト事業1', 'budget': 50000000},
            {'id': 2, 'name': 'テスト事業2', 'budget': 60000000}
        ],
        'user_ip': '127.0.0.1',
        'user_agent': 'Test User Agent',
        'processing_time': 1.5,
        'status': 'success'
    }
    
    log_id = db_manager.save_analysis_log(test_log)
    print(f"テストログを保存しました。ID: {log_id}")
    
    # ログの取得テスト
    logs = db_manager.get_analysis_logs(limit=10)
    print(f"保存されたログ数: {len(logs)}")
    
    # 統計情報の取得テスト
    stats = db_manager.get_log_statistics()
    print(f"統計情報: {stats}")
