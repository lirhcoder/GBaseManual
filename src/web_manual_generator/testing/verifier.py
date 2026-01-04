"""验证引擎 - 整合截图对比和元素检查"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.async_api import Page

from .models import (
    TestConfig,
    CompareMode,
    VerificationResult,
    VerificationType,
    CompareResult,
    ElementCheckResult,
)
from .comparator import ScreenshotComparator, AIScreenshotComparator

logger = logging.getLogger(__name__)


class Verifier:
    """验证引擎"""

    def __init__(self, config: TestConfig):
        """
        初始化验证器

        Args:
            config: 测试配置
        """
        self.config = config
        self.screenshot_compare = config.screenshot_compare
        self.compare_mode = config.screenshot_compare_mode
        self.element_check = config.element_check

        # 初始化截图对比器
        if self.screenshot_compare:
            if self.compare_mode == CompareMode.PIXEL:
                self.pixel_comparator = ScreenshotComparator(
                    threshold=config.threshold,
                    ignore_regions=config.ignore_regions,
                )
                self.ai_comparator = None
            else:
                self.pixel_comparator = None
                self.ai_comparator = AIScreenshotComparator(
                    provider=config.ai_provider,
                    strictness=config.ai_strictness,
                )

    async def verify_step(
        self,
        page: Page,
        step_data: Dict[str, Any],
        baseline_screenshot: Optional[Path],
        actual_screenshot: Optional[Path],
        diff_output_dir: Optional[Path] = None,
    ) -> list[VerificationResult]:
        """
        验证单个步骤

        Args:
            page: Playwright页面对象
            step_data: 步骤数据（包含selector等信息）
            baseline_screenshot: 基准截图路径
            actual_screenshot: 实际截图路径
            diff_output_dir: 差异图片输出目录

        Returns:
            验证结果列表
        """
        results = []

        # 1. 截图对比验证
        if self.screenshot_compare:
            if baseline_screenshot and actual_screenshot:
                screenshot_result = await self._verify_screenshot(
                    baseline_screenshot,
                    actual_screenshot,
                    step_data.get("description", ""),
                    diff_output_dir,
                    step_data.get("id", 0),
                )
                results.append(screenshot_result)
            else:
                # 缺少基准截图或实际截图，添加警告
                missing = []
                if not baseline_screenshot:
                    missing.append("基准截图")
                if not actual_screenshot:
                    missing.append("实际截图")
                logger.warning(f"跳过截图对比: 缺少 {', '.join(missing)}")
                results.append(VerificationResult(
                    type=VerificationType.SCREENSHOT,
                    passed=True,  # 警告不影响通过状态
                    message=f"跳过截图对比: 缺少 {', '.join(missing)}",
                    details={"skipped": True, "missing": missing},
                ))

        # 2. 元素检查验证
        if self.element_check:
            selector = step_data.get("selector")
            if selector:
                element_result = await self._verify_element(
                    page,
                    selector,
                    step_data.get("expected_text"),
                )
                results.append(element_result)

        return results

    async def _verify_screenshot(
        self,
        baseline: Path,
        actual: Path,
        step_description: str,
        diff_output_dir: Optional[Path],
        step_id: int,
    ) -> VerificationResult:
        """
        验证截图

        Args:
            baseline: 基准截图
            actual: 实际截图
            step_description: 步骤描述
            diff_output_dir: 差异图输出目录
            step_id: 步骤ID

        Returns:
            验证结果
        """
        try:
            diff_path = None
            if self.compare_mode == CompareMode.PIXEL:
                # 像素对比
                if diff_output_dir:
                    diff_path = diff_output_dir / f"diff_step_{step_id:03d}.png"

                result = self.pixel_comparator.compare(baseline, actual, diff_path)
                message = f"差异比例: {result.diff_ratio * 100:.1f}%" if result.diff_ratio else None
            else:
                # AI对比
                result = await self.ai_comparator.compare(
                    baseline, actual, step_description
                )
                message = result.reason

            # 构建截图路径信息
            screenshots = {
                "baseline": str(baseline.name) if baseline else None,
                "actual": str(actual.name) if actual else None,
            }
            if diff_path and diff_path.exists():
                screenshots["diff"] = str(diff_path.name)

            return VerificationResult(
                type=VerificationType.SCREENSHOT,
                passed=result.passed,
                message=message,
                diff_ratio=result.diff_ratio,
                screenshots=screenshots,
                details=result.to_dict(),
            )

        except Exception as e:
            logger.error(f"截图验证失败: {e}")
            return VerificationResult(
                type=VerificationType.SCREENSHOT,
                passed=False,
                message=f"验证出错: {str(e)}",
                details={"error": str(e)},
            )

    async def _verify_element(
        self,
        page: Page,
        selector: str,
        expected_text: Optional[str] = None,
    ) -> VerificationResult:
        """
        验证元素存在性和文本

        Args:
            page: Playwright页面对象
            selector: 元素选择器
            expected_text: 预期文本（可选）

        Returns:
            验证结果
        """
        try:
            # 等待元素出现
            element = await page.wait_for_selector(
                selector,
                timeout=5000,
                state="visible",
            )

            if element is None:
                result = ElementCheckResult(
                    passed=False,
                    selector=selector,
                    reason="元素未找到",
                    element_found=False,
                )
            else:
                # 元素存在
                result = ElementCheckResult(
                    passed=True,
                    selector=selector,
                    element_found=True,
                )

                # 检查文本（如果指定）
                if expected_text:
                    text = await element.text_content()
                    if text and expected_text in text:
                        result.text_matched = True
                    else:
                        result.passed = False
                        result.text_matched = False
                        result.reason = f"文本不匹配: 期望包含 '{expected_text}'，实际 '{text}'"

            return VerificationResult(
                type=VerificationType.ELEMENT,
                passed=result.passed,
                message=result.reason if not result.passed else "元素存在",
                details=result.to_dict(),
            )

        except Exception as e:
            error_msg = str(e)
            if "Timeout" in error_msg:
                reason = f"元素在超时时间内未找到: {selector}"
            else:
                reason = f"元素检查失败: {error_msg}"

            return VerificationResult(
                type=VerificationType.ELEMENT,
                passed=False,
                message=reason,
                details=ElementCheckResult(
                    passed=False,
                    selector=selector,
                    reason=reason,
                    element_found=False,
                ).to_dict(),
            )

    async def take_screenshot(
        self,
        page: Page,
        output_path: Path,
        full_page: bool = False,
    ) -> Path:
        """
        截取页面截图

        Args:
            page: Playwright页面对象
            output_path: 输出路径
            full_page: 是否截取整个页面

        Returns:
            截图路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output_path), full_page=full_page)
        return output_path
