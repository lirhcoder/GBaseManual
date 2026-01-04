"""
Projects API router.

Provides CRUD operations for projects.
"""

from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    RecordingResponse,
    RecordingListResponse,
    SuccessResponse,
)
from ...project import ProjectManager, ProjectSummary

router = APIRouter()


def get_manager() -> ProjectManager:
    """Get project manager instance."""
    return ProjectManager()


def project_to_response(project: ProjectSummary) -> ProjectResponse:
    """Convert ProjectSummary to API response."""
    return ProjectResponse(
        id=project.id,
        slug=project.slug,
        name=project.name,
        description=project.description,
        base_url=None,  # Not in summary
        created_at=project.created_at,
        updated_at=project.updated_at,
        recording_count=project.recording_count,
        tags=project.tags,
        status=project.status,
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    status: Optional[str] = Query(None, description="Filter by status (active/archived)"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
):
    """
    List all projects.

    Returns a list of projects with optional filtering by status and tags.
    Recording counts are refreshed by scanning the actual recordings directories.
    """
    manager = get_manager()
    projects = manager.list_projects(status=status, tags=tags)

    # Refresh recording counts by scanning actual directories
    responses = []
    for p in projects:
        # Get actual recording count by scanning directory
        actual_recordings = manager.list_recordings(p.slug)
        actual_count = len(actual_recordings)

        responses.append(ProjectResponse(
            id=p.id,
            slug=p.slug,
            name=p.name,
            description=p.description,
            base_url=None,
            created_at=p.created_at,
            updated_at=p.updated_at,
            recording_count=actual_count,  # Use actual count from directory scan
            tags=p.tags,
            status=p.status,
        ))

    return ProjectListResponse(
        projects=responses,
        total=len(responses),
    )


@router.post("", response_model=ProjectResponse)
async def create_project(request: ProjectCreate):
    """
    Create a new project.

    Creates a new project with the specified name and settings.
    """
    manager = get_manager()

    try:
        project = manager.create_project(
            name=request.name,
            slug=request.slug,
            description=request.description,
            base_url=request.base_url,
            tags=request.tags,
        )

        return ProjectResponse(
            id=project.id,
            slug=project.slug,
            name=project.name,
            description=project.description,
            base_url=project.base_url,
            created_at=project.created_at,
            updated_at=project.updated_at,
            recording_count=len(project.recordings),
            tags=project.tags,
            status=project.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{slug}", response_model=ProjectResponse)
async def get_project(slug: str):
    """
    Get project details.

    Returns detailed information about a specific project.
    """
    manager = get_manager()
    project = manager.get_project(slug)

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return ProjectResponse(
        id=project.id,
        slug=project.slug,
        name=project.name,
        description=project.description,
        base_url=project.base_url,
        created_at=project.created_at,
        updated_at=project.updated_at,
        recording_count=len(project.recordings),
        tags=project.tags,
        status=project.status,
    )


@router.put("/{slug}", response_model=ProjectResponse)
async def update_project(slug: str, request: ProjectUpdate):
    """
    Update a project.

    Updates the specified fields of a project.
    """
    manager = get_manager()

    project = manager.update_project(
        slug=slug,
        name=request.name,
        description=request.description,
        base_url=request.base_url,
        tags=request.tags,
        status=request.status,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return ProjectResponse(
        id=project.id,
        slug=project.slug,
        name=project.name,
        description=project.description,
        base_url=project.base_url,
        created_at=project.created_at,
        updated_at=project.updated_at,
        recording_count=len(project.recordings),
        tags=project.tags,
        status=project.status,
    )


@router.delete("/{slug}", response_model=SuccessResponse)
async def delete_project(slug: str, force: bool = Query(False)):
    """
    Delete a project.

    Deletes a project and optionally all its recordings.
    """
    manager = get_manager()

    try:
        if manager.delete_project(slug, force=force):
            return SuccessResponse(success=True, message=f"Project '{slug}' deleted")
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{slug}/recordings", response_model=RecordingListResponse)
async def list_recordings(slug: str):
    """
    List recordings in a project.

    Returns all recordings belonging to the specified project by scanning the recordings directory.
    """
    manager = get_manager()

    # Check if project exists
    if not manager.project_exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    # Use list_recordings which scans the directory
    recordings_list = manager.list_recordings(slug)

    recordings = [
        RecordingResponse(
            id=r.id,
            folder_name=r.folder_name,
            title=r.title,
            title_zh=r.title_zh,
            title_ja=r.title_ja,
            title_en=r.title_en,
            created_at=r.created_at,
            updated_at=r.updated_at,
            step_count=r.step_count,
            has_manual=r.has_manual,
            has_video=r.has_video,
            status=r.status,
            tags=r.tags,
        )
        for r in recordings_list
    ]

    return RecordingListResponse(
        recordings=recordings,
        total=len(recordings),
    )
