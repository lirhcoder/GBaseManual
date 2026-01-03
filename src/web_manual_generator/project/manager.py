"""
Project manager for handling project and recording operations.

Provides CRUD operations for projects and their recordings.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .models import Project, ProjectIndex, ProjectSummary, RecordingInfo
from .utils import (
    generate_slug,
    generate_recording_folder_name,
    ensure_directory,
    get_projects_dir,
)
from ..capture.action_log import ActionLog


class ProjectManager:
    """
    Manager for project and recording operations.

    Handles file system operations for projects stored in the projects directory.
    """

    def __init__(self, projects_dir: Optional[Path] = None):
        """
        Initialize the project manager.

        Args:
            projects_dir: Optional custom projects directory
        """
        self.projects_dir = projects_dir or get_projects_dir()
        ensure_directory(self.projects_dir)

    @property
    def index_path(self) -> Path:
        """Path to the projects index file."""
        return self.projects_dir / "projects.json"

    # ==================== Index Operations ====================

    def load_index(self) -> ProjectIndex:
        """Load the project index."""
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            return ProjectIndex.model_validate(data)
        return ProjectIndex()

    def save_index(self, index: ProjectIndex) -> None:
        """Save the project index."""
        self.index_path.write_text(
            index.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def update_index_entry(self, project: Project) -> None:
        """Update a single project entry in the index."""
        index = self.load_index()
        summary = ProjectSummary.from_project(project)

        # Update or add
        for i, p in enumerate(index.projects):
            if p.slug == project.slug:
                index.projects[i] = summary
                break
        else:
            index.projects.append(summary)

        self.save_index(index)

    def remove_index_entry(self, slug: str) -> None:
        """Remove a project entry from the index."""
        index = self.load_index()
        index.projects = [p for p in index.projects if p.slug != slug]
        self.save_index(index)

    # ==================== Project Operations ====================

    def get_project_dir(self, slug: str) -> Path:
        """Get the directory path for a project."""
        return self.projects_dir / slug

    def get_project_json_path(self, slug: str) -> Path:
        """Get the path to project.json for a project."""
        return self.get_project_dir(slug) / "project.json"

    def project_exists(self, slug: str) -> bool:
        """Check if a project exists."""
        return self.get_project_json_path(slug).exists()

    def list_projects(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ProjectSummary]:
        """
        List all projects.

        Args:
            status: Filter by status ("active", "archived")
            tags: Filter by tags (any match)

        Returns:
            List of project summaries
        """
        index = self.load_index()
        projects = index.projects

        if status:
            projects = [p for p in projects if p.status == status]

        if tags:
            projects = [
                p for p in projects
                if any(t in p.tags for t in tags)
            ]

        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def create_project(
        self,
        name: str,
        slug: Optional[str] = None,
        description: str = "",
        base_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            name: Project name
            slug: Optional custom slug (auto-generated if not provided)
            description: Project description
            base_url: Base URL for recordings
            tags: Project tags

        Returns:
            The created project

        Raises:
            ValueError: If the slug already exists
        """
        # Generate slug if not provided
        if slug is None:
            existing_slugs = [p.slug for p in self.list_projects()]
            slug = generate_slug(name, existing_slugs)
        elif self.project_exists(slug):
            raise ValueError(f"Project with slug '{slug}' already exists")

        # Create project
        project = Project(
            slug=slug,
            name=name,
            name_zh=name if self._is_chinese(name) else "",
            description=description,
            base_url=base_url,
            tags=tags or [],
        )

        # Create directory structure
        project_dir = self.get_project_dir(slug)
        ensure_directory(project_dir)
        ensure_directory(project_dir / "recordings")

        # Save project.json
        self.save_project(project)

        # Update index
        self.update_index_entry(project)

        return project

    def _is_chinese(self, text: str) -> bool:
        """Check if text contains Chinese characters."""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def get_project(self, slug: str) -> Optional[Project]:
        """
        Get a project by slug.

        Args:
            slug: Project slug

        Returns:
            The project or None if not found
        """
        project_path = self.get_project_json_path(slug)
        if not project_path.exists():
            return None

        data = json.loads(project_path.read_text(encoding="utf-8"))
        return Project.model_validate(data)

    def save_project(self, project: Project) -> None:
        """Save a project to disk."""
        project.updated_at = datetime.now()
        project_path = self.get_project_json_path(project.slug)
        project_path.write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def update_project(
        self,
        slug: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        base_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Optional[Project]:
        """
        Update a project.

        Args:
            slug: Project slug
            name: New name
            description: New description
            base_url: New base URL
            tags: New tags
            status: New status

        Returns:
            Updated project or None if not found
        """
        project = self.get_project(slug)
        if not project:
            return None

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if base_url is not None:
            project.base_url = base_url
        if tags is not None:
            project.tags = tags
        if status is not None:
            project.status = status

        self.save_project(project)
        self.update_index_entry(project)

        return project

    def delete_project(self, slug: str, force: bool = False) -> bool:
        """
        Delete a project.

        Args:
            slug: Project slug
            force: If True, delete even if project has recordings

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If project has recordings and force is False
        """
        project = self.get_project(slug)
        if not project:
            return False

        if project.recordings and not force:
            raise ValueError(
                f"Project '{slug}' has {len(project.recordings)} recordings. "
                "Use force=True to delete anyway."
            )

        # Remove directory
        project_dir = self.get_project_dir(slug)
        if project_dir.exists():
            shutil.rmtree(project_dir)

        # Remove from index
        self.remove_index_entry(slug)

        return True

    def archive_project(self, slug: str) -> Optional[Project]:
        """Archive a project."""
        return self.update_project(slug, status="archived")

    # ==================== Recording Operations ====================

    def get_recordings_dir(self, slug: str) -> Path:
        """Get the recordings directory for a project."""
        return self.get_project_dir(slug) / "recordings"

    def get_recording_dir(self, slug: str, folder_name: str) -> Path:
        """Get the directory for a specific recording."""
        return self.get_recordings_dir(slug) / folder_name

    def get_screenshots_dir(self, slug: str, folder_name: str) -> Path:
        """Get the screenshots directory for a recording."""
        return self.get_recording_dir(slug, folder_name) / "screenshots"

    def get_screenshot_path(self, slug: str, folder_name: str, filename: str) -> Path:
        """Get the path to a specific screenshot."""
        return self.get_screenshots_dir(slug, folder_name) / filename

    def list_recordings(self, slug: str) -> List[RecordingInfo]:
        """
        List all recordings for a project by scanning the recordings directory.

        Args:
            slug: Project slug

        Returns:
            List of recording info
        """
        recordings_dir = self.get_recordings_dir(slug)
        if not recordings_dir.exists():
            return []

        recordings = []
        for folder in recordings_dir.iterdir():
            if not folder.is_dir():
                continue

            action_log_path = folder / "action_log.json"
            if not action_log_path.exists():
                continue

            # Parse folder name for date and title
            from .utils import parse_recording_folder_name
            created_date, title = parse_recording_folder_name(folder.name)

            # Try to load action log for more info
            step_count = 0
            try:
                import json
                with open(action_log_path, "r", encoding="utf-8") as f:
                    action_log = json.load(f)
                    step_count = len(action_log.get("steps", []))
                    if action_log.get("title"):
                        title = action_log["title"]
            except Exception:
                pass

            # Check for manual and video
            has_manual = (folder / "manual").exists()
            has_video = (folder / "videos").exists() and any((folder / "videos").iterdir())

            recording = RecordingInfo(
                id=folder.name,
                folder_name=folder.name,
                title=title,
                created_at=created_date or datetime.fromtimestamp(folder.stat().st_ctime),
                updated_at=datetime.fromtimestamp(folder.stat().st_mtime),
                step_count=step_count,
                has_manual=has_manual,
                has_video=has_video,
            )
            recordings.append(recording)

        return sorted(recordings, key=lambda r: r.created_at, reverse=True)

    def create_recording(
        self,
        slug: str,
        title: str,
        folder_name: Optional[str] = None,
    ) -> tuple[RecordingInfo, Path]:
        """
        Create a new recording entry.

        Args:
            slug: Project slug
            title: Recording title
            folder_name: Optional custom folder name

        Returns:
            Tuple of (RecordingInfo, recording_path)

        Raises:
            ValueError: If project not found or folder already exists
        """
        project = self.get_project(slug)
        if not project:
            raise ValueError(f"Project '{slug}' not found")

        # Generate folder name if not provided
        if folder_name is None:
            folder_name = generate_recording_folder_name(title)

        # Ensure unique folder name
        recording_dir = self.get_recording_dir(slug, folder_name)
        if recording_dir.exists():
            # Add timestamp suffix
            folder_name = f"{folder_name}_{datetime.now().strftime('%H%M%S')}"
            recording_dir = self.get_recording_dir(slug, folder_name)

        # Create directory structure
        ensure_directory(recording_dir)
        ensure_directory(recording_dir / "screenshots")
        ensure_directory(recording_dir / "videos")
        ensure_directory(recording_dir / "manual")

        # Create recording info
        recording = RecordingInfo(
            folder_name=folder_name,
            title=title,
            title_zh=title if self._is_chinese(title) else "",
        )

        # Add to project
        project.add_recording(recording)
        self.save_project(project)
        self.update_index_entry(project)

        return recording, recording_dir

    def load_recording(self, slug: str, folder_name: str) -> Optional[ActionLog]:
        """
        Load an action log for a recording.

        Args:
            slug: Project slug
            folder_name: Recording folder name

        Returns:
            ActionLog or None if not found
        """
        recording_dir = self.get_recording_dir(slug, folder_name)
        action_log_path = recording_dir / "action_log.json"

        if not action_log_path.exists():
            # Try enhanced version
            action_log_path = recording_dir / "action_log_enhanced.json"

        if not action_log_path.exists():
            return None

        return ActionLog.load(action_log_path)

    def save_recording(
        self,
        slug: str,
        folder_name: str,
        action_log: ActionLog,
    ) -> Path:
        """
        Save an action log for a recording.

        Args:
            slug: Project slug
            folder_name: Recording folder name
            action_log: ActionLog to save

        Returns:
            Path to saved file
        """
        recording_dir = self.get_recording_dir(slug, folder_name)
        action_log_path = recording_dir / "action_log.json"

        action_log.save(action_log_path)

        # Update recording info
        project = self.get_project(slug)
        if project:
            recording = project.get_recording(folder_name)
            if recording:
                recording.step_count = len(action_log.steps)
                recording.updated_at = datetime.now()
                self.save_project(project)

        return action_log_path

    def delete_recording(self, slug: str, folder_name: str) -> bool:
        """
        Delete a recording.

        Args:
            slug: Project slug
            folder_name: Recording folder name

        Returns:
            True if deleted, False if not found
        """
        project = self.get_project(slug)
        if not project:
            return False

        recording_dir = self.get_recording_dir(slug, folder_name)
        if not recording_dir.exists():
            return False

        # Remove directory
        shutil.rmtree(recording_dir)

        # Remove from project
        project.remove_recording(folder_name)
        self.save_project(project)
        self.update_index_entry(project)

        return True

    def move_recording(
        self,
        from_slug: str,
        folder_name: str,
        to_slug: str,
    ) -> bool:
        """
        Move a recording to another project.

        Args:
            from_slug: Source project slug
            folder_name: Recording folder name
            to_slug: Target project slug

        Returns:
            True if moved, False if source or target not found
        """
        from_project = self.get_project(from_slug)
        to_project = self.get_project(to_slug)

        if not from_project or not to_project:
            return False

        recording = from_project.get_recording(folder_name)
        if not recording:
            return False

        # Move directory
        from_dir = self.get_recording_dir(from_slug, folder_name)
        to_dir = self.get_recording_dir(to_slug, folder_name)

        if not from_dir.exists():
            return False

        shutil.move(str(from_dir), str(to_dir))

        # Update projects
        from_project.remove_recording(folder_name)
        to_project.add_recording(recording)

        self.save_project(from_project)
        self.save_project(to_project)
        self.update_index_entry(from_project)
        self.update_index_entry(to_project)

        return True

    def update_recording_status(
        self,
        slug: str,
        folder_name: str,
        has_manual: Optional[bool] = None,
        has_video: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> bool:
        """
        Update recording metadata.

        Args:
            slug: Project slug
            folder_name: Recording folder name
            has_manual: Whether manual has been generated
            has_video: Whether video exists
            status: Recording status

        Returns:
            True if updated, False if not found
        """
        project = self.get_project(slug)
        if not project:
            return False

        recording = project.get_recording(folder_name)
        if not recording:
            return False

        if has_manual is not None:
            recording.has_manual = has_manual
        if has_video is not None:
            recording.has_video = has_video
        if status is not None:
            recording.status = status

        recording.updated_at = datetime.now()
        self.save_project(project)

        return True
