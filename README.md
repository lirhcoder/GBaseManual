# Web Manual Generator

Browser automation tool with automatic documentation generation. Supports recording user actions, AI-driven execution, video recording, and generating operation manuals with screenshots.

浏览器自动化工具，支持录制用户操作、AI自动执行、视频录制，自动生成带截图的操作手册。

ブラウザ自動化ツール。ユーザー操作の記録、AI自動実行、ビデオ録画、スクリーンショット付きマニュアル自動生成をサポート。

## Features

- **Recording Mode**: Record browser interactions with automatic screenshots and video
- **Execution Mode**: Replay scripts automatically or semi-automatically
- **AI-Driven Mode**: Describe tasks in natural language, let AI plan and execute
- **Manual Generation**: Generate HTML/PDF documentation with screenshots
- **Multi-Language**: Support for Chinese (中文), Japanese (日本語), and English

## Installation

```bash
# Clone or download the project
cd web-manual-generator

# Install the package
pip install -e .

# Install Playwright browsers
python -m playwright install chromium
```

## Quick Start

### 1. Record Browser Actions

```bash
# Start recording
web-manual record https://example.com -o ./my-recording

# Perform actions in the browser, then press Ctrl+C to stop
```

### 2. Generate Documentation

```bash
# Generate HTML and PDF manuals
web-manual generate ./my-recording --format both -l zh
```

### 3. Execute Recorded Script

```bash
# Automatic execution
web-manual run ./my-recording/action_log.json

# Semi-automatic (confirm each step)
web-manual run ./my-recording/action_log.json --semi-auto
```

### 4. AI-Driven Automation

```bash
# Let AI plan and execute a task
web-manual ai "Login and search for products" --url https://example.com --template login
```

## Commands

| Command | Description |
|---------|-------------|
| `record` | Record browser actions |
| `run` | Execute a recorded script |
| `generate` | Generate manual from recording |
| `ai` | AI-driven task execution |
| `install-browsers` | Install Playwright browsers |

## Options

### Global Options

- `--lang, -l`: Interface language (zh/ja/en)
- `--version`: Show version

### Record Options

- `--output, -o`: Output directory
- `--title, -t`: Recording title
- `--headless/--no-headless`: Run in headless mode

### Run Options

- `--semi-auto/--auto`: Semi-automatic mode
- `--output, -o`: Output directory
- `--headless/--no-headless`: Run in headless mode

### Generate Options

- `--format, -f`: Output format (html/pdf/both)
- `--output, -o`: Output directory

## Output Structure

```
recording/
├── action_log.json     # Recorded actions
├── script.py           # Generated Playwright script
├── screenshots/        # Step screenshots
├── videos/             # Session video
└── manual/             # Generated documentation
    ├── manual.html
    ├── manual.pdf
    └── screenshots/
```

## Claude Code Skill

This project includes a Claude Code skill. To use it:

1. Copy the `skill/` directory to your Claude Code skills location
2. Use `/web-manual` in Claude Code to access the functionality

## Python API

```python
import asyncio
from web_manual_generator import BrowserSession, ActionRecorder, ManualGenerator

async def main():
    async with BrowserSession(output_dir="./output") as session:
        page = await session.new_page()

        recorder = ActionRecorder(output_dir="./output", language="zh")
        await recorder.start_recording(page, start_url="https://example.com")

        # ... perform actions ...

        action_log = await recorder.stop_recording()

        generator = ManualGenerator(output_dir="./output/manual", language="zh")
        generator.generate_html(action_log)

asyncio.run(main())
```

## Requirements

- Python 3.9+
- Playwright
- Jinja2
- WeasyPrint (for PDF generation)
- Rich (for CLI output)
- Pydantic

## Web Editor Development

To start the Web Editor (Frontend + Backend), simply run the provided batch script:

```bat
start_app.bat
```

Or run them manually:

1. **Start Backend Server:**
   ```bash
   web-manual serve
   # Server runs at http://127.0.0.1:8080
   ```

2. **Start Frontend (in a new terminal):**
   ```bash
   cd src/web_manual_generator/web_editor
   npm run dev
   # UI available at http://localhost:5173
   ```

## License

MIT
