"""
API request/response schemas for Web Manual Generator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ==================== Project Schemas ====================

class ProjectCreate(BaseModel):
    """Request to create a new project."""
    name: str
    slug: Optional[str] = None
    description: str = ""
    base_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """Request to update a project."""
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    """Project response."""
    id: str
    slug: str
    name: str
    description: str
    base_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    recording_count: int
    tags: List[str]
    status: str


class ProjectListResponse(BaseModel):
    """List of projects response."""
    projects: List[ProjectResponse]
    total: int


# ==================== Recording Schemas ====================

class RecordingResponse(BaseModel):
    """Recording info response."""
    id: str
    folder_name: str
    title: str
    title_zh: str = ""
    title_ja: str = ""
    title_en: str = ""
    created_at: datetime
    updated_at: datetime
    step_count: int
    has_manual: bool
    has_video: bool
    status: str
    tags: List[str]


class RecordingListResponse(BaseModel):
    """List of recordings response."""
    recordings: List[RecordingResponse]
    total: int


# ==================== Step Schemas ====================

class StepResponse(BaseModel):
    """Action step response."""
    id: int
    action: str
    timestamp: datetime
    selector: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    key: Optional[str] = None
    description: str
    description_zh: str = ""
    description_ja: str = ""
    description_en: str = ""
    screenshot: Optional[str] = None
    element_screenshot: Optional[str] = None
    page_title: Optional[str] = None
    page_url: Optional[str] = None
    notes: Optional[str] = None


class StepsResponse(BaseModel):
    """Recording steps response."""
    title: str
    steps: List[StepResponse]
    metadata: dict


class StepCreate(BaseModel):
    """Request to create a new step."""
    action: str
    description: str = ""
    description_zh: str = ""
    description_en: str = ""
    description_ja: str = ""
    selector: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    insert_after: Optional[int] = None  # Insert after this step ID, None = append


class StepUpdate(BaseModel):
    """Request to update a step."""
    description: Optional[str] = None
    description_zh: Optional[str] = None
    description_ja: Optional[str] = None
    description_en: Optional[str] = None
    notes: Optional[str] = None


class StepBatchUpdate(BaseModel):
    """Request to batch update steps."""
    steps: List[dict]  # [{id: 1, description: "...", ...}]


class StepReorder(BaseModel):
    """Request to reorder steps."""
    step_ids: List[int]  # New order of step IDs


# ==================== Screenshot Schemas ====================

class CropRequest(BaseModel):
    """Request to crop a screenshot."""
    x: int
    y: int
    width: int
    height: int


class AnnotationItem(BaseModel):
    """Single annotation item."""
    type: str  # rect, circle, arrow, text, highlight
    x: Optional[int] = None
    y: Optional[int] = None
    left: Optional[int] = None
    top: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    radius: Optional[int] = None
    stroke: str = "#ef4444"
    stroke_width: int = 2
    fill: Optional[str] = None
    text: Optional[str] = None
    font_size: int = 16
    points: Optional[List[int]] = None  # For arrows/lines


class AnnotateRequest(BaseModel):
    """Request to annotate a screenshot."""
    annotations: List[AnnotationItem]


# ==================== AI Schemas ====================

class AIRegenerateRequest(BaseModel):
    """Request to regenerate descriptions with AI."""
    step_ids: Optional[List[int]] = None  # None = all steps
    languages: List[str] = Field(default_factory=lambda: ["zh", "en", "ja"])
    provider: str = "gemini"
    api_key: Optional[str] = None  # API key from frontend


class AIRegenerateResponse(BaseModel):
    """AI regeneration response."""
    success: bool
    enhanced_steps: int
    message: str = ""


# ==================== Manual Schemas ====================

class ManualGenerateRequest(BaseModel):
    """Request to generate a manual."""
    project_slug: str
    recording_name: str
    format: str = "html"  # html, pdf, both
    languages: List[str] = Field(default_factory=lambda: ["zh"])
    use_ai: bool = False
    provider: str = "gemini"


class ManualGenerateResponse(BaseModel):
    """Manual generation response."""
    success: bool
    html_path: Optional[str] = None
    pdf_path: Optional[str] = None
    message: str = ""


class ManualPreviewResponse(BaseModel):
    """Manual preview response."""
    html_content: str
    title: str


# ==================== Recording Schemas ====================

class StartRecordingRequest(BaseModel):
    """Request to start a new recording."""
    url: str
    project_slug: str
    title: str = ""
    show_cursor: bool = True


class StartRecordingResponse(BaseModel):
    """Response after starting recording."""
    success: bool
    message: str = ""
    recording_name: Optional[str] = None


# ==================== Common Schemas ====================

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool
    message: str = ""


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
