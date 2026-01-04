"""
AI视觉元素定位器

当CSS选择器失败时，使用AI多模态能力来定位页面元素。
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LocatorResult:
    """定位结果"""
    success: bool
    x: int = 0
    y: int = 0
    confidence: float = 0.0
    element_description: str = ""
    error: Optional[str] = None


class AIElementLocator:
    """
    AI视觉元素定位器

    使用AI多模态模型分析截图，定位需要点击的元素位置。
    """

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None):
        """
        初始化定位器

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

    async def locate_element(
        self,
        screenshot_path: Path,
        action_description: str,
        element_text: Optional[str] = None,
        action_type: str = "click",
    ) -> LocatorResult:
        """
        使用AI定位页面元素

        Args:
            screenshot_path: 当前页面截图路径
            action_description: 动作描述（如"点击登录按钮"）
            element_text: 元素文本（可选）
            action_type: 动作类型（click, fill等）

        Returns:
            LocatorResult: 定位结果，包含坐标
        """
        if not screenshot_path.exists():
            return LocatorResult(
                success=False,
                error=f"Screenshot not found: {screenshot_path}"
            )

        # 读取并编码图片
        with open(screenshot_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 构建提示词
        prompt = self._build_prompt(action_description, element_text, action_type)

        try:
            if self.provider == "gemini":
                return await self._locate_with_gemini(image_data, prompt)
            elif self.provider == "claude":
                return await self._locate_with_claude(image_data, prompt)
            elif self.provider == "openai":
                return await self._locate_with_openai(image_data, prompt)
            else:
                return LocatorResult(
                    success=False,
                    error=f"Unsupported provider: {self.provider}"
                )
        except Exception as e:
            logger.error(f"AI定位失败: {e}")
            return LocatorResult(success=False, error=str(e))

    def _build_prompt(
        self,
        action_description: str,
        element_text: Optional[str],
        action_type: str,
    ) -> str:
        """构建AI提示词"""
        text_hint = f'\n元素可能包含文本: "{element_text}"' if element_text else ""

        return f"""分析这张网页截图，找到需要{action_type}的元素位置。

任务描述: {action_description}{text_hint}

请仔细分析截图，找到与描述最匹配的可点击元素（按钮、链接、输入框等）。

返回JSON格式:
{{
    "found": true/false,
    "x": 元素中心的X坐标(像素),
    "y": 元素中心的Y坐标(像素),
    "confidence": 置信度(0-1),
    "element_description": "找到的元素描述"
}}

注意:
1. 坐标是相对于图片左上角的像素坐标
2. 返回元素的中心点坐标
3. 如果找不到匹配的元素，设置found为false
4. 只返回JSON，不要其他文字"""

    async def _locate_with_gemini(self, image_data: str, prompt: str) -> LocatorResult:
        """使用Gemini定位元素"""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return LocatorResult(
                success=False,
                error="google-genai package not installed"
            )

        if not self.api_key:
            return LocatorResult(
                success=False,
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
        return self._parse_response(response.text)

    async def _locate_with_claude(self, image_data: str, prompt: str) -> LocatorResult:
        """使用Claude定位元素"""
        try:
            import anthropic
        except ImportError:
            return LocatorResult(
                success=False,
                error="anthropic package not installed"
            )

        if not self.api_key:
            return LocatorResult(
                success=False,
                error="ANTHROPIC_API_KEY not set"
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
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

        return self._parse_response(message.content[0].text)

    async def _locate_with_openai(self, image_data: str, prompt: str) -> LocatorResult:
        """使用OpenAI GPT-4V定位元素"""
        try:
            import openai
        except ImportError:
            return LocatorResult(
                success=False,
                error="openai package not installed"
            )

        if not self.api_key:
            return LocatorResult(
                success=False,
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
            max_tokens=1024,
        )

        return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, response_text: str) -> LocatorResult:
        """解析AI响应"""
        try:
            # 尝试提取JSON
            text = response_text.strip()

            # 处理markdown代码块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            if data.get("found", False):
                return LocatorResult(
                    success=True,
                    x=int(data.get("x", 0)),
                    y=int(data.get("y", 0)),
                    confidence=float(data.get("confidence", 0.0)),
                    element_description=data.get("element_description", ""),
                )
            else:
                return LocatorResult(
                    success=False,
                    error="Element not found in screenshot"
                )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {response_text}")
            return LocatorResult(
                success=False,
                error=f"Invalid JSON response: {e}"
            )
        except Exception as e:
            return LocatorResult(
                success=False,
                error=f"Parse error: {e}"
            )


async def locate_and_click(
    page,
    screenshot_path: Path,
    action_description: str,
    element_text: Optional[str] = None,
    provider: str = "gemini",
    api_key: Optional[str] = None,
) -> bool:
    """
    便捷函数：使用AI定位并点击元素

    Args:
        page: Playwright页面对象
        screenshot_path: 截图路径
        action_description: 动作描述
        element_text: 元素文本
        provider: AI提供商
        api_key: API密钥

    Returns:
        bool: 是否成功点击
    """
    locator = AIElementLocator(provider=provider, api_key=api_key)
    result = await locator.locate_element(
        screenshot_path=screenshot_path,
        action_description=action_description,
        element_text=element_text,
        action_type="click",
    )

    if result.success:
        logger.info(f"AI定位成功: ({result.x}, {result.y}) - {result.element_description}")
        await page.mouse.click(result.x, result.y)
        return True
    else:
        logger.warning(f"AI定位失败: {result.error}")
        return False


async def locate_and_fill(
    page,
    screenshot_path: Path,
    action_description: str,
    value: str,
    element_text: Optional[str] = None,
    provider: str = "gemini",
    api_key: Optional[str] = None,
) -> bool:
    """
    便捷函数：使用AI定位输入框并填充

    Args:
        page: Playwright页面对象
        screenshot_path: 截图路径
        action_description: 动作描述
        value: 要填充的值
        element_text: 元素文本
        provider: AI提供商
        api_key: API密钥

    Returns:
        bool: 是否成功填充
    """
    locator = AIElementLocator(provider=provider, api_key=api_key)
    result = await locator.locate_element(
        screenshot_path=screenshot_path,
        action_description=action_description,
        element_text=element_text,
        action_type="fill",
    )

    if result.success:
        logger.info(f"AI定位输入框: ({result.x}, {result.y}) - {result.element_description}")
        # 点击输入框
        await page.mouse.click(result.x, result.y)
        # 清空并输入
        await page.keyboard.press("Control+a")
        await page.keyboard.type(value)
        return True
    else:
        logger.warning(f"AI定位失败: {result.error}")
        return False
