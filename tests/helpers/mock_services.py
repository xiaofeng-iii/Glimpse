"""
Mock 服务类

提供常用外部依赖的 Mock 实现，供单元测试使用。
"""

from unittest.mock import MagicMock, patch
from typing import Optional, List, Dict, Any, Tuple


class MockOpenAI:
    """模拟 OpenAI 客户端"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url


def create_mock_ai_response(content: str) -> MagicMock:
    """创建模拟的 OpenAI API 响应对象。

    Args:
        content: 模拟返回的文本内容

    Returns:
        带有 choices[0].message.content 的 MagicMock
    """
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def create_mock_stream_response(chunks: List[str]) -> MagicMock:
    """创建模拟的流式响应对象。

    Args:
        chunks: 按顺序发送的文本块列表

    Returns:
        可迭代的模拟流式响应
    """
    mock_chunks = []
    for text in chunks:
        mock_delta = MagicMock()
        mock_delta.content = text
        mock_choice = MagicMock()
        mock_choice.delta = mock_delta
        mock_chunks.append(mock_choice)

    return mock_chunks


def create_mock_ocr_result(text: Optional[str] = None, boxes=None) -> Tuple[Optional[MagicMock], ...]:
    """创建模拟的 RapidOCR 返回结果。

    Args:
        text: 模拟识别的文本列表，如 [["Hello"], ["World"]]
        boxes: 模拟的文本框坐标

    Returns:
        (result, elapse, ...) 元组
    """
    if text is None:
        return (None, 0, 0)
    result = [([x1, y1, x2, y2], t, conf) for ((x1, y1, x2, y2), t, conf) in text]
    return (result, 0, 0)


def create_mock_embedding(dim: int = 384) -> List[float]:
    """创建一个模拟的嵌入向量。

    Args:
        dim: 向量维度，默认 384 (all-MiniLM-L6-v2 的维度)

    Returns:
        长度 dim 的浮点数列表
    """
    import random
    random.seed(42)
    # 返回归一化的随机向量
    import math
    vec = [random.random() for _ in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]
