"""
AI Task Planner for automated browser operations.

Uses natural language descriptions to plan and execute browser tasks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..capture.action_log import ActionLog, ActionStep
from ..i18n import get_text

if TYPE_CHECKING:
    from playwright.async_api import Page

console = Console()


@dataclass
class TaskStep:
    """A planned step in a task."""

    action: str
    target: str  # Natural language description of target
    value: Optional[str] = None
    description: str = ""
    selector: Optional[str] = None  # CSS selector (discovered during execution)
    wait_for_input: bool = False  # Whether to wait for user input


@dataclass
class TaskPlan:
    """A complete task plan."""

    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_step(
        self,
        action: str,
        target: str,
        value: Optional[str] = None,
        description: str = "",
        wait_for_input: bool = False,
    ) -> TaskStep:
        """Add a step to the plan."""
        step = TaskStep(
            action=action,
            target=target,
            value=value,
            description=description or f"{action}: {target}",
            wait_for_input=wait_for_input,
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "goal": self.goal,
            "steps": [
                {
                    "action": s.action,
                    "target": s.target,
                    "value": s.value,
                    "description": s.description,
                    "selector": s.selector,
                    "wait_for_input": s.wait_for_input,
                }
                for s in self.steps
            ],
            "prerequisites": self.prerequisites,
            "notes": self.notes,
        }

    def save(self, path: str | Path) -> None:
        """Save plan to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "TaskPlan":
        """Load plan from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        plan = cls(goal=data["goal"])
        plan.prerequisites = data.get("prerequisites", [])
        plan.notes = data.get("notes", [])
        for step_data in data.get("steps", []):
            step = TaskStep(
                action=step_data["action"],
                target=step_data["target"],
                value=step_data.get("value"),
                description=step_data.get("description", ""),
                selector=step_data.get("selector"),
                wait_for_input=step_data.get("wait_for_input", False),
            )
            plan.steps.append(step)
        return plan


class TaskPlanner:
    """
    Plans and executes browser tasks based on natural language descriptions.

    This class provides templates and utilities for common web automation tasks.
    In a full implementation, this could integrate with an LLM for intelligent planning.
    """

    # Common action templates
    TEMPLATES = {
        "login": [
            TaskStep(action="fill", target="username field", description="Enter username", wait_for_input=True),
            TaskStep(action="fill", target="password field", description="Enter password", wait_for_input=True),
            TaskStep(action="click", target="login button", description="Click login"),
        ],
        "search": [
            TaskStep(action="fill", target="search box", description="Enter search term", wait_for_input=True),
            TaskStep(action="click", target="search button", description="Submit search"),
        ],
        "form_submit": [
            TaskStep(action="fill", target="form fields", description="Fill form", wait_for_input=True),
            TaskStep(action="click", target="submit button", description="Submit form"),
        ],
    }

    def __init__(self, language: str = "zh"):
        self.language = language
        self._current_plan: Optional[TaskPlan] = None

    def create_plan(
        self,
        goal: str,
        template: Optional[str] = None,
    ) -> TaskPlan:
        """
        Create a task plan.

        Args:
            goal: Natural language description of the goal
            template: Optional template name (login, search, form_submit)

        Returns:
            TaskPlan object
        """
        plan = TaskPlan(goal=goal)

        if template and template in self.TEMPLATES:
            for step in self.TEMPLATES[template]:
                plan.steps.append(TaskStep(
                    action=step.action,
                    target=step.target,
                    value=step.value,
                    description=step.description,
                    wait_for_input=step.wait_for_input,
                ))

        self._current_plan = plan
        return plan

    def display_plan(self, plan: Optional[TaskPlan] = None) -> None:
        """Display the plan in a formatted table."""
        plan = plan or self._current_plan
        if not plan:
            console.print("[yellow]No plan available[/yellow]")
            return

        console.print(Panel(plan.goal, title="Task Goal", border_style="blue"))

        table = Table(title="Planned Steps")
        table.add_column("#", style="dim")
        table.add_column("Action")
        table.add_column("Target")
        table.add_column("Description")
        table.add_column("Input?")

        for i, step in enumerate(plan.steps, 1):
            table.add_row(
                str(i),
                step.action,
                step.target,
                step.description,
                "\u2713" if step.wait_for_input else "",
            )

        console.print(table)

    async def discover_selector(
        self,
        page: "Page",
        target: str,
    ) -> Optional[str]:
        """
        Attempt to discover a CSS selector for a target description.

        Uses heuristics to find elements matching the description.

        Args:
            page: Playwright page
            target: Natural language description

        Returns:
            CSS selector or None if not found
        """
        # Common selector patterns based on target description
        patterns = []

        target_lower = target.lower()

        # Username/email field
        if any(x in target_lower for x in ["username", "user", "email", "login"]):
            patterns.extend([
                'input[type="text"][name*="user"]',
                'input[type="email"]',
                'input[name*="email"]',
                'input[id*="user"]',
                'input[id*="email"]',
                'input[placeholder*="user" i]',
                'input[placeholder*="email" i]',
            ])

        # Password field
        if "password" in target_lower:
            patterns.extend([
                'input[type="password"]',
                'input[name*="pass"]',
                'input[id*="pass"]',
            ])

        # Login button
        if "login" in target_lower and "button" in target_lower:
            patterns.extend([
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("\u767b\u5f55")',
                'button:has-text("\u30ed\u30b0\u30a4\u30f3")',
                'a:has-text("Login")',
            ])

        # Search box
        if "search" in target_lower and any(x in target_lower for x in ["box", "field", "input"]):
            patterns.extend([
                'input[type="search"]',
                'input[name*="search"]',
                'input[id*="search"]',
                'input[placeholder*="search" i]',
            ])

        # Search button
        if "search" in target_lower and "button" in target_lower:
            patterns.extend([
                'button[type="submit"]',
                'button:has-text("Search")',
                'button:has-text("\u641c\u7d22")',
                'button:has-text("\u691c\u7d22")',
            ])

        # Submit button
        if "submit" in target_lower:
            patterns.extend([
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("\u63d0\u4ea4")',
                'button:has-text("\u9001\u4fe1")',
            ])

        # Try each pattern
        for pattern in patterns:
            try:
                element = await page.query_selector(pattern)
                if element:
                    return pattern
            except Exception:
                continue

        return None

    async def execute_plan(
        self,
        page: "Page",
        plan: Optional[TaskPlan] = None,
        action_log: Optional[ActionLog] = None,
    ) -> ActionLog:
        """
        Execute a task plan.

        Args:
            page: Playwright page
            plan: TaskPlan to execute (uses current plan if not specified)
            action_log: ActionLog to record to (creates new if not specified)

        Returns:
            ActionLog with recorded steps
        """
        import asyncio

        plan = plan or self._current_plan
        if not plan:
            raise ValueError("No plan available")

        if action_log is None:
            action_log = ActionLog(title=plan.goal)

        console.print(Panel(
            f"Executing: {plan.goal}",
            title="Task Execution",
            border_style="green",
        ))

        for i, step in enumerate(plan.steps, 1):
            console.print(f"\n[{i}/{len(plan.steps)}] {step.description}")

            # Discover selector if not set
            if not step.selector:
                step.selector = await self.discover_selector(page, step.target)

            if not step.selector:
                console.print(f"  [yellow]Could not find: {step.target}[/yellow]")
                # Ask user for selector
                loop = asyncio.get_event_loop()
                user_selector = await loop.run_in_executor(
                    None,
                    lambda: input("  Enter CSS selector (or press Enter to skip): ")
                )
                if user_selector.strip():
                    step.selector = user_selector.strip()
                else:
                    continue

            # Get value if needed
            value = step.value
            if step.wait_for_input and step.action == "fill":
                loop = asyncio.get_event_loop()
                value = await loop.run_in_executor(
                    None,
                    lambda: input(f"  Enter value for {step.target}: ")
                )

            # Execute the action
            try:
                if step.action == "click":
                    await page.click(step.selector, timeout=10000)
                elif step.action == "fill":
                    if value:
                        await page.fill(step.selector, value, timeout=10000)
                elif step.action == "select":
                    if value:
                        await page.select_option(step.selector, value, timeout=10000)
                elif step.action == "check":
                    await page.check(step.selector, timeout=10000)
                elif step.action == "hover":
                    await page.hover(step.selector, timeout=10000)

                # Record the action
                action_log.add_step(
                    action=step.action,
                    selector=step.selector,
                    value=value,
                    description=step.description,
                )

                console.print(f"  [green]\u2713 Completed[/green]")

            except Exception as e:
                console.print(f"  [red]\u2717 Failed: {e}[/red]")

            # Brief pause between actions
            await asyncio.sleep(0.5)

        return action_log

    def get_current_plan(self) -> Optional[TaskPlan]:
        """Get the current plan."""
        return self._current_plan


# Convenience functions for common tasks
def plan_login(url: str, language: str = "zh") -> TaskPlan:
    """Create a login task plan."""
    planner = TaskPlanner(language=language)
    plan = planner.create_plan(
        goal=f"Login to {url}",
        template="login",
    )
    plan.steps.insert(0, TaskStep(
        action="navigate",
        target=url,
        description=f"Navigate to {url}",
    ))
    return plan


def plan_search(query: str, language: str = "zh") -> TaskPlan:
    """Create a search task plan."""
    planner = TaskPlanner(language=language)
    plan = planner.create_plan(
        goal=f"Search for: {query}",
        template="search",
    )
    # Pre-fill the search value
    if plan.steps:
        plan.steps[0].value = query
        plan.steps[0].wait_for_input = False
    return plan
