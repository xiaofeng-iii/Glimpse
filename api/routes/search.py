"""
Search Routes - Search functionality
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from api.schemas import SearchResult, MemoryResponse
from api.dependencies import get_search_service

router = APIRouter(prefix="/search", tags=["search"])


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
        "sync_status": getattr(memory, "sync_status", "PENDING"),
        "match_sources": getattr(memory, "match_sources", []),
    }


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("all", description="Filter source: all, ocr, semantic"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search memories by query"""
    try:
        search_service = get_search_service()
        memories = search_service.search(q, limit=limit, source_filter=source)
        return SearchResult(
            memories=[MemoryResponse(**memory_to_response(m)) for m in memories],
            query=q,
            source=source,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))