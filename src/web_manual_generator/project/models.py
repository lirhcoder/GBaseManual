"""
Data models for project management.

Provides structured storage for projects and their recordings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


def generate_id(prefix: str = "id") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class ProjectSettings(BaseModel):
    """Project-level settings."""
    default_language: str = "zh"
    auto_screenshot: bool = True
    highlight_elements: bool = True
    show_cursor: bool = True


class RecordingInfo(BaseModel):
    """Recording metadata (lightweight, stored in project.json)."""
    id: str = Field(default_factory=lambda: generate_id("rec"))
    folder_name: str  # e.g., 2026-01-03_登录测试
    title: str
    title_zh: str = ""
    title_ja: str = ""
    title_en: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    step_count: int = 0
    has_manual: bool = False
    has_video: bool = False
    status: Literal["recording", "completed", "archived"] = "completed"
    tags: List[str] = Field(default_factory=list)


class Project(BaseModel):
    """Project model."""
    id: str = Field(default_factory=lambda: generate_id("proj"))
    slug: str  # URL-safe name
    name: str
    name_zh: str = ""
    name_ja: str = ""
    name_en: str = ""
    description: str = ""
    base_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list)
    status: Literal["active", "archived"] = "active"
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    recordings: List[RecordingInfo] = Field(default_factory=list)

    def add_recording(self, recording: RecordingInfo) -> None:
        """Add a recording to the project."""
        self.recordings.append(recording)
        self.updated_at = datetime.now()

    def remove_recording(self, folder_name: str) -> bool:
        """Remove a recording by folder name."""
        for i, rec in enumerate(self.recordings):
            if rec.folder_name == folder_name:
                self.recordings.pop(i)
                self.updated_at = datetime.now()
                return True
        return False

    def get_recording(self, folder_name: str) -> Optional[RecordingInfo]:
        """Get a recording by folder name."""
        for rec in self.recordings:
            if rec.folder_name == folder_name:
                return rec
        return None


class ProjectIndex(BaseModel):
    """Project index (stored in projects.json)."""
    version: str = "1.0.0"
    projects: List[ProjectSummary] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Lightweight project info for index."""
    id: str
    slug: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime
    recording_count: int = 0
    tags: List[str] = Field(default_factory=list)
    status: Literal["active", "archived"] = "active"

    @classmethod
    def from_project(cls, project: Project) -> "ProjectSummary":
        """Create summary from full project."""
        return cls(
            id=project.id,
            slug=project.slug,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            recording_count=len(project.recordings),
            tags=project.tags,
            status=project.status,
        )


# Fix forward reference
ProjectIndex.model_rebuild()
