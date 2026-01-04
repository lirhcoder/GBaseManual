"""
AI状态验证器

在执行操作后使用AI验证页面状态是否符合预期，
如果状态不一致则自动生成并执行修正操作。
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class CorrectionAction:
    """修正操作"""
    action_type: str  # click, fill, select
    description: str  # 操作描述
    target_description: str  # 目标元素描述
    value: Optional[str] = None  # fill操作的值
    x: int = 0  # 点击坐标X
    y: int = 0  # 点击坐标Y
    confidence: float = 0.0  # 置信度


@dataclass
class StateVerificationResult:
    """状态验证结果"""
    verified: bool  # 状态是否符合预期
    matches_expected: bool  # 当前状态是否与预期匹配
    current_state: str  # 当前状态描述
    expected_state: str  # 预期状态描述
    discrepancies: List[str] = field(default_factory=list)  # 差异列表
    corrections: List[CorrectionAction] = field(default_factory=list)  # 建议的修正操作
    error: Optional[str] = None  # 错误信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "matches_expected": self.matches_expected,
            "current_state": self.current_state,
            "expected_state": self.expected_state,
            "discrepancies": self.discrepancies,
            "corrections": [
                {
                    "action_type": c.action_type,
                    "description": c.description,
                    "target_description": c.target_description,
                    "value": c.value,
                    "x": c.x,
                    "y": c.y,
                    "confidence": c.confidence,
                }
                for c in self.corrections
            ],
            "error": self.error,
        }


class AIStateVerifier:
    """
    AI状态验证器

    使用AI视觉模型分析页面截图，验证操作后的状态是否正确，
    并在状态不一致时生成修正操作。
    """

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None):
        """
        初始化验证器

        Args:
            provider: AI提供商 (gemini, claude, openai)
            api_key: API密钥（可选，默认从环境变量获取）
        """
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)

    def _get_api_key(self, provider: str) -> Optional[str]:
        """从环境变量获取API密钥"""
        key_map = {
            "gemini": "GOOGLE_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_var = key_map.get(provider)
        if env_var:
            return os.getenv(env_var)
        return None

    async def verify_state(
        self,
        screenshot_path: Path,
        action_description: str,
        expected_result: str,
        form_context: Optional[Dict[str, Any]] = None,
    ) -> StateVerificationResult:
        """
        验证页面状态

        Args:
            screenshot_path: 当前页面截图路径
            action_description: 刚执行的操作描述
            expected_result: 预期的结果状态
            form_context: 表单上下文（包含已填写的字段值等）

        Returns:
            StateVerificationResult: 验证结果
        """
        if not screenshot_path.exists():
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error=f"Screenshot not found: {screenshot_path}"
            )

        # 读取并编码图片
        with open(screenshot_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 构建提示词
        prompt = self._build_verification_prompt(
            action_description, expected_result, form_context
        )

        try:
            if self.provider == "gemini":
                return await self._verify_with_gemini(image_data, prompt, expected_result)
            elif self.provider == "claude":
                return await self._verify_with_claude(image_data, prompt, expected_result)
            elif self.provider == "openai":
                return await self._verify_with_openai(image_data, prompt, expected_result)
            else:
                return StateVerificationResult(
                    verified=False,
                    matches_expected=False,
                    current_state="",
                    expected_state=expected_result,
                    error=f"Unsupported provider: {self.provider}"
                )
        except Exception as e:
            logger.error(f"AI状态验证失败: {e}")
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error=str(e)
            )

    def _build_verification_prompt(
        self,
        action_description: str,
        expected_result: str,
        form_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建验证提示词"""
        context_str = ""
        if form_context:
            context_str = f"""
之前已完成的操作:
{json.dumps(form_context, ensure_ascii=False, indent=2)}
"""

        return f"""分析这张网页截图，验证页面当前状态是否符合预期。

刚执行的操作: {action_description}
预期结果: {expected_result}
{context_str}

请仔细分析截图中的:
1. 表单字段的当前值
2. 下拉框/选择框的当前选项
3. 单选按钮/复选框的选中状态
4. 是否有错误提示或模态框
5. 整体UI状态

返回JSON格式:
{{
    "matches_expected": true/false,
    "current_state": "当前页面状态的详细描述",
    "discrepancies": ["差异1", "差异2"],
    "corrections": [
        {{
            "action_type": "click/fill/select",
            "description": "需要执行的修正操作描述",
            "target_description": "目标元素描述（如'Agent类型单选按钮'）",
            "value": "fill操作时需要输入的值",
            "x": 目标元素中心X坐标,
            "y": 目标元素中心Y坐标,
            "confidence": 置信度(0-1)
        }}
    ]
}}

注意:
1. 仔细检查表单选项是否正确（特别是类型选择、模式选择等）
2. 如果发现状态不符，提供具体的修正操作和元素坐标
3. corrections数组可以包含多个修正操作，按执行顺序排列
4. 如果状态符合预期，corrections应为空数组
5. 只返回JSON，不要其他文字"""

    async def _verify_with_gemini(
        self, image_data: str, prompt: str, expected_result: str
    ) -> StateVerificationResult:
        """使用Gemini验证状态"""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="google-genai package not installed"
            )

        if not self.api_key:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="GOOGLE_API_KEY not set"
            )

        client = genai.Client(api_key=self.api_key)

        # 创建图片对象
        image_part = types.Part.from_bytes(
            data=base64.b64decode(image_data),
            mime_type="image/png"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[prompt, image_part]
        )
        return self._parse_response(response.text, expected_result)

    async def _verify_with_claude(
        self, image_data: str, prompt: str, expected_result: str
    ) -> StateVerificationResult:
        """使用Claude验证状态"""
        try:
            import anthropic
        except ImportError:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="anthropic package not installed"
            )

        if not self.api_key:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="ANTHROPIC_API_KEY not set"
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        return self._parse_response(message.content[0].text, expected_result)

    async def _verify_with_openai(
        self, image_data: str, prompt: str, expected_result: str
    ) -> StateVerificationResult:
        """使用OpenAI GPT-4V验证状态"""
        try:
            import openai
        except ImportError:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="openai package not installed"
            )

        if not self.api_key:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error="OPENAI_API_KEY not set"
            )

        client = openai.OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ],
                }
            ],
            max_tokens=2048,
        )

        return self._parse_response(
            response.choices[0].message.content, expected_result
        )

    def _parse_response(
        self, response_text: str, expected_result: str
    ) -> StateVerificationResult:
        """解析AI响应"""
        try:
            text = response_text.strip()

            # 处理markdown代码块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            # 解析修正操作
            corrections = []
            for c in data.get("corrections", []):
                corrections.append(CorrectionAction(
                    action_type=c.get("action_type", "click"),
                    description=c.get("description", ""),
                    target_description=c.get("target_description", ""),
                    value=c.get("value"),
                    x=int(c.get("x", 0)),
                    y=int(c.get("y", 0)),
                    confidence=float(c.get("confidence", 0.0)),
                ))

            return StateVerificationResult(
                verified=True,
                matches_expected=data.get("matches_expected", False),
                current_state=data.get("current_state", ""),
                expected_state=expected_result,
                discrepancies=data.get("discrepancies", []),
                corrections=corrections,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {response_text}")
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error=f"Invalid JSON response: {e}"
            )
        except Exception as e:
            return StateVerificationResult(
                verified=False,
                matches_expected=False,
                current_state="",
                expected_state=expected_result,
                error=f"Parse error: {e}"
            )


async def verify_form_state(
    page,
    screenshot_path: Path,
    action_description: str,
    expected_result: str,
    form_context: Optional[Dict[str, Any]] = None,
    provider: str = "gemini",
    api_key: Optional[str] = None,
    auto_correct: bool = True,
) -> StateVerificationResult:
    """
    便捷函数：验证表单状态并可选自动修正

    Args:
        page: Playwright页面对象
        screenshot_path: 截图路径
        action_description: 刚执行的操作
        expected_result: 预期结果
        form_context: 表单上下文
        provider: AI提供商
        api_key: API密钥
        auto_correct: 是否自动执行修正

    Returns:
        StateVerificationResult: 验证结果
    """
    import asyncio

    verifier = AIStateVerifier(provider=provider, api_key=api_key)
    result = await verifier.verify_state(
        screenshot_path=screenshot_path,
        action_description=action_description,
        expected_result=expected_result,
        form_context=form_context,
    )

    if result.verified and not result.matches_expected and auto_correct:
        # 状态不匹配，执行修正操作
        for correction in result.corrections:
            logger.info(
                f"执行修正操作: {correction.description} "
                f"({correction.action_type} at {correction.x}, {correction.y})"
            )

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

    return result
