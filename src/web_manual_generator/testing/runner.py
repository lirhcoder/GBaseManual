"""测试执行引擎"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from playwright.async_api import async_playwright, Page

from urllib.parse import urlparse, parse_qs

from ..capture.action_log import ActionLog, ActionStep

# OAuth/SSO 提供商的域名模式
OAUTH_DOMAINS = [
    'auth0.com',
    'accounts.google.com',
    'login.microsoftonline.com',
    'github.com/login',
    'login.salesforce.com',
    'okta.com',
    'onelogin.com',
    'cognito',
]
from .models import (
    TestConfig,
    TestResult,
    TestStatus,
    TestProgress,
    StepResult,
    VerificationResult,
    VerificationType,
    AIAnalysisResult,
)
from .verifier import Verifier
from .ai_locator import AIElementLocator
from .ai_state_verifier import AIStateVerifier, StateVerificationResult
from .ai_debug_controller import AIDebugController, StepAnalysis, FailureDiagnosis, DebugAction

logger = logging.getLogger(__name__)


class TestRunner:
    """测试执行引擎"""

    def __init__(
        self,
        project_id: str,
        recording_id: str,
        recording_dir: Path,
        config: TestConfig,
        progress_callback: Optional[Callable[[TestProgress], None]] = None,
    ):
        """
        初始化测试执行器

        Args:
            project_id: 项目ID
            recording_id: 录制ID
            recording_dir: 录制目录路径
            config: 测试配置
            progress_callback: 进度回调函数（用于实时更新）
        """
        self.project_id = project_id
        self.recording_id = recording_id
        self.recording_dir = Path(recording_dir)
        self.config = config
        self.progress_callback = progress_callback

        # 初始化验证器
        self.verifier = Verifier(config)

        # 初始化状态验证器（用于操作后状态检查）
        if config.ai_state_verify:
            self.state_verifier = AIStateVerifier(provider=config.ai_state_verify_provider)
        else:
            self.state_verifier = None

        # 初始化AI调试控制器（用于AI-in-the-loop模式）
        if config.ai_in_the_loop or config.debug_mode:
            self.debug_controller = AIDebugController(provider=config.ai_provider)
        else:
            self.debug_controller = None

        # Debug模式状态
        self._debug_paused = False
        self._debug_action: Optional[DebugAction] = None
        self._pending_selector_fix: Optional[str] = None
        self._current_ai_analysis: Optional[AIAnalysisResult] = None  # 当前AI分析结果
        self._waiting_for_confirmation = False  # 是否等待用户确认

        # 用户自定义AI提示词（用于调整AI行为）
        self.user_ai_prompt: str = ""

        # 表单上下文（跟踪已填写的字段）
        self.form_context: Dict[str, Any] = {}

        # 测试结果
        self.test_id = str(uuid.uuid4())[:8]
        self.result: Optional[TestResult] = None

        # 测试运行目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.test_run_dir = self.recording_dir / "test_runs" / f"{timestamp}_{self.test_id}"
        self.test_run_dir.mkdir(parents=True, exist_ok=True)

        # 截图目录
        self.screenshots_dir = self.test_run_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)

        # 差异图目录
        self.diff_dir = self.test_run_dir / "diff"
        self.diff_dir.mkdir(exist_ok=True)

        # 基准截图目录
        self.baseline_screenshots_dir = self.recording_dir / "screenshots"

        # 当前状态
        self._cancelled = False

        # 预期的域名（用于检测意外重定向）
        self.expected_domain: Optional[str] = None

    async def run(self) -> TestResult:
        """
        执行测试

        Returns:
            TestResult: 测试结果
        """
        # 初始化结果
        self.result = TestResult(
            test_id=self.test_id,
            project_id=self.project_id,
            recording_id=self.recording_id,
            status=TestStatus.RUNNING,
            started_at=datetime.now(),
            config=self.config,
        )

        # 加载 action log
        action_log_path = self.recording_dir / "action_log.json"
        if not action_log_path.exists():
            self.result.status = TestStatus.FAILED
            self.result.error_message = f"找不到 action_log.json: {action_log_path}"
            self.result.completed_at = datetime.now()
            return self.result

        try:
            action_log = ActionLog.load(action_log_path)
        except Exception as e:
            self.result.status = TestStatus.FAILED
            self.result.error_message = f"加载 action_log.json 失败: {e}"
            self.result.completed_at = datetime.now()
            return self.result

        # 保存测试配置
        self._save_config()

        # 执行测试
        try:
            await self._execute(action_log)
        except Exception as e:
            logger.exception("测试执行异常")
            self.result.status = TestStatus.FAILED
            self.result.error_message = str(e)
        finally:
            self.result.completed_at = datetime.now()
            self._save_result()

        return self.result

    async def _execute(self, action_log: ActionLog) -> None:
        """执行测试步骤"""
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(headless=self.config.headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # 导航到起始URL
                if action_log.start_url:
                    await page.goto(action_log.start_url)
                    await asyncio.sleep(self.config.step_delay)
                    # 记录预期域名
                    self.expected_domain = urlparse(action_log.start_url).netloc

                start_from = self.config.start_from_step
                total_steps = len(action_log.steps)

                # 执行每个步骤
                for step in action_log.steps:
                    if self._cancelled:
                        self.result.status = TestStatus.CANCELLED
                        break

                    # 判断是快速回放模式还是完整验证模式
                    is_quick_replay = step.id < start_from

                    if is_quick_replay:
                        # 快速回放：只执行动作，不验证，最小延迟
                        step_result = await self._execute_step_quick(page, step)
                    else:
                        # 完整验证：执行动作 + 验证
                        step_result = await self._execute_step(page, step)

                    self.result.steps.append(step_result)

                    # 发送进度更新（包含总步数）
                    self._send_progress(total_steps)

                    # 步骤间延迟（快速模式用最小延迟）
                    delay = 0.1 if is_quick_replay else self.config.step_delay
                    await asyncio.sleep(delay)

                # 设置最终状态
                if not self._cancelled:
                    if self.result.failed_steps > 0:
                        self.result.status = TestStatus.FAILED
                    else:
                        self.result.status = TestStatus.COMPLETED

            finally:
                await browser.close()

    async def _execute_step_quick(self, page: Page, step: ActionStep) -> StepResult:
        """
        快速执行步骤（不验证，用于回放到指定步骤）

        Args:
            page: Playwright页面
            step: 动作步骤

        Returns:
            步骤执行结果
        """
        start_time = time.time()

        result = StepResult(
            step_id=step.id,
            step_description=f"[快速回放] {step.description or step.get_description('zh')}",
            action_type=step.action,
            selector=step.selector,
            value=step.value,
        )

        try:
            # 只执行动作，不验证
            await self._perform_action(page, step)
            result.executed = True
            # 快速模式下直接标记为通过（跳过验证）
        except Exception as e:
            logger.warning(f"快速回放步骤 {step.id} 失败: {e}")
            result.execution_error = f"[快速回放失败] {str(e)}"

        result.execution_time_ms = int((time.time() - start_time) * 1000)
        return result

    async def _execute_step(self, page: Page, step: ActionStep) -> StepResult:
        """
        执行单个步骤（完整验证模式，支持AI-in-the-loop）

        Args:
            page: Playwright页面
            step: 动作步骤

        Returns:
            步骤执行结果
        """
        start_time = time.time()

        result = StepResult(
            step_id=step.id,
            step_description=step.description or step.get_description("zh"),
            action_type=step.action,
            selector=step.selector,
            value=step.value,
        )

        # AI-in-the-loop: 执行前分析
        if self.debug_controller and self.config.ai_in_the_loop:
            analysis = await self._ai_analyze_before_step(page, step)
            if analysis and analysis.should_skip:
                logger.info(f"AI建议跳过步骤 {step.id}: {analysis.skip_reason}")
                result.executed = True
                result.verifications.append(VerificationResult(
                    type=VerificationType.ELEMENT,
                    passed=True,
                    message=f"[AI跳过] {analysis.skip_reason}",
                    details={"skipped_by_ai": True, "skip_reason": analysis.skip_reason},
                ))
                result.execution_time_ms = int((time.time() - start_time) * 1000)
                return result

            # 如果AI建议使用不同的选择器
            if analysis and analysis.suggested_selector:
                logger.info(f"AI建议使用选择器: {analysis.suggested_selector} (原: {step.selector})")
                self._pending_selector_fix = analysis.suggested_selector

        # Debug模式: 暂停等待用户确认
        if self.config.debug_mode and self._debug_paused:
            await self._wait_for_debug_action()
            if self._debug_action == DebugAction.SKIP:
                result.executed = True
                result.verifications.append(VerificationResult(
                    type=VerificationType.ELEMENT,
                    passed=True,
                    message="[用户跳过]",
                    details={"skipped_by_user": True},
                ))
                result.execution_time_ms = int((time.time() - start_time) * 1000)
                return result
            elif self._debug_action == DebugAction.ABORT:
                raise Exception("用户终止测试")

        # 执行动作（带重试逻辑）
        max_retries = self.config.max_auto_retries if self.config.ai_auto_fix else 0
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # 如果有待应用的选择器修复，使用它
                effective_step = step
                if self._pending_selector_fix:
                    effective_step = self._create_step_with_new_selector(step, self._pending_selector_fix)
                    self._pending_selector_fix = None

                # 执行动作
                await self._perform_action(page, effective_step)
                result.executed = True
                break

            except Exception as e:
                last_error = e
                retry_count += 1
                logger.warning(f"步骤 {step.id} 执行失败 (尝试 {retry_count}/{max_retries + 1}): {e}")

                # AI自动修复
                if retry_count <= max_retries and self.debug_controller and self.config.ai_auto_fix:
                    fix_result = await self._ai_diagnose_and_fix(page, step, str(e))
                    if fix_result and fix_result.new_selector:
                        logger.info(f"AI建议新选择器: {fix_result.new_selector}")
                        self._pending_selector_fix = fix_result.new_selector
                        continue

                # 如果配置了失败时暂停
                if self.config.pause_on_failure and self.config.debug_mode:
                    self._debug_paused = True
                    await self._wait_for_debug_action()
                    if self._debug_action == DebugAction.RETRY:
                        continue
                    elif self._debug_action == DebugAction.SKIP:
                        result.executed = True
                        result.execution_error = f"[用户跳过] {str(e)}"
                        break
                    elif self._debug_action == DebugAction.ABORT:
                        raise Exception("用户终止测试")

                # 最后一次尝试失败
                result.execution_error = str(e)
                break

        if last_error and not result.executed:
            result.execution_error = str(last_error)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result

        # 等待页面稳定
        await asyncio.sleep(0.3)

        # 检查URL是否被重定向到意外的域名
        url_check = self._check_url_redirect(page)
        if not url_check["valid"]:
            logger.warning(f"检测到意外重定向: {url_check['current_url']}")
            result.verifications.append(VerificationResult(
                type=VerificationType.ELEMENT,  # 作为一种特殊的元素检查
                passed=False,
                message=f"页面被重定向到意外URL: {url_check['current_url']}",
                details={
                    "expected_domain": url_check["expected_domain"],
                    "current_domain": url_check["current_domain"],
                    "current_url": url_check["current_url"],
                },
            ))
            # 提前返回，不再继续验证
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result

        # 截图
        if self.config.keep_screenshots:
            actual_screenshot = self.screenshots_dir / f"step_{step.id:03d}.png"
            await page.screenshot(path=str(actual_screenshot))
            result.actual_screenshot = actual_screenshot

        # 查找基准截图
        baseline_screenshot = self._find_baseline_screenshot(step)
        if baseline_screenshot:
            result.baseline_screenshot = baseline_screenshot

        # 验证
        if self.config.screenshot_compare or self.config.element_check:
            verifications = await self.verifier.verify_step(
                page=page,
                step_data={
                    "id": step.id,
                    "description": step.description or step.get_description("zh"),
                    "selector": step.selector,
                },
                baseline_screenshot=baseline_screenshot,
                actual_screenshot=result.actual_screenshot,
                diff_output_dir=self.diff_dir,
            )
            result.verifications = verifications

            # 检查是否有差异截图
            for v in verifications:
                if v.details.get("diff_image_path"):
                    result.diff_screenshot = Path(v.details["diff_image_path"])

        # 记录执行上下文（用于AI分析）
        if self.debug_controller:
            self.debug_controller.add_execution_context(
                step_data={"id": step.id, "action": step.action, "selector": step.selector, "description": step.description},
                result={"passed": result.passed, "error": result.execution_error}
            )

        result.execution_time_ms = int((time.time() - start_time) * 1000)
        return result

    async def _ai_analyze_before_step(
        self, page: Page, step: ActionStep
    ) -> Optional[StepAnalysis]:
        """
        AI执行前分析 - 判断步骤是否应该跳过或修改

        Args:
            page: Playwright页面
            step: 待执行步骤

        Returns:
            StepAnalysis结果
        """
        if not self.debug_controller:
            return None

        try:
            # 截取当前页面状态
            temp_screenshot = self.test_run_dir / f"pre_step_{step.id}.png"
            await page.screenshot(path=str(temp_screenshot))

            # 获取之前执行的步骤上下文
            previous_steps = [
                ctx["step"] for ctx in self.debug_controller._execution_context
            ]

            # 添加用户自定义提示词（如果有）
            extra_context = ""
            if self.user_ai_prompt:
                extra_context = f"\n用户指示: {self.user_ai_prompt}"

            # 调用AI分析
            analysis = await self.debug_controller.analyze_step_before_execution(
                step_data={
                    "id": step.id,
                    "action": step.action,
                    "selector": step.selector,
                    "description": step.description or step.get_description("zh"),
                    "url": getattr(step, "url", None),
                    "value": step.value,
                    "extra_context": extra_context,
                },
                previous_steps=previous_steps,
                current_screenshot=temp_screenshot,
            )

            # 存储AI分析结果用于UI显示
            if analysis:
                self._current_ai_analysis = AIAnalysisResult(
                    step_id=step.id,
                    action_type=step.action,
                    analysis_type="pre_execution",
                    should_skip=analysis.should_skip,
                    skip_reason=analysis.skip_reason or "",
                    should_modify=bool(analysis.suggested_selector),
                    suggested_selector=analysis.suggested_selector or "",
                    confidence=getattr(analysis, "confidence", 0.8),
                    analysis_text=getattr(analysis, "analysis", ""),
                    screenshot_path=str(temp_screenshot),
                )
                # 如果AI建议跳过或修改，等待用户确认（如果启用）
                if self.config.debug_mode and (analysis.should_skip or analysis.suggested_selector):
                    self._waiting_for_confirmation = True

            return analysis
        except Exception as e:
            logger.warning(f"AI步骤前分析失败: {e}")
            return None

    async def _ai_diagnose_and_fix(
        self, page: Page, step: ActionStep, error_message: str
    ) -> Optional[FailureDiagnosis]:
        """
        AI诊断失败并建议修复

        Args:
            page: Playwright页面
            step: 失败的步骤
            error_message: 错误信息

        Returns:
            FailureDiagnosis诊断结果
        """
        if not self.debug_controller:
            return None

        try:
            # 截取当前页面状态
            temp_screenshot = self.test_run_dir / f"error_step_{step.id}.png"
            await page.screenshot(path=str(temp_screenshot))

            # 调用AI诊断
            return await self.debug_controller.diagnose_failure(
                step_data={
                    "id": step.id,
                    "action": step.action,
                    "selector": step.selector,
                    "description": step.description or step.get_description("zh"),
                },
                error_message=error_message,
                screenshot=temp_screenshot,
            )
        except Exception as e:
            logger.warning(f"AI诊断失败: {e}")
            return None

    async def _wait_for_debug_action(self) -> None:
        """
        等待用户在debug模式下的操作决策

        通过回调机制与前端通信，等待用户选择：
        - CONTINUE: 继续执行
        - RETRY: 重试当前步骤
        - SKIP: 跳过当前步骤
        - ABORT: 终止测试
        """
        # 发送暂停通知（通过进度回调）
        if self.progress_callback and self.result:
            progress = TestProgress(
                test_id=self.test_id,
                status=TestStatus.RUNNING,
                current_step=len(self.result.steps),
                total_steps=len(self.result.steps),
                current_step_description="[DEBUG] 等待用户操作...",
                current_action_type="debug_pause",
                completed_steps=[],
            )
            self.progress_callback(progress)

        # 轮询等待用户操作
        while self._debug_paused:
            await asyncio.sleep(0.1)
            if self._debug_action:
                self._debug_paused = False
                break

    def set_debug_action(self, action: DebugAction, new_selector: Optional[str] = None) -> None:
        """
        设置debug操作（由外部调用，如API或前端）

        Args:
            action: 用户选择的操作
            new_selector: 新的选择器（如果用户手动修改）
        """
        self._debug_action = action
        if new_selector:
            self._pending_selector_fix = new_selector
        self._debug_paused = False

    def _create_step_with_new_selector(
        self, step: ActionStep, new_selector: str
    ) -> ActionStep:
        """
        创建使用新选择器的步骤副本

        Args:
            step: 原步骤
            new_selector: 新选择器

        Returns:
            修改后的步骤副本
        """
        # 创建步骤的副本并替换选择器
        new_step = ActionStep(
            id=step.id,
            action=step.action,
            timestamp=step.timestamp,
            selector=new_selector,
            value=step.value,
            url=getattr(step, "url", None),
            key=getattr(step, "key", None),
            screenshot=step.screenshot,
            description=step.description,
            description_zh=step.description_zh,
            description_ja=step.description_ja,
            description_en=step.description_en,
        )
        return new_step

    async def _perform_action(self, page: Page, step: ActionStep) -> None:
        """执行浏览器操作，支持AI后备定位和状态验证"""
        timeout = self.config.timeout

        if step.action == "navigate":
            # 检测OAuth重定向URL - 这些URL包含会话特定参数，不能直接回放
            if self._is_oauth_redirect_url(step.url):
                logger.info(f"检测到OAuth重定向URL，跳过直接导航，等待自然重定向: {step.url[:80]}...")
                # 不直接导航到OAuth URL，而是等待页面自然完成重定向
                try:
                    # 等待页面稳定（重定向应该已经在进行中）
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass  # 超时继续
                return

            # 检查是否是OAuth回调URL（带code参数）- 也应该跳过
            if step.url and ('code=' in step.url or '/login?code=' in step.url):
                logger.info(f"检测到OAuth回调URL，跳过直接导航: {step.url[:80]}...")
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                return

            await page.goto(step.url, timeout=timeout)
            # 等待页面网络空闲，确保动态内容加载完成
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # 超时不影响继续执行

        elif step.action == "click":
            if step.selector:
                clicked = False
                selectors_to_try = [step.selector]

                # 如果原选择器看起来是复杂的CSS路径，添加基于文本的备选选择器
                if ' > ' in step.selector or ':nth-of-type' in step.selector:
                    desc = step.description or ""
                    # 从描述中提取文本（如 "点击 ログイン"）
                    if "点击" in desc:
                        text = desc.replace("点击", "").replace("(触发页面跳转)", "").strip()
                        if text and len(text) < 30:
                            selectors_to_try.extend([
                                f'text="{text}"',
                                f'button:has-text("{text}")',
                                f'a:has-text("{text}")',
                            ])

                # 尝试所有选择器
                last_error = None
                for selector in selectors_to_try:
                    try:
                        await page.click(selector, timeout=5000)
                        clicked = True
                        if selector != step.selector:
                            logger.info(f"使用备选选择器成功: {selector}")
                        break
                    except Exception as e:
                        last_error = e
                        continue

                # 所有选择器都失败，尝试AI定位
                if not clicked:
                    if self.config.ai_fallback:
                        logger.info(f"所有选择器失败，尝试AI定位: {step.selector}")
                        await self._ai_fallback_click(page, step)
                    else:
                        raise last_error

                # 可选：点击后状态验证
                if self.config.ai_state_verify and self.config.ai_verify_after_click:
                    await self._verify_state_after_action(page, step)

        elif step.action == "fill":
            if step.selector and step.value is not None:
                # 获取实际填入的值（支持变量替换）
                fill_value = self._resolve_fill_value(step)

                try:
                    await page.fill(step.selector, fill_value, timeout=timeout)
                except Exception as e:
                    if self.config.ai_fallback:
                        logger.info(f"选择器失败，尝试AI定位: {step.selector}")
                        await self._ai_fallback_fill(page, step, fill_value)
                    else:
                        raise e

                # 更新表单上下文
                field_name = step.description or step.selector
                self.form_context[field_name] = fill_value

                # fill后状态验证
                if self.config.ai_state_verify and self.config.ai_verify_after_fill:
                    await self._verify_state_after_action(page, step)

        elif step.action == "select":
            if step.selector and step.value:
                await page.select_option(step.selector, step.value, timeout=timeout)

        elif step.action == "check":
            if step.selector:
                await page.check(step.selector, timeout=timeout)

        elif step.action == "uncheck":
            if step.selector:
                await page.uncheck(step.selector, timeout=timeout)

        elif step.action == "hover":
            if step.selector:
                await page.hover(step.selector, timeout=timeout)

        elif step.action == "keyboard":
            if step.key:
                await page.keyboard.press(step.key)

        elif step.action == "wait":
            wait_time = int(step.value) if step.value else 1000
            await page.wait_for_timeout(wait_time)

        elif step.action == "scroll":
            await page.evaluate("window.scrollBy(0, 300)")

        elif step.action == "screenshot":
            # 只截图，不执行其他操作
            pass

    async def _verify_state_after_action(self, page: Page, step: ActionStep) -> None:
        """
        在操作后验证页面状态，如有必要执行修正

        Args:
            page: Playwright页面对象
            step: 刚执行的操作步骤
        """
        if not self.state_verifier:
            return

        # 等待页面稳定
        await asyncio.sleep(0.3)

        # 截图
        verify_screenshot = self.test_run_dir / f"verify_state_{step.id}.png"
        await page.screenshot(path=str(verify_screenshot))

        # 构建预期结果描述
        action_desc = step.description or step.get_description("zh")
        if step.action == "fill":
            expected = f"输入框应该包含值 '{step.value}'，且页面状态应该正确反映此输入"
        elif step.action == "click":
            expected = f"点击操作应该成功执行，页面应该正确响应"
        else:
            expected = "操作应该成功执行"

        # 验证状态
        logger.info(f"验证操作后状态: {action_desc}")
        result = await self.state_verifier.verify_state(
            screenshot_path=verify_screenshot,
            action_description=action_desc,
            expected_result=expected,
            form_context=self.form_context,
        )

        if result.verified:
            if result.matches_expected:
                logger.info(f"状态验证通过: {result.current_state[:100]}...")
            else:
                logger.warning(f"状态不匹配! 当前: {result.current_state[:100]}...")
                logger.warning(f"差异: {result.discrepancies}")

                # 自动修正
                if self.config.ai_auto_correct and result.corrections:
                    logger.info(f"执行 {len(result.corrections)} 个修正操作")
                    await self._execute_corrections(page, result.corrections)
        else:
            logger.warning(f"状态验证失败: {result.error}")

    async def _execute_corrections(
        self, page: Page, corrections: list
    ) -> None:
        """
        执行AI生成的修正操作

        Args:
            page: Playwright页面对象
            corrections: 修正操作列表
        """
        for correction in corrections:
            logger.info(
                f"执行修正: {correction.description} "
                f"({correction.action_type} at {correction.x}, {correction.y})"
            )

            try:
                if correction.action_type == "click":
                    if correction.x > 0 and correction.y > 0:
                        await page.mouse.click(correction.x, correction.y)
                        await asyncio.sleep(0.3)

                elif correction.action_type == "fill":
                    if correction.x > 0 and correction.y > 0 and correction.value:
                        await page.mouse.click(correction.x, correction.y)
                        await asyncio.sleep(0.1)
                        await page.keyboard.press("Control+a")
                        await page.keyboard.type(correction.value)
                        await asyncio.sleep(0.2)

                elif correction.action_type == "select":
                    if correction.x > 0 and correction.y > 0:
                        await page.mouse.click(correction.x, correction.y)
                        await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"修正操作失败: {e}")

    async def _ai_fallback_click(self, page: Page, step: ActionStep) -> None:
        """使用AI视觉定位进行点击"""
        # 先截图
        temp_screenshot = self.test_run_dir / f"ai_locate_{step.id}.png"
        await page.screenshot(path=str(temp_screenshot))

        # 使用AI定位
        locator = AIElementLocator(provider=self.config.ai_fallback_provider)
        description = step.description or step.get_description("zh") or f"点击 {step.selector}"

        result = await locator.locate_element(
            screenshot_path=temp_screenshot,
            action_description=description,
            action_type="click",
        )

        if result.success:
            logger.info(f"AI定位成功: ({result.x}, {result.y}) - {result.element_description}")
            await page.mouse.click(result.x, result.y)
        else:
            raise Exception(f"AI定位失败: {result.error}")

    async def _ai_fallback_fill(self, page: Page, step: ActionStep, fill_value: str = None) -> None:
        """使用AI视觉定位进行输入"""
        # 先截图
        temp_screenshot = self.test_run_dir / f"ai_locate_{step.id}.png"
        await page.screenshot(path=str(temp_screenshot))

        # 使用AI定位
        locator = AIElementLocator(provider=self.config.ai_fallback_provider)
        description = step.description or step.get_description("zh") or f"输入框 {step.selector}"

        result = await locator.locate_element(
            screenshot_path=temp_screenshot,
            action_description=description,
            action_type="fill",
        )

        if result.success:
            logger.info(f"AI定位输入框: ({result.x}, {result.y}) - {result.element_description}")
            # 点击输入框
            await page.mouse.click(result.x, result.y)
            await asyncio.sleep(0.1)
            # 清空并输入（使用传入的fill_value或原始值）
            await page.keyboard.press("Control+a")
            await page.keyboard.type(fill_value if fill_value is not None else (step.value or ""))
        else:
            raise Exception(f"AI定位失败: {result.error}")

    def _resolve_fill_value(self, step: ActionStep) -> str:
        """
        解析填充值，支持从测试变量中获取（用于密码等敏感字段）

        匹配优先级：
        1. 选择器完全匹配 (如 "#password")
        2. 选择器包含匹配 (如 "password" 匹配 "#password", "[name=password]")
        3. 描述关键字匹配 (如 "密码", "password", "パスワード")

        Args:
            step: 动作步骤

        Returns:
            解析后的填充值
        """
        original_value = step.value or ""

        # 如果原始值不为空，直接使用
        if original_value:
            return original_value

        # 原始值为空，尝试从测试变量中查找
        test_vars = self.config.test_variables
        if not test_vars:
            return original_value

        selector = step.selector or ""
        description = step.description or ""

        # 1. 选择器完全匹配
        if selector in test_vars:
            logger.info(f"从测试变量获取值 (选择器匹配: {selector})")
            return test_vars[selector]

        # 2. 选择器包含匹配
        for var_key, var_value in test_vars.items():
            if var_key in selector:
                logger.info(f"从测试变量获取值 (选择器包含: {var_key})")
                return var_value

        # 3. 描述关键字匹配
        password_keywords = ['密码', 'password', 'パスワード', 'pwd', 'pass', 'secret']
        for keyword in password_keywords:
            if keyword.lower() in description.lower() or keyword.lower() in selector.lower():
                # 查找变量中的密码
                for var_key, var_value in test_vars.items():
                    if any(kw in var_key.lower() for kw in password_keywords):
                        logger.info(f"从测试变量获取密码 (关键字匹配: {keyword})")
                        return var_value

        return original_value

    def _is_oauth_redirect_url(self, url: str) -> bool:
        """
        检测URL是否是OAuth/SSO重定向URL

        这些URL包含会话特定的state参数，不能直接回放

        Args:
            url: 要检查的URL

        Returns:
            True如果是OAuth重定向URL
        """
        if not url:
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 检查是否是已知的OAuth提供商域名
        for oauth_domain in OAUTH_DOMAINS:
            if oauth_domain in domain:
                return True

        # 检查URL参数是否包含OAuth特征
        query_params = parse_qs(parsed.query)

        # OAuth回调URL特征：包含code参数（一次性授权码）
        if 'code' in query_params:
            # 检查路径是否包含login/callback/auth等关键字
            path_lower = parsed.path.lower()
            if any(kw in path_lower for kw in ['login', 'callback', 'auth', 'oauth']):
                return True

        # 检查是否有多个OAuth相关参数
        oauth_params = ['state', 'code', 'client_id', 'redirect_uri', 'response_type']
        oauth_param_count = sum(1 for p in oauth_params if p in query_params)

        # 如果有2个以上OAuth相关参数，很可能是OAuth URL
        if oauth_param_count >= 2:
            return True

        return False

    def _check_url_redirect(self, page: Page) -> Dict[str, Any]:
        """
        检查页面是否被重定向到意外的域名

        Args:
            page: Playwright页面对象

        Returns:
            验证结果字典，包含 valid, current_url, current_domain, expected_domain
        """
        current_url = page.url
        current_domain = urlparse(current_url).netloc

        # 如果没有预期域名，或者域名匹配，返回有效
        if not self.expected_domain or current_domain == self.expected_domain:
            return {
                "valid": True,
                "current_url": current_url,
                "current_domain": current_domain,
                "expected_domain": self.expected_domain,
            }

        # OAuth/SSO重定向是预期行为，应该允许
        if self._is_oauth_redirect_url(current_url):
            logger.debug(f"允许OAuth重定向: {current_domain}")
            return {
                "valid": True,
                "current_url": current_url,
                "current_domain": current_domain,
                "expected_domain": self.expected_domain,
                "is_oauth": True,
            }

        # 检查是否是同一主域名的子域名（如 www.example.com vs example.com）
        expected_parts = self.expected_domain.split(".")
        current_parts = current_domain.split(".")

        # 比较主域名部分（最后两段）
        if len(expected_parts) >= 2 and len(current_parts) >= 2:
            expected_main = ".".join(expected_parts[-2:])
            current_main = ".".join(current_parts[-2:])
            if expected_main == current_main:
                return {
                    "valid": True,
                    "current_url": current_url,
                    "current_domain": current_domain,
                    "expected_domain": self.expected_domain,
                }

        # 域名不匹配
        return {
            "valid": False,
            "current_url": current_url,
            "current_domain": current_domain,
            "expected_domain": self.expected_domain,
        }

    def _find_baseline_screenshot(self, step: ActionStep) -> Optional[Path]:
        """
        查找步骤的基准截图

        Args:
            step: 动作步骤

        Returns:
            基准截图路径，如果存在
        """
        # 首先尝试步骤中指定的截图
        if step.screenshot:
            path = self.baseline_screenshots_dir / step.screenshot
            if path.exists():
                return path

        # 尝试按步骤ID查找
        for pattern in [
            f"step_{step.id:03d}.png",
            f"step_{step.id:03d}_*.png",
            f"step_{step.id}.png",
        ]:
            matches = list(self.baseline_screenshots_dir.glob(pattern))
            if matches:
                # 返回最新的一个
                return max(matches, key=lambda p: p.stat().st_mtime)

        return None

    def _send_progress(self, total_steps: int = 0) -> None:
        """发送进度更新"""
        if self.progress_callback and self.result:
            last_step = self.result.steps[-1] if self.result.steps else None
            progress = TestProgress(
                test_id=self.test_id,
                status=self.result.status,
                current_step=len(self.result.steps),
                total_steps=total_steps or len(self.result.steps),
                current_step_description=last_step.step_description if last_step else "",
                current_action_type=last_step.action_type if last_step else "",
                completed_steps=[
                    {
                        "step_id": s.step_id,
                        "passed": s.passed,
                        "description": s.step_description,
                        "action_type": s.action_type,
                    }
                    for s in self.result.steps
                ],
                # AI分析结果
                ai_analysis=self._current_ai_analysis,
                waiting_for_confirmation=self._waiting_for_confirmation,
            )
            self.progress_callback(progress)

    def _save_config(self) -> None:
        """保存测试配置"""
        config_path = self.test_run_dir / "test_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

    def _save_result(self) -> None:
        """保存测试结果"""
        if self.result:
            result_path = self.test_run_dir / "test_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(self.result.to_dict(), f, ensure_ascii=False, indent=2)

    def cancel(self) -> None:
        """取消测试"""
        self._cancelled = True


async def run_test(
    project_id: str,
    recording_id: str,
    recording_dir: Path,
    config: Optional[TestConfig] = None,
    progress_callback: Optional[Callable[[TestProgress], None]] = None,
) -> TestResult:
    """
    运行测试的便捷函数

    Args:
        project_id: 项目ID
        recording_id: 录制ID
        recording_dir: 录制目录
        config: 测试配置（可选，使用默认配置）
        progress_callback: 进度回调

    Returns:
        测试结果
    """
    if config is None:
        config = TestConfig()

    runner = TestRunner(
        project_id=project_id,
        recording_id=recording_id,
        recording_dir=recording_dir,
        config=config,
        progress_callback=progress_callback,
    )

    return await runner.run()


def get_test_runs(recording_dir: Path) -> list[Dict[str, Any]]:
    """
    获取录制的所有测试运行记录

    Args:
        recording_dir: 录制目录

    Returns:
        测试运行列表
    """
    test_runs_dir = recording_dir / "test_runs"
    if not test_runs_dir.exists():
        return []

    runs = []
    for run_dir in sorted(test_runs_dir.iterdir(), reverse=True):
        if run_dir.is_dir():
            result_path = run_dir / "test_result.json"
            if result_path.exists():
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        result_data = json.load(f)
                    runs.append({
                        "run_dir": str(run_dir),
                        "test_id": result_data.get("test_id"),
                        "status": result_data.get("status"),
                        "started_at": result_data.get("started_at"),
                        "completed_at": result_data.get("completed_at"),
                        "total_steps": result_data.get("total_steps", 0),
                        "passed_steps": result_data.get("passed_steps", 0),
                        "failed_steps": result_data.get("failed_steps", 0),
                        "success": result_data.get("success", False),
                    })
                except Exception as e:
                    logger.warning(f"加载测试结果失败 {result_path}: {e}")

    return runs


def get_test_result(test_run_dir: Path) -> Optional[TestResult]:
    """
    获取特定测试运行的结果

    Args:
        test_run_dir: 测试运行目录

    Returns:
        测试结果
    """
    result_path = test_run_dir / "test_result.json"
    if not result_path.exists():
        return None

    try:
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TestResult.from_dict(data)
    except Exception as e:
        logger.error(f"加载测试结果失败: {e}")
        return None
