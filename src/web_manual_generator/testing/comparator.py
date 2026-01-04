"""截图对比器"""
import json
import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image
import numpy as np

from .models import CompareResult, Rect, AIStrictness

logger = logging.getLogger(__name__)


class ScreenshotComparator:
    """基于像素的截图对比"""

    def __init__(self, threshold: float = 0.05, ignore_regions: Optional[List[Rect]] = None):
        """
        初始化对比器

        Args:
            threshold: 差异阈值 (0-1)，默认5%
            ignore_regions: 忽略区域列表
        """
        self.threshold = threshold
        self.ignore_regions = ignore_regions or []

    def compare(
        self,
        baseline: Path,
        current: Path,
        output_diff: Optional[Path] = None,
    ) -> CompareResult:
        """
        对比两张截图

        Args:
            baseline: 基准图片路径
            current: 当前图片路径
            output_diff: 差异图片输出路径

        Returns:
            CompareResult: 对比结果
        """
        try:
            # 加载图片
            img1 = Image.open(baseline).convert("RGB")
            img2 = Image.open(current).convert("RGB")

            # 检查尺寸
            if img1.size != img2.size:
                # 尺寸不同，调整到相同尺寸（以基准图为准）
                logger.warning(
                    f"图片尺寸不同: 基准图 {img1.size}, 当前图 {img2.size}，将调整当前图尺寸"
                )
                img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)

            # 转换为numpy数组
            arr1 = np.array(img1, dtype=np.float32)
            arr2 = np.array(img2, dtype=np.float32)

            # 应用忽略区域（将两张图的忽略区域设为相同）
            for region in self.ignore_regions:
                x1, y1 = region.x, region.y
                x2, y2 = x1 + region.width, y1 + region.height
                # 确保不超出边界
                x2 = min(x2, arr1.shape[1])
                y2 = min(y2, arr1.shape[0])
                arr1[y1:y2, x1:x2] = 0
                arr2[y1:y2, x1:x2] = 0

            # 计算差异
            diff = np.abs(arr1 - arr2)

            # 像素级差异大于阈值(10)的视为不同
            pixel_threshold = 10
            diff_mask = np.any(diff > pixel_threshold, axis=2)
            diff_pixels = np.sum(diff_mask)
            total_pixels = diff_mask.size

            diff_ratio = float(diff_pixels / total_pixels)  # 转换为Python float

            # 判断是否通过
            passed = bool(diff_ratio <= self.threshold)  # 转换为Python bool

            # 生成差异图片
            diff_image_path = None
            if output_diff and diff_pixels > 0:
                diff_image_path = self._generate_diff_image(
                    img1, img2, diff_mask, output_diff
                )

            return CompareResult(
                passed=passed,
                diff_ratio=diff_ratio,
                method="pixel",
                diff_image_path=diff_image_path,
            )

        except Exception as e:
            logger.error(f"截图对比失败: {e}")
            return CompareResult(
                passed=False,
                reason=f"对比失败: {str(e)}",
                method="pixel",
            )

    def _generate_diff_image(
        self,
        img1: Image.Image,
        img2: Image.Image,
        diff_mask: np.ndarray,
        output_path: Path,
    ) -> Path:
        """
        生成差异高亮图片

        差异区域用红色半透明覆盖标记
        """
        # 创建输出图片（左右并排：基准图 | 当前图 | 差异图）
        width, height = img1.size
        result = Image.new("RGB", (width * 3, height))

        # 放置基准图
        result.paste(img1, (0, 0))

        # 放置当前图
        result.paste(img2, (width, 0))

        # 创建差异图（在当前图上标记差异）
        diff_img = img2.copy()
        diff_arr = np.array(diff_img)

        # 将差异区域标记为红色
        diff_arr[diff_mask] = [255, 0, 0]  # 红色

        diff_img = Image.fromarray(diff_arr.astype(np.uint8))

        # 与原图混合（半透明效果）
        diff_overlay = Image.blend(img2, diff_img, 0.5)
        result.paste(diff_overlay, (width * 2, 0))

        # 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)

        return output_path


class AIScreenshotComparator:
    """基于AI的截图对比"""

    # 严格程度对应的提示词
    STRICTNESS_PROMPTS = {
        AIStrictness.LENIENT: "只关注主要功能元素是否一致，忽略样式、颜色、布局的细微差异。例如：按钮文字、输入框值、主要图标位置等核心功能元素。",
        AIStrictness.NORMAL: "检查功能元素和主要UI布局是否一致，允许小的样式差异。例如：元素位置、文字内容、图标显示都要基本一致，但颜色深浅、边框样式等可以有小差异。",
        AIStrictness.STRICT: "严格对比所有可见元素，包括文字、图标、颜色、布局、间距等。任何明显的视觉差异都应该报告。",
    }

    def __init__(
        self,
        provider: str = "gemini",
        strictness: AIStrictness = AIStrictness.NORMAL,
    ):
        """
        初始化AI对比器

        Args:
            provider: AI提供商 (gemini/claude/openai)
            strictness: 严格程度
        """
        self.provider = provider
        self.strictness = strictness

    async def compare(
        self,
        baseline: Path,
        current: Path,
        step_description: str = "",
    ) -> CompareResult:
        """
        使用AI对比两张截图

        Args:
            baseline: 基准图片路径
            current: 当前图片路径
            step_description: 当前步骤描述（帮助AI理解上下文）

        Returns:
            CompareResult: 对比结果
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(step_description)

            # 调用视觉AI
            from ..agent.description_generator import DescriptionGenerator

            generator = DescriptionGenerator(provider=self.provider)

            # 读取图片为base64
            import base64

            with open(baseline, "rb") as f:
                baseline_b64 = base64.b64encode(f.read()).decode()
            with open(current, "rb") as f:
                current_b64 = base64.b64encode(f.read()).decode()

            # 调用AI对比
            result = await generator.compare_images_for_test(
                baseline_b64, current_b64, prompt
            )

            return CompareResult(
                passed=result.get("match", False),
                reason=result.get("reason", ""),
                method="ai",
                critical=result.get("critical", False),
            )

        except Exception as e:
            logger.error(f"AI截图对比失败: {e}")
            return CompareResult(
                passed=False,
                reason=f"AI对比失败: {str(e)}",
                method="ai",
            )

    def _build_prompt(self, step_description: str) -> str:
        """构建AI对比提示词"""
        strictness_desc = self.STRICTNESS_PROMPTS[self.strictness]

        prompt = f"""对比这两张截图，判断它们是否显示相同或等效的UI状态。

第一张图是"基准图"（录制时的截图），第二张图是"当前图"（测试执行时的截图）。

当前操作步骤: {step_description if step_description else "未提供"}

对比标准: {strictness_desc}

请分析两张图片并回答：
1. 两张图是否显示相同的UI状态？
2. 如果有差异，具体差异是什么？
3. 这些差异是否会影响用户操作或功能正确性？

请以JSON格式回答：
{{
    "match": true或false,
    "reason": "差异说明（如果有）",
    "critical": true或false（差异是否影响功能）
}}

只返回JSON，不要有其他内容。"""

        return prompt
