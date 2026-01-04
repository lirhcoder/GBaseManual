"""HTML测试报告生成器"""
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import TestResult, TestStatus

logger = logging.getLogger(__name__)


class TestReporter:
    """测试报告生成器"""

    def __init__(self, test_run_dir: Path):
        """
        初始化报告生成器

        Args:
            test_run_dir: 测试运行目录
        """
        self.test_run_dir = Path(test_run_dir)
        self.templates_dir = Path(__file__).parent / "templates"

        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # 注册自定义过滤器
        self.env.filters["format_datetime"] = self._format_datetime
        self.env.filters["format_duration"] = self._format_duration
        self.env.filters["format_percent"] = self._format_percent

    def generate(self, result: TestResult, embed_images: bool = True) -> Path:
        """
        生成HTML测试报告

        Args:
            result: 测试结果
            embed_images: 是否嵌入图片（base64）

        Returns:
            报告文件路径
        """
        template = self.env.get_template("report.html")

        # 准备数据
        context = self._prepare_context(result, embed_images)

        # 渲染模板
        html_content = template.render(**context)

        # 保存报告
        report_path = self.test_run_dir / "report.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"测试报告已生成: {report_path}")
        return report_path

    def _prepare_context(self, result: TestResult, embed_images: bool) -> dict:
        """准备模板上下文"""
        steps_data = []

        for step in result.steps:
            step_data = {
                "id": step.step_id,
                "description": step.step_description,
                "action_type": step.action_type,
                "passed": step.passed,
                "executed": step.executed,
                "execution_error": step.execution_error,
                "execution_time_ms": step.execution_time_ms,
                "verifications": [v.to_dict() for v in step.verifications],
            }

            # 处理截图
            if embed_images:
                step_data["baseline_image"] = self._encode_image(step.baseline_screenshot)
                step_data["actual_image"] = self._encode_image(step.actual_screenshot)
                step_data["diff_image"] = self._encode_image(step.diff_screenshot)
            else:
                step_data["baseline_image"] = self._get_relative_path(step.baseline_screenshot)
                step_data["actual_image"] = self._get_relative_path(step.actual_screenshot)
                step_data["diff_image"] = self._get_relative_path(step.diff_screenshot)

            steps_data.append(step_data)

        return {
            "test_id": result.test_id,
            "project_id": result.project_id,
            "recording_id": result.recording_id,
            "status": result.status.value,
            "status_class": self._get_status_class(result.status),
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "duration_ms": result.duration_ms,
            "total_steps": result.total_steps,
            "passed_steps": result.passed_steps,
            "failed_steps": result.failed_steps,
            "success": result.success,
            "success_rate": result.passed_steps / result.total_steps * 100 if result.total_steps > 0 else 0,
            "error_message": result.error_message,
            "config": result.config.to_dict() if result.config else {},
            "steps": steps_data,
            "embed_images": embed_images,
            "generated_at": datetime.now(),
        }

    def _encode_image(self, image_path: Optional[Path]) -> Optional[str]:
        """将图片编码为base64"""
        if not image_path or not Path(image_path).exists():
            return None

        try:
            with open(image_path, "rb") as f:
                data = f.read()
            return f"data:image/png;base64,{base64.b64encode(data).decode()}"
        except Exception as e:
            logger.warning(f"读取图片失败 {image_path}: {e}")
            return None

    def _get_relative_path(self, image_path: Optional[Path]) -> Optional[str]:
        """获取相对于报告的图片路径"""
        if not image_path:
            return None

        try:
            return str(Path(image_path).relative_to(self.test_run_dir))
        except ValueError:
            # 如果不在test_run_dir下，返回绝对路径
            return str(image_path)

    def _get_status_class(self, status: TestStatus) -> str:
        """获取状态对应的CSS类"""
        return {
            TestStatus.PENDING: "status-pending",
            TestStatus.RUNNING: "status-running",
            TestStatus.COMPLETED: "status-completed",
            TestStatus.FAILED: "status-failed",
            TestStatus.CANCELLED: "status-cancelled",
        }.get(status, "status-unknown")

    @staticmethod
    def _format_datetime(value: Optional[datetime]) -> str:
        """格式化日期时间"""
        if not value:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_duration(ms: int) -> str:
        """格式化持续时间"""
        if ms < 1000:
            return f"{ms}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            minutes = ms // 60000
            seconds = (ms % 60000) / 1000
            return f"{minutes}m {seconds:.0f}s"

    @staticmethod
    def _format_percent(value: float) -> str:
        """格式化百分比"""
        return f"{value:.1f}%"


def generate_report(
    test_run_dir: Path,
    result: Optional[TestResult] = None,
    embed_images: bool = True,
) -> Optional[Path]:
    """
    生成测试报告的便捷函数

    Args:
        test_run_dir: 测试运行目录
        result: 测试结果（可选，从文件加载）
        embed_images: 是否嵌入图片

    Returns:
        报告文件路径
    """
    test_run_dir = Path(test_run_dir)

    # 如果未提供结果，从文件加载
    if result is None:
        result_path = test_run_dir / "test_result.json"
        if not result_path.exists():
            logger.error(f"找不到测试结果文件: {result_path}")
            return None

        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result = TestResult.from_dict(data)
        except Exception as e:
            logger.error(f"加载测试结果失败: {e}")
            return None

    reporter = TestReporter(test_run_dir)
    return reporter.generate(result, embed_images)
