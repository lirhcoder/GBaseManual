"""Playwright 脚本生成器

将录制的操作转换为独立可执行的 Playwright Python 脚本。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Literal
from urllib.parse import urlparse

from ..capture.action_log import ActionLog, ActionStep


class PlaywrightScriptGenerator:
    """生成 Playwright Python 脚本"""

    def __init__(
        self,
        action_log: ActionLog,
        language: str = "zh",
        headless: bool = False,
        step_delay: float = 0.5,
        timeout: int = 30000,
    ):
        """
        初始化脚本生成器

        Args:
            action_log: 操作日志
            language: 注释语言 (zh/en/ja)
            headless: 是否无头模式
            step_delay: 步骤间延迟（秒）
            timeout: 超时时间（毫秒）
        """
        self.action_log = action_log
        self.language = language
        self.headless = headless
        self.step_delay = step_delay
        self.timeout = timeout
        self._prev_action: Optional[str] = None  # Track previous action for redirect detection
        self._password_fields: list[dict] = []  # Track password fields for env var generation
        self._deduplicated_steps: list[ActionStep] = []  # Deduplicated steps

    def generate(self) -> str:
        """生成完整的 Python 脚本"""
        # First pass: deduplicate steps
        self._deduplicate_steps()

        # Second pass: collect password fields (from deduplicated steps)
        self._collect_password_fields()

        lines = []

        # 文件头注释
        lines.extend(self._generate_header())

        # 导入语句
        lines.extend(self._generate_imports())

        # 密码获取函数（如果有密码字段）
        if self._password_fields:
            lines.extend(self._generate_password_helper())

        # 主函数
        lines.extend(self._generate_main_function())

        # 入口点
        lines.extend(self._generate_entry_point())

        return "\n".join(lines)

    def _deduplicate_steps(self) -> None:
        """Remove duplicate consecutive steps from the recording.

        The recorder sometimes captures duplicate events due to:
        - Both mousedown and click events being captured
        - Event bubbling causing multiple captures
        - Rapid sequential events with same action/selector

        This method also filters out orphaned actions - actions that were
        recorded with a page_url that doesn't match the current page after
        a navigation event.
        """
        self._deduplicated_steps = []
        prev_step: Optional[ActionStep] = None
        current_page_url: Optional[str] = None  # Track current page URL after navigations

        for step in self.action_log.steps:
            # Track the current page URL based on navigate actions
            if step.action == "navigate" and step.url:
                current_page_url = step.url

            if prev_step is None:
                self._deduplicated_steps.append(step)
                prev_step = step
                continue

            # Check if this is a duplicate of the previous step
            is_duplicate = self._is_duplicate_step(prev_step, step)

            # Check if this is an orphaned action (action targeting a different page)
            is_orphaned = self._is_orphaned_action(step, current_page_url)

            if not is_duplicate and not is_orphaned:
                self._deduplicated_steps.append(step)
                prev_step = step

    def _is_orphaned_action(self, step: ActionStep, current_page_url: Optional[str]) -> bool:
        """Check if an action is orphaned (targets a page we've navigated away from).

        This happens when the recorder captures a click/fill event after a navigation
        event has already been recorded, due to async event handling.

        We need to be careful not to mark legitimate actions as orphaned:
        - Auth flows have complex redirect chains where actions can be recorded
          out of order
        - Only mark as orphaned if we're confident the action can't succeed
        """
        # Only check for click actions (fill/select might still work on forms)
        if step.action != "click":
            return False

        # If we don't know the current page, can't detect orphaned actions
        if not current_page_url:
            return False

        current_page_host = self._get_url_host(current_page_url)

        # Get the page_url from the step
        step_page_host = self._get_url_host(step.page_url or "")
        if not step_page_host:
            return False

        # Same host - not orphaned
        if step_page_host == current_page_host:
            return False

        # Check if this is an auth flow action
        auth_hosts = ["auth0.com", "okta.com", "login.microsoftonline.com"]
        step_is_auth = any(auth in step_page_host for auth in auth_hosts)
        current_is_auth = any(auth in current_page_host for auth in auth_hosts)

        # If action is on auth page but we've navigated to non-auth page
        if step_is_auth and not current_is_auth:
            # If URL has 'code=' parameter, the OAuth exchange is complete
            # Any auth provider actions after this point are orphaned
            if "code=" in current_page_url:
                return True
            # Check if current page is still part of auth flow (no code yet)
            if "/login" in current_page_url or "/callback" in current_page_url:
                return False  # Keep the action - we're still in auth flow
            # Current page is final destination - action is orphaned
            return True

        return False

    def _is_duplicate_step(self, prev: ActionStep, curr: ActionStep) -> bool:
        """Check if current step is a duplicate of the previous step."""
        # Different action types are not duplicates
        if prev.action != curr.action:
            return False

        # For navigate actions, check if URL host is the same
        if curr.action == "navigate":
            prev_host = self._get_url_host(prev.url or "")
            curr_host = self._get_url_host(curr.url or "")
            return prev_host == curr_host

        # For click/fill/select actions, check selector
        if curr.action in ("click", "fill", "select", "check", "uncheck", "hover"):
            if prev.selector != curr.selector:
                return False
            # For fill actions, also check value
            if curr.action == "fill":
                return prev.value == curr.value
            return True

        # For keyboard actions, check key
        if curr.action == "keyboard":
            return prev.key == curr.key

        return False

    def _collect_password_fields(self) -> None:
        """Scan steps to collect password fields and generate env var names."""
        self._password_fields = []
        seen_selectors = set()

        for step in self._deduplicated_steps:
            if step.action == "fill" and step.selector:
                selector_lower = step.selector.lower()
                # Detect password fields by selector name
                if "password" in selector_lower or "passwd" in selector_lower:
                    if step.selector not in seen_selectors:
                        seen_selectors.add(step.selector)
                        # Generate env var name from page context
                        env_name = self._generate_env_var_name(step)
                        self._password_fields.append({
                            "selector": step.selector,
                            "env_var": env_name,
                            "page_url": step.page_url or "",
                            "step_id": step.id,
                        })

    def _generate_env_var_name(self, step: ActionStep) -> str:
        """Generate a descriptive environment variable name for a password field."""
        if step.page_url:
            parsed = urlparse(step.page_url)
            netloc = parsed.netloc.lower()

            # Try to find a recognizable service name in the domain
            known_services = ["auth0", "okta", "azure", "google", "github", "gitlab", "aws"]
            for service in known_services:
                if service in netloc:
                    return f"{service.upper()}_PASSWORD"

            # Use the main domain name (second-to-last part before TLD)
            parts = netloc.split(".")
            if len(parts) >= 2:
                # Get the main domain (e.g., "gbase" from "admin.gbase.ai")
                domain = parts[-2].upper()
                if domain and len(domain) > 2:
                    domain = "".join(c if c.isalnum() else "_" for c in domain)
                    return f"{domain}_PASSWORD"

        return "LOGIN_PASSWORD"

    def _get_password_field(self, selector: str) -> Optional[dict]:
        """Get password field info by selector."""
        for pf in self._password_fields:
            if pf["selector"] == selector:
                return pf
        return None

    def _generate_password_helper(self) -> list[str]:
        """Generate password retrieval helper function."""
        lines = [
            "def get_password(env_var: str, prompt: str) -> str:",
            '    """Get password from environment variable or prompt user."""',
            "    import os",
            "    import getpass",
            "    password = os.environ.get(env_var)",
            "    if not password:",
            '        print(f"\\n[!] Environment variable {env_var} not set.")',
            "        password = getpass.getpass(prompt)",
            "    return password",
            "",
            "",
        ]
        return lines

    def _generate_header(self) -> list[str]:
        """生成文件头注释"""
        title = self.action_log.get_title(self.language) or "Playwright Test Script"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = [
            '"""',
            f"{title}",
            "",
            f"Generated by Web Manual Generator",
            f"Generated at: {now}",
            "",
            "Usage:",
            "    pip install playwright",
            "    playwright install chromium",
            "    python <script_name>.py",
            "",
            "Options:",
            "    python <script_name>.py --headless    # Run in headless mode",
            "    python <script_name>.py --slow 1000   # Slow down actions by 1000ms",
        ]

        # Add environment variables section if there are password fields
        if self._password_fields:
            header.append("")
            header.append("Required Environment Variables:")
            for pf in self._password_fields:
                header.append(f"    {pf['env_var']:<25} # Password for {pf['selector']}")
            header.append("")
            header.append("Example:")
            if len(self._password_fields) == 1:
                env_var = self._password_fields[0]['env_var']
                header.append(f"    set {env_var}=your_password    # Windows")
                header.append(f"    export {env_var}=your_password # Linux/Mac")
            else:
                header.append("    # Windows:")
                for pf in self._password_fields:
                    header.append(f"    set {pf['env_var']}=your_password")
                header.append("    # Linux/Mac:")
                for pf in self._password_fields:
                    header.append(f"    export {pf['env_var']}=your_password")
            header.append("")
            header.append("Note: If environment variable is not set, you will be prompted to enter the password.")

        header.append('"""')
        header.append("")
        return header

    def _generate_imports(self) -> list[str]:
        """生成导入语句"""
        imports = [
            "import sys",
            "import argparse",
            "from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout",
            "",
            "",
        ]
        return imports

    def _generate_main_function(self) -> list[str]:
        """生成主函数"""
        lines = []

        # 函数签名
        lines.append("def run(headless: bool = False, slow_mo: int = 0):")
        lines.append('    """')
        lines.append(f'    {self.action_log.get_title(self.language) or "Execute recorded actions"}')
        lines.append("")
        lines.append("    Args:")
        lines.append("        headless: Run browser in headless mode")
        lines.append("        slow_mo: Slow down actions by specified milliseconds")
        lines.append('    """')
        lines.append("    with sync_playwright() as p:")
        lines.append(f"        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)")
        lines.append("        context = browser.new_context()")
        lines.append(f"        context.set_default_timeout({self.timeout})")
        lines.append("        page = context.new_page()")
        lines.append("")
        lines.append("        try:")

        # 导航到起始 URL
        if self.action_log.start_url:
            lines.append(f'            # Navigate to start URL')
            lines.append(f'            page.goto("{self._escape_string(self.action_log.start_url)}")')
            lines.append("")
            # Mark that we've done an initial navigation
            self._prev_action = "navigate"
            self._start_url_host = self._get_url_host(self.action_log.start_url)
        else:
            self._start_url_host = None

        # 生成每个步骤（使用去重后的步骤列表）
        self._is_first_step = True
        steps = self._deduplicated_steps
        for i, step in enumerate(steps):
            # Look ahead to check if next step is also a navigate (chain of redirects)
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            self._next_is_navigate = next_step and next_step.action == "navigate"

            # Use sequential step number (1-indexed) instead of original ID
            self._current_step_num = i + 1
            step_lines = self._generate_step(step)
            lines.extend(step_lines)
            self._is_first_step = False

        # 成功完成
        lines.append("")
        lines.append('            print("All steps completed successfully!")')
        lines.append("")

        # 异常处理
        lines.append("        except PlaywrightTimeout as e:")
        lines.append('            print(f"Timeout error: {e}")')
        lines.append("            raise")
        lines.append("        except Exception as e:")
        lines.append('            print(f"Error: {e}")')
        lines.append("            raise")
        lines.append("        finally:")
        lines.append("            browser.close()")
        lines.append("")

        return lines

    def _generate_step(self, step: ActionStep) -> list[str]:
        """生成单个步骤的代码"""
        lines = []
        step_num = self._current_step_num
        description = step.get_description(self.language) or step.description or f"Step {step_num}"

        # Clean up description - remove newlines and extra whitespace
        description = " ".join(description.split())

        # 步骤注释
        lines.append(f"            # Step {step_num}: {description}")

        # 生成动作代码
        action_code = self._generate_action(step)
        if action_code:
            lines.append(f"            {action_code}")

        # 添加步骤间延迟（可选）
        if self.step_delay > 0:
            delay_ms = int(self.step_delay * 1000)
            lines.append(f"            page.wait_for_timeout({delay_ms})")

        lines.append("")

        # Track action for next step's redirect detection
        self._prev_action = step.action

        return lines

    def _generate_action(self, step: ActionStep) -> Optional[str]:
        """生成单个动作的代码"""
        action = step.action

        if action == "navigate":
            url = step.url or ""
            url_host = self._get_url_host(url)

            # Skip first navigate if it's the same as start_url (already navigated)
            if self._is_first_step and self._start_url_host and url_host == self._start_url_host:
                return "pass  # Already navigated to start URL"

            # In a recording, navigates after the first one are almost always auto-redirects
            # triggered by clicks, form submissions, or other actions.
            # If next step is also navigate, this is an intermediate redirect - skip waiting
            if self._next_is_navigate:
                return "pass  # Intermediate redirect, will wait for final URL"
            # This is the final redirect in the chain - wait for page to load
            # Using wait_for_load_state instead of wait_for_url because the navigation
            # may have already happened by the time we get here
            return 'page.wait_for_load_state("load")'

        elif action == "click":
            if step.selector:
                selector = self._escape_string(step.selector)
                return f'page.click("{selector}")'

        elif action == "fill":
            if step.selector:
                selector = self._escape_string(step.selector)
                # Check if this is a password field
                password_field = self._get_password_field(step.selector)
                if password_field:
                    env_var = password_field["env_var"]
                    return f'page.fill("{selector}", get_password("{env_var}", "Enter password for {selector}: "))'
                value = self._escape_string(step.value or "")
                return f'page.fill("{selector}", "{value}")'

        elif action == "select":
            if step.selector:
                selector = self._escape_string(step.selector)
                value = self._escape_string(step.value or "")
                return f'page.select_option("{selector}", "{value}")'

        elif action == "check":
            if step.selector:
                selector = self._escape_string(step.selector)
                return f'page.check("{selector}")'

        elif action == "uncheck":
            if step.selector:
                selector = self._escape_string(step.selector)
                return f'page.uncheck("{selector}")'

        elif action == "hover":
            if step.selector:
                selector = self._escape_string(step.selector)
                return f'page.hover("{selector}")'

        elif action == "keyboard":
            if step.key:
                key = self._escape_string(step.key)
                return f'page.keyboard.press("{key}")'

        elif action == "wait":
            wait_time = step.value or "1000"
            return f"page.wait_for_timeout({wait_time})"

        elif action == "scroll":
            return 'page.evaluate("window.scrollBy(0, 300)")'

        elif action == "screenshot":
            # 截图步骤只是标记，不生成代码
            return "pass  # Screenshot step"

        return None

    def _generate_entry_point(self) -> list[str]:
        """生成脚本入口点"""
        headless_default = "True" if self.headless else "False"

        lines = [
            'if __name__ == "__main__":',
            "    parser = argparse.ArgumentParser(description='Run Playwright test script')",
            f"    parser.add_argument('--headless', action='store_true', default={headless_default},",
            "                        help='Run in headless mode')",
            "    parser.add_argument('--slow', type=int, default=0,",
            "                        help='Slow down actions by specified milliseconds')",
            "    args = parser.parse_args()",
            "",
            "    run(headless=args.headless, slow_mo=args.slow)",
            "",
        ]
        return lines

    def _escape_string(self, s: str) -> str:
        """转义字符串中的特殊字符"""
        if not s:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

    def _get_url_pattern(self, url: str) -> str:
        """Extract URL pattern for wait_for_url (host + path prefix)"""
        if not url:
            return ""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # Use host + path (without query string) for pattern matching
        # This handles dynamic query parameters like auth tokens
        path = parsed.path.rstrip("/") if parsed.path else ""
        return f"{parsed.netloc}{path}"

    def _get_url_host(self, url: str) -> str:
        """Extract host from URL"""
        if not url:
            return ""
        from urllib.parse import urlparse
        return urlparse(url).netloc


def generate_script(
    action_log_path: Path,
    language: str = "zh",
    headless: bool = False,
    step_delay: float = 0.5,
    timeout: int = 30000,
) -> str:
    """
    从 action_log.json 生成 Playwright 脚本

    Args:
        action_log_path: action_log.json 文件路径
        language: 注释语言
        headless: 是否无头模式
        step_delay: 步骤间延迟
        timeout: 超时时间

    Returns:
        生成的 Python 脚本内容
    """
    action_log = ActionLog.load(action_log_path)
    generator = PlaywrightScriptGenerator(
        action_log=action_log,
        language=language,
        headless=headless,
        step_delay=step_delay,
        timeout=timeout,
    )
    return generator.generate()
