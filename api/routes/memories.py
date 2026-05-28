"""
Memory Routes - CRUD operations for memories
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from api.schemas import MemoryResponse, MemoryListResponse
from api.dependencies import get_search_service, get_memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


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


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get list of recent memories"""
    try:
        search_service = get_search_service()
        memories = search_service.get_recent_memories(limit=limit)
        return MemoryListResponse(
            memories=[MemoryResponse(**memory_to_response(m)) for m in memories],
            total=len(memories),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str):
    """Get a single memory by ID"""
    try:
        search_service = get_search_service()
        memory = search_service.get_memory_by_id(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        return MemoryResponse(**memory_to_response(memory))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory by ID"""
    try:
        memory_service = get_memory_service()
        success = memory_service.delete_memory(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        return {"success": True, "message": f"Memory {memory_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))