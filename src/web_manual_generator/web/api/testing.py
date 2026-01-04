"""测试执行API端点"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ...project import ProjectManager
from ...testing import (
    TestConfig,
    TestRunner,
    TestResult,
    TestStatus,
    CompareMode,
    AIStrictness,
    get_test_runs,
    get_test_result,
    generate_report,
    generate_script,
)
from ...testing.ai_debug_controller import DebugAction

logger = logging.getLogger(__name__)
router = APIRouter()

# 存储运行中的测试
_running_tests: Dict[str, Dict[str, Any]] = {}


class TestRunRequest(BaseModel):
    """测试运行请求"""
    screenshot_compare: bool = Field(True, description="启用截图对比")
    screenshot_compare_mode: str = Field("pixel", description="对比模式: pixel | ai")
    element_check: bool = Field(True, description="启用元素检查")
    threshold: float = Field(0.10, description="像素差异阈值")
    ai_strictness: str = Field("normal", description="AI严格程度: lenient | normal | strict")
    headless: bool = Field(True, description="无头模式")
    step_delay: float = Field(0.5, description="步骤间延迟(秒)")
    start_from_step: int = Field(1, description="从第几步开始验证（之前的步骤快速回放）")
    # AI相关配置
    ai_provider: str = Field("gemini", description="AI提供商: gemini | claude | openai")
    google_api_key: Optional[str] = Field(None, description="Google API Key (用于Gemini)")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API Key (用于Claude)")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API Key")
    # Debug模式配置
    debug_mode: bool = Field(False, description="启用调试模式（单步执行）")
    ai_in_the_loop: bool = Field(False, description="AI全程参与分析")
    ai_auto_skip: bool = Field(True, description="AI自动跳过不必要的步骤")
    ai_auto_fix: bool = Field(True, description="AI自动修复失败的选择器")
    pause_on_failure: bool = Field(True, description="步骤失败时暂停等待用户决策")
    max_auto_retries: int = Field(2, description="自动重试次数")
    # 测试变量（用于密码等敏感信息）
    # 格式: {"#password": "value", "密码": "value"}
    test_variables: Dict[str, str] = Field(default_factory=dict, description="测试变量（如密码）")


class TestRunResponse(BaseModel):
    """测试运行响应"""
    test_id: str
    status: str
    message: str


class TestStatusResponse(BaseModel):
    """测试状态响应"""
    test_id: str
    status: str
    current_step: int
    total_steps: int
    current_step_description: str = ""
    progress_percent: int = 0


class TestResultResponse(BaseModel):
    """测试结果响应"""
    test_id: str
    status: str
    success: bool
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_ms: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    steps: list


class TestRunInfo(BaseModel):
    """测试运行信息"""
    test_id: str
    status: str
    success: bool
    total_steps: int
    passed_steps: int
    failed_steps: int
    started_at: Optional[str]
    run_dir: str


@router.post("/run/{project_id}/{recording_id}", response_model=TestRunResponse)
async def run_test(
    project_id: str,
    recording_id: str,
    request: TestRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    启动测试执行

    异步执行测试，返回测试ID用于查询状态
    """
    manager = ProjectManager()

    # 验证项目和录制存在
    project = manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 '{project_id}' 不存在")

    recording = manager.get_recording(project_id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail=f"录制 '{recording_id}' 不存在")

    recording_dir = manager.get_recording_dir(project_id, recording_id)

    # 设置API密钥到环境变量（如果提供）
    api_keys = {}
    if request.google_api_key:
        api_keys["GOOGLE_API_KEY"] = request.google_api_key
        os.environ["GOOGLE_API_KEY"] = request.google_api_key
    if request.anthropic_api_key:
        api_keys["ANTHROPIC_API_KEY"] = request.anthropic_api_key
        os.environ["ANTHROPIC_API_KEY"] = request.anthropic_api_key
    if request.openai_api_key:
        api_keys["OPENAI_API_KEY"] = request.openai_api_key
        os.environ["OPENAI_API_KEY"] = request.openai_api_key

    # 构建配置
    config = TestConfig(
        screenshot_compare=request.screenshot_compare,
        screenshot_compare_mode=CompareMode(request.screenshot_compare_mode),
        element_check=request.element_check,
        threshold=request.threshold,
        ai_provider=request.ai_provider,
        ai_strictness=AIStrictness(request.ai_strictness),
        ai_fallback_provider=request.ai_provider,
        ai_state_verify_provider=request.ai_provider,
        headless=request.headless,
        step_delay=request.step_delay,
        start_from_step=request.start_from_step,
        # Debug模式配置
        debug_mode=request.debug_mode,
        ai_in_the_loop=request.ai_in_the_loop,
        ai_auto_skip=request.ai_auto_skip,
        ai_auto_fix=request.ai_auto_fix,
        pause_on_failure=request.pause_on_failure,
        max_auto_retries=request.max_auto_retries,
        # 测试变量
        test_variables=request.test_variables,
    )

    # 创建测试运行器
    runner = TestRunner(
        project_id=project_id,
        recording_id=recording_id,
        recording_dir=recording_dir,
        config=config,
    )

    test_id = runner.test_id

    # 存储运行状态
    _running_tests[test_id] = {
        "runner": runner,
        "status": TestStatus.PENDING,
        "current_step": 0,
        "total_steps": 0,
        "current_step_description": "",
        "result": None,
    }

    # 后台执行测试
    background_tasks.add_task(_execute_test, test_id, runner)

    return TestRunResponse(
        test_id=test_id,
        status="running",
        message="测试已启动",
    )


async def _execute_test(test_id: str, runner: TestRunner):
    """后台执行测试"""
    try:
        # 设置进度回调
        def progress_callback(progress):
            if test_id in _running_tests:
                _running_tests[test_id].update({
                    "status": progress.status,
                    "current_step": progress.current_step,
                    "total_steps": progress.total_steps,
                    "current_step_description": progress.current_step_description,
                    "current_action_type": progress.current_action_type,
                })

        runner.progress_callback = progress_callback

        # 执行测试
        result = await runner.run()

        # 生成报告
        if result.steps:
            generate_report(runner.test_run_dir, result)

        # 更新结果
        if test_id in _running_tests:
            _running_tests[test_id]["result"] = result
            _running_tests[test_id]["status"] = result.status

    except Exception as e:
        logger.exception(f"测试执行失败: {e}")
        if test_id in _running_tests:
            _running_tests[test_id]["status"] = TestStatus.FAILED
            _running_tests[test_id]["error"] = str(e)


@router.get("/status/{test_id}", response_model=TestStatusResponse)
async def get_test_status(test_id: str):
    """
    获取测试执行状态
    """
    if test_id not in _running_tests:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_info = _running_tests[test_id]
    total_steps = test_info.get("total_steps", 0)
    current_step = test_info.get("current_step", 0)

    return TestStatusResponse(
        test_id=test_id,
        status=test_info["status"].value if isinstance(test_info["status"], TestStatus) else test_info["status"],
        current_step=current_step,
        total_steps=total_steps,
        current_step_description=test_info.get("current_step_description", ""),
        progress_percent=int(current_step / total_steps * 100) if total_steps > 0 else 0,
    )


@router.get("/result/{test_id}", response_model=TestResultResponse)
async def get_test_result_api(test_id: str):
    """
    获取测试执行结果
    """
    if test_id not in _running_tests:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_info = _running_tests[test_id]
    result: TestResult = test_info.get("result")

    if not result:
        status = test_info["status"]
        if isinstance(status, TestStatus) and status in (TestStatus.PENDING, TestStatus.RUNNING):
            raise HTTPException(status_code=202, detail="测试仍在执行中")
        raise HTTPException(status_code=500, detail="测试结果不可用")

    return TestResultResponse(
        test_id=result.test_id,
        status=result.status.value,
        success=result.success,
        total_steps=result.total_steps,
        passed_steps=result.passed_steps,
        failed_steps=result.failed_steps,
        duration_ms=result.duration_ms,
        started_at=result.started_at.isoformat() if result.started_at else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        error_message=result.error_message,
        steps=[s.to_dict() for s in result.steps],
    )


@router.post("/cancel/{test_id}")
async def cancel_test(test_id: str):
    """
    取消正在执行的测试
    """
    if test_id not in _running_tests:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_info = _running_tests[test_id]
    runner: TestRunner = test_info.get("runner")

    if runner:
        runner.cancel()

    return {"message": "取消请求已发送"}


class DebugActionRequest(BaseModel):
    """Debug模式操作请求"""
    action: str = Field(..., description="操作: continue | retry | skip | modify | abort")
    new_selector: Optional[str] = Field(None, description="新选择器（当action=modify时）")
    user_ai_prompt: Optional[str] = Field(None, description="用户自定义AI提示词")


@router.post("/debug/{test_id}")
async def send_debug_action(test_id: str, request: DebugActionRequest):
    """
    发送Debug模式操作

    在测试暂停等待用户决策时，通过此API发送操作指令：
    - continue: 继续执行下一步
    - retry: 重试当前失败的步骤
    - skip: 跳过当前步骤
    - modify: 使用新选择器重试（需提供new_selector）
    - abort: 终止测试
    """
    if test_id not in _running_tests:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_info = _running_tests[test_id]
    runner: TestRunner = test_info.get("runner")

    if not runner:
        raise HTTPException(status_code=400, detail="测试运行器不可用")

    # 转换action字符串为DebugAction枚举
    try:
        action = DebugAction(request.action)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的action: {request.action}. 有效值: continue, retry, skip, modify, abort"
        )

    # 设置用户AI提示词（如果有）
    if request.user_ai_prompt is not None:
        runner.user_ai_prompt = request.user_ai_prompt

    # 发送操作到runner
    runner.set_debug_action(action, request.new_selector)

    return {
        "message": f"Debug操作已发送: {request.action}",
        "action": request.action,
        "new_selector": request.new_selector,
        "user_ai_prompt": request.user_ai_prompt,
    }


@router.get("/debug/status/{test_id}")
async def get_debug_status(test_id: str):
    """
    获取Debug模式状态

    返回当前测试是否处于暂停状态，以及暂停原因
    """
    if test_id not in _running_tests:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_info = _running_tests[test_id]
    runner: TestRunner = test_info.get("runner")

    if not runner:
        return {"paused": False, "debug_mode": False}

    ai_analysis = None
    if runner._current_ai_analysis:
        ai_analysis = runner._current_ai_analysis.to_dict()

    return {
        "paused": runner._debug_paused,
        "debug_mode": runner.config.debug_mode if runner.config else False,
        "ai_in_the_loop": runner.config.ai_in_the_loop if runner.config else False,
        "pending_selector_fix": runner._pending_selector_fix,
        "waiting_for_confirmation": runner._waiting_for_confirmation,
        "current_step": test_info.get("current_step", 0),
        "current_step_description": test_info.get("current_step_description", ""),
        "ai_analysis": ai_analysis,
        "user_ai_prompt": runner.user_ai_prompt,
    }


@router.get("/runs/{project_id}/{recording_id}", response_model=list[TestRunInfo])
async def list_test_runs(project_id: str, recording_id: str):
    """
    获取录制的所有测试运行记录
    """
    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_id, recording_id)

    if not recording_dir.exists():
        raise HTTPException(status_code=404, detail=f"录制 '{recording_id}' 不存在")

    runs = get_test_runs(recording_dir)

    return [
        TestRunInfo(
            test_id=run.get("test_id", "unknown"),
            status=run.get("status", "unknown"),
            success=run.get("success", False),
            total_steps=run.get("total_steps", 0),
            passed_steps=run.get("passed_steps", 0),
            failed_steps=run.get("failed_steps", 0),
            started_at=run.get("started_at"),
            run_dir=run.get("run_dir", ""),
        )
        for run in runs
    ]


@router.get("/report/{project_id}/{recording_id}/{test_id}")
async def get_test_report(project_id: str, recording_id: str, test_id: str):
    """
    获取测试报告HTML
    """
    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_id, recording_id)
    test_runs_dir = recording_dir / "test_runs"

    if not test_runs_dir.exists():
        raise HTTPException(status_code=404, detail="没有测试运行记录")

    # 查找测试运行目录
    matching = [d for d in test_runs_dir.iterdir() if test_id in d.name]
    if not matching:
        raise HTTPException(status_code=404, detail=f"测试 '{test_id}' 不存在")

    test_run_dir = matching[0]
    report_path = test_run_dir / "report.html"

    # 如果报告不存在，生成它
    if not report_path.exists():
        result_path = test_run_dir / "test_result.json"
        if result_path.exists():
            generate_report(test_run_dir)
        else:
            raise HTTPException(status_code=404, detail="测试结果不存在")

    if not report_path.exists():
        raise HTTPException(status_code=500, detail="无法生成报告")

    # 返回报告内容
    from fastapi.responses import HTMLResponse
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@router.get("/export/{project_id}/{recording_id}")
async def export_script(
    project_id: str,
    recording_id: str,
    language: str = "zh",
    headless: bool = False,
    step_delay: float = 0.5,
):
    """
    导出 Playwright Python 脚本

    Args:
        project_id: 项目ID
        recording_id: 录制ID
        language: 注释语言 (zh/en/ja)
        headless: 是否默认无头模式
        step_delay: 步骤间延迟（秒）

    Returns:
        Python 脚本文件下载
    """
    manager = ProjectManager()
    recording_dir = manager.get_recording_dir(project_id, recording_id)
    action_log_path = recording_dir / "action_log.json"

    if not action_log_path.exists():
        raise HTTPException(status_code=404, detail=f"录制 '{recording_id}' 不存在")

    try:
        script_content = generate_script(
            action_log_path=action_log_path,
            language=language,
            headless=headless,
            step_delay=step_delay,
        )
    except Exception as e:
        logger.exception(f"生成脚本失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成脚本失败: {str(e)}")

    # 生成文件名
    safe_name = recording_id.replace(" ", "_").replace("-", "_")
    filename = f"test_{safe_name}.py"

    from fastapi.responses import Response
    return Response(
        content=script_content,
        media_type="text/x-python",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.websocket("/ws/{test_id}")
async def test_progress_websocket(websocket: WebSocket, test_id: str):
    """
    WebSocket 实时测试进度更新
    """
    await websocket.accept()

    try:
        while True:
            if test_id not in _running_tests:
                await websocket.send_json({"error": "测试不存在"})
                break

            test_info = _running_tests[test_id]
            status = test_info["status"]

            if isinstance(status, TestStatus):
                status_value = status.value
            else:
                status_value = str(status)

            total_steps = test_info.get("total_steps", 0)
            current_step = test_info.get("current_step", 0)

            # 获取debug模式状态
            runner: TestRunner = test_info.get("runner")
            debug_info = {}
            ai_analysis_data = None
            if runner:
                debug_info = {
                    "debug_mode": runner.config.debug_mode if runner.config else False,
                    "debug_paused": runner._debug_paused,
                    "ai_in_the_loop": runner.config.ai_in_the_loop if runner.config else False,
                    "pending_selector_fix": runner._pending_selector_fix,
                    "waiting_for_confirmation": runner._waiting_for_confirmation,
                }
                # 添加AI分析结果
                if runner._current_ai_analysis:
                    ai_analysis_data = runner._current_ai_analysis.to_dict()

            await websocket.send_json({
                "test_id": test_id,
                "status": status_value,
                "current_step": current_step,
                "total_steps": total_steps,
                "current_step_description": test_info.get("current_step_description", ""),
                "action_type": test_info.get("current_action_type", ""),
                "progress_percent": int(current_step / total_steps * 100) if total_steps > 0 else 0,
                "ai_analysis": ai_analysis_data,
                **debug_info,
            })

            # 检查是否完成
            if status in (TestStatus.COMPLETED, TestStatus.FAILED, TestStatus.CANCELLED):
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开连接: {test_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
    finally:
        await websocket.close()
