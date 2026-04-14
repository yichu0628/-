"""
大模型解析模块
支持阶跃星辰视觉模型直接解析截图或 OCR + 文本解析

阶跃星辰 API 兼容 OpenAI SDK，迁移方式：
  client = OpenAI(
      api_key="STEP_API_KEY",
      base_url="https://api.stepfun.com/v1"
  )

视觉理解模型：
  - step-1o-turbo-vision : 推荐使用，速度快，视觉能力强
  - step-1o-vision-32k   : 更强视觉性能，上下文32k
  - step-1v              : 经典视觉模型

文档参考：
  https://platform.stepfun.com/docs/zh/guides/developer/openai
  https://platform.stepfun.com/docs/zh/guides/models/vision
"""

import os
import base64
import json
import re
from typing import Optional, List, Dict, Any

from openai import OpenAI


# 大模型解析 Prompt 模板
PARSE_PROMPT_TEMPLATE = """你是一个日程提取助手。请从以下截图内容中提取所有隐含的待办事项或日程。

要求：
1. 仔细分析截图中的文字、日期、时间等信息
2. 推断出可能的任务或日程安排
3. 如果有明确的截止时间，请准确提取
4. 优先级判断：紧急/重要为1，一般任务为2，不紧急为3

返回严格的JSON数组格式，不要包含任何其他文字：
[{"task": "任务简述", "deadline": "YYYY-MM-DD HH:MM", "priority": 1}]

如果提取不到任何任务，返回空列表：[]
"""


class MockOCR:
    """模拟 OCR 类，返回固定的示例文本"""

    def __init__(self):
        self.sample_texts = [
            """
            项目进度会议
            时间：2026-05-15 14:00
            地点：会议室A

            待办事项：
            1. 完成初赛作品提交 - 截止日期：2026-05-12 23:59
            2. 准备演示PPT - 截止日期：2026-05-14
            3. 代码审查 - 本周五前完成
            """,
            """
            本周任务清单：
            - 周一：提交周报
            - 周三：产品评审会议 10:00
            - 周五：项目里程碑检查
            """,
            """
            重要提醒：
            明天下午3点有客户演示
            请提前准备好演示环境
            """,
        ]
        self.current_index = 0

    def extract_text(self, image_path: str) -> str:
        """
        模拟从图片中提取文本

        Args:
            image_path: 图片路径

        Returns:
            模拟的 OCR 文本
        """
        # 轮流返回不同的示例文本
        text = self.sample_texts[self.current_index % len(self.sample_texts)]
        self.current_index += 1

        print(f"[模拟OCR] 从 {image_path} 提取文本（模拟数据）")
        return text.strip()


class LLMParser:
    """大模型解析器"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        use_vision: bool = True
    ):
        """
        初始化大模型解析器

        Args:
            base_url: API 基础地址
            api_key: API 密钥
            model: 模型名称
            use_vision: 是否使用视觉模型直接解析图片
        """
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.model = model
        self.use_vision = use_vision
        self.mock_ocr = MockOCR()

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _extract_json_from_response(self, response_text: str) -> List[Dict[str, Any]]:
        """从响应文本中提取 JSON 数组"""
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 数组
        json_pattern = r'\[\s*\{.*?\}\s*\]'
        matches = re.findall(json_pattern, response_text, re.DOTALL)

        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # 尝试提取多个 JSON 对象
        obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(obj_pattern, response_text, re.DOTALL)

        results = []
        for match in matches:
            try:
                obj = json.loads(match)
                if "task" in obj:
                    results.append(obj)
            except json.JSONDecodeError:
                continue

        return results

    def parse_with_vision(self, image_path: str) -> List[Dict[str, Any]]:
        """使用视觉模型直接解析图片"""
        try:
            base64_image = self._encode_image_to_base64(image_path)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": PARSE_PROMPT_TEMPLATE
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )

            response_text = response.choices[0].message.content
            print(f"[LLM] 响应: {response_text}")

            return self._extract_json_from_response(response_text)

        except Exception as e:
            print(f"[错误] 视觉模型解析失败: {e}")
            return []

    def parse_with_ocr_and_text(self, image_path: str) -> List[Dict[str, Any]]:
        """使用 OCR 提取文本后，再用文本模型解析"""
        try:
            # 使用模拟 OCR 提取文本
            ocr_text = self.mock_ocr.extract_text(image_path)
            print(f"[OCR] 提取文本:\n{ocr_text}")

            # 构建完整 prompt
            full_prompt = f"""{PARSE_PROMPT_TEMPLATE}

截图文本内容：
{ocr_text}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=1000
            )

            response_text = response.choices[0].message.content
            print(f"[LLM] 响应: {response_text}")

            return self._extract_json_from_response(response_text)

        except Exception as e:
            print(f"[错误] OCR+文本解析失败: {e}")
            return []

    def parse_screenshot(self, image_path: str) -> List[Dict[str, Any]]:
        """
        解析截图，提取任务列表

        Args:
            image_path: 截图文件路径

        Returns:
            任务列表，每个任务包含 task, deadline, priority 字段
        """
        if not os.path.exists(image_path):
            print(f"[错误] 图片文件不存在: {image_path}")
            return []

        print(f"[LLM] 开始解析截图: {image_path}")

        if self.use_vision:
            # 尝试使用视觉模型
            tasks = self.parse_with_vision(image_path)
            if tasks:
                return tasks

            # 如果视觉模型失败，回退到 OCR
            print("[LLM] 视觉模型解析失败，尝试 OCR 方式...")
            return self.parse_with_ocr_and_text(image_path)
        else:
            return self.parse_with_ocr_and_text(image_path)


def parse_screenshot(
    image_path: str,
    base_url: str = "https://api.stepfun.com/v1",
    api_key: str = "YOUR_API_KEY",
    model: str = "step-1o-turbo-vision",
    use_vision: bool = True
) -> List[Dict[str, Any]]:
    """
    解析截图的便捷函数

    Args:
        image_path: 截图文件路径
        base_url: API 基础地址（阶跃星辰：https://api.stepfun.com/v1）
        api_key: API 密钥（阶跃星辰平台创建）
        model: 模型名称（推荐 step-1o-turbo-vision）
        use_vision: 是否使用视觉模型

    Returns:
        任务列表
    """
    parser = LLMParser(
        base_url=base_url,
        api_key=api_key,
        model=model,
        use_vision=use_vision
    )
    return parser.parse_screenshot(image_path)


# 测试代码
if __name__ == "__main__":
    # 使用模拟数据测试
    parser = LLMParser(
        base_url="https://api.stepfun.com/v1",
        api_key="test_key",
        model="step-1o-turbo-vision",
        use_vision=False  # 测试时使用 OCR 模式
    )

    # 测试 OCR 模拟
    mock_ocr = MockOCR()
    text = mock_ocr.extract_text("test.png")
    print(f"OCR 文本: {text}")
