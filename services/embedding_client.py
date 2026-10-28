"""
嵌入服务客户端：bge-small-zh-v1.5 的 ONNX 推理（替代 sentence-transformers/torch）。

与旧 torch 管线逐位等价（POC 对拍：26 条真实文本 cos=1.000000、top-5 检索重合率 100%），
等价要点：分词前 strip+lower（sentence-transformers 2.2.2 的 do_lower_case 语义）、
CLS pooling、L2 归一化、512 维、截断 512。模型随包分发（assets/embedding），
运行时绝不联网下载；加载失败只尝试一次，之后语义搜索按空结果降级（与 OCR 引擎同策略）。
"""
import sys
import threading
from pathlib import Path

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

MODEL_FILENAME = "bge-small-zh-v1.5.onnx"
TOKENIZER_FILENAME = "bge-small-zh-v1.5.tokenizer.json"
MAX_SEQ_LENGTH = 512


def _default_model_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / "embedding"


class _OnnxEncoder:
    """ONNX 推理器：tokenize → BERT → CLS → L2 归一化。"""

    def __init__(self, model_dir: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(model_dir / TOKENIZER_FILENAME))
        self._tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)
        self._session = ort.InferenceSession(
            str(model_dir / MODEL_FILENAME), providers=["CPUExecutionProvider"]
        )
        self._lock = threading.Lock()

    def encode(self, texts: list) -> np.ndarray:
        # sentence-transformers 2.2.2 的分词前处理：strip + lower（do_lower_case=true）。
        vectors = []
        with self._lock:
            for text in texts:
                enc = self._tokenizer.encode(str(text).strip().lower())
                feed = {
                    "input_ids": np.array([enc.ids], dtype=np.int64),
                    "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
                    "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
                }
                output = self._session.run(None, feed)[0]
                vector = np.asarray(output[0, 0], dtype=np.float32)
                vector /= np.linalg.norm(vector) + 1e-12
                vectors.append(vector)
        return np.vstack(vectors)


class EmbeddingClient:
    """嵌入服务客户端"""

    def __init__(self, model_name: str = 'BAAI/bge-small-zh-v1.5', model_dir: Path | None = None):
        """初始化嵌入客户端。模型按需加载，避免拖慢应用启动。"""
        # model_name 仅作标识保留（模型文件已随包分发，不再按 HF 名下载）。
        self._model_name = model_name
        self._model_dir = model_dir
        self._model = None
        self._load_attempted = False
        self._model_lock = threading.Lock()

    @property
    def model(self):
        """Lazy-load ONNX encoder on first embedding request; failure is one-shot."""
        if self._model is None and not self._load_attempted:
            with self._model_lock:
                if self._model is None and not self._load_attempted:
                    self._load_attempted = True
                    model_dir = self._model_dir or _default_model_dir()
                    try:
                        self._model = _OnnxEncoder(model_dir)
                    except Exception as e:
                        logger.warning("嵌入模型不可用（语义搜索将降级为文本检索）: %s", e)
        return self._model

    def get_embedding(self, text: str) -> list:
        """获取文本嵌入

        Args:
            text: 要嵌入的文本

        Returns:
            嵌入向量
        """
        try:
            if self.model is None:
                return []
            embedding = self.model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            logger.error("获取嵌入失败: %s", e)
            return []

    def get_embeddings(self, texts: list) -> list:
        """批量获取文本嵌入

        Args:
            texts: 要嵌入的文本列表

        Returns:
            嵌入向量列表
        """
        try:
            if not texts:
                return []
            if self.model is None:
                return []
            embeddings = self.model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error("批量获取嵌入失败: %s", e)
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
            logger.error("计算相似度失败: %s", e)
            return 0.0


embedding_client = EmbeddingClient()
