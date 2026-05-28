"""
Cluster Routes - Cluster mode management
"""
from fastapi import APIRouter, HTTPException

from api.schemas import ClusterStatus, ClusterAction
from api.dependencies import get_cluster_buffer, get_settings_manager

router = APIRouter(prefix="/cluster", tags=["cluster"])


@router.get("/status", response_model=ClusterStatus)
async def get_cluster_status():
    """Get current cluster buffer status"""
    try:
        cluster_buffer = get_cluster_buffer()
        settings_manager = get_settings_manager()

        max_count = settings_manager.get("cluster.cluster_max_images", 5)

        return ClusterStatus(
            state="COLLECTING" if cluster_buffer.is_collecting() else "IDLE",
            count=cluster_buffer.get_count(),
            max_count=max_count,
            images=cluster_buffer.get_images(),
            remaining_seconds=cluster_buffer.get_remaining_seconds(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit", response_model=ClusterAction)
async def submit_cluster():
    """Submit current cluster for processing"""
    try:
        cluster_buffer = get_cluster_buffer()
        images = cluster_buffer.get_images()

        if not images:
            return ClusterAction(
                success=False,
                message="No images in cluster to submit",
            )

        cluster_buffer.flush()

        return ClusterAction(
            success=True,
            message=f"Cluster submitted with {len(images)} images",
            images=images,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel", response_model=ClusterAction)
async def cancel_cluster():
    """Cancel current cluster collection"""
    try:
        cluster_buffer = get_cluster_buffer()
        images = cluster_buffer.get_images()

        cluster_buffer.discard()

        return ClusterAction(
            success=True,
            message="Cluster collection cancelled",
            images=images,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
