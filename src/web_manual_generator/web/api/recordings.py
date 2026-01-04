"""
Recordings API router.

Provides operations for editing recordings, steps, and screenshots.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw

from ..schemas import (
    StepsResponse,
    StepResponse,
    StepCreate,
    StepUpdate,
    StepBatchUpdate,
    StepReorder,
    CropRequest,
    AnnotateRequest,
    AIRegenerateRequest,
    AIRegenerateResponse,
    SuccessResponse,
)
from ...project import ProjectManager
from ...capture.action_log import ActionLog

router = APIRouter()


def get_manager() -> ProjectManager:
    """Get project manager instance."""
    return ProjectManager()


# ==================== Recording API ====================

@router.delete("/{project_slug}/{recording_name}", response_model=SuccessResponse)
async def delete_recording(project_slug: str, recording_name: str):
    """
    Delete a recording.

    Deletes a recording and all its associated files (screenshots, videos, etc.).
    """
    manager = get_manager()

    # Check if recording exists
    recording = manager.get_recording(project_slug, recording_name)
    if not recording:
        raise HTTPException(
            status_code=404,
            detail=f"Recording '{recording_name}' not found in project '{project_slug}'"
        )

    # Delete recording
    if manager.delete_recording(project_slug, recording_name):
        return SuccessResponse(
            success=True,
            message=f"Recording '{recording_name}' deleted successfully"
        )

    raise HTTPException(
        status_code=500,
        detail="Failed to delete recording"
    )


# ==================== Steps API ====================

@router.get("/{project_slug}/{recording_name}/steps", response_model=StepsResponse)
async def get_steps(project_slug: str, recording_name: str):
    """
    Get all steps for a recording.

    Returns the action log with all steps and metadata.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(
            status_code=404,
            detail=f"Recording '{recording_name}' not found in project '{project_slug}'"
        )

    steps = [
        StepResponse(
            id=step.id,
            action=step.action,
            timestamp=step.timestamp,
            selector=step.selector,
            value=step.value,
            url=step.url,
            key=step.key,
            description=step.description,
            description_zh=step.description_zh,
            description_ja=step.description_ja,
            description_en=step.description_en,
            screenshot=step.screenshot,
            element_screenshot=step.element_screenshot,
            page_title=step.page_title,
            page_url=step.page_url,
            notes=step.notes,
        )
        for step in action_log.steps
    ]

    return StepsResponse(
        title=action_log.title,
        steps=steps,
        metadata={
            "created_at": action_log.created_at.isoformat() if action_log.created_at else None,
            "updated_at": action_log.updated_at.isoformat() if action_log.updated_at else None,
            "start_url": action_log.start_url,
            "video_file": action_log.video_file,
        }
    )


@router.put("/{project_slug}/{recording_name}/steps/{step_id}", response_model=StepResponse)
async def update_step(
    project_slug: str,
    recording_name: str,
    step_id: int,
    request: StepUpdate
):
    """
    Update a single step.

    Updates the specified fields of a step.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Find and update step
    step = None
    for s in action_log.steps:
        if s.id == step_id:
            step = s
            if request.description is not None:
                s.description = request.description
            if request.description_zh is not None:
                s.description_zh = request.description_zh
            if request.description_ja is not None:
                s.description_ja = request.description_ja
            if request.description_en is not None:
                s.description_en = request.description_en
            if request.notes is not None:
                s.notes = request.notes
            break

    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")

    manager.save_recording(project_slug, recording_name, action_log)

    return StepResponse(
        id=step.id,
        action=step.action,
        timestamp=step.timestamp,
        selector=step.selector,
        value=step.value,
        url=step.url,
        key=step.key,
        description=step.description,
        description_zh=step.description_zh,
        description_ja=step.description_ja,
        description_en=step.description_en,
        screenshot=step.screenshot,
        element_screenshot=step.element_screenshot,
        page_title=step.page_title,
        page_url=step.page_url,
        notes=step.notes,
    )


@router.put("/{project_slug}/{recording_name}/steps", response_model=SuccessResponse)
async def batch_update_steps(
    project_slug: str,
    recording_name: str,
    request: StepBatchUpdate
):
    """
    Batch update multiple steps.

    Updates multiple steps at once.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Build step map for quick lookup
    step_map = {s.id: s for s in action_log.steps}

    updated_count = 0
    for update in request.steps:
        step_id = update.get("id")
        if step_id and step_id in step_map:
            step = step_map[step_id]
            for key, value in update.items():
                if key != "id" and hasattr(step, key):
                    setattr(step, key, value)
            updated_count += 1

    manager.save_recording(project_slug, recording_name, action_log)

    return SuccessResponse(
        success=True,
        message=f"Updated {updated_count} steps"
    )


@router.post("/{project_slug}/{recording_name}/steps", response_model=StepResponse)
async def create_step(
    project_slug: str,
    recording_name: str,
    request: StepCreate
):
    """
    Create a new step.

    Adds a new step to the recording, optionally inserting after a specific step.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    from ...capture.action_log import ActionStep

    # Create new step
    new_step = ActionStep(
        id=0,  # Will be assigned below
        action=request.action,
        timestamp=datetime.now(),
        selector=request.selector,
        value=request.value,
        url=request.url,
        description=request.description or request.description_zh,
        description_zh=request.description_zh or request.description,
        description_en=request.description_en,
        description_ja=request.description_ja,
    )

    # Insert at correct position
    if request.insert_after is not None:
        # Find insert position
        insert_idx = None
        for i, step in enumerate(action_log.steps):
            if step.id == request.insert_after:
                insert_idx = i + 1
                break

        if insert_idx is None:
            raise HTTPException(status_code=400, detail=f"Step {request.insert_after} not found")

        action_log.steps.insert(insert_idx, new_step)
    else:
        # Append to end
        action_log.steps.append(new_step)

    # Renumber all steps
    for i, step in enumerate(action_log.steps, 1):
        step.id = i

    # Find the new step's ID after renumbering
    if request.insert_after is not None:
        new_step_id = insert_idx + 1
    else:
        new_step_id = len(action_log.steps)

    new_step = action_log.steps[new_step_id - 1]

    manager.save_recording(project_slug, recording_name, action_log)

    return StepResponse(
        id=new_step.id,
        action=new_step.action,
        timestamp=new_step.timestamp,
        selector=new_step.selector,
        value=new_step.value,
        url=new_step.url,
        key=new_step.key,
        description=new_step.description,
        description_zh=new_step.description_zh,
        description_ja=new_step.description_ja,
        description_en=new_step.description_en,
        screenshot=new_step.screenshot,
        element_screenshot=new_step.element_screenshot,
        page_title=new_step.page_title,
        page_url=new_step.page_url,
        notes=new_step.notes,
    )


@router.delete("/{project_slug}/{recording_name}/steps/{step_id}", response_model=SuccessResponse)
async def delete_step(project_slug: str, recording_name: str, step_id: int):
    """
    Delete a step.

    Removes a step from the recording and renumbers remaining steps.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    original_count = len(action_log.steps)
    action_log.steps = [s for s in action_log.steps if s.id != step_id]

    if len(action_log.steps) == original_count:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")

    # Renumber steps
    for i, step in enumerate(action_log.steps, 1):
        step.id = i

    manager.save_recording(project_slug, recording_name, action_log)

    return SuccessResponse(
        success=True,
        message=f"Step deleted, {len(action_log.steps)} steps remaining"
    )


@router.post("/{project_slug}/{recording_name}/steps/reorder", response_model=SuccessResponse)
async def reorder_steps(
    project_slug: str,
    recording_name: str,
    request: StepReorder
):
    """
    Reorder steps.

    Changes the order of steps according to the provided ID list.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Build step map
    step_map = {s.id: s for s in action_log.steps}

    # Validate all IDs exist
    for step_id in request.step_ids:
        if step_id not in step_map:
            raise HTTPException(status_code=400, detail=f"Invalid step ID: {step_id}")

    # Reorder steps
    new_steps = []
    for new_id, old_id in enumerate(request.step_ids, 1):
        step = step_map[old_id]
        step.id = new_id
        new_steps.append(step)

    action_log.steps = new_steps
    manager.save_recording(project_slug, recording_name, action_log)

    return SuccessResponse(success=True, message="Steps reordered")


# ==================== Screenshots API ====================

@router.get("/{project_slug}/{recording_name}/screenshots/{filename}")
async def get_screenshot(project_slug: str, recording_name: str, filename: str):
    """
    Get a screenshot file.

    Returns the screenshot image file.
    """
    manager = get_manager()
    screenshot_path = manager.get_screenshot_path(project_slug, recording_name, filename)

    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(screenshot_path)


@router.put("/{project_slug}/{recording_name}/screenshots/{filename}", response_model=SuccessResponse)
async def replace_screenshot(
    project_slug: str,
    recording_name: str,
    filename: str,
    file: UploadFile = File(...)
):
    """
    Replace a screenshot.

    Uploads a new image to replace an existing screenshot.
    """
    manager = get_manager()
    screenshot_path = manager.get_screenshot_path(project_slug, recording_name, filename)

    # Backup original
    if screenshot_path.exists():
        backup_path = screenshot_path.with_suffix('.png.bak')
        screenshot_path.rename(backup_path)

    # Save new file
    content = await file.read()
    screenshot_path.write_bytes(content)

    return SuccessResponse(success=True, message=f"Screenshot '{filename}' replaced")


@router.post("/{project_slug}/{recording_name}/screenshots/{filename}/crop", response_model=SuccessResponse)
async def crop_screenshot(
    project_slug: str,
    recording_name: str,
    filename: str,
    request: CropRequest
):
    """
    Crop a screenshot.

    Crops the screenshot to the specified region.
    """
    manager = get_manager()
    screenshot_path = manager.get_screenshot_path(project_slug, recording_name, filename)

    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    try:
        img = Image.open(screenshot_path)
        cropped = img.crop((
            request.x,
            request.y,
            request.x + request.width,
            request.y + request.height
        ))
        cropped.save(screenshot_path)

        return SuccessResponse(
            success=True,
            message=f"Cropped to {request.width}x{request.height}"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_slug}/{recording_name}/screenshots/{filename}/annotate", response_model=SuccessResponse)
async def annotate_screenshot(
    project_slug: str,
    recording_name: str,
    filename: str,
    request: AnnotateRequest
):
    """
    Add annotations to a screenshot.

    Draws shapes, text, and highlights on the screenshot.
    """
    manager = get_manager()
    screenshot_path = manager.get_screenshot_path(project_slug, recording_name, filename)

    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    try:
        img = Image.open(screenshot_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        for ann in request.annotations:
            color = ann.stroke
            width = ann.stroke_width

            if ann.type == "rect":
                x = ann.left or ann.x or 0
                y = ann.top or ann.y or 0
                w = ann.width or 100
                h = ann.height or 100
                draw.rectangle(
                    [x, y, x + w, y + h],
                    outline=color,
                    width=width
                )

            elif ann.type == "circle":
                x = ann.left or ann.x or 0
                y = ann.top or ann.y or 0
                r = ann.radius or 50
                draw.ellipse(
                    [x - r, y - r, x + r, y + r],
                    outline=color,
                    width=width
                )

            elif ann.type == "highlight":
                x = ann.left or ann.x or 0
                y = ann.top or ann.y or 0
                w = ann.width or 100
                h = ann.height or 30
                # Semi-transparent yellow highlight
                draw.rectangle(
                    [x, y, x + w, y + h],
                    fill=(255, 255, 0, 100)
                )

            elif ann.type == "text":
                x = ann.left or ann.x or 0
                y = ann.top or ann.y or 0
                text = ann.text or ""
                draw.text((x, y), text, fill=color)

            elif ann.type == "arrow" and ann.points:
                # Draw arrow line
                if len(ann.points) >= 4:
                    draw.line(ann.points, fill=color, width=width)

        # Merge overlay
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")
        img.save(screenshot_path)

        return SuccessResponse(
            success=True,
            message=f"Added {len(request.annotations)} annotations"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== AI API ====================

@router.post("/{project_slug}/{recording_name}/ai/regenerate", response_model=AIRegenerateResponse)
async def ai_regenerate_descriptions(
    project_slug: str,
    recording_name: str,
    request: AIRegenerateRequest
):
    """
    Regenerate step descriptions using AI.

    Uses vision AI to analyze screenshots and generate natural descriptions.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    screenshots_dir = manager.get_screenshots_dir(project_slug, recording_name)

    try:
        from ...agent.description_generator import enhance_action_log_with_ai

        # Filter steps if specific IDs provided
        if request.step_ids:
            # Create temp log with only specified steps
            from ...capture.action_log import ActionLog as AL
            temp_log = AL(
                title=action_log.title,
                steps=[s for s in action_log.steps if s.id in request.step_ids]
            )
        else:
            temp_log = action_log

        # Enhance for each language
        for lang in request.languages:
            temp_log = await enhance_action_log_with_ai(
                temp_log,
                screenshots_dir,
                language=lang,
                provider=request.provider,
                api_key=request.api_key
            )

        # Merge back if filtered
        if request.step_ids:
            enhanced_map = {s.id: s for s in temp_log.steps}
            for i, step in enumerate(action_log.steps):
                if step.id in enhanced_map:
                    action_log.steps[i] = enhanced_map[step.id]
        else:
            action_log = temp_log

        manager.save_recording(project_slug, recording_name, action_log)

        enhanced_count = len(request.step_ids) if request.step_ids else len(action_log.steps)
        return AIRegenerateResponse(
            success=True,
            enhanced_steps=enhanced_count,
            message=f"Enhanced {enhanced_count} steps with AI"
        )

    except Exception as e:
        return AIRegenerateResponse(
            success=False,
            enhanced_steps=0,
            message=str(e)
        )


# ==================== Video API ====================

@router.get("/{project_slug}/{recording_name}/video")
async def get_video(project_slug: str, recording_name: str):
    """
    Get video file for streaming.

    Returns the recorded video for playback.
    """
    manager = get_manager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)
    videos_dir = recording_dir / "videos"

    if not videos_dir.exists():
        raise HTTPException(status_code=404, detail="No video directory found")

    # Find video file (webm format)
    video_files = list(videos_dir.glob("*.webm"))
    if not video_files:
        raise HTTPException(status_code=404, detail="No video file found")

    video_path = video_files[0]
    return FileResponse(
        video_path,
        media_type="video/webm",
        headers={"Accept-Ranges": "bytes"}
    )


@router.get("/{project_slug}/{recording_name}/video/info")
async def get_video_info(project_slug: str, recording_name: str):
    """
    Get video information.

    Returns video file details and chapter markers if available.
    """
    manager = get_manager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)
    videos_dir = recording_dir / "videos"

    if not videos_dir.exists():
        return {"has_video": False}

    video_files = list(videos_dir.glob("*.webm"))
    if not video_files:
        return {"has_video": False}

    video_path = video_files[0]

    # Check for chapters file
    chapters = []
    chapters_file = recording_dir / "chapters.json"
    if chapters_file.exists():
        import json
        with open(chapters_file, "r", encoding="utf-8") as f:
            chapters = json.load(f)

    return {
        "has_video": True,
        "filename": video_path.name,
        "size": video_path.stat().st_size,
        "chapters": chapters,
    }


@router.post("/{project_slug}/{recording_name}/video/capture", response_model=SuccessResponse)
async def capture_video_frame(
    project_slug: str,
    recording_name: str,
    file: UploadFile = File(...),
    step_id: Optional[int] = None,
):
    """
    Capture a frame from video and save as screenshot.

    The frame image is uploaded from the frontend (captured via canvas).
    If step_id is provided, the screenshot will be associated with that step.
    """
    manager = get_manager()
    screenshots_dir = manager.get_screenshots_dir(project_slug, recording_name)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    import time
    timestamp = int(time.time() * 1000)
    filename = f"video_capture_{timestamp}.png"
    screenshot_path = screenshots_dir / filename

    # Save uploaded frame
    content = await file.read()
    screenshot_path.write_bytes(content)

    # If step_id provided, update the step's screenshot
    if step_id is not None:
        action_log = manager.load_recording(project_slug, recording_name)
        if action_log:
            for step in action_log.steps:
                if step.id == step_id:
                    step.screenshot = filename
                    break
            manager.save_recording(project_slug, recording_name, action_log)

    return SuccessResponse(
        success=True,
        message=f"Frame captured as {filename}"
    )


@router.post("/{project_slug}/{recording_name}/steps/{step_id}/screenshot", response_model=SuccessResponse)
async def set_step_screenshot(
    project_slug: str,
    recording_name: str,
    step_id: int,
    file: UploadFile = File(...)
):
    """
    Set or replace a step's screenshot.

    Uploads an image and sets it as the screenshot for the specified step.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Find step
    step = None
    for s in action_log.steps:
        if s.id == step_id:
            step = s
            break

    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")

    # Save screenshot
    screenshots_dir = manager.get_screenshots_dir(project_slug, recording_name)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp to avoid browser caching
    import time
    timestamp = int(time.time() * 1000)
    filename = f"step_{step_id:03d}_{timestamp}.png"
    screenshot_path = screenshots_dir / filename

    content = await file.read()
    screenshot_path.write_bytes(content)

    # Update step with new filename
    step.screenshot = filename
    manager.save_recording(project_slug, recording_name, action_log)

    return SuccessResponse(
        success=True,
        message=f"Screenshot set for step {step_id}"
    )


# ==================== Recording API ====================

from ..schemas import StartRecordingRequest, StartRecordingResponse
import subprocess
import sys


@router.post("/start", response_model=StartRecordingResponse)
async def start_recording(request: StartRecordingRequest):
    """
    Start a new browser recording session.

    Opens a browser window for the user to record actions.
    The recording will be saved to the specified project.
    """
    from ...project.utils import generate_recording_folder_name

    manager = get_manager()

    # Check project exists
    project = manager.get_project(request.project_slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{request.project_slug}' not found")

    # Generate recording folder name
    folder_name = generate_recording_folder_name(request.title or "recording")

    # Get output path
    recordings_dir = manager.get_recordings_dir(request.project_slug)
    output_path = recordings_dir / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Launch recording in subprocess (non-blocking)
        # Use web-manual CLI command directly
        cmd = [
            "web-manual",
            "record", request.url,
            "-o", str(output_path),
            "-t", request.title or folder_name,
        ]

        if not request.show_cursor:
            cmd.append("--no-cursor")

        # Start subprocess - open in new console window on Windows
        if sys.platform == "win32":
            # Use shell=True and start command to open new window
            shell_cmd = f'start "Recording" cmd /c "{" ".join(cmd)}"'
            subprocess.Popen(shell_cmd, shell=True)
        else:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return StartRecordingResponse(
            success=True,
            message="Recording started. A browser window will open. Press F2 or click Stop button to end recording.",
            recording_name=folder_name,
        )

    except Exception as e:
        return StartRecordingResponse(
            success=False,
            message=f"Failed to start recording: {str(e)}",
        )
