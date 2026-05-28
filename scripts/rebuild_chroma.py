#!/usr/bin/env python3
"""
重建向量数据库脚本
当切换 Embedding 模型时，需要重建 ChromaDB 中的向量数据

使用方法:
    python scripts/rebuild_chroma.py

注意：
    - 会自动备份旧的 ChromaDB 数据
    - 需要重新下载模型（首次运行）
    - 重建过程可能需要几分钟，取决于记忆数量
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.path_manager import PathManager
from db.sqlite_manager import SQLiteManager
from db.chroma_manager import ChromaManager
from services.embedding_client import EmbeddingClient


def backup_chroma(path_manager: PathManager):
    """备份现有 ChromaDB 数据"""
    chroma_path = path_manager.chroma_path
    if chroma_path.exists():
        backup_name = f"chroma_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = chroma_path.parent / backup_name
        shutil.copytree(chroma_path, backup_path)
        print(f"✓ 已备份旧数据到: {backup_path}")
        return backup_path
    return None


def rebuild_chroma():
    """重建向量数据库"""
    print("=" * 50)
    print("开始重建 ChromaDB 向量数据库")
    print("=" * 50)
    
    # 1. 初始化路径管理器
    path_manager = PathManager()
    print(f"\n1. 数据目录: {path_manager.data_root}")
    
    # 2. 备份旧数据
    print("\n2. 备份现有数据...")
    backup_path = backup_chroma(path_manager)
    
    # 3. 删除旧的 ChromaDB collection（维度不匹配时必须重建）
    print(f"\n3. 删除旧的向量 collection...")
    try:
        # 使用 ChromaDB 客户端删除 collection
        import chromadb
        temp_client = chromadb.PersistentClient(
            path=str(path_manager.chroma_path),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            temp_client.delete_collection("memories")
            print("   ✓ 已删除旧 collection")
        except Exception:
            print("   无旧 collection 或已删除")
        finally:
            del temp_client
    except Exception as e:
        print(f"   警告: {e}")
        print("   将尝试直接覆盖")
    
    # 4. 初始化服务
    print("\n4. 初始化服务（首次会下载模型，请耐心等待）...")
    sqlite_manager = SQLiteManager(path_manager)
    embedding_client = EmbeddingClient()  # 使用新的 BGE-Small-ZH 模型
    chroma_manager = ChromaManager(path_manager)
    
    # 5. 加载模型（提前触发下载）
    print("\n5. 加载 Embedding 模型...")
    _ = embedding_client.model  # 触发懒加载
    print(f"   模型名称: {embedding_client._model_name}")
    print(f"   向量维度: {len(embedding_client.get_embedding('测试'))}")
    
    # 6. 获取所有记忆
    print("\n6. 读取 SQLite 中的记忆...")
    memories = sqlite_manager.get_all_memories(limit=10000)
    total = len(memories)
    print(f"   共有 {total} 条记忆需要重建")
    
    if total == 0:
        print("\n✓ 没有记忆数据，重建完成！")
        return
    
    # 7. 重建向量
    print("\n7. 开始重建向量（这可能需要几分钟）...")
    success_count = 0
    failed_count = 0
    
    for i, memory in enumerate(memories, 1):
        # 构造嵌入文本
        embedding_text = f"{memory.ai_summary} {memory.text_content or ''}".strip()
        
        if not embedding_text:
            print(f"   [{i}/{total}] 跳过空内容记忆: {memory.id[:8]}")
            failed_count += 1
            continue
        
        # 生成向量
        embedding = embedding_client.get_embedding(embedding_text)
        
        if not embedding:
            print(f"   [{i}/{total}] 嵌入失败: {memory.id[:8]}")
            failed_count += 1
            continue
        
        # 存入 ChromaDB
        metadata = {
            "memory_id": memory.id,
            "created_at": memory.created_at,
            "app_name": memory.app_name,
        }
        
        if chroma_manager.add_memory(
            memory_id=memory.id,
            text=embedding_text,
            embedding=embedding,
            metadata=metadata,
        ):
            success_count += 1
        else:
            failed_count += 1
        
        # 每 10 条显示进度
        if i % 10 == 0 or i == total:
            print(f"   进度: {i}/{total} ({success_count} 成功, {failed_count} 失败)")
    
    # 8. 完成
    print("\n" + "=" * 50)
    print("重建完成！")
    print(f"   成功: {success_count}")
    print(f"   失败: {failed_count}")
    if backup_path:
        print(f"   备份: {backup_path}")
    print("=" * 50)
    
    # 9. 验证
    print("\n9. 验证搜索功能...")
    test_query = "测试搜索"
    test_embedding = embedding_client.get_embedding(test_query)
    results = chroma_manager.search_similar(test_embedding, n_results=5)
    
    if results:
        print(f"   ✓ 搜索正常，返回 {len(results)} 条结果")
        print(f"   第一条相似度分数: {results[0].get('distance', 'N/A')}")
    else:
        print("   ✗ 搜索返回空结果")
    
    # 清理
    sqlite_manager.close()
    chroma_manager.close()
    
    print("\n✓ 全部完成！")


if __name__ == "__main__":
    try:
        rebuild_chroma()
    except KeyboardInterrupt:
        print("\n\n用户中断，重建已取消。")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
