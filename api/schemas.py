"""
API Schemas - Pydantic models for request/response validation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class MemoryResponse(BaseModel):
    """Single memory record response"""
    id: str
    created_at: str
    image_path: str
    ai_summary: str
    app_name: str
    text_content: Optional[str] = None
    extra_images: Optional[str] = None
    sync_status: str = "PENDING"
    match_sources: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class MemoryListResponse(BaseModel):
    """List of memories response"""
    memories: List[MemoryResponse]
    total: int


class SearchQuery(BaseModel):
    """Search request parameters"""
    query: str
    source: str = "all"  # all, exact, semantic
    limit: int = 20


class SearchResult(BaseModel):
    """Search result response"""
    memories: List[MemoryResponse]
    query: str
    source: str


class SettingsResponse(BaseModel):
    """Settings response"""
    hotkeys: Dict[str, str] = Field(default_factory=lambda: {
        "screenshot": "<ctrl>+<shift>+g",
        "search": "<ctrl>+<f>",
    })
    screenshot: Dict[str, Any] = Field(default_factory=lambda: {
        "debounce_interval": 5.0,
        "cluster_threshold": 2.0,
        "max_captures_per_window": 10,
    })
    ai: Dict[str, Any] = Field(default_factory=lambda: {
        "provider": "OpenAI",
        "provider_type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "timeout": 30,
    })
    ocr: Dict[str, str] = Field(default_factory=lambda: {
        "engine": "rapidocr",
        "language": "ch",
    })
    ui: Dict[str, Any] = Field(default_factory=lambda: {
        "theme": "light",
        "auto_hide": False,
        "start_minimized": False,
        "close_action": "ask",
    })
    cluster: Dict[str, Any] = Field(default_factory=lambda: {
        "cluster_mode": False,
        "cluster_auto_submit": True,
        "cluster_max_images": 5,
        "cluster_timeout": 5,
    })


class SettingsUpdate(BaseModel):
    """Settings update request"""
    hotkeys: Optional[Dict[str, str]] = None
    screenshot: Optional[Dict[str, Any]] = None
    ai: Optional[Dict[str, Any]] = None
    ocr: Optional[Dict[str, str]] = None
    ui: Optional[Dict[str, Any]] = None
    cluster: Optional[Dict[str, Any]] = None


class AITestRequest(BaseModel):
    """AI connection test request"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class AITestResponse(BaseModel):
    """AI connection test response"""
    success: bool
    message: str


class ScreenshotRequest(BaseModel):
    """Screenshot trigger request"""
    force: bool = False  # bypass debounce


class ScreenshotResponse(BaseModel):
    """Screenshot trigger response"""
    success: bool
    message: str
    image_path: Optional[str] = None


class ClusterStatus(BaseModel):
    """Cluster buffer status"""
    state: str  # IDLE, COLLECTING
    count: int
    max_count: int
    images: List[str] = Field(default_factory=list)
    remaining_seconds: int = 0


class ClusterAction(BaseModel):
    """Cluster action (submit/cancel) response"""
    success: bool
    message: str
    images: Optional[List[str]] = None


class WebSocketEvent(BaseModel):
    """WebSocket event structure"""
    type: str  # screenshot_completed, memory_saved, status_updated, etc.
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
