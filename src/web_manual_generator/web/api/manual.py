"""
Manual generation API router.

Provides endpoints for generating and previewing manuals.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from ..schemas import (
    ManualGenerateRequest,
    ManualGenerateResponse,
    ManualPreviewResponse,
)
from ...project import ProjectManager

router = APIRouter()


def get_manager() -> ProjectManager:
    """Get project manager instance."""
    return ProjectManager()


@router.get("/preview/{project_slug}/{recording_name}", response_model=ManualPreviewResponse)
async def preview_manual(
    project_slug: str,
    recording_name: str,
    language: str = "zh"
):
    """
    Preview a manual.

    Generates and returns the HTML content for preview without saving.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    screenshots_dir = manager.get_screenshots_dir(project_slug, recording_name)

    try:
        from ...manual.generator import ManualGenerator
        import tempfile

        # Generate to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            generator = ManualGenerator(
                output_dir=temp_path,
                language=language,
                embed_images=True,  # Embed images for preview
            )

            html_path = generator.generate_html(
                action_log,
                screenshots_dir=screenshots_dir,
            )

            html_content = html_path.read_text(encoding="utf-8")

            return ManualPreviewResponse(
                html_content=html_content,
                title=action_log.title,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/{project_slug}/{recording_name}/html")
async def preview_manual_html(
    project_slug: str,
    recording_name: str,
    language: str = "zh"
):
    """
    Get manual preview as raw HTML.

    Returns the HTML directly for iframe embedding.
    """
    manager = get_manager()
    action_log = manager.load_recording(project_slug, recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    screenshots_dir = manager.get_screenshots_dir(project_slug, recording_name)

    try:
        from ...manual.generator import ManualGenerator
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            generator = ManualGenerator(
                output_dir=temp_path,
                language=language,
                embed_images=True,
            )

            html_path = generator.generate_html(
                action_log,
                screenshots_dir=screenshots_dir,
            )

            html_content = html_path.read_text(encoding="utf-8")
            return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=ManualGenerateResponse)
async def generate_manual(request: ManualGenerateRequest):
    """
    Generate a manual.

    Creates HTML and/or PDF manual files from a recording.
    """
    manager = get_manager()
    action_log = manager.load_recording(request.project_slug, request.recording_name)

    if not action_log:
        raise HTTPException(status_code=404, detail="Recording not found")

    recording_dir = manager.get_recording_dir(request.project_slug, request.recording_name)
    screenshots_dir = manager.get_screenshots_dir(request.project_slug, request.recording_name)
    output_dir = recording_dir / "manual"
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = None
    pdf_path = None

    try:
        # Apply AI enhancement if requested
        if request.use_ai:
            from ...agent.description_generator import enhance_action_log_with_ai

            for lang in request.languages:
                action_log = await enhance_action_log_with_ai(
                    action_log,
                    screenshots_dir,
                    language=lang,
                    provider=request.provider,
                )

            # Save enhanced log
            enhanced_path = recording_dir / "action_log_enhanced.json"
            action_log.save(enhanced_path)

        from ...manual.generator import ManualGenerator

        # Generate for primary language
        primary_lang = request.languages[0] if request.languages else "zh"

        if request.format in ("html", "both"):
            # For HTML download, embed images so the file is self-contained
            html_generator = ManualGenerator(
                output_dir=output_dir,
                language=primary_lang,
                embed_images=True,  # Embed images as base64 for standalone HTML
            )
            html_path = html_generator.generate_html(
                action_log,
                screenshots_dir=screenshots_dir,
            )

        if request.format in ("pdf", "both"):
            # PDF generator (PDF generation always embeds images internally)
            pdf_generator = ManualGenerator(
                output_dir=output_dir,
                language=primary_lang,
            )
            try:
                pdf_path = pdf_generator.generate_pdf(
                    action_log,
                    screenshots_dir=screenshots_dir,
                )
            except (ImportError, OSError) as e:
                if request.format == "pdf":
                    raise HTTPException(
                        status_code=500,
                        detail=f"PDF generation failed: {e}"
                    )
                # For "both", just skip PDF

        # Update recording status
        manager.update_recording_status(
            request.project_slug,
            request.recording_name,
            has_manual=True,
        )

        return ManualGenerateResponse(
            success=True,
            html_path=str(html_path) if html_path else None,
            pdf_path=str(pdf_path) if pdf_path else None,
            message="Manual generated successfully",
        )

    except Exception as e:
        return ManualGenerateResponse(
            success=False,
            message=str(e),
        )


@router.get("/download/{project_slug}/{recording_name}/{format}")
async def download_manual(
    project_slug: str,
    recording_name: str,
    format: str
):
    """
    Download a generated manual.

    Returns the manual file for download.
    """
    manager = get_manager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)
    manual_dir = recording_dir / "manual"

    if format == "html":
        file_path = manual_dir / "manual.html"
    elif format == "pdf":
        file_path = manual_dir / "manual.pdf"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Manual ({format}) not found")

    return FileResponse(
        file_path,
        filename=f"{recording_name}_manual.{format}",
        media_type="text/html" if format == "html" else "application/pdf"
    )
