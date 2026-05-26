"""
嵌入服务客户端
负责文本嵌入和向量处理
"""
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingClient:
    """嵌入服务客户端"""
    
    def __init__(self):
        """初始化嵌入模型"""
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def get_embedding(self, text: str) -> list:
        """获取文本嵌入
        
        Args:
            text: 要嵌入的文本
            
        Returns:
            嵌入向量
        """
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"获取嵌入失败: {e}")
            return []
    
    def get_embeddings(self, texts: list) -> list:
        """批量获取文本嵌入
        
        Args:
            texts: 要嵌入的文本列表
            
        Returns:
            嵌入向量列表
        """
        try:
            embeddings = self.model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            print(f"批量获取嵌入失败: {e}")
            return []
    
    def calculate_similarity(self, embedding1: list, embedding2: list) -> float:
        """计算两个嵌入向量的相似度
        
        Args:
            embedding1: 第一个嵌入向量
            embedding2: 第二个嵌入向量
            
        Returns:
            相似度分数（0-1）
        """
        try:
            # 计算余弦相似度
            if not embedding1 or not embedding2:
                return 0.0
            
            embedding1 = np.array(embedding1)
            embedding2 = np.array(embedding2)
            
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            print(f"计算相似度失败: {e}")
            return 0.0


embedding_client = EmbeddingClient()