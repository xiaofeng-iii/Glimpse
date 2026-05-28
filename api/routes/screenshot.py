"""
Screenshot Routes - Trigger screenshot capture
"""
from fastapi import APIRouter, HTTPException

from api.schemas import ScreenshotRequest, ScreenshotResponse
from api.desktop_actions import capture_and_analyze, capture_only

router = APIRouter(prefix="/screenshot", tags=["screenshot"])


@router.post("", response_model=ScreenshotResponse)
async def trigger_screenshot(request: ScreenshotRequest = None):
    """Trigger a fullscreen screenshot capture"""
    if request is None:
        request = ScreenshotRequest()

    try:
        result = await capture_only(force=request.force, source="api")
        return ScreenshotResponse(
            success=result["success"],
            message=result["message"],
            image_path=result.get("image_path"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def trigger_and_analyze(request: ScreenshotRequest = None):
    """Trigger screenshot and start AI analysis"""
    if request is None:
        request = ScreenshotRequest()

    try:
        return await capture_and_analyze(force=request.force, source="api")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
