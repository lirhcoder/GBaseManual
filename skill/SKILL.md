---
name: web-manual
description: |
  Browser automation and manual generation tool. Supports recording user actions,
  AI-driven automated execution, video recording, and automatic documentation generation
  (HTML/PDF with screenshots). Use when: creating operation manuals, automating web tasks,
  recording browser workflows, generating step-by-step guides with screenshots.

  浏览器自动化与手册生成工具。支持录制用户操作、AI自动执行、视频录制、自动生成操作手册（带截图的HTML/PDF）。

  ブラウザ自動化とマニュアル生成ツール。ユーザー操作の記録、AI自動実行、ビデオ録画、スクリーンショット付きマニュアル自動生成をサポート。
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Web Manual Generator

A comprehensive tool for browser automation with automatic documentation generation.

## Quick Start

### 1. Install Dependencies

```bash
cd /path/to/web-manual-generator
pip install -e .
python -m playwright install chromium
```

### 2. Basic Commands

```bash
# Record browser actions
web-manual record https://example.com -o ./my-recording

# Execute a recorded script
web-manual run ./my-recording/action_log.json --semi-auto

# Generate documentation
web-manual generate ./my-recording --format both

# AI-driven execution
web-manual ai "Login and search for products" --url https://example.com --template login
```

## Features

### Recording Mode
Record user interactions in the browser with automatic:
- Screenshot capture at each step
- Video recording of the entire session
- Action logging in JSON format
- Python script generation

### Execution Mode
Replay recorded scripts with:
- Automatic mode: runs all steps without intervention
- Semi-automatic mode: confirms each step with user
- Support for user input during execution

### Manual Generation
Generate professional documentation:
- HTML format with embedded or linked screenshots
- PDF format for printing
- Multi-language support (Chinese, Japanese, English)
- Table of contents and step numbering

### AI-Driven Automation
Describe tasks in natural language:
- Pre-built templates for common tasks (login, search, forms)
- Automatic element discovery
- Interactive mode for unknown elements

## Workflow Examples

### Example 1: Create a Login Tutorial

```bash
# Step 1: Record the login process
web-manual record https://myapp.com/login -o ./login-tutorial -t "Login Tutorial"

# Step 2: Perform login actions in the browser, then press Ctrl+C

# Step 3: Generate the manual
web-manual generate ./login-tutorial --format both -l zh
```

### Example 2: AI-Assisted Task

```bash
# Let AI plan and execute a login task
web-manual ai "登录系统并搜索订单" --url https://myapp.com --template login -l zh
```

### Example 3: Semi-Automatic Script Execution

```bash
# Execute with confirmation at each step
web-manual run ./recording/action_log.json --semi-auto -l ja
```

## Claude Code Integration

When using this skill in Claude Code, you can:

1. **Record a workflow**:
   Ask Claude to start a recording session for a specific URL

2. **Execute with assistance**:
   Run scripts in semi-automatic mode where Claude can help with inputs

3. **Generate documentation**:
   Create manuals in your preferred language and format

4. **AI automation**:
   Describe complex tasks and let the tool plan and execute

## Language Options

- `--lang zh` or `-l zh`: Chinese (中文)
- `--lang ja` or `-l ja`: Japanese (日本語)
- `--lang en` or `-l en`: English

## Output Structure

```
recording/
├── action_log.json     # Recorded actions
├── script.py           # Generated Playwright script
├── screenshots/        # Step screenshots
│   ├── step_001.png
│   └── ...
├── videos/             # Session video
│   └── *.webm
└── manual/             # Generated documentation
    ├── manual.html
    ├── manual.pdf
    └── screenshots/
```

## Tips

1. **For better screenshots**: Use a larger viewport (1280x720 default)
2. **For sensitive data**: Passwords are automatically masked in logs
3. **For complex forms**: Use semi-automatic mode to input values
4. **For documentation**: Add custom descriptions using the annotation feature
