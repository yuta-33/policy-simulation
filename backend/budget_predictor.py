import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from config import Config
from data_processor import DataProcessor

class BudgetPredictor:
    """予算予測クラス"""
    
    def __init__(self, data_processor: DataProcessor):
        self.data_processor = data_processor
        self.embeddings = None
        self.metadata = None
        
    def predict_budget_from_query_embeddings(self, query_embedding: np.ndarray) -> Tuple[float, pd.DataFrame]:
        """
        クエリベクトルから予算を予測し、類似事業の詳細を返す
        
        Args:
            query_embedding: クエリテキストのベクトル埋め込み
            
        Returns:
            predicted_budget: 予測予算額
            topk_df: 類似度上位K件の事業詳細DataFrame
        """
        # ベクトルデータベースを読み込み
        if self.embeddings is None or self.metadata is None:
            self.embeddings, self.metadata = self.data_processor.load_vector_database()
        
        # 類似度上位K件を検索
        similarities, indices = self.data_processor.find_similar_projects(
            query_embedding, top_k=Config.TOPK
        )
        
        # 類似度が閾値以上のもののみを抽出
        valid_mask = similarities >= Config.TAU
        valid_similarities = similarities[valid_mask]
        valid_indices = indices[valid_mask]
        
        if len(valid_similarities) == 0:
            # 類似度が閾値以上の事業がない場合
            print(f"類似度が閾値 {Config.TAU} 以上の事業が見つかりませんでした")
            return 0.0, pd.DataFrame()
        
        # 類似事業の詳細情報を取得
        similar_projects = self.data_processor.get_projects_by_indices(valid_indices)
        
        # DataFrameに変換
        topk_df = pd.DataFrame(similar_projects)
        topk_df['similarity'] = valid_similarities
        topk_df['weight'] = self._calculate_weights(valid_similarities)
        
        # 予算予測を実行
        predicted_budget = self._predict_budget(topk_df)
        
        return predicted_budget, topk_df
    
    def _calculate_weights(self, similarities: np.ndarray) -> np.ndarray:
        """
        類似度に基づいて重みを計算
        
        Args:
            similarities: 類似度の配列
            
        Returns:
            weights: 重みの配列
        """
        # 類似度を正規化して重みとして使用
        weights = similarities / np.sum(similarities)
        return weights
    
    def _predict_budget(self, topk_df: pd.DataFrame) -> float:
        """
        類似事業の情報から予算を予測
        
        Args:
            topk_df: 類似度上位K件の事業詳細DataFrame
            
        Returns:
            predicted_budget: 予測予算額
        """
        if len(topk_df) == 0:
            return 0.0
        
        # 類似度重み付き予算の計算
        weighted_budgets = topk_df['budget'] * topk_df['weight']
        predicted_budget = np.sum(weighted_budgets)
        
        return predicted_budget
    
    def analyze_query(self, issue_text: str, summary_text: str) -> Dict[str, Any]:
        """
        クエリテキストを分析して予算予測と類似事業を返す
        
        Args:
            issue_text: 現状・目的（課題）のテキスト
            summary_text: 事業概要（課題解決策）のテキスト
            
        Returns:
            analysis_result: 分析結果の辞書
        """
        try:
            # テキストを結合
            combined_text = f"{issue_text} {summary_text}"
            
            # ベクトル化（実際のAPIキーがある場合）
            if Config.OPENAI_API_KEY != 'your-api-key-here':
                query_embedding = self.data_processor.client.embeddings.create(
                    model=Config.OPENAI_MODEL,
                    input=[combined_text]
                ).data[0].embedding
                query_embedding = np.array(query_embedding)
            else:
                # APIキーがない場合はサンプルベクトルを使用
                print("OpenAI APIキーが設定されていないため、サンプルベクトルを使用します")
                query_embedding = self._generate_sample_query_embedding(combined_text)
            
            # 予算予測を実行
            predicted_budget, topk_df = self.predict_budget_from_query_embeddings(query_embedding)
            
            # 結果を整形
            analysis_result = self._format_analysis_result(predicted_budget, topk_df)
            
            return analysis_result
            
        except Exception as e:
            print(f"分析中にエラーが発生しました: {e}")
            return self._create_error_response(str(e))
    
    def _generate_sample_query_embedding(self, text: str) -> np.ndarray:
        """
        サンプルクエリベクトルを生成（APIキーがない場合用）
        
        Args:
            text: クエリテキスト
            
        Returns:
            sample_embedding: サンプルのベクトル埋め込み
        """
        # テキストの長さに基づいてサンプルベクトルを生成
        np.random.seed(hash(text) % 2**32)
        embedding = np.random.normal(0, 0.1, 1536)
        
        # 正規化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def _format_analysis_result(self, predicted_budget: float, topk_df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析結果をフロントエンド用の形式に整形
        
        Args:
            predicted_budget: 予測予算額
            topk_df: 類似事業の詳細DataFrame
            
        Returns:
            formatted_result: 整形された結果
        """
        if len(topk_df) == 0:
            return {
                "predicted_budget": 0.0,
                "average_budget": 0.0,
                "case_count": 0,
                "similar_cases": [],
                "message": "類似の事業が見つかりませんでした"
            }
        
        # 平均予算を計算
        average_budget = topk_df['budget'].mean()
        
        # 類似事業のリストを整形
        similar_cases = []
        for _, row in topk_df.iterrows():
            case = {
                "id": int(row['id']),
                "name": str(row['project_name']),
                "budget": str(int(row['initial_budget'])),
                "eval": str(row['rating']),
                "evalText": f"{row['rating']}評価: {self._get_evaluation_text(row['rating'])}",
                "details": str(row['outcomes']),
                "similarity": float(row['similarity']),
                "weight": float(row['weight']),
                "year": int(row['year']),
                "ministry": str(row.get('ministry', '')),
                "bureau": str(row.get('bureau', '')),
                "scale_category": str(row.get('scale_category', ''))
            }
            similar_cases.append(case)
        
        return {
            "predicted_budget": float(predicted_budget),
            "average_budget": float(average_budget),
            "case_count": len(similar_cases),
            "similar_cases": similar_cases,
            "message": "分析が完了しました"
        }
    
    def _get_evaluation_text(self, rating: str) -> str:
        """
        評価ランクから評価テキストを取得
        
        Args:
            rating: 評価ランク（A, B, C, D）
            
        Returns:
            evaluation_text: 評価テキスト
        """
        evaluation_texts = {
            'A': '高評価、目標達成、効果的',
            'B': '良好、概ね目標達成、一部改善の余地あり',
            'C': '要改善、一部目標未達、改善が必要',
            'D': '低評価、目標未達、大幅な改善が必要'
        }
        
        return evaluation_texts.get(rating, '評価情報なし')
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        エラー時のレスポンスを作成
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            error_response: エラーレスポンス
        """
        return {
            "predicted_budget": 0.0,
            "average_budget": 0.0,
            "case_count": 0,
            "similar_cases": [],
            "message": f"エラーが発生しました: {error_message}",
            "error": True
        }

if __name__ == "__main__":
    # 予算予測のテスト
    
    try:
        # データプロセッサーを初期化
        processor = DataProcessor()
        
        # ベクトルデータベースを準備
        processor.prepare_vector_database(use_sample_data=True)
        
        # 予算予測器を初期化
        predictor = BudgetPredictor(processor)
        
        # サンプルクエリでテスト
        test_issue = "地域の小規模事業者がデジタル化の波に取り残されている"
        test_summary = "地域の小規模事業者のデジタル化を支援し、地域経済の活性化を図る"
        
        print(f"テストクエリ:")
        print(f"現状・目的: {test_issue}")
        print(f"事業概要: {test_summary}")
        print()
        
        # 分析を実行
        result = predictor.analyze_query(test_issue, test_summary)
        
        print("分析結果:")
        print(f"予測予算: ¥{result['predicted_budget']:,.0f}")
        print(f"平均予算: ¥{result['average_budget']:,.0f}")
        print(f"類似事業数: {result['case_count']}件")
        print()
        
        if result['similar_cases']:
            print("類似事業上位3件:")
            for i, case in enumerate(result['similar_cases'][:3]):
                print(f"{i+1}. {case['name']}")
                print(f"   予算: ¥{case['budget']:,}")
                print(f"   評価: {case['eval']} ({case['evalText']})")
                print(f"   類似度: {case['similarity']:.3f}")
                print()
        
    except Exception as e:
        print(f"テスト中にエラーが発生しました: {e}")
