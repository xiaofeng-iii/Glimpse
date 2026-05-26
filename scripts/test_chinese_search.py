#!/usr/bin/env python3
"""
测试中文语义搜索
对比新旧模型的搜索效果
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.path_manager import PathManager
from db.sqlite_manager import SQLiteManager
from db.chroma_manager import ChromaManager
from services.embedding_client import EmbeddingClient


def test_chinese_search():
    print("=" * 50)
    print("中文语义搜索测试")
    print("=" * 50)
    
    # 初始化
    path_manager = PathManager()
    sqlite_manager = SQLiteManager(path_manager)
    chroma_manager = ChromaManager(path_manager)
    embedding_client = EmbeddingClient()
    
    # 显示模型信息
    print(f"\n模型: {embedding_client._model_name}")
    print(f"向量维度: {len(embedding_client.get_embedding('测试'))}")
    
    # 测试查询词
    test_queries = [
        "识图",  # 测试之前的问题查询
        "截图",
        "图片识别",
        "人工智能",
        "代码",
        "网页",
        "聊天记录",
    ]
    
    print("\n" + "-" * 50)
    print("搜索测试")
    print("-" * 50)
    
    for query in test_queries:
        print(f"\n查询词: '{query}'")
        
        # 1. 文本搜索（OCR）
        text_results = sqlite_manager.search_memories(query, limit=3)
        print(f"  [OCR] 找到 {len(text_results)} 条:")
        for i, memory in enumerate(text_results[:2], 1):
            summary = memory.ai_summary[:40] if memory.ai_summary else "无摘要"
            print(f"    {i}. {summary}...")
        
        # 2. 向量搜索（语义）
        embedding = embedding_client.get_embedding(query)
        if embedding:
            vector_results = chroma_manager.search_similar(embedding, n_results=3)
            print(f"  [语义] 找到 {len(vector_results)} 条:")
            for i, result in enumerate(vector_results[:2], 1):
                doc = result.get('document', '')[:40] if result.get('document') else "无文档"
                distance = result.get('distance', 'N/A')
                print(f"    {i}. {doc}... (距离: {distance:.4f})")
        else:
            print("  [语义] 嵌入失败")
    
    # 清理
    sqlite_manager.close()
    chroma_manager.close()
    
    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    test_chinese_search()
