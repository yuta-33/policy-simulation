import pandas as pd
import numpy as np
import pickle
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from config import Config
# from sample_data import SampleDataGenerator  # CSVデータを使用するため不要

class DataProcessor:
    """データ処理・ベクトル化クラス"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.embeddings = None
        self.metadata = None
        
    def create_sample_dataset(self) -> Tuple[pd.DataFrame, np.ndarray]:
        """最小限のサンプルデータセットを作成（フォールバック用）"""
        print("最小限のサンプルデータセットを作成中...")
        
        # 最小限のサンプルデータを生成
        sample_data = [{
            'id': 1,
            'project_name': 'サンプル事業',
            'year': 2024,
            'initial_budget': 50000000,
            'rating': 'B',
            'summary_text': 'サンプル事業の概要です',
            'issue_text': 'サンプル事業の課題です',
            'outcomes': 'サンプル事業の成果です',
            'description': 'サンプル事業の説明です',
            'ministry': 'サンプル省庁',
            'bureau': 'サンプル局',
            'scale_category': '中規模',
            'error_rate': 0.2
        }]
        
        projects_df = pd.DataFrame(sample_data)
        
        # ランダムなベクトル埋め込みを生成
        embeddings = np.random.normal(0, 0.1, (1, 1536))
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        print(f"サンプルデータセット作成完了: {len(projects_df)}件のプロジェクト")
        return projects_df, embeddings
    
    def create_embeddings_from_texts(self, texts: List[str]) -> np.ndarray:
        """テキストリストからベクトル埋め込みを生成"""
        embeddings = []
        
        for i in range(0, len(texts), Config.BATCH_SIZE):
            batch_texts = texts[i:i + Config.BATCH_SIZE]
            batch_embeddings = self._get_embeddings_batch(batch_texts)
            embeddings.extend(batch_embeddings)
            
            # API制限を考慮して少し待機
            if i + Config.BATCH_SIZE < len(texts):
                time.sleep(0.1)
        
        return np.array(embeddings)
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """バッチ処理でベクトル埋め込みを取得"""
        for attempt in range(Config.MAX_RETRIES):
            try:
                response = self.client.embeddings.create(
                    model=Config.OPENAI_MODEL,
                    input=texts
                )
                return [embedding.embedding for embedding in response.data]
                
            except Exception as e:
                print(f"ベクトル化エラー (試行 {attempt + 1}/{Config.MAX_RETRIES}): {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 指数バックオフ
                else:
                    raise Exception(f"ベクトル化に失敗しました: {e}")
    
    def prepare_vector_database(self, use_sample_data: bool = False) -> None:
        """ベクトルデータベースを準備"""
        Config.ensure_data_dir()
        
        if use_sample_data:
            # サンプルデータを使用
            metadata, embeddings = self.create_sample_dataset()
        else:
            # 実際のCSVファイルからデータを読み込む
            metadata, embeddings = self.load_csv_data()
        
        # ベクトルデータを保存
        vector_file_path = Config.get_vector_file_path()
        np.save(vector_file_path, embeddings)
        print(f"ベクトルデータを保存: {vector_file_path}")
        
        # メタデータを保存
        metadata_file_path = Config.get_metadata_file_path()
        with open(metadata_file_path, 'wb') as f:
            pickle.dump(metadata, f)
        print(f"メタデータを保存: {metadata_file_path}")
        
        self.embeddings = embeddings
        self.metadata = metadata
        
        print("ベクトルデータベースの準備が完了しました")
    
    def load_vector_database(self) -> Tuple[np.ndarray, pd.DataFrame]:
        """保存されたベクトルデータベースを読み込み"""
        vector_file_path = Config.get_vector_file_path()
        metadata_file_path = Config.get_metadata_file_path()
        
        if not os.path.exists(vector_file_path) or not os.path.exists(metadata_file_path):
            print("ベクトルデータベースが見つかりません。CSVデータで初期化します。")
            self.prepare_vector_database(use_sample_data=False)
        
        # ベクトルデータを読み込み
        self.embeddings = np.load(vector_file_path)
        
        # メタデータを読み込み
        with open(metadata_file_path, 'rb') as f:
            self.metadata = pickle.load(f)
        
        print(f"ベクトルデータベースを読み込みました: {len(self.metadata)}件のプロジェクト")
        return self.embeddings, self.metadata
    
    def get_project_texts(self) -> List[str]:
        """プロジェクトのテキストデータを取得（ベクトル化用）"""
        if self.metadata is None:
            raise ValueError("メタデータが読み込まれていません")
        
        texts = []
        for _, row in self.metadata.iterrows():
            # 現状・目的と事業概要を結合
            combined_text = f"{row['issue_text']} {row['summary_text']}"
            texts.append(combined_text)
        
        return texts
    
    def calculate_similarity(self, query_embedding: np.ndarray, project_embeddings: np.ndarray) -> np.ndarray:
        """コサイン類似度を計算"""
        # クエリベクトルを正規化
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        
        # コサイン類似度を計算
        similarities = np.dot(project_embeddings, query_embedding)
        return similarities
    
    def find_similar_projects(self, query_embedding: np.ndarray, top_k: int = None) -> Tuple[np.ndarray, np.ndarray]:
        """類似度の高いプロジェクトを検索"""
        if top_k is None:
            top_k = Config.TOPK
        
        # 類似度を計算
        similarities = self.calculate_similarity(query_embedding, self.embeddings)
        
        # 類似度上位K件のインデックスを取得
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # 類似度とインデックスを返す
        return similarities[top_indices], top_indices
    
    def get_project_by_index(self, index: int) -> Dict[str, Any]:
        """インデックスでプロジェクト情報を取得"""
        if self.metadata is None:
            raise ValueError("メタデータが読み込まれていません")
        
        if index >= len(self.metadata):
            raise ValueError(f"インデックス {index} が範囲外です")
        
        project = self.metadata.iloc[index].to_dict()
        return project
    
    def get_projects_by_indices(self, indices: np.ndarray) -> List[Dict[str, Any]]:
        """複数のインデックスでプロジェクト情報を取得"""
        projects = []
        for index in indices:
            project = self.get_project_by_index(index)
            projects.append(project)
        return projects
    
    def load_csv_data(self) -> Tuple[pd.DataFrame, np.ndarray]:
        """CSVファイルからデータを読み込み"""
        print("CSVファイルからデータを読み込み中...")
        
        try:
            # CSVファイルのパスを設定
            csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__), '..', 'data', 'final_2024.csv')
            
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
            
            # CSVファイルを読み込み
            df = pd.read_csv(csv_path, encoding='utf-8')
            print(f"CSVファイル読み込み完了: {len(df)}件のデータ")
            
            # 必要な列を選択・リネーム（列名の前後の空白を除去）
            df.columns = df.columns.str.strip()  # 列名の空白を除去
            
            metadata = df[[
                '予算事業ID', '府省庁', '局・庁', '事業の概要', '当初予算', 
                '歳出予算現額', '事業名', '現状・課題', '規模区分', '相対誤差%'
            ]].copy()
            
            # 列名を英語に変更
            metadata.columns = [
                'id', 'ministry', 'bureau', 'summary_text', 'initial_budget',
                'current_budget', 'project_name', 'issue_text', 'scale_category', 'error_rate'
            ]
            
            # データの前処理
            metadata = self.preprocess_csv_data(metadata)
            
            # ベクトル埋め込みデータを処理
            embeddings = self.process_csv_embeddings(df)
            
            print(f"CSVデータ処理完了: {len(metadata)}件のプロジェクト")
            return metadata, embeddings
            
        except Exception as e:
            print(f"CSVファイル読み込みエラー: {e}")
            print("サンプルデータにフォールバックします")
            return self.create_sample_dataset()
    
    def preprocess_csv_data(self, metadata: pd.DataFrame) -> pd.DataFrame:
        """CSVデータの前処理"""
        # 数値データの処理
        metadata['initial_budget'] = pd.to_numeric(metadata['initial_budget'], errors='coerce').fillna(0)
        metadata['current_budget'] = pd.to_numeric(metadata['current_budget'], errors='coerce').fillna(0)
        metadata['error_rate'] = pd.to_numeric(metadata['error_rate'], errors='coerce').fillna(0)
        
        # 予算が0の場合は除外
        metadata = metadata[metadata['initial_budget'] > 0]
        
        # テキストデータのクリーニング
        metadata['summary_text'] = metadata['summary_text'].fillna('').astype(str)
        metadata['issue_text'] = metadata['issue_text'].fillna('').astype(str)
        metadata['project_name'] = metadata['project_name'].fillna('').astype(str)
        
        # 空のテキストを除外
        metadata = metadata[
            (metadata['summary_text'].str.len() > 10) | 
            (metadata['issue_text'].str.len() > 10)
        ]
        
        # 評価ランクを生成（相対誤差に基づく）
        metadata['rating'] = self.generate_rating_from_error(metadata['error_rate'])
        
        # 年度情報を追加（CSVファイル名から推定）
        metadata['year'] = 2024
        
        # 成果・課題の説明を生成
        metadata['outcomes'] = self.generate_outcomes_description(metadata)
        
        # 説明文を生成
        metadata['description'] = metadata['summary_text']
        
        return metadata
    
    def process_csv_embeddings(self, df: pd.DataFrame) -> np.ndarray:
        """CSVファイルのベクトル埋め込みデータを処理"""
        try:
            # embedding_sum列からベクトルデータを抽出
            embeddings = []
            
            for idx, row in df.iterrows():
                try:
                    # 文字列として保存されたベクトルデータを解析
                    embedding_str = str(row.get('embedding_sum', ''))
                    
                    if embedding_str and embedding_str != 'nan':
                        # 文字列から数値配列を解析
                        embedding_values = self.parse_embedding_string(embedding_str)
                        if embedding_values is not None:
                            embeddings.append(embedding_values)
                        else:
                            # 解析できない場合はランダムベクトルを生成
                            embeddings.append(self.generate_random_embedding())
                    else:
                        # 空の場合はランダムベクトルを生成
                        embeddings.append(self.generate_random_embedding())
                        
                except Exception as e:
                    print(f"ベクトル処理エラー (行 {idx}): {e}")
                    embeddings.append(self.generate_random_embedding())
            
            embeddings = np.array(embeddings)
            
            # ベクトルを正規化
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # ゼロ除算を防ぐ
            embeddings = embeddings / norms
            
            print(f"ベクトル処理完了: {embeddings.shape}")
            return embeddings
            
        except Exception as e:
            print(f"ベクトル処理エラー: {e}")
            print("ランダムベクトルを生成します")
            return self.generate_sample_embeddings(len(df), 1536)
    
    def parse_embedding_string(self, embedding_str: str) -> Optional[np.ndarray]:
        """文字列からベクトル配列を解析"""
        try:
            # 文字列から数値を抽出
            import re
            numbers = re.findall(r'-?\d+\.?\d*', embedding_str)
            
            if len(numbers) >= 100:  # 最低限の次元数を確認
                embedding = np.array([float(x) for x in numbers])
                
                # 次元数を1536に調整（必要に応じて）
                if len(embedding) > 1536:
                    embedding = embedding[:1536]
                elif len(embedding) < 1536:
                    # 不足分を0で埋める
                    padding = np.zeros(1536 - len(embedding))
                    embedding = np.concatenate([embedding, padding])
                
                return embedding
            else:
                return None
                
        except Exception as e:
            print(f"ベクトル文字列解析エラー: {e}")
            return None
    
    def generate_random_embedding(self) -> np.ndarray:
        """ランダムなベクトル埋め込みを生成"""
        embedding = np.random.normal(0, 0.1, 1536)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    
    def generate_rating_from_error(self, error_rates: pd.Series) -> pd.Series:
        """相対誤差から評価ランクを生成"""
        def get_rating(error_rate):
            if pd.isna(error_rate) or error_rate == 0:
                return 'B'  # デフォルト
            elif error_rate < 0.1:
                return 'A'  # 高精度
            elif error_rate < 0.3:
                return 'B'  # 良好
            elif error_rate < 0.5:
                return 'C'  # 要改善
            else:
                return 'D'  # 低精度
        
        return error_rates.apply(get_rating)
    
    def generate_outcomes_description(self, metadata: pd.DataFrame) -> pd.Series:
        """成果・課題の説明を生成"""
        def get_outcomes(row):
            if pd.isna(row['error_rate']) or row['error_rate'] == 0:
                return '予測精度の評価が困難'
            
            if row['error_rate'] < 0.1:
                return '予測精度が高く、事業計画が適切に策定されている'
            elif row['error_rate'] < 0.3:
                return '予測精度は良好で、一部改善の余地がある'
            elif row['error_rate'] < 0.5:
                return '予測精度に改善の余地があり、計画の見直しが必要'
            else:
                return '予測精度が低く、大幅な計画の見直しが必要'
        
        return metadata.apply(get_outcomes, axis=1)

if __name__ == "__main__":
    # データ処理のテスト
    processor = DataProcessor()
    
    try:
        # ベクトルデータベースを準備
        processor.prepare_vector_database(use_sample_data=True)
        
        # データベースを読み込み
        embeddings, metadata = processor.load_vector_database()
        
        print(f"読み込み完了: {len(metadata)}件のプロジェクト")
        print(f"ベクトル次元: {embeddings.shape[1]}")
        
        # サンプルクエリで類似度計算をテスト
        sample_query = "地域のデジタル化を推進したい"
        print(f"\nサンプルクエリ: {sample_query}")
        
        # 実際のAPIキーがある場合はベクトル化を実行
        if Config.OPENAI_API_KEY != 'your-api-key-here':
            query_embedding = processor.client.embeddings.create(
                model=Config.OPENAI_MODEL,
                input=[sample_query]
            ).data[0].embedding
            
            similarities, indices = processor.find_similar_projects(
                np.array(query_embedding), top_k=3
            )
            
            print("\n類似度上位3件:")
            for i, (sim, idx) in enumerate(zip(similarities, indices)):
                project = processor.get_project_by_index(idx)
                print(f"{i+1}. {project['project_name']} (類似度: {sim:.3f})")
        else:
            print("OpenAI APIキーが設定されていないため、ベクトル化テストはスキップします")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
