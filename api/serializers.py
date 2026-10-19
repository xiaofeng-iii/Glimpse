"""Shared serializers for memory API responses.

Both the memories and the search routes build MemoryResponse payloads through
this module so the two surfaces cannot drift apart on fields such as
user_text, search_debug, or tags.
"""


def memory_to_response(memory) -> dict:
    """Convert MemoryRecord to dict for API response"""
    return {
        "id": memory.id,
        "created_at": memory.created_at,
        "image_path": memory.image_path,
        "ai_summary": memory.ai_summary,
        "app_name": memory.app_name,
        "text_content": memory.text_content,
        "extra_images": memory.extra_images,
        "user_text": getattr(memory, "user_text", None),
        "sync_status": getattr(memory, "sync_status", "PENDING"),
        "analysis_status": getattr(memory, "analysis_status", "COMPLETED"),
        "memory_type": getattr(memory, "memory_type", "screenshot"),
        "match_sources": getattr(memory, "match_sources", []),
        "search_debug": getattr(memory, "search_debug", None),
        "tags": [
            {"id": tag.id, "name": tag.name}
            for tag in getattr(memory, "tags", None) or []
        ],
    }
