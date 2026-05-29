"""
Image Routes - serve captured screenshot files safely.
"""
from pathlib import Path
import mimetypes

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.dependencies import get_path_manager

router = APIRouter(prefix="/images", tags=["images"])


def _ensure_within_data_root(file_path: Path, data_root: Path) -> Path:
    resolved = file_path.resolve()
    root = data_root.resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Forbidden image path") from exc

    return resolved


@router.get("")
async def open_image(path: str = Query(..., min_length=1)):
    """Return an image file if it is stored under GlimpseData."""
    path_manager = get_path_manager()
    requested_path = Path(path)
    safe_path = _ensure_within_data_root(requested_path, path_manager.data_root)

    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    media_type, _ = mimetypes.guess_type(str(safe_path))
    return FileResponse(safe_path, media_type=media_type or "application/octet-stream")
