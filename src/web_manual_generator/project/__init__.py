"""
Project management module.

Provides project and recording management functionality.
"""

from .models import (
    Project,
    ProjectIndex,
    ProjectSummary,
    ProjectSettings,
    RecordingInfo,
)
from .manager import ProjectManager
from .utils import (
    generate_slug,
    generate_recording_folder_name,
    get_projects_dir,
    get_workspace_root,
)

__all__ = [
    "Project",
    "ProjectIndex",
    "ProjectSummary",
    "ProjectSettings",
    "RecordingInfo",
    "ProjectManager",
    "generate_slug",
    "generate_recording_folder_name",
    "get_projects_dir",
    "get_workspace_root",
]
