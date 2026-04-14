"""
语音助手模块测试
验证本地动作识别逻辑。
"""

import unittest

from voice_assistant import VoiceAssistant


class DummyTTSClient:
    """用于测试的空 TTS 客户端。"""

    def speak_async(self, text, force=False):
        """
        占位异步播报方法。

        Args:
            text: str - 播报文本。
            force: bool - 是否强制播报。

        Returns:
            None - 无返回值。
        """
        return None


class VoiceAssistantTestCase(unittest.TestCase):
    """语音助手测试用例。"""

    def setUp(self):
        """
        创建测试用语音助手实例。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.assistant = VoiceAssistant(
            base_url="https://api.stepfun.com/v1",
            api_key="test_key",
            model="test_model",
            tts_client=DummyTTSClient(),
            timeout_seconds=3,
        )

    def test_detect_screenshot_action(self):
        """
        验证截图指令识别。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.assertEqual(self.assistant.detect_action("帮我截图识别一下"), "take_screenshot")

    def test_detect_show_tasks_action(self):
        """
        验证任务列表指令识别。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.assertEqual(self.assistant.detect_action("打开任务列表"), "show_tasks")

    def test_detect_unknown_action(self):
        """
        验证普通闲聊不会命中本地动作。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.assertIsNone(self.assistant.detect_action("你今天过得怎么样"))


if __name__ == "__main__":
    unittest.main()
