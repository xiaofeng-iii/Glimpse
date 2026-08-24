"""
Memory Routes - CRUD operations for memories
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import date

from starlette.concurrency import run_in_threadpool

from api.schemas import (
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryType,
    MemoryUpdateRequest,
)
from api.dependencies import get_search_service, get_memory_service
from api.memory_filters import normalize_memory_date_range
from api.websocket import broadcast_event
from utils.logger import get_logger

logger = get_logger(__name__)

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
        "memory_type": getattr(memory, "memory_type", "screenshot"),
        "match_sources": getattr(memory, "match_sources", []),
    }


@router.post("", response_model=MemoryResponse, status_code=201)
async def create_text_memory(request: MemoryCreateRequest):
    """Create a user-authored text memory and finish its first index attempt."""
    try:
        memory_service = get_memory_service()
        memory_id = await run_in_threadpool(
            memory_service.create_text_memory,
            request.content,
        )
        memory = memory_service.get_memory(memory_id) if memory_id else None
        if memory is None:
            raise RuntimeError("Text memory was created without a readable record")

        response = MemoryResponse(**memory_to_response(memory))
        try:
            await broadcast_event(
                "memory_saved",
                {
                    "memory_id": memory.id,
                    "source": "text",
                    "notify": False,
                },
            )
        except Exception as exc:
            logger.warning("Failed to broadcast text memory %s: %s", memory.id, exc)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_from: date | None = None,
    date_to: date | None = None,
    memory_type: MemoryType | None = None,
):
    """Get list of recent memories"""
    try:
        search_service = get_search_service()
        bounds = normalize_memory_date_range(date_from, date_to)
        if offset or bounds.created_after or bounds.created_before or memory_type:
            recent_options = {
                "limit": limit,
                "offset": offset,
                "created_after": bounds.created_after,
                "created_before": bounds.created_before,
            }
            if memory_type:
                recent_options["memory_type"] = memory_type
            memories = search_service.get_recent_memories(**recent_options)
        else:
            memories = search_service.get_recent_memories(limit=limit)
        count_options = {
            "created_after": bounds.created_after,
            "created_before": bounds.created_before,
        }
        if memory_type:
            count_options["memory_type"] = memory_type
        return MemoryListResponse(
            memories=[MemoryResponse(**memory_to_response(m)) for m in memories],
            total=search_service.get_recent_memories_count(**count_options),
        )
    except HTTPException:
        raise
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


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: str, request: MemoryUpdateRequest):
    """Update a user-editable memory summary and queue semantic reindexing."""
    try:
        memory_service = get_memory_service()
        memory = memory_service.update_memory_summary(
            memory_id,
            request.ai_summary,
        )
        if memory is None:
            raise HTTPException(
                status_code=404,
                detail=f"Memory {memory_id} not found",
            )

        # MemoryService emits PENDING before it starts the serial reindex worker;
        # that worker emits the terminal SYNCED/FAILED event. Broadcasting again
        # here could race and deliver a late PENDING event after the terminal one.
        return MemoryResponse(**memory_to_response(memory))
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory by ID"""
    try:
        memory_service = get_memory_service()
        success = memory_service.delete_memory(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

        try:
            await broadcast_event(
                "memory_deleted",
                {
                    "memory_id": memory_id,
                    "source": "api",
                },
            )
        except Exception as exc:
            logger.warning("Failed to broadcast deleted memory %s: %s", memory_id, exc)

        return {"success": True, "message": f"Memory {memory_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
