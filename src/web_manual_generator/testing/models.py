"""测试相关数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class CompareMode(str, Enum):
    """截图对比模式"""
    PIXEL = "pixel"
    AI = "ai"


class AIStrictness(str, Enum):
    """AI对比严格程度"""
    LENIENT = "lenient"   # 宽松 - 只关注主要功能元素
    NORMAL = "normal"     # 一般 - 检查功能元素和主要UI布局
    STRICT = "strict"     # 严格 - 对比所有可见元素


class TestStatus(str, Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationType(str, Enum):
    """验证类型"""
    SCREENSHOT = "screenshot"
    ELEMENT = "element"


@dataclass
class Rect:
    """矩形区域（用于忽略区域）"""
    x: int
    y: int
    width: int
    height: int


@dataclass
class TestConfig:
    """测试配置"""
    # 验证选项
    screenshot_compare: bool = True
    screenshot_compare_mode: CompareMode = CompareMode.PIXEL
    element_check: bool = True

    # 像素对比设置
    threshold: float = 0.10  # 差异阈值 (10%) - 考虑动态内容和动画
    ignore_regions: List[Rect] = field(default_factory=list)

    # AI对比设置
    ai_provider: str = "gemini"
    ai_strictness: AIStrictness = AIStrictness.NORMAL

    # AI元素定位后备（当选择器失败时使用AI视觉定位）
    ai_fallback: bool = True  # 启用AI后备定位
    ai_fallback_provider: str = "gemini"  # AI后备定位使用的提供商

    # AI状态验证（执行操作后验证页面状态）
    ai_state_verify: bool = True  # 启用AI状态验证
    ai_verify_after_fill: bool = True  # 在fill操作后验证
    ai_verify_after_click: bool = False  # 在click操作后验证（默认关闭，可能导致性能问题）
    ai_auto_correct: bool = True  # 自动修正状态不一致
    ai_state_verify_provider: str = "gemini"  # 状态验证使用的AI提供商

    # Debug模式 - AI-in-the-loop
    debug_mode: bool = False  # 启用调试模式（单步执行）
    ai_in_the_loop: bool = False  # AI全程参与分析
    ai_auto_skip: bool = True  # AI自动跳过不必要的步骤（如快速重定向）
    ai_auto_fix: bool = True  # AI自动修复失败的选择器
    pause_on_failure: bool = True  # 步骤失败时暂停等待用户决策
    max_auto_retries: int = 2  # 自动重试次数

    # 测试变量（用于存储敏感信息如密码）
    # 变量可以通过选择器名称或描述关键字匹配
    # 例如: {"#password": "mypassword", "密码": "mypassword"}
    test_variables: Dict[str, str] = field(default_factory=dict)

    # 执行设置
    headless: bool = True
    timeout: int = 30000  # 步骤超时(ms)
    step_delay: float = 0.5  # 步骤间延迟(s)

    # 起始步骤（从第几步开始验证，之前的步骤快速回放）
    start_from_step: int = 1  # 默认从第1步开始

    # 报告设置
    generate_report: bool = True
    keep_screenshots: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "screenshot_compare": self.screenshot_compare,
            "screenshot_compare_mode": self.screenshot_compare_mode.value,
            "element_check": self.element_check,
            "threshold": self.threshold,
            "ignore_regions": [
                {"x": r.x, "y": r.y, "width": r.width, "height": r.height}
                for r in self.ignore_regions
            ],
            "ai_provider": self.ai_provider,
            "ai_strictness": self.ai_strictness.value,
            "ai_fallback": self.ai_fallback,
            "ai_fallback_provider": self.ai_fallback_provider,
            "ai_state_verify": self.ai_state_verify,
            "ai_verify_after_fill": self.ai_verify_after_fill,
            "ai_verify_after_click": self.ai_verify_after_click,
            "ai_auto_correct": self.ai_auto_correct,
            "ai_state_verify_provider": self.ai_state_verify_provider,
            # Debug模式配置
            "debug_mode": self.debug_mode,
            "ai_in_the_loop": self.ai_in_the_loop,
            "ai_auto_skip": self.ai_auto_skip,
            "ai_auto_fix": self.ai_auto_fix,
            "pause_on_failure": self.pause_on_failure,
            "max_auto_retries": self.max_auto_retries,
            # 执行配置
            "headless": self.headless,
            "timeout": self.timeout,
            "step_delay": self.step_delay,
            "start_from_step": self.start_from_step,
            "generate_report": self.generate_report,
            "keep_screenshots": self.keep_screenshots,
            # 注意：test_variables 不保存到文件（安全考虑），仅运行时使用
            # "test_variables": self.test_variables,  # 敏感信息不持久化
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestConfig":
        """从字典创建"""
        ignore_regions = [
            Rect(**r) for r in data.get("ignore_regions", [])
        ]
        return cls(
            screenshot_compare=data.get("screenshot_compare", True),
            screenshot_compare_mode=CompareMode(data.get("screenshot_compare_mode", "pixel")),
            element_check=data.get("element_check", True),
            threshold=data.get("threshold", 0.10),
            ignore_regions=ignore_regions,
            ai_provider=data.get("ai_provider", "gemini"),
            ai_strictness=AIStrictness(data.get("ai_strictness", "normal")),
            ai_fallback=data.get("ai_fallback", True),
            ai_fallback_provider=data.get("ai_fallback_provider", "gemini"),
            ai_state_verify=data.get("ai_state_verify", True),
            ai_verify_after_fill=data.get("ai_verify_after_fill", True),
            ai_verify_after_click=data.get("ai_verify_after_click", False),
            ai_auto_correct=data.get("ai_auto_correct", True),
            ai_state_verify_provider=data.get("ai_state_verify_provider", "gemini"),
            # Debug模式配置
            debug_mode=data.get("debug_mode", False),
            ai_in_the_loop=data.get("ai_in_the_loop", False),
            ai_auto_skip=data.get("ai_auto_skip", True),
            ai_auto_fix=data.get("ai_auto_fix", True),
            pause_on_failure=data.get("pause_on_failure", True),
            max_auto_retries=data.get("max_auto_retries", 2),
            # 执行配置
            headless=data.get("headless", True),
            timeout=data.get("timeout", 30000),
            step_delay=data.get("step_delay", 0.5),
            start_from_step=data.get("start_from_step", 1),
            generate_report=data.get("generate_report", True),
            keep_screenshots=data.get("keep_screenshots", True),
            # 测试变量（运行时传入）
            test_variables=data.get("test_variables", {}),
        )


@dataclass
class CompareResult:
    """截图对比结果"""
    passed: bool
    diff_ratio: Optional[float] = None  # 像素模式: 差异比例
    reason: Optional[str] = None  # AI模式: 差异原因
    method: str = "pixel"  # pixel | ai
    diff_image_path: Optional[Path] = None  # 差异图片路径
    critical: bool = False  # AI模式: 差异是否影响功能

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "diff_ratio": self.diff_ratio,
            "reason": self.reason,
            "method": self.method,
            "diff_image_path": str(self.diff_image_path) if self.diff_image_path else None,
            "critical": self.critical,
        }


@dataclass
class ElementCheckResult:
    """元素检查结果"""
    passed: bool
    selector: str
    reason: Optional[str] = None
    element_found: bool = False
    text_matched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "selector": self.selector,
            "reason": self.reason,
            "element_found": self.element_found,
            "text_matched": self.text_matched,
        }


@dataclass
class VerificationResult:
    """单个验证结果"""
    type: VerificationType
    passed: bool
    message: Optional[str] = None
    diff_ratio: Optional[float] = None
    screenshots: Optional[Dict[str, str]] = None  # baseline, actual, diff paths
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.type.value,
            "passed": self.passed,
            "message": self.message,
        }
        if self.diff_ratio is not None:
            result["diff_ratio"] = self.diff_ratio
        if self.screenshots:
            result["screenshots"] = self.screenshots
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class StepResult:
    """单步执行结果"""
    step_id: int
    step_description: str
    action_type: str

    # 执行状态
    executed: bool = False
    execution_error: Optional[str] = None
    execution_time_ms: int = 0

    # 元素信息
    selector: Optional[str] = None
    value: Optional[str] = None

    # 截图
    baseline_screenshot: Optional[Path] = None
    actual_screenshot: Optional[Path] = None
    diff_screenshot: Optional[Path] = None

    # 验证结果
    verifications: List[VerificationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """是否通过"""
        if not self.executed:
            return False
        if self.execution_error:
            return False
        # 如果没有验证项，执行成功即通过
        if not self.verifications:
            return True
        return all(v.passed for v in self.verifications)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_description": self.step_description,
            "action_type": self.action_type,
            "executed": self.executed,
            "execution_error": self.execution_error,
            "execution_time_ms": self.execution_time_ms,
            "passed": self.passed,
            "selector": self.selector,
            "value": self.value,
            "baseline_screenshot": str(self.baseline_screenshot) if self.baseline_screenshot else None,
            "actual_screenshot": str(self.actual_screenshot) if self.actual_screenshot else None,
            "diff_screenshot": str(self.diff_screenshot) if self.diff_screenshot else None,
            "verifications": [v.to_dict() for v in self.verifications],
        }


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    project_id: str
    recording_id: str

    # 状态
    status: TestStatus = TestStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 配置
    config: Optional[TestConfig] = None

    # 结果
    steps: List[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None

    # 报告路径
    report_path: Optional[Path] = None

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.steps if s.passed)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.executed and not s.passed)

    @property
    def success(self) -> bool:
        return self.status == TestStatus.COMPLETED and self.failed_steps == 0

    @property
    def duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "project_id": self.project_id,
            "recording_id": self.recording_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": self.config.to_dict() if self.config else None,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "report_path": str(self.report_path) if self.report_path else None,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResult":
        """从字典创建（简化版，主要用于加载基本信息）"""
        result = cls(
            test_id=data["test_id"],
            project_id=data["project_id"],
            recording_id=data["recording_id"],
            status=TestStatus(data.get("status", "pending")),
            error_message=data.get("error_message"),
        )

        if data.get("started_at"):
            result.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            result.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("config"):
            result.config = TestConfig.from_dict(data["config"])
        if data.get("report_path"):
            result.report_path = Path(data["report_path"])

        return result


@dataclass
class AIAnalysisResult:
    """AI分析结果（用于UI显示）"""
    step_id: int
    action_type: str = ""
    analysis_type: str = ""  # "pre_execution" | "failure_diagnosis" | "skip_decision"

    # 分析结论
    should_skip: bool = False
    skip_reason: str = ""
    should_modify: bool = False
    suggested_selector: str = ""
    confidence: float = 0.0

    # 分析详情
    analysis_text: str = ""
    screenshot_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "analysis_type": self.analysis_type,
            "should_skip": self.should_skip,
            "skip_reason": self.skip_reason,
            "should_modify": self.should_modify,
            "suggested_selector": self.suggested_selector,
            "confidence": self.confidence,
            "analysis_text": self.analysis_text,
            "screenshot_path": self.screenshot_path,
        }


@dataclass
class TestProgress:
    """测试进度（用于实时更新）"""
    test_id: str
    status: TestStatus
    current_step: int
    total_steps: int
    current_step_description: str = ""
    current_action_type: str = ""
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)

    # AI分析相关
    ai_analysis: Optional[AIAnalysisResult] = None  # 当前步骤的AI分析结果
    waiting_for_confirmation: bool = False  # 是否等待用户确认

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "test_id": self.test_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_step_description": self.current_step_description,
            "action_type": self.current_action_type,
            "progress_percent": int(self.current_step / self.total_steps * 100) if self.total_steps > 0 else 0,
            "completed_steps": self.completed_steps,
            "waiting_for_confirmation": self.waiting_for_confirmation,
        }
        if self.ai_analysis:
            result["ai_analysis"] = self.ai_analysis.to_dict()
        return result
