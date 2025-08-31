import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # OpenAI API設定
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = 'text-embedding-3-small'
    
    # ベクトル化設定
    BATCH_SIZE = 128
    MAX_RETRIES = 3
    
    # 予算予測パラメータ
    TOPK = 10  # 類似度上位K件
    TAU = 0.1  # 類似度閾値
    ALPHA = 0.7  # 類似度重み
    BETA = 0.3   # 予算重み
    
    # ファイルパス設定
    DATA_DIR = 'data'
    VECTOR_FILE = 'embeddings.npy'
    METADATA_FILE = 'metadata.pkl'
    
    # API設定
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True
    
    # CORS設定
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:5000', 'http://localhost:5000','https://policy-simulation.onrender.com']
    
    @classmethod
    def get_vector_file_path(cls):
        """ベクトルファイルの完全パスを取得"""
        return os.path.join(cls.DATA_DIR, cls.VECTOR_FILE)
    
    @classmethod
    def get_metadata_file_path(cls):
        """メタデータファイルの完全パスを取得"""
        return os.path.join(cls.DATA_DIR, cls.METADATA_FILE)
    
    @classmethod
    def ensure_data_dir(cls):
        """データディレクトリが存在しない場合は作成"""
        if not os.path.exists(cls.DATA_DIR):
            os.makedirs(cls.DATA_DIR)
