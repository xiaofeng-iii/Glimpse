"""
Tag Routes - read-only tag listing
"""
from fastapi import APIRouter, HTTPException

from api.dependencies import get_memory_service
from api.schemas import TagListResponse

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=TagListResponse)
async def list_tags():
    """List all tags with their memory counts, zero-count tags included."""
    try:
        memory_service = get_memory_service()
        return TagListResponse(tags=memory_service.get_all_tags())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
