"""
语音交互模块
负责麦克风识别、语音指令解析和大模型回复生成。
"""

import subprocess
from typing import Dict, Optional

from openai import OpenAI


class WindowsVoiceRecognizer:
    """基于 Windows System.Speech 的单次语音识别器。"""

    def __init__(self, language: str = "zh-CN", timeout_seconds: int = 8):
        """
        初始化语音识别器。

        Args:
            language: str - 识别语言，默认中文。
            timeout_seconds: int - 单次识别等待时长（秒）。

        Returns:
            None - 无返回值。
        """
        self.language = language
        self.timeout_seconds = max(3, timeout_seconds)

    def recognize_once(self) -> str:
        """
        执行一次麦克风语音识别。

        Args:
            无。

        Returns:
            str - 识别出的文本，失败时抛出异常。
        """
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

function New-Recognizer {{
    param([string]$LanguageName)

    try {{
        $culture = New-Object System.Globalization.CultureInfo($LanguageName)
        return New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
    }} catch {{
        return New-Object System.Speech.Recognition.SpeechRecognitionEngine
    }}
}}

$recognizer = New-Recognizer -LanguageName '{self.language}'
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$result = $recognizer.Recognize([TimeSpan]::FromSeconds({self.timeout_seconds}))

if ($null -eq $result) {{
    Write-Output ''
}} else {{
    Write-Output $result.Text
}}
"""

        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds + 12,
            check=False,
        )

        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(error_text or "系统语音识别调用失败")

        return completed.stdout.strip()


class VoiceAssistant:
    """语音助手，负责指令判断和自然语言回复。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        tts_client,
        timeout_seconds: int = 8,
    ):
        """
        初始化语音助手。

        Args:
            base_url: str - 大模型服务地址。
            api_key: str - 大模型访问密钥。
            model: str - 对话模型名称。
            tts_client: object - 语音播报客户端实例。
            timeout_seconds: int - 单次语音识别时长。

        Returns:
            None - 无返回值。
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.tts_client = tts_client
        self.recognizer = WindowsVoiceRecognizer(timeout_seconds=timeout_seconds)

    def listen_once(self) -> str:
        """
        监听一次用户语音输入。

        Args:
            无。

        Returns:
            str - 识别到的文本。
        """
        return self.recognizer.recognize_once()

    def detect_action(self, text: str) -> Optional[str]:
        """
        从文本中提取本地可执行动作。

        Args:
            text: str - 用户语音文本。

        Returns:
            Optional[str] - 动作名称，无法识别时返回 None。
        """
        normalized = (text or "").strip().lower()
        if not normalized:
            return None

        action_keywords = {
            "take_screenshot": ["截图", "截屏", "识别屏幕", "识别一下", "帮我截图"],
            "show_tasks": ["任务列表", "待办", "看看任务", "打开任务"],
            "refresh_tasks": ["刷新任务", "同步任务", "更新任务"],
            "hide_window": ["隐藏窗口", "最小化", "缩小窗口"],
            "exit_app": ["退出", "关闭程序", "结束程序"],
        }

        for action_name, keywords in action_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                return action_name

        return None

    def generate_reply(self, user_text: str) -> str:
        """
        基于大模型生成对话回复。

        Args:
            user_text: str - 用户说的话。

        Returns:
            str - 模型生成的中文回复。
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是桌面语音助手“流光 Glance”。"
                        "请用简短自然的中文回复，控制在两句话内。"
                        "如果用户是闲聊就正常回应，如果涉及任务管理可给出提醒建议。"
                    ),
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
            temperature=0.7,
            max_tokens=180,
        )
        return (response.choices[0].message.content or "").strip()

    def interact_once(self) -> Dict[str, str]:
        """
        完成一次完整语音交互。

        Args:
            无。

        Returns:
            Dict[str, str] - 包含识别文本、动作和回复内容。
        """
        user_text = self.listen_once()
        if not user_text:
            return {"text": "", "action": "", "reply": "我没有听清，你可以再说一次。"}

        action = self.detect_action(user_text) or ""
        if action:
            local_replies = {
                "take_screenshot": "好的，我来帮你截图并识别任务。",
                "show_tasks": "好的，我帮你打开任务列表。",
                "refresh_tasks": "好的，我来刷新任务状态。",
                "hide_window": "好的，我先隐藏到后台。",
                "exit_app": "好的，我准备退出程序。",
            }
            reply = local_replies.get(action, "好的，我来处理。")
        else:
            reply = self.generate_reply(user_text)

        if reply:
            self.tts_client.speak_async(reply, force=True)

        return {"text": user_text, "action": action, "reply": reply}
