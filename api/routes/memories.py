"""
Memory Routes - CRUD operations for memories
"""
import asyncio
import os
import time
from datetime import date
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from starlette.concurrency import run_in_threadpool

from api.schemas import (
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryType,
    MemoryUpdateRequest,
)
from api.dependencies import get_path_manager, get_search_service, get_memory_service
from api.memory_filters import normalize_memory_date_range
from api.websocket import broadcast_event, broadcast_event_from_thread
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

MAX_IMPORT_IMAGES = 10
MAX_IMPORT_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMPORT_TEXT_LENGTH = 4000
IMPORT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


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


@router.post("/images", response_model=MemoryResponse, status_code=201)
async def create_image_memory(
    images: List[UploadFile] = File(...),
    content: str = Form(""),
):
    """Create an image memory from uploaded files, with an optional user note.

    The record is returned immediately in PROCESSING state; OCR and the AI
    summary continue in the background exactly like screenshot memories.
    """
    if not images:
        raise HTTPException(status_code=422, detail="At least one image is required")
    if len(images) > MAX_IMPORT_IMAGES:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_IMPORT_IMAGES} images per memory",
        )

    caption = content.strip() if isinstance(content, str) else ""
    if len(caption) > MAX_IMPORT_TEXT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Content cannot exceed {MAX_IMPORT_TEXT_LENGTH} characters",
        )

    path_manager = get_path_manager()
    saved_paths: List[str] = []
    try:
        timestamp = int(time.time() * 1000)
        for index, upload in enumerate(images):
            extension = os.path.splitext(upload.filename or "")[1].lower()
            if extension not in IMPORT_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported image type: {upload.filename or 'unknown'}",
                )

            data = await upload.read(MAX_IMPORT_IMAGE_BYTES + 1)
            if not data:
                raise HTTPException(
                    status_code=422,
                    detail=f"Empty image file: {upload.filename or 'unknown'}",
                )
            if len(data) > MAX_IMPORT_IMAGE_BYTES:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Image exceeds {MAX_IMPORT_IMAGE_BYTES // (1024 * 1024)} MB: "
                        f"{upload.filename or 'unknown'}"
                    ),
                )

            filename = f"screenshot_{timestamp}_{index}{extension}"
            target = path_manager.get_screenshot_path(filename)
            target.write_bytes(data)
            saved_paths.append(str(target))
    except HTTPException:
        _remove_saved_files(saved_paths)
        raise

    memory_service = get_memory_service()
    try:
        pending_memory = memory_service.prepare_cluster_memory(
            saved_paths,
            app_name="",
            user_text=caption or None,
        )
    except Exception as exc:
        _remove_saved_files(saved_paths)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        await broadcast_event(
            "memory_processing_started",
            {
                "memory": pending_memory.to_dict(),
                "source": "import",
            },
        )
    except Exception as exc:
        logger.warning(
            "Failed to broadcast image memory %s: %s", pending_memory.id, exc
        )

    loop = asyncio.get_running_loop()

    def on_complete(memory_id):
        if not memory_id:
            broadcast_event_from_thread(
                loop,
                "error_occurred",
                _import_event_data("Image memory creation failed", saved_paths),
            )
            return

        broadcast_event_from_thread(
            loop,
            "memory_saved",
            _import_event_data("", saved_paths, memory_id=memory_id),
        )

    def on_error(message: str):
        broadcast_event_from_thread(
            loop,
            "error_occurred",
            _import_event_data(message, saved_paths),
        )

    try:
        memory_service.create_cluster_memory_async(
            saved_paths,
            app_name="",
            on_complete=on_complete,
            on_error=on_error,
            memory_id=pending_memory.id,
        )
    except Exception as exc:
        logger.warning(
            "Image memory async queue unavailable, falling back to thread: %s", exc
        )

        async def create_in_background():
            try:
                completed_id = await asyncio.to_thread(
                    memory_service.create_cluster_memory,
                    saved_paths,
                    "",
                    memory_id=pending_memory.id,
                )
                on_complete(completed_id)
            except Exception as background_exc:
                on_error(str(background_exc))

        asyncio.create_task(create_in_background())

    return MemoryResponse(**memory_to_response(pending_memory))


def _import_event_data(message: str, image_paths: List[str], *, memory_id=None) -> dict:
    data = {
        "image_path": image_paths[0],
        "images": image_paths,
        "source": "import",
    }
    if message:
        data["message"] = message
    if memory_id:
        data["memory_id"] = memory_id
    return data


def _remove_saved_files(paths: List[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


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
    """Update user-editable memory fields and queue semantic reindexing."""
    try:
        if request.ai_summary is None and request.user_text is None:
            raise HTTPException(
                status_code=422,
                detail="Provide ai_summary or user_text to update",
            )

        memory_service = get_memory_service()
        memory = None
        if request.ai_summary is not None:
            memory = memory_service.update_memory_summary(
                memory_id,
                request.ai_summary,
            )
            if memory is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory {memory_id} not found",
                )
        if request.user_text is not None:
            memory = memory_service.update_memory_user_text(
                memory_id,
                request.user_text,
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
