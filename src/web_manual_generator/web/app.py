"""
FastAPI application for Web Manual Generator editor.

Provides REST API for managing projects, recordings, and manual generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from .api import projects, recordings, manual, testing


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Web Manual Generator API",
        description="API for managing and editing web operation manuals",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(
        projects.router,
        prefix="/api/v1/projects",
        tags=["projects"]
    )
    app.include_router(
        recordings.router,
        prefix="/api/v1/recordings",
        tags=["recordings"]
    )
    app.include_router(
        manual.router,
        prefix="/api/v1/manual",
        tags=["manual"]
    )
    app.include_router(
        testing.router,
        prefix="/api/v1/test",
        tags=["testing"]
    )

    # Health check endpoint
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "1.0.0"}

    # Serve static files for screenshots
    # This will be configured dynamically based on projects directory
    @app.get("/api/v1/screenshots/{project_slug}/{recording_name}/{filename}")
    async def get_screenshot(project_slug: str, recording_name: str, filename: str):
        """Serve screenshot files."""
        from ..project import ProjectManager

        manager = ProjectManager()
        screenshot_path = manager.get_screenshot_path(project_slug, recording_name, filename)

        if screenshot_path.exists():
            return FileResponse(screenshot_path)
        return {"error": "Screenshot not found"}, 404

    # Root endpoint - serve frontend or redirect to docs
    @app.get("/")
    async def root():
        """Root endpoint."""
        return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Web Manual Generator</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        p { font-size: 1.2rem; opacity: 0.9; }
        .links { margin-top: 2rem; }
        a {
            display: inline-block;
            margin: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: transform 0.2s;
        }
        a:hover { transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="container">
        <h1>Web Manual Generator</h1>
        <p>Browser automation with automatic documentation</p>
        <div class="links">
            <a href="/api/docs">API Documentation</a>
            <a href="/api/v1/projects">Projects API</a>
        </div>
    </div>
</body>
</html>
        """)

    return app


# Create the default app instance
app = create_app()


if __name__ == "__main__":
    import sys
    import uvicorn

    port = 8081
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    uvicorn.run(app, host="0.0.0.0", port=port)
