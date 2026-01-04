"""
Command-line interface for Web Manual Generator.

Provides commands for recording, executing, and generating manuals.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from .i18n import set_language, get_text, SUPPORTED_LANGUAGES

console = Console()


@click.group()
@click.option(
    "--lang", "-l",
    type=click.Choice(SUPPORTED_LANGUAGES),
    default="zh",
    help="Interface language / \u754c\u9762\u8bed\u8a00 / \u30a4\u30f3\u30bf\u30fc\u30d5\u30a7\u30fc\u30b9\u8a00\u8a9e",
)
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx, lang: str):
    """
    Web Manual Generator - Browser automation with automatic documentation.

    \u7f51\u9875\u64cd\u4f5c\u624b\u518c\u751f\u6210\u5668 - \u6d4f\u89c8\u5668\u81ea\u52a8\u5316\u4e0e\u6587\u6863\u751f\u6210\u5de5\u5177

    Web\u64cd\u4f5c\u30de\u30cb\u30e5\u30a2\u30eb\u30b8\u30a7\u30cd\u30ec\u30fc\u30bf\u30fc - \u30d6\u30e9\u30a6\u30b6\u81ea\u52d5\u5316\u3068\u30c9\u30ad\u30e5\u30e1\u30f3\u30c8\u751f\u6210\u30c4\u30fc\u30eb
    """
    ctx.ensure_object(dict)
    ctx.obj["lang"] = lang
    set_language(lang)


@main.command()
@click.argument("url")
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="./recording",
    help="Output directory / 输出目录",
)
@click.option(
    "--title", "-t",
    default="",
    help="Recording title / 录制标题",
)
@click.option(
    "--headless/--no-headless",
    default=False,
    help="Run in headless mode / 无头模式",
)
@click.option(
    "--show-cursor/--no-cursor",
    default=True,
    help="Show cursor in screenshots / 截图中显示鼠标",
)
@click.pass_context
def record(ctx, url: str, output: str, title: str, headless: bool, show_cursor: bool):
    """
    Record browser actions.

    Start a browser session and record all user interactions.
    Press F2 or click the Stop button in the browser to end recording.

    Example:
        web-manual record https://example.com -o ./my-recording
    """
    lang = ctx.obj.get("lang", "zh")

    console.print(Panel(
        f"[bold]{get_text('record_help', lang)}[/bold]\n\n"
        f"URL: {url}\n"
        f"Output: {output}\n"
        f"Show cursor: {show_cursor}",
        title="Web Manual Generator",
        border_style="blue",
    ))

    asyncio.run(_record_async(url, output, title, headless, lang, show_cursor))


async def _record_async(url: str, output: str, title: str, headless: bool, lang: str, show_cursor: bool):
    """Async recording function."""
    from .core.session import BrowserSession
    from .core.recorder import ActionRecorder

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    async with BrowserSession(
        output_dir=output_path,
        headless=headless,
        record_video=True,
    ) as session:
        page = await session.new_page()

        recorder = ActionRecorder(
            output_dir=output_path,
            language=lang,
            show_cursor=show_cursor,
        )

        await recorder.start_recording(page, title=title, start_url=url)

        # Wait for stop signal (F2 key, Stop button, or Ctrl+C)
        try:
            await recorder.wait_for_stop()
        except KeyboardInterrupt:
            console.print("\n[yellow]Ctrl+C detected, stopping...[/yellow]")

        action_log = await recorder.stop_recording()

        # Save generated script
        script_path = recorder.save_script()
        console.print(f"\n[green]Script saved to: {script_path}[/green]")

        # Get video path
        video_path = await session.get_video_path()
        if video_path:
            console.print(f"[green]Video saved to: {video_path}[/green]")

        console.print(f"[green]Action log saved to: {output_path / 'action_log.json'}[/green]")


@main.command()
@click.argument("script", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="./execution",
    help="Output directory / \u8f93\u51fa\u76ee\u5f55",
)
@click.option(
    "--semi-auto/--auto",
    default=False,
    help="Semi-automatic mode (confirm each step) / \u534a\u81ea\u52a8\u6a21\u5f0f",
)
@click.option(
    "--headless/--no-headless",
    default=False,
    help="Run in headless mode / \u65e0\u5934\u6a21\u5f0f",
)
@click.pass_context
def run(ctx, script: str, output: str, semi_auto: bool, headless: bool):
    """
    Execute a recorded script.

    Run a previously recorded action script with optional semi-automatic mode.

    Example:
        web-manual run ./recording/action_log.json --semi-auto
    """
    lang = ctx.obj.get("lang", "zh")

    console.print(Panel(
        f"[bold]{get_text('run_help', lang)}[/bold]\n\n"
        f"Script: {script}\n"
        f"Mode: {'Semi-automatic' if semi_auto else 'Automatic'}",
        title="Web Manual Generator",
        border_style="blue",
    ))

    asyncio.run(_run_async(script, output, semi_auto, headless, lang))


async def _run_async(script: str, output: str, semi_auto: bool, headless: bool, lang: str):
    """Async execution function."""
    from .core.session import BrowserSession
    from .core.executor import ScriptExecutor

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    async with BrowserSession(
        output_dir=output_path,
        headless=headless,
        record_video=True,
    ) as session:
        page = await session.new_page()

        executor = ScriptExecutor(
            output_dir=output_path,
            language=lang,
            semi_automatic=semi_auto,
        )

        results = await executor.execute(page, script)

        # Summary
        success_count = sum(1 for r in results if r["success"])
        console.print(Panel(
            f"Completed: {success_count}/{len(results)} steps successful",
            title="Execution Summary",
            border_style="green" if success_count == len(results) else "yellow",
        ))


@main.command()
@click.argument("recording_dir", type=click.Path(exists=True))
@click.option(
    "--format", "-f",
    type=click.Choice(["html", "pdf", "both"]),
    default="html",
    help="Output format / 输出格式",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output directory (default: recording_dir/manual)",
)
@click.option(
    "--ai/--no-ai",
    default=False,
    help="Use AI to generate intelligent descriptions / 使用AI生成智能描述",
)
@click.option(
    "--provider", "-p",
    type=click.Choice(["gemini", "claude", "openai"]),
    default="gemini",
    help="AI provider (gemini=lowest cost) / AI服务商",
)
@click.option(
    "--api-key",
    default=None,
    help="API key (or set GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY)",
)
@click.option(
    "--model",
    default=None,
    help="Model name override (default: auto based on provider)",
)
@click.pass_context
def generate(ctx, recording_dir: str, format: str, output: Optional[str], ai: bool, provider: str, api_key: Optional[str], model: Optional[str]):
    """
    Generate manual from recording.

    Create HTML and/or PDF documentation from a recording.
    Use --ai flag to generate intelligent descriptions using vision AI.

    Examples:
        web-manual generate ./recording --format html --ai
        web-manual generate ./recording --ai --provider gemini
        web-manual generate ./recording --ai --provider claude --api-key sk-xxx
    """
    lang = ctx.obj.get("lang", "zh")

    console.print(Panel(
        f"[bold]{get_text('generate_help', lang)}[/bold]\n\n"
        f"Source: {recording_dir}\n"
        f"Format: {format}\n"
        f"AI Enhancement: {'Enabled (' + provider + ')' if ai else 'Disabled'}",
        title="Web Manual Generator",
        border_style="blue",
    ))

    from .manual.generator import ManualGenerator
    from .capture.action_log import ActionLog

    recording_path = Path(recording_dir)
    action_log_path = recording_path / "action_log.json"

    if not action_log_path.exists():
        console.print("[red]Error: action_log.json not found in recording directory[/red]")
        return

    # Load action log
    action_log = ActionLog.load(action_log_path)
    screenshots_dir = recording_path / "screenshots"

    # Apply AI enhancement if requested
    if ai:
        import asyncio
        from .agent.description_generator import enhance_action_log_with_ai

        console.print("\n[blue]Generating AI-enhanced descriptions...[/blue]")
        try:
            action_log = asyncio.run(enhance_action_log_with_ai(
                action_log=action_log,
                screenshots_dir=screenshots_dir,
                language=lang,
                api_key=api_key,
                provider=provider,
                model=model,
            ))
            # Save enhanced action log
            enhanced_log_path = recording_path / "action_log_enhanced.json"
            action_log.save(enhanced_log_path)
            console.print(f"[green]Enhanced action log saved: {enhanced_log_path}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: AI enhancement failed - {e}[/yellow]")
            console.print("[yellow]Continuing with original descriptions...[/yellow]")

    output_path = Path(output) if output else recording_path / "manual"
    output_path.mkdir(parents=True, exist_ok=True)

    generator = ManualGenerator(
        output_dir=output_path,
        language=lang,
    )

    if format in ("html", "both"):
        html_path = generator.generate_html(
            action_log,
            screenshots_dir=screenshots_dir,
        )
        console.print(f"[green]HTML manual generated: {html_path}[/green]")

    if format in ("pdf", "both"):
        try:
            pdf_path = generator.generate_pdf(
                action_log,
                screenshots_dir=screenshots_dir,
            )
            console.print(f"[green]PDF manual generated: {pdf_path}[/green]")
        except (ImportError, OSError) as e:
            console.print(f"[yellow]Warning: PDF generation failed - {e}[/yellow]")
            console.print("[yellow]For PDF support on Windows, install GTK: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows[/yellow]")


@main.command()
@click.argument("goal")
@click.option(
    "--url", "-u",
    required=True,
    help="Target URL / \u76ee\u6807\u7f51\u5740",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="./ai-execution",
    help="Output directory / \u8f93\u51fa\u76ee\u5f55",
)
@click.option(
    "--template", "-t",
    type=click.Choice(["login", "search", "form_submit", "custom"]),
    default="custom",
    help="Task template / \u4efb\u52a1\u6a21\u677f",
)
@click.pass_context
def ai(ctx, goal: str, url: str, output: str, template: str):
    """
    AI-driven automated execution.

    Describe a task and let the AI plan and execute it.

    Example:
        web-manual ai "Login to the system" --url https://example.com/login --template login
    """
    lang = ctx.obj.get("lang", "zh")

    console.print(Panel(
        f"[bold]AI Execution[/bold]\n\n"
        f"Goal: {goal}\n"
        f"URL: {url}\n"
        f"Template: {template}",
        title="Web Manual Generator",
        border_style="blue",
    ))

    asyncio.run(_ai_async(goal, url, output, template, lang))


async def _ai_async(goal: str, url: str, output: str, template: str, lang: str):
    """Async AI execution function."""
    from .core.session import BrowserSession
    from .agent.planner import TaskPlanner, TaskStep

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    planner = TaskPlanner(language=lang)

    # Create plan
    if template != "custom":
        plan = planner.create_plan(goal, template=template)
    else:
        plan = planner.create_plan(goal)

    # Add navigation step
    plan.steps.insert(0, TaskStep(
        action="navigate",
        target=url,
        description=f"Navigate to {url}",
    ))

    # Display plan
    planner.display_plan(plan)

    # Confirm execution
    confirm = input("\nProceed with execution? [Y/n] ")
    if confirm.lower() == "n":
        console.print("[yellow]Execution cancelled[/yellow]")
        return

    # Execute
    async with BrowserSession(
        output_dir=output_path,
        headless=False,
        record_video=True,
    ) as session:
        page = await session.new_page()

        action_log = await planner.execute_plan(page, plan)

        # Save action log
        log_path = output_path / "action_log.json"
        action_log.save(log_path)
        console.print(f"\n[green]Action log saved to: {log_path}[/green]")


@main.command()
def install_browsers():
    """
    Install Playwright browsers.

    Downloads and installs the required browser binaries.
    """
    import subprocess
    console.print("[blue]Installing Playwright browsers...[/blue]")
    subprocess.run(["python", "-m", "playwright", "install"], check=True)
    console.print("[green]Browsers installed successfully![/green]")


# ==================== Project Management Commands ====================

@main.group()
def project():
    """
    Project management commands.

    项目管理命令 / プロジェクト管理コマンド
    """
    pass


@project.command("list")
@click.option(
    "--status", "-s",
    type=click.Choice(["active", "archived", "all"]),
    default="active",
    help="Filter by status / 按状态筛选",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format / 输出格式",
)
def list_projects(status: str, format: str):
    """
    List all projects.

    列出所有项目 / すべてのプロジェクトを一覧表示

    Example:
        web-manual project list
        web-manual project list --status all
    """
    from rich.table import Table
    import json
    from .project import ProjectManager

    manager = ProjectManager()
    projects = manager.list_projects(
        status=None if status == "all" else status
    )

    if format == "json":
        data = [p.model_dump(mode="json") for p in projects]
        console.print_json(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        console.print("Create one with: web-manual project create \"Project Name\"")
        return

    table = Table(title="Projects / 项目列表")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Recordings", justify="right")
    table.add_column("Status")
    table.add_column("Updated")

    for p in projects:
        table.add_row(
            p.slug,
            p.name,
            str(p.recording_count),
            "🟢" if p.status == "active" else "📦",
            p.updated_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@project.command("create")
@click.argument("name")
@click.option(
    "--slug", "-s",
    default=None,
    help="URL-safe project identifier (auto-generated if not provided)",
)
@click.option(
    "--base-url", "-u",
    default=None,
    help="Base URL for recordings / 录制的基础URL",
)
@click.option(
    "--tags", "-t",
    multiple=True,
    help="Project tags / 项目标签",
)
@click.option(
    "--description", "-d",
    default="",
    help="Project description / 项目描述",
)
def create_project(name: str, slug: Optional[str], base_url: Optional[str], tags: tuple, description: str):
    """
    Create a new project.

    创建新项目 / 新しいプロジェクトを作成

    Example:
        web-manual project create "用户管理系统" -u https://admin.example.com
        web-manual project create "Login Flow" -t admin -t auth
    """
    from .project import ProjectManager

    manager = ProjectManager()

    try:
        project = manager.create_project(
            name=name,
            slug=slug,
            description=description,
            base_url=base_url,
            tags=list(tags),
        )
        console.print(Panel(
            f"[green]Project created successfully![/green]\n\n"
            f"Name: {project.name}\n"
            f"Slug: {project.slug}\n"
            f"Path: {manager.get_project_dir(project.slug)}",
            title="✅ Project Created",
            border_style="green",
        ))
        console.print(f"\nStart recording with: web-manual record <url> -p {project.slug}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@project.command("delete")
@click.argument("project_slug")
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Force delete without confirmation / 强制删除",
)
def delete_project(project_slug: str, force: bool):
    """
    Delete a project.

    删除项目 / プロジェクトを削除

    Example:
        web-manual project delete my-project
        web-manual project delete my-project --force
    """
    from .project import ProjectManager

    manager = ProjectManager()
    project = manager.get_project(project_slug)

    if not project:
        console.print(f"[red]Error: Project '{project_slug}' not found[/red]")
        return

    if not force:
        console.print(f"[yellow]Warning: This will delete project '{project.name}'[/yellow]")
        if project.recordings:
            console.print(f"[yellow]Including {len(project.recordings)} recording(s)[/yellow]")
        confirm = input("Are you sure? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        manager.delete_project(project_slug, force=True)
        console.print(f"[green]Project '{project_slug}' deleted successfully[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@project.command("info")
@click.argument("project_slug")
def project_info(project_slug: str):
    """
    Show project details.

    显示项目详情 / プロジェクトの詳細を表示

    Example:
        web-manual project info my-project
    """
    from rich.table import Table
    from .project import ProjectManager

    manager = ProjectManager()
    project = manager.get_project(project_slug)

    if not project:
        console.print(f"[red]Error: Project '{project_slug}' not found[/red]")
        return

    console.print(Panel(
        f"[bold]{project.name}[/bold]\n\n"
        f"Slug: {project.slug}\n"
        f"Description: {project.description or '(none)'}\n"
        f"Base URL: {project.base_url or '(none)'}\n"
        f"Tags: {', '.join(project.tags) if project.tags else '(none)'}\n"
        f"Status: {project.status}\n"
        f"Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"Updated: {project.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"Recordings: {len(project.recordings)}",
        title=f"Project: {project_slug}",
        border_style="blue",
    ))

    if project.recordings:
        table = Table(title="Recordings / 录制列表")
        table.add_column("Folder", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Steps", justify="right")
        table.add_column("Manual")
        table.add_column("Created")

        for r in project.recordings:
            table.add_row(
                r.folder_name,
                r.title,
                str(r.step_count),
                "✅" if r.has_manual else "❌",
                r.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)


@project.command("archive")
@click.argument("project_slug")
def archive_project(project_slug: str):
    """
    Archive a project.

    归档项目 / プロジェクトをアーカイブ

    Example:
        web-manual project archive my-project
    """
    from .project import ProjectManager

    manager = ProjectManager()
    project = manager.archive_project(project_slug)

    if not project:
        console.print(f"[red]Error: Project '{project_slug}' not found[/red]")
        return

    console.print(f"[green]Project '{project_slug}' archived successfully[/green]")


# ==================== Recording Management Commands ====================

@project.group("recording")
def recording():
    """
    Recording management commands.

    录制管理命令 / 録画管理コマンド
    """
    pass


@recording.command("list")
@click.argument("project_slug")
def list_recordings(project_slug: str):
    """
    List recordings in a project.

    列出项目中的录制 / プロジェクト内の録画を一覧表示

    Example:
        web-manual project recording list my-project
    """
    from rich.table import Table
    from .project import ProjectManager

    manager = ProjectManager()
    recordings = manager.list_recordings(project_slug)

    if not recordings:
        console.print(f"[yellow]No recordings found in project '{project_slug}'[/yellow]")
        return

    table = Table(title=f"Recordings in '{project_slug}'")
    table.add_column("Folder", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Steps", justify="right")
    table.add_column("Manual")
    table.add_column("Video")
    table.add_column("Created")

    for r in recordings:
        table.add_row(
            r.folder_name,
            r.title,
            str(r.step_count),
            "✅" if r.has_manual else "❌",
            "✅" if r.has_video else "❌",
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@recording.command("delete")
@click.argument("project_slug")
@click.argument("recording_name")
@click.option("--force", "-f", is_flag=True, help="Force delete without confirmation")
def delete_recording(project_slug: str, recording_name: str, force: bool):
    """
    Delete a recording.

    删除录制 / 録画を削除

    Example:
        web-manual project recording delete my-project 2026-01-03_login-test
    """
    from .project import ProjectManager

    manager = ProjectManager()

    if not force:
        confirm = input(f"Delete recording '{recording_name}'? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Cancelled[/yellow]")
            return

    if manager.delete_recording(project_slug, recording_name):
        console.print(f"[green]Recording '{recording_name}' deleted[/green]")
    else:
        console.print(f"[red]Error: Recording not found[/red]")


@recording.command("move")
@click.argument("project_slug")
@click.argument("recording_name")
@click.option("--to-project", "-t", required=True, help="Target project slug")
def move_recording(project_slug: str, recording_name: str, to_project: str):
    """
    Move recording to another project.

    移动录制到另一个项目 / 録画を別のプロジェクトに移動

    Example:
        web-manual project recording move old-project 2026-01-03_login --to-project new-project
    """
    from .project import ProjectManager

    manager = ProjectManager()

    if manager.move_recording(project_slug, recording_name, to_project):
        console.print(f"[green]Recording moved to '{to_project}'[/green]")
    else:
        console.print("[red]Error: Could not move recording. Check project/recording names.[/red]")


# ==================== Test Commands ====================

@main.group()
def test():
    """
    Automated testing commands.

    自动化测试命令 / 自動テストコマンド
    """
    pass


@test.command("run")
@click.argument("project_slug")
@click.argument("recording_name")
@click.option(
    "--no-screenshot-compare",
    is_flag=True,
    help="Disable screenshot comparison / 禁用截图对比",
)
@click.option(
    "--no-element-check",
    is_flag=True,
    help="Disable element checking / 禁用元素检查",
)
@click.option(
    "--compare-mode", "-m",
    type=click.Choice(["pixel", "ai"]),
    default="pixel",
    help="Screenshot comparison mode / 截图对比模式",
)
@click.option(
    "--threshold", "-t",
    type=float,
    default=0.05,
    help="Pixel difference threshold (0-1) / 像素差异阈值",
)
@click.option(
    "--ai-strictness",
    type=click.Choice(["lenient", "normal", "strict"]),
    default="normal",
    help="AI comparison strictness / AI对比严格程度",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run in headless mode / 无头模式",
)
@click.option(
    "--report/--no-report",
    default=True,
    help="Generate HTML report / 生成HTML报告",
)
def test_run(
    project_slug: str,
    recording_name: str,
    no_screenshot_compare: bool,
    no_element_check: bool,
    compare_mode: str,
    threshold: float,
    ai_strictness: str,
    headless: bool,
    report: bool,
):
    """
    Run automated test for a recording.

    运行录制的自动化测试 / 録画の自動テストを実行

    Example:
        web-manual test run my-project login-test
        web-manual test run my-project login-test --compare-mode ai --ai-strictness strict
    """
    from .project import ProjectManager
    from .testing import TestConfig, CompareMode, AIStrictness, run_test, generate_report

    manager = ProjectManager()
    project = manager.get_project(project_slug)

    if not project:
        console.print(f"[red]Error: Project '{project_slug}' not found[/red]")
        return

    recording = manager.get_recording(project_slug, recording_name)
    if not recording:
        console.print(f"[red]Error: Recording '{recording_name}' not found[/red]")
        return

    recording_dir = manager.get_recording_dir(project_slug, recording_name)

    # Build config
    config = TestConfig(
        screenshot_compare=not no_screenshot_compare,
        screenshot_compare_mode=CompareMode(compare_mode),
        element_check=not no_element_check,
        threshold=threshold,
        ai_strictness=AIStrictness(ai_strictness),
        headless=headless,
        generate_report=report,
    )

    console.print(Panel(
        f"[bold]Running Automated Test[/bold]\n\n"
        f"Project: {project_slug}\n"
        f"Recording: {recording_name}\n"
        f"Screenshot Compare: {not no_screenshot_compare} ({compare_mode})\n"
        f"Element Check: {not no_element_check}\n"
        f"Headless: {headless}",
        title="Web Manual Generator - Test",
        border_style="blue",
    ))

    # Run test
    def progress_callback(progress):
        console.print(
            f"  [{progress.current_step}/{progress.total_steps}] "
            f"{progress.current_step_description[:50]}..."
        )

    result = asyncio.run(run_test(
        project_id=project_slug,
        recording_id=recording_name,
        recording_dir=recording_dir,
        config=config,
        progress_callback=progress_callback,
    ))

    # Generate report
    if report and result.steps:
        from pathlib import Path
        test_run_dir = Path(recording_dir) / "test_runs"
        # Find the latest test run
        latest_run = max(test_run_dir.iterdir(), key=lambda p: p.stat().st_mtime)
        report_path = generate_report(latest_run, result)
        if report_path:
            console.print(f"\n[blue]Report generated: {report_path}[/blue]")

    # Summary
    status_color = "green" if result.success else "red"
    console.print(Panel(
        f"[{status_color}]Status: {result.status.value}[/{status_color}]\n\n"
        f"Total Steps: {result.total_steps}\n"
        f"Passed: {result.passed_steps}\n"
        f"Failed: {result.failed_steps}\n"
        f"Duration: {result.duration_ms}ms",
        title="Test Result",
        border_style=status_color,
    ))


@test.command("list")
@click.argument("project_slug")
@click.argument("recording_name")
def test_list(project_slug: str, recording_name: str):
    """
    List test runs for a recording.

    列出录制的测试运行记录 / 録画のテスト実行履歴を一覧表示

    Example:
        web-manual test list my-project login-test
    """
    from rich.table import Table
    from .project import ProjectManager
    from .testing import get_test_runs

    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)

    if not recording_dir.exists():
        console.print(f"[red]Error: Recording '{recording_name}' not found[/red]")
        return

    runs = get_test_runs(recording_dir)

    if not runs:
        console.print(f"[yellow]No test runs found for '{recording_name}'[/yellow]")
        return

    table = Table(title=f"Test Runs for '{recording_name}'")
    table.add_column("Test ID", style="cyan")
    table.add_column("Status")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Started")

    for run in runs:
        status = run.get("status", "unknown")
        status_icon = "✓" if run.get("success") else "✗"
        status_color = "green" if run.get("success") else "red"

        table.add_row(
            run.get("test_id", "?"),
            f"[{status_color}]{status_icon} {status}[/{status_color}]",
            str(run.get("passed_steps", 0)),
            str(run.get("failed_steps", 0)),
            run.get("started_at", "?")[:19] if run.get("started_at") else "?",
        )

    console.print(table)


@test.command("report")
@click.argument("project_slug")
@click.argument("recording_name")
@click.option(
    "--test-id", "-t",
    default=None,
    help="Specific test ID (default: latest)",
)
@click.option(
    "--open", "-o", "open_browser",
    is_flag=True,
    help="Open report in browser / 在浏览器中打开",
)
def test_report(project_slug: str, recording_name: str, test_id: Optional[str], open_browser: bool):
    """
    View or regenerate test report.

    查看或重新生成测试报告 / テストレポートを表示または再生成

    Example:
        web-manual test report my-project login-test --open
    """
    from pathlib import Path
    from .project import ProjectManager
    from .testing import generate_report

    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)
    test_runs_dir = recording_dir / "test_runs"

    if not test_runs_dir.exists():
        console.print(f"[red]Error: No test runs found[/red]")
        return

    # Find test run directory
    if test_id:
        # Find by test ID
        matching = [d for d in test_runs_dir.iterdir() if test_id in d.name]
        if not matching:
            console.print(f"[red]Error: Test run '{test_id}' not found[/red]")
            return
        test_run_dir = matching[0]
    else:
        # Use latest
        test_run_dir = max(test_runs_dir.iterdir(), key=lambda p: p.stat().st_mtime)

    # Check for existing report
    report_path = test_run_dir / "report.html"
    if not report_path.exists():
        # Generate report
        report_path = generate_report(test_run_dir)
        if not report_path:
            console.print("[red]Error: Could not generate report[/red]")
            return

    console.print(f"[green]Report: {report_path}[/green]")

    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{report_path.absolute()}")


@test.command("export")
@click.argument("project_slug")
@click.argument("recording_name")
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output script path",
)
def test_export(project_slug: str, recording_name: str, output: Optional[str]):
    """
    Export recording as standalone Playwright script.

    导出录制为独立的Playwright脚本 / 録画をPlaywrightスクリプトとしてエクスポート

    Example:
        web-manual test export my-project login-test -o test_login.py
    """
    from .project import ProjectManager
    from .capture.action_log import ActionLog

    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_slug, recording_name)
    action_log_path = recording_dir / "action_log.json"

    if not action_log_path.exists():
        console.print(f"[red]Error: action_log.json not found[/red]")
        return

    action_log = ActionLog.load(action_log_path)
    script = action_log.to_script()

    output_path = Path(output) if output else recording_dir / "test_script.py"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    console.print(f"[green]Script exported: {output_path}[/green]")


# ==================== Web Editor Server ====================

@main.command()
@click.option(
    "--host", "-h",
    default="127.0.0.1",
    help="Server host / 服务器地址",
)
@click.option(
    "--port", "-p",
    default=8080,
    type=int,
    help="Server port / 服务器端口",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development / 开发模式自动重载",
)
def serve(host: str, port: int, reload: bool):
    """
    Start the web editor server.

    启动Web编辑器服务 / Webエディタサーバーを起動

    Example:
        web-manual serve
        web-manual serve --port 3000
    """
    console.print(Panel(
        f"[bold]Starting Web Editor Server[/bold]\n\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"URL: http://{host}:{port}\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="Web Manual Generator",
        border_style="blue",
    ))

    import uvicorn
    uvicorn.run(
        "web_manual_generator.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
