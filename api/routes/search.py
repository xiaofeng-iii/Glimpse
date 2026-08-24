"""
Search Routes - Search functionality
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import date

from api.schemas import SearchResult, MemoryResponse
from api.dependencies import get_search_service, get_task_queue
from api.memory_filters import normalize_memory_date_range

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
        "search_debug": getattr(memory, "search_debug", None),
    }


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("all", description="Filter source: all, exact, semantic"),
    limit: int = Query(20, ge=1, le=100),
    semantic_threshold: float | None = Query(
        None,
        ge=0,
        le=4,
        description="Maximum Chroma distance accepted as a semantic match",
    ),
    candidate_multiplier: int = Query(
        2,
        ge=1,
        le=10,
        description="Candidate pool size as a multiple of limit",
    ),
    rrf_k: int = Query(60, ge=1, le=200, description="RRF rank constant"),
    debug: bool = Query(False, description="Include development search scores"),
    date_from: date | None = None,
    date_to: date | None = None,
):
    """Search memories by query"""
    try:
        search_service = get_search_service()
        bounds = normalize_memory_date_range(date_from, date_to)
        search_options = {
            "limit": limit,
            "source_filter": source,
            "semantic_threshold": semantic_threshold,
            "candidate_multiplier": candidate_multiplier,
            "rrf_k": rrf_k,
            "include_debug": debug,
        }
        if bounds.created_after or bounds.created_before:
            search_options.update(
                created_after=bounds.created_after,
                created_before=bounds.created_before,
            )
        memories = search_service.search(
            q,
            **search_options,
        )
        return SearchResult(
            memories=[MemoryResponse(**memory_to_response(m)) for m in memories],
            query=q,
            source=source,
        )
    except HTTPException:
        raise
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
