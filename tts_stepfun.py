"""
阶跃星辰 TTS 语音播报模块

基于阶跃星辰语音合成 API 实现语音播报功能。

API 接口：
  POST https://api.stepfun.com/v1/audio/speech
  Headers:
    Authorization: Bearer {STEP_API_KEY}
    Content-Type: application/json
  Body:
    {
      "model": "step-tts-2",
      "input": "要合成的文本",
      "voice": "elegantgentle-female"
    }

可用模型：
  - step-tts-2     : 最新版，情绪风格可控度更强（推荐）
  - step-tts-mini  : 高性价比，11种情绪7种风格
  - step-tts-vivid : 真人感极强

限制：
  - 单次请求最多支持输入 1000 个字符
  - 输出格式支持：mp3, wav, flac, opus

文档参考：
  https://platform.stepfun.com/docs/zh/guides/developer/tts
  https://platform.stepfun.com/docs/zh/guides/models/audio
"""

import os
import io
import time
import threading
import subprocess
import tempfile
from typing import Optional

import requests


class TTSClient:
    """阶跃星辰 TTS 客户端"""

    def __init__(
        self,
        base_url: str = "https://api.stepfun.com/v1/audio/speech",
        api_key: str = "",
        model: str = "step-tts-2",
        voice: str = "elegantgentle-female",
        output_format: str = "mp3",
        speed: float = 1.0,
        enabled: bool = False
    ):
        """
        初始化 TTS 客户端

        Args:
            base_url: TTS API 地址（阶跃星辰：https://api.stepfun.com/v1/audio/speech）
            api_key: API 密钥（阶跃星辰平台创建，与大模型共用同一个 Key）
            model: TTS 模型名称（step-tts-2 / step-tts-mini / step-tts-vivid）
            voice: 音色 Voice ID（如 elegantgentle-female, cixingnansheng 等）
            output_format: 输出格式（mp3 / wav / flac / opus）
            speed: 语速 (0.5 - 2.0)
            enabled: 是否启用语音播报
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.output_format = output_format
        self.speed = max(0.5, min(2.0, speed))
        self.enabled = enabled

        # 用于防止重复播报
        self._last_spoken_text = None
        self._last_spoken_time = 0
        self._min_interval = 60  # 最小播报间隔（秒）

        # 临时音频文件目录
        self._temp_dir = os.path.join(tempfile.gettempdir(), "glance_tts")
        os.makedirs(self._temp_dir, exist_ok=True)

    def _call_tts_api(self, text: str) -> Optional[bytes]:
        """
        调用阶跃星辰 TTS API 生成语音

        API 调用格式（curl 示例）：
          curl --location 'https://api.stepfun.com/v1/audio/speech' \\
          --header 'Content-Type: application/json' \\
          --header "Authorization: Bearer $STEP_API_KEY" \\
          --data '{"model":"step-tts-2","input":"你好","voice":"elegantgentle-female"}' \\
          --output "output.mp3"

        Args:
            text: 要转换的文本（单次最多1000字符）

        Returns:
            音频数据（字节），失败返回 None
        """
        if not self.api_key:
            print("[TTS] API Key 未配置，无法调用 TTS 服务")
            return None

        # 阶跃星辰 TTS 单次请求最多 1000 字符
        if len(text) > 1000:
            text = text[:997] + "..."
            print(f"[TTS] 文本超过1000字符，已截断")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": self.output_format
        }

        try:
            print(f"[TTS] 正在调用阶跃星辰 TTS API...")
            print(f"[TTS] 模型: {self.model}, 音色: {self.voice}, 文本: {text[:50]}...")

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                print(f"[TTS] 语音合成成功，音频大小: {len(response.content)} 字节")
                return response.content
            else:
                print(f"[TTS] API 错误: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            print("[TTS] API 请求超时")
            return None
        except requests.exceptions.ConnectionError:
            print("[TTS] 网络连接失败，请检查网络")
            return None
        except Exception as e:
            print(f"[TTS] API 调用异常: {e}")
            return None

    def _play_audio(self, audio_data: bytes):
        """
        播放音频数据

        优先使用系统命令播放，跨平台兼容：
          - Windows: 使用内置媒体播放器
          - macOS: 使用 afplay
          - Linux: 使用 mpg123 或 aplay

        Args:
            audio_data: 音频字节流
        """
        # 保存为临时文件
        ext = self.output_format if self.output_format else "mp3"
        timestamp = int(time.time())
        temp_file = os.path.join(self._temp_dir, f"tts_{timestamp}.{ext}")

        try:
            with open(temp_file, "wb") as f:
                f.write(audio_data)

            print(f"[TTS] 音频已保存: {temp_file}")

            # 根据操作系统选择播放方式
            import platform
            system = platform.system()

            if system == "Windows":
                # Windows: 使用 Windows Media Player COM，兼容 mp3/wav
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        (
                            "$player = New-Object -ComObject WMPlayer.OCX; "
                            f"$player.URL = '{temp_file}'; "
                            "$player.controls.play(); "
                            "while ($player.playState -ne 1) { Start-Sleep -Milliseconds 200 }; "
                            "$player.close()"
                        ),
                    ],
                    capture_output=True,
                    timeout=60
                )
            elif system == "Darwin":
                # macOS: 使用 afplay
                subprocess.run(
                    ["afplay", temp_file],
                    capture_output=True,
                    timeout=60
                )
            else:
                # Linux: 优先使用 mpg123，回退到 aplay（wav）或 ffplay
                players = ["mpg123", "ffplay", "aplay"]
                played = False
                for player in players:
                    try:
                        if player == "ffplay":
                            subprocess.run(
                                ["ffplay", "-nodisp", "-autoexit", temp_file],
                                capture_output=True,
                                timeout=60
                            )
                        else:
                            subprocess.run(
                                [player, temp_file],
                                capture_output=True,
                                timeout=60
                            )
                        played = True
                        break
                    except FileNotFoundError:
                        continue

                if not played:
                    print(f"[TTS] 未找到音频播放器，请安装 mpg123 或 ffmpeg")

        except subprocess.TimeoutExpired:
            print("[TTS] 播放超时")
        except Exception as e:
            print(f"[TTS] 播放失败: {e}")
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

    def speak(self, text: str, force: bool = False) -> bool:
        """
        播报文本

        Args:
            text: 要播报的文本
            force: 是否强制播报（忽略间隔限制）

        Returns:
            是否播报成功
        """
        if not self.enabled:
            print(f"[TTS] 待播报（未启用）: {text}")
            return False

        if not text or not text.strip():
            return False

        # 检查是否重复播报
        current_time = time.time()
        if not force:
            if text == self._last_spoken_text:
                if current_time - self._last_spoken_time < self._min_interval:
                    print(f"[TTS] 跳过重复播报: {text}")
                    return False

        print(f"[TTS] 开始播报: {text}")

        # 调用阶跃星辰 TTS API
        audio_data = self._call_tts_api(text)

        if audio_data:
            # 播放音频
            self._play_audio(audio_data)

            # 记录播报信息
            self._last_spoken_text = text
            self._last_spoken_time = current_time

            return True
        else:
            print(f"[TTS] 播报失败: {text}")
            return False

    def speak_async(self, text: str, force: bool = False):
        """
        异步播报文本（不阻塞主线程）

        Args:
            text: 要播报的文本
            force: 是否强制播报
        """
        thread = threading.Thread(
            target=self.speak,
            args=(text, force),
            daemon=True
        )
        thread.start()

    def speak_task_reminder(self, task_name: str, deadline: str):
        """
        播报任务提醒

        Args:
            task_name: 任务名称
            deadline: 截止时间
        """
        text = f"提醒：{task_name}，截止时间 {deadline}"
        self.speak_async(text)

    def speak_overdue_warning(self, task_name: str):
        """
        播报逾期警告

        Args:
            task_name: 任务名称
        """
        text = f"警告：{task_name} 已逾期，请尽快处理"
        self.speak_async(text, force=True)

    def speak_break_reminder(self, work_duration_minutes: int):
        """
        播报休息提醒

        Args:
            work_duration_minutes: 已工作时长（分钟）
        """
        text = f"您已连续工作 {work_duration_minutes} 分钟，建议休息一下"
        self.speak_async(text)

    def speak_new_task(self, task_name: str):
        """
        播报新任务通知

        Args:
            task_name: 任务名称
        """
        text = f"已添加新任务：{task_name}"
        self.speak_async(text)


def speak(text: str, config: Optional[dict] = None) -> bool:
    """
    便捷函数：播报文本

    Args:
        text: 要播报的文本
        config: 配置字典（可选）

    Returns:
        是否播报成功
    """
    if config is None:
        config = {
            "enabled": False,
            "base_url": "https://api.stepfun.com/v1/audio/speech",
            "api_key": "",
            "model": "step-tts-2",
            "voice": "elegantgentle-female",
            "output_format": "mp3",
            "speed": 1.0
        }

    client = TTSClient(
        base_url=config.get("base_url", "https://api.stepfun.com/v1/audio/speech"),
        api_key=config.get("api_key", ""),
        model=config.get("model", "step-tts-2"),
        voice=config.get("voice", "elegantgentle-female"),
        output_format=config.get("output_format", "mp3"),
        speed=config.get("speed", 1.0),
        enabled=config.get("enabled", False)
    )

    return client.speak(text)


# 测试代码
if __name__ == "__main__":
    # 测试未启用状态（仅打印日志）
    tts = TTSClient(enabled=False)
    tts.speak("这是一个测试消息")

    # 测试异步播报
    tts.speak_async("这是异步播报测试")

    # 测试任务提醒
    tts.speak_task_reminder("提交项目报告", "今天下午5点")

    # 测试新任务通知
    tts.speak_new_task("完成代码审查")

    print("TTS 模块测试完成")
    print("提示：在 config.yaml 中设置 tts.enabled: true 并填入 API Key 即可启用语音播报")
