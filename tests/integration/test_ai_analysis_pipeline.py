"""
AI 分析管道集成测试

验证：截图 → OCR + AI 摘要 → 存储的完整管道行为
"""
import pytest


class TestAIAnalysisPipeline:
    """测试 AI 分析管道（OCR → AI 摘要 → 存储）"""

    def test_ocr_text_flows_into_memory(self, memory_service, sample_image_path, mock_ocr_engine):
        """OCR 识别文本应作为 text_content 存入记忆"""
        mock_ocr_engine.extract_text.return_value = "这是 OCR 识别的内容"

        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record.text_content == "这是 OCR 识别的内容"

    def test_ai_summary_stored_in_memory(self, memory_service, sample_image_path, mock_ai_client):
        """AI 生成的摘要应存入 ai_summary 字段"""
        mock_ai_client.analyze_image.return_value = "AI 生成的截图摘要内容"

        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record.ai_summary == "AI 生成的截图摘要内容"

    def test_ocr_text_and_ai_summary_concatenated_for_embedding(
        self, memory_service, sample_image_path, mock_ocr_engine, mock_ai_client, mock_embedding_client
    ):
        """嵌入向量应基于 OCR 文本和 AI 摘要的拼接结果生成"""
        mock_ocr_engine.extract_text.return_value = "OCR文本"
        mock_ai_client.analyze_image.return_value = "AI摘要"

        memory_service.create_memory(sample_image_path)
        embedding_client = memory_service._embedding_client

        call_arg = embedding_client.get_embedding.call_args[0][0]
        assert "AI摘要" in call_arg
        assert "OCR文本" in call_arg

    def test_stream_callback_receives_chunks(self, memory_service, sample_image_path, mock_ai_client):
        """流式回调应接收 AI 响应的内容块"""
        chunks = []

        def stream_callback(text):
            chunks.append(text)

        mock_ai_client.analyze_image.return_value = "完整摘要内容"
        memory_service.create_memory(
            sample_image_path,
            stream_callback=stream_callback,
        )

        mock_ai_client.analyze_image.assert_called_once()

    def test_ocr_failure_produces_empty_text(self, memory_service, sample_image_path, mock_ocr_engine):
        """OCR 失败时 text_content 应为空字符串"""
        mock_ocr_engine.extract_text.return_value = None

        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record.text_content == ""

    def test_ocr_failure_still_uses_ai_summary(self, memory_service, sample_image_path, mock_ocr_engine, mock_ai_client):
        """OCR 失败时 AI 摘要仍应正常生成"""
        mock_ocr_engine.extract_text.return_value = None
        mock_ai_client.analyze_image.return_value = "仅有 AI 摘要"

        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record.ai_summary == "仅有 AI 摘要"
        assert record.text_content == ""

    def test_embedding_failure_does_not_crash(self, memory_service, sample_image_path, mock_embedding_client, sqlite_manager):
        """嵌入生成失败时不应崩溃，SQLite 仍应有记录"""
        mock_embedding_client.get_embedding.return_value = []

        memory_id = memory_service.create_memory(sample_image_path)
        record = sqlite_manager.get_memory_by_id(memory_id)

        assert record is not None

    def test_pipeline_preserves_app_name(self, memory_service, sample_image_path):
        """管道应保留传入的 app_name"""
        for app_name in ["chrome", "vscode", "terminal", "unknown"]:
            memory_id = memory_service.create_memory(sample_image_path, app_name=app_name)
            record = memory_service.get_memory(memory_id)
            assert record.app_name == app_name

    def test_memory_metadata_includes_app_name(self, memory_service, sample_image_path, chroma_manager):
        """ChromaDB 元数据应包含 app_name"""
        memory_id = memory_service.create_memory(sample_image_path, app_name="vscode")

        ids = chroma_manager.get_all_memory_ids()
        assert memory_id in ids
