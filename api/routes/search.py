"""
Search Routes - Search functionality
"""
from fastapi import APIRouter, HTTPException, Query

from api.schemas import SearchResult, MemoryResponse
from api.dependencies import get_search_service, get_task_queue

router = APIRouter(prefix="/search", tags=["search"])
SEARCH_WARMUP_TASK_ID = "semantic_search_warmup"


def task_is_active(task) -> bool:
    return bool(task and task.status.name in {"PENDING", "RUNNING"})


def task_can_be_reused(task) -> bool:
    return bool(task and task.status.name in {"PENDING", "RUNNING", "COMPLETED"})


def serialize_warmup_task(task) -> dict:
    if not task:
        return {
            "task_id": SEARCH_WARMUP_TASK_ID,
            "status": "idle",
            "running": False,
            "result": None,
            "error": None,
        }

    return {
        "task_id": task.id,
        "status": task.status.name.lower(),
        "running": task_is_active(task),
        "result": task.result,
        "error": task.error,
    }


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
    source: str = Query("all", description="Filter source: all, exact, semantic"),
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


@router.post("/warmup")
async def warmup_search():
    """Open the vector store and load the embedding model in a background task."""
    try:
        task_queue = get_task_queue()
        existing = task_queue.get_task(SEARCH_WARMUP_TASK_ID)
        if task_can_be_reused(existing):
            return serialize_warmup_task(existing)

        search_service = get_search_service()
        task = task_queue.submit(SEARCH_WARMUP_TASK_ID, search_service.warmup)
        return serialize_warmup_task(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
