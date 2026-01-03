# Web Manual Generator - Usage Examples

## Example 1: Recording a Complete Workflow

### Scenario
Create a tutorial for logging into a web application and submitting a form.

### Steps

```bash
# 1. Start recording
web-manual record https://myapp.com -o ./form-tutorial -t "Form Submission Guide" -l zh

# 2. In the browser:
#    - Navigate to login page
#    - Enter credentials
#    - Submit form
#    - Wait for success message

# 3. Press Ctrl+C to stop

# 4. Generate documentation
web-manual generate ./form-tutorial --format both
```

### Output
- `action_log.json`: Complete action record
- `script.py`: Replayable Python script
- `manual.html`: Interactive HTML manual
- `manual.pdf`: Printable PDF version
- Video recording of the entire session

---

## Example 2: AI-Driven Login

### Scenario
Automatically log into a system using AI planning.

### Command

```bash
web-manual ai "Login with username admin" \
  --url https://demo.example.com/login \
  --template login \
  -l en
```

### What Happens
1. AI creates a plan with steps
2. Automatically discovers login form elements
3. Prompts for username and password
4. Executes login and captures results

---

## Example 3: Semi-Automatic Execution

### Scenario
Run a recorded script with manual confirmation at each step.

### Command

```bash
web-manual run ./recording/action_log.json --semi-auto -l ja
```

### Interaction
```
[1/5] Navigate to login page
Confirm execution: navigate - Navigate to https://example.com [Y/n/s(kip)]> y
  ✓ Completed

[2/5] Enter username
Confirm execution: fill - Enter username field [Y/n/s(kip)]> y
  Enter value for username field: admin
  ✓ Completed
```

---

## Example 4: Multi-Language Documentation

### Scenario
Generate manuals in multiple languages from the same recording.

### Commands

```bash
# Chinese manual
web-manual generate ./recording --format html -l zh -o ./manual-zh

# Japanese manual
web-manual generate ./recording --format html -l ja -o ./manual-ja

# English manual
web-manual generate ./recording --format pdf -l en -o ./manual-en
```

---

## Example 5: Using Python API

### Scenario
Integrate the tool into a custom Python script.

```python
import asyncio
from web_manual_generator import BrowserSession, ActionRecorder, ManualGenerator

async def create_tutorial():
    async with BrowserSession(output_dir="./my-tutorial") as session:
        page = await session.new_page()

        recorder = ActionRecorder(output_dir="./my-tutorial", language="zh")
        await recorder.start_recording(page, title="My Tutorial", start_url="https://example.com")

        # Perform actions
        await page.click("#login-button")
        await page.fill("#username", "admin")

        # Add custom annotations
        await recorder.annotate_last_step(
            description_zh="输入用户名",
            description_en="Enter username",
            notes="Use your assigned username"
        )

        action_log = await recorder.stop_recording()

        # Generate manual
        generator = ManualGenerator(output_dir="./my-tutorial/manual", language="zh")
        generator.generate_html(action_log, screenshots_dir="./my-tutorial/screenshots")
        generator.generate_pdf(action_log, screenshots_dir="./my-tutorial/screenshots")

asyncio.run(create_tutorial())
```

---

## Example 6: Custom Task Planning

### Scenario
Create and execute a custom task plan.

```python
from web_manual_generator.agent.planner import TaskPlanner, TaskStep

planner = TaskPlanner(language="zh")

# Create custom plan
plan = planner.create_plan(goal="Search and add product to cart")

plan.steps = [
    TaskStep(action="navigate", target="https://shop.example.com"),
    TaskStep(action="fill", target="search box", value="laptop", description="Search for laptop"),
    TaskStep(action="click", target="search button", description="Submit search"),
    TaskStep(action="click", target="first product", description="Select first result"),
    TaskStep(action="click", target="add to cart button", description="Add to cart"),
]

# Display the plan
planner.display_plan(plan)

# Save for later execution
plan.save("./my-plan.json")
```

---

## Common Patterns

### Wait for User Input During Recording

In recording mode, the tool automatically pauses when it detects input fields. You can also manually trigger a pause:

```python
await recorder.wait_for_user_action("Please complete the CAPTCHA, then press Enter")
```

### Handle Dynamic Content

For pages with dynamic content, add wait steps:

```python
# In your script
await page.wait_for_selector(".results-loaded")
await recorder.add_manual_step("Wait for results to load", action="wait")
```

### Capture Specific Elements

Highlight and capture specific elements:

```python
from web_manual_generator.capture.screenshot import ScreenshotManager

screenshot_mgr = ScreenshotManager("./screenshots")
await screenshot_mgr.capture_with_highlight(page, "#important-button", name="highlight_button")
```
