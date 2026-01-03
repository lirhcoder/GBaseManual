"""
Utility functions for project management.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import re

from slugify import slugify


def generate_slug(name: str, existing_slugs: Optional[list] = None) -> str:
    """
    Generate a URL-safe slug from a name.

    Args:
        name: The name to convert to a slug
        existing_slugs: List of existing slugs to avoid duplicates

    Returns:
        A unique URL-safe slug
    """
    base_slug = slugify(name, lowercase=True, separator="-")

    if not base_slug:
        base_slug = "project"

    if existing_slugs is None:
        return base_slug

    # Ensure uniqueness
    slug = base_slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def generate_recording_folder_name(title: str, timestamp: Optional[datetime] = None) -> str:
    """
    Generate a folder name for a recording.

    Format: YYYY-MM-DD_title-slug

    Args:
        title: Recording title
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Folder name like "2026-01-03_login-test"
    """
    if timestamp is None:
        timestamp = datetime.now()

    date_str = timestamp.strftime("%Y-%m-%d")
    title_slug = slugify(title, lowercase=True, separator="-")

    if not title_slug:
        title_slug = "recording"

    # Limit title length
    if len(title_slug) > 50:
        title_slug = title_slug[:50]

    return f"{date_str}_{title_slug}"


def parse_recording_folder_name(folder_name: str) -> tuple[Optional[datetime], str]:
    """
    Parse a recording folder name to extract date and title.

    Args:
        folder_name: Folder name like "2026-01-03_login-test"

    Returns:
        Tuple of (date, title) or (None, folder_name) if parsing fails
    """
    pattern = r"^(\d{4}-\d{2}-\d{2})_(.+)$"
    match = re.match(pattern, folder_name)

    if match:
        date_str, title = match.groups()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            return date, title
        except ValueError:
            pass

    return None, folder_name


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Path to the directory

    Returns:
        The path (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_workspace_root() -> Path:
    """
    Get the workspace root directory.

    Returns the current working directory by default.
    Can be overridden by setting WMG_WORKSPACE environment variable.
    """
    import os

    workspace = os.environ.get("WMG_WORKSPACE")
    if workspace:
        return Path(workspace)

    return Path.cwd()


def get_projects_dir() -> Path:
    """
    Get the projects directory.

    Returns:
        Path to the projects directory
    """
    return get_workspace_root() / "projects"
