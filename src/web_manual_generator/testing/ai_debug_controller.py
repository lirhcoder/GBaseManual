"""
AI Debug Controller - AI-in-the-loop 调试控制器

在测试执行过程中，AI全程参与分析和决策：
1. 执行前分析：判断步骤是否需要执行、是否需要修改选择器
2. 执行失败处理：诊断失败原因、自动修复选择器
3. 智能跳过：识别可以跳过的步骤（如快速重定向）
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class DebugAction(Enum):
    """调试动作"""
    CONTINUE = "continue"  # 继续执行
    RETRY = "retry"  # 重试当前步骤
    SKIP = "skip"  # 跳过当前步骤
    MODIFY = "modify"  # 修改选择器后重试
    ABORT = "abort"  # 终止测试
    PAUSE = "pause"  # 暂停等待用户决策


@dataclass
class StepAnalysis:
    """步骤分析结果"""
    should_execute: bool = True  # 是否应该执行
    should_skip: bool = False  # 是否应该跳过
    skip_reason: Optional[str] = None  # 跳过原因
    suggested_selector: Optional[str] = None  # 建议的选择器
    suggested_action: Optional[str] = None  # 建议的动作修改
    confidence: float = 1.0  # 置信度
    warnings: List[str] = field(default_factory=list)  # 警告信息


@dataclass
class FailureDiagnosis:
    """失败诊断结果"""
    cause: str  # 失败原因
    can_auto_fix: bool = False  # 是否可以自动修复
    suggested_fix: Optional[str] = None  # 建议的修复方法
    new_selector: Optional[str] = None  # 新的选择器
    recommended_action: DebugAction = DebugAction.PAUSE  # 推荐的动作
    details: Dict[str, Any] = field(default_factory=dict)


class AIDebugController:
    """
    AI调试控制器

    在测试执行过程中提供智能分析和决策支持
    """

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)
        self._execution_context: List[Dict[str, Any]] = []  # 执行上下文历史

    def _get_api_key(self, provider: str) -> Optional[str]:
        """从环境变量获取API密钥"""
        key_map = {
            "gemini": "GOOGLE_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_var = key_map.get(provider)
        return os.getenv(env_var) if env_var else None

    async def analyze_step_before_execution(
        self,
        step_data: Dict[str, Any],
        previous_steps: List[Dict[str, Any]],
        current_screenshot: Optional[Path] = None,
    ) -> StepAnalysis:
        """
        在步骤执行前分析

        决定：
        1. 是否应该执行这个步骤
        2. 是否应该跳过（如快速重定向）
        3. 选择器是否需要修改
        """
        analysis = StepAnalysis()

        action = step_data.get("action", "")
        selector = step_data.get("selector", "")
        description = step_data.get("description", "")

        # 1. 检查是否是快速导航/重定向步骤
        if action == "navigate":
            # 检查是否是连续的导航步骤
            if previous_steps:
                last_step = previous_steps[-1]
                if last_step.get("action") == "navigate":
                    # 连续导航，检查是否是重定向
                    last_url = last_step.get("url", "")
                    current_url = step_data.get("url", "")

                    # 如果是同一域名的重定向或OAuth流程
                    if self._is_redirect_chain(last_url, current_url):
                        analysis.should_skip = True
                        analysis.skip_reason = f"检测到重定向链: {last_url} → {current_url}"
                        analysis.confidence = 0.8
                        return analysis

        # 2. 检查选择器是否可能有问题
        if selector and self._is_fragile_selector(selector):
            analysis.warnings.append(f"选择器可能不稳定: {selector}")
            # 尝试从描述生成更稳定的选择器
            if description:
                better_selector = self._suggest_better_selector(description, selector)
                if better_selector:
                    analysis.suggested_selector = better_selector
                    analysis.warnings.append(f"建议使用: {better_selector}")

        # 3. 如果有截图，使用AI分析页面状态
        if current_screenshot and current_screenshot.exists():
            ai_analysis = await self._ai_analyze_page_state(
                current_screenshot, step_data, previous_steps
            )
            if ai_analysis:
                if ai_analysis.get("should_skip"):
                    analysis.should_skip = True
                    analysis.skip_reason = ai_analysis.get("skip_reason", "AI建议跳过")
                if ai_analysis.get("suggested_selector"):
                    analysis.suggested_selector = ai_analysis["suggested_selector"]
                analysis.confidence = ai_analysis.get("confidence", 0.8)

        return analysis

    async def diagnose_failure(
        self,
        step_data: Dict[str, Any],
        error_message: str,
        screenshot: Optional[Path] = None,
    ) -> FailureDiagnosis:
        """
        诊断步骤失败原因并提供修复建议
        """
        diagnosis = FailureDiagnosis(cause=error_message)

        selector = step_data.get("selector", "")
        action = step_data.get("action", "")
        description = step_data.get("description", "")

        # 1. 分析错误类型
        if "timeout" in error_message.lower() or "not found" in error_message.lower():
            diagnosis.cause = "元素未找到或超时"

            # 尝试生成新选择器
            if description:
                new_selector = self._suggest_better_selector(description, selector)
                if new_selector and new_selector != selector:
                    diagnosis.can_auto_fix = True
                    diagnosis.new_selector = new_selector
                    diagnosis.suggested_fix = f"使用新选择器: {new_selector}"
                    diagnosis.recommended_action = DebugAction.MODIFY

        elif "detached" in error_message.lower() or "closed" in error_message.lower():
            diagnosis.cause = "页面已关闭或元素已分离"
            diagnosis.recommended_action = DebugAction.SKIP
            diagnosis.suggested_fix = "页面状态异常，建议跳过此步骤"

        elif "intercept" in error_message.lower():
            diagnosis.cause = "点击被其他元素拦截"
            diagnosis.suggested_fix = "可能有弹窗或覆盖层，需要先处理"
            diagnosis.recommended_action = DebugAction.RETRY

        # 2. 如果有截图，使用AI进行更深入的分析
        if screenshot and screenshot.exists():
            ai_diagnosis = await self._ai_diagnose_failure(
                screenshot, step_data, error_message
            )
            if ai_diagnosis:
                if ai_diagnosis.get("new_selector"):
                    diagnosis.new_selector = ai_diagnosis["new_selector"]
                    diagnosis.can_auto_fix = True
                if ai_diagnosis.get("cause"):
                    diagnosis.cause = ai_diagnosis["cause"]
                if ai_diagnosis.get("suggested_fix"):
                    diagnosis.suggested_fix = ai_diagnosis["suggested_fix"]
                diagnosis.details = ai_diagnosis

        return diagnosis

    async def suggest_selector_fix(
        self,
        screenshot: Path,
        step_data: Dict[str, Any],
        failed_selector: str,
    ) -> Optional[str]:
        """
        基于截图分析，建议新的选择器
        """
        if not screenshot.exists():
            return None

        description = step_data.get("description", "")
        action = step_data.get("action", "")

        # 首先尝试基于描述生成选择器
        text_selector = self._suggest_better_selector(description, failed_selector)
        if text_selector:
            return text_selector

        # 使用AI分析截图
        try:
            result = await self._ai_find_element(screenshot, description, action)
            if result and result.get("selector"):
                return result["selector"]
        except Exception as e:
            logger.warning(f"AI选择器建议失败: {e}")

        return None

    def _is_redirect_chain(self, url1: str, url2: str) -> bool:
        """检测是否是重定向链"""
        from urllib.parse import urlparse

        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # OAuth/SSO 重定向模式
        oauth_domains = ["auth0.com", "okta.com", "login.microsoftonline.com"]

        # 检查是否是OAuth流程
        if any(domain in parsed1.netloc or domain in parsed2.netloc for domain in oauth_domains):
            return True

        # 检查URL参数中是否有重定向标记
        redirect_params = ["redirect", "callback", "return", "state", "code"]
        if any(param in url2.lower() for param in redirect_params):
            return True

        return False

    def _is_fragile_selector(self, selector: str) -> bool:
        """检测选择器是否脆弱（容易失效）"""
        fragile_patterns = [
            ":nth-of-type(",  # 位置依赖
            ":nth-child(",
            " > ",  # 深层嵌套
            "mantine-",  # 框架动态类
            "css-",  # CSS-in-JS
            "sc-",  # Styled Components
        ]

        # 选择器太长通常意味着太脆弱
        if len(selector) > 100:
            return True

        return any(pattern in selector for pattern in fragile_patterns)

    def _suggest_better_selector(self, description: str, current_selector: str) -> Optional[str]:
        """基于描述建议更好的选择器"""
        # 从描述中提取文本
        text = None

        if "点击" in description:
            text = description.replace("点击", "").replace("(触发页面跳转)", "").strip()
        elif "输入" in description:
            # 输入操作通常保持原选择器
            return None

        if text and len(text) < 30:
            # 根据上下文生成选择器
            if "按钮" in description or "button" in current_selector.lower():
                return f'button:has-text("{text}")'
            elif "链接" in description or "a" in current_selector.lower():
                return f'a:has-text("{text}")'
            else:
                return f'text="{text}"'

        return None

    async def _ai_analyze_page_state(
        self,
        screenshot: Path,
        step_data: Dict[str, Any],
        previous_steps: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """使用AI分析页面状态"""
        if not self.api_key:
            return None

        try:
            with open(screenshot, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            prompt = f"""分析这张网页截图，判断以下操作是否应该执行：

待执行操作: {step_data.get('description', '')}
选择器: {step_data.get('selector', '')}
动作类型: {step_data.get('action', '')}

请分析：
1. 页面当前状态是否适合执行此操作？
2. 目标元素是否可见？
3. 是否应该跳过此步骤？

返回JSON格式:
{{
    "should_execute": true/false,
    "should_skip": true/false,
    "skip_reason": "跳过原因（如果应该跳过）",
    "element_visible": true/false,
    "suggested_selector": "建议的选择器（如果当前选择器有问题）",
    "confidence": 0.0-1.0
}}

只返回JSON，不要其他内容。"""

            return await self._call_ai(image_data, prompt)
        except Exception as e:
            logger.warning(f"AI页面分析失败: {e}")
            return None

    async def _ai_diagnose_failure(
        self,
        screenshot: Path,
        step_data: Dict[str, Any],
        error_message: str,
    ) -> Optional[Dict[str, Any]]:
        """使用AI诊断失败原因"""
        if not self.api_key:
            return None

        try:
            with open(screenshot, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            prompt = f"""分析这张网页截图，诊断操作失败的原因：

失败的操作: {step_data.get('description', '')}
选择器: {step_data.get('selector', '')}
错误信息: {error_message}

请分析：
1. 目标元素是否存在？在哪里？
2. 失败的可能原因是什么？
3. 如何修复？

返回JSON格式:
{{
    "cause": "失败原因",
    "element_found": true/false,
    "element_location": "元素位置描述",
    "new_selector": "建议的新选择器",
    "suggested_fix": "修复建议",
    "can_retry": true/false
}}

只返回JSON，不要其他内容。"""

            return await self._call_ai(image_data, prompt)
        except Exception as e:
            logger.warning(f"AI诊断失败: {e}")
            return None

    async def _ai_find_element(
        self,
        screenshot: Path,
        description: str,
        action: str,
    ) -> Optional[Dict[str, Any]]:
        """使用AI在截图中定位元素并建议选择器"""
        if not self.api_key:
            return None

        try:
            with open(screenshot, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            prompt = f"""在这张网页截图中找到需要操作的元素：

操作描述: {description}
动作类型: {action}

请找到目标元素并提供：
1. 元素在页面上的位置
2. 建议的Playwright选择器
3. 元素的文本内容（如果有）

返回JSON格式:
{{
    "found": true/false,
    "selector": "建议的选择器（如 button:has-text('登录')）",
    "element_text": "元素文本",
    "x": 元素中心X坐标,
    "y": 元素中心Y坐标,
    "confidence": 0.0-1.0
}}

只返回JSON，不要其他内容。"""

            return await self._call_ai(image_data, prompt)
        except Exception as e:
            logger.warning(f"AI元素定位失败: {e}")
            return None

    async def _call_ai(self, image_data: str, prompt: str) -> Optional[Dict[str, Any]]:
        """调用AI API"""
        try:
            if self.provider == "gemini":
                return await self._call_gemini(image_data, prompt)
            elif self.provider == "claude":
                return await self._call_claude(image_data, prompt)
            elif self.provider == "openai":
                return await self._call_openai(image_data, prompt)
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
        return None

    async def _call_gemini(self, image_data: str, prompt: str) -> Optional[Dict[str, Any]]:
        """调用Gemini API"""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.error("google-genai package not installed")
            return None

        client = genai.Client(api_key=self.api_key)
        image_part = types.Part.from_bytes(
            data=base64.b64decode(image_data),
            mime_type="image/png"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[prompt, image_part]
        )

        return self._parse_json_response(response.text)

    async def _call_claude(self, image_data: str, prompt: str) -> Optional[Dict[str, Any]]:
        """调用Claude API"""
        try:
            import anthropic
        except ImportError:
            logger.error("anthropic package not installed")
            return None

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                    {"type": "text", "text": prompt}
                ],
            }],
        )

        return self._parse_json_response(message.content[0].text)

    async def _call_openai(self, image_data: str, prompt: str) -> Optional[Dict[str, Any]]:
        """调用OpenAI API"""
        try:
            import openai
        except ImportError:
            logger.error("openai package not installed")
            return None

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ],
            }],
            max_tokens=1024,
        )

        return self._parse_json_response(response.choices[0].message.content)

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """解析AI返回的JSON"""
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return None

    def add_execution_context(self, step_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """添加执行上下文，用于后续分析"""
        self._execution_context.append({
            "step": step_data,
            "result": result,
        })
        # 保留最近20步的上下文
        if len(self._execution_context) > 20:
            self._execution_context.pop(0)

    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        total = len(self._execution_context)
        passed = sum(1 for ctx in self._execution_context if ctx["result"].get("passed"))
        failed = total - passed

        return {
            "total_executed": total,
            "passed": passed,
            "failed": failed,
            "recent_failures": [
                ctx for ctx in self._execution_context[-5:]
                if not ctx["result"].get("passed")
            ],
        }
