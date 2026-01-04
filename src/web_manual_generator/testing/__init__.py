"""自动化测试模块"""
from .models import (
    TestConfig,
    TestResult,
    TestStatus,
    TestProgress,
    StepResult,
    VerificationResult,
    CompareResult,
    ElementCheckResult,
    CompareMode,
    AIStrictness,
    VerificationType,
    Rect,
)
from .runner import TestRunner, run_test, get_test_runs, get_test_result
from .verifier import Verifier
from .comparator import ScreenshotComparator, AIScreenshotComparator
from .reporter import TestReporter, generate_report
from .script_generator import PlaywrightScriptGenerator, generate_script
from .ai_locator import AIElementLocator, locate_and_click, locate_and_fill
from .ai_state_verifier import (
    AIStateVerifier,
    StateVerificationResult,
    CorrectionAction,
    verify_form_state,
)
from .ai_debug_controller import (
    AIDebugController,
    DebugAction,
    StepAnalysis,
    FailureDiagnosis,
)

__all__ = [
    # Models
    "TestConfig",
    "TestResult",
    "TestStatus",
    "TestProgress",
    "StepResult",
    "VerificationResult",
    "CompareResult",
    "ElementCheckResult",
    "CompareMode",
    "AIStrictness",
    "VerificationType",
    "Rect",
    # Runner
    "TestRunner",
    "run_test",
    "get_test_runs",
    "get_test_result",
    # Verifier
    "Verifier",
    # Comparator
    "ScreenshotComparator",
    "AIScreenshotComparator",
    # Reporter
    "TestReporter",
    "generate_report",
    # Script Generator
    "PlaywrightScriptGenerator",
    "generate_script",
    # AI Locator
    "AIElementLocator",
    "locate_and_click",
    "locate_and_fill",
    # AI State Verifier
    "AIStateVerifier",
    "StateVerificationResult",
    "CorrectionAction",
    "verify_form_state",
    # AI Debug Controller
    "AIDebugController",
    "DebugAction",
    "StepAnalysis",
    "FailureDiagnosis",
]
