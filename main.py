"""
流光 Glance - 主入口程序
PC 端后台服务，系统托盘入口
"""

import os
import sys
import json
import time
import signal
import threading
from datetime import datetime
from typing import Optional, Dict, Any

import yaml
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        """
        兼容未安装 python-dotenv 的场景。

        Args:
            *args: tuple - 位置参数。
            **kwargs: dict - 关键字参数。

        Returns:
            bool - 始终返回 False。
        """
        return False

# 导入各模块
from screenshot_listener import ScreenshotListener, take_manual_screenshot
from llm_parser import LLMParser
from task_manager import TaskManager
from mqtt_client import MQTTManager
from tts_stepfun import TTSClient


class GlanceApp:
    """流光 Glance 主应用"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化应用

        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_path)

        # 初始化各模块
        self.task_manager = TaskManager(
            db_path=self.config.get("database", {}).get("path", "./glance_tasks.db")
        )

        self.llm_parser = LLMParser(
            base_url=self.config.get("llm", {}).get("base_url", ""),
            api_key=self.config.get("llm", {}).get("api_key", ""),
            model=self.config.get("llm", {}).get("model", ""),
            use_vision=True
        )

        self.mqtt_manager = MQTTManager(
            config=self.config.get("mqtt", {})
        )

        self.tts_client = TTSClient(
            base_url=self.config.get("tts", {}).get("base_url", "https://api.stepfun.com/v1/audio/speech"),
            api_key=self.config.get("tts", {}).get("api_key", ""),
            model=self.config.get("tts", {}).get("model", "step-tts-2"),
            voice=self.config.get("tts", {}).get("voice", "elegantgentle-female"),
            output_format=self.config.get("tts", {}).get("output_format", "mp3"),
            speed=self.config.get("tts", {}).get("speed", 1.0),
            enabled=self.config.get("tts", {}).get("enabled", False)
        )

        self.screenshot_listener = ScreenshotListener(
            hotkey=self.config.get("screenshot", {}).get("hotkey", "ctrl+shift+s"),
            temp_dir=self.config.get("screenshot", {}).get("temp_dir", "./temp_screenshots"),
            watch_clipboard=self.config.get("screenshot", {}).get("watch_clipboard", True),
            on_screenshot=self._on_screenshot
        )

        # 运行状态
        self._running = False
        self._reminder_thread = None

        # 确保临时目录存在
        os.makedirs(
            self.config.get("screenshot", {}).get("temp_dir", "./temp_screenshots"),
            exist_ok=True
        )

        print("[Glance] 初始化完成")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        default_config = {
            "llm": {
                "base_url": "https://api.stepfun.com/v1",
                "api_key": "",
                "model": "step-1v-8k"
            },
            "mqtt": {
                "broker": "broker.emqx.io",
                "port": 1883,
                "topic": "glance/tasks",
                "client_id": "glance_pc_client"
            },
            "screenshot": {
                "hotkey": "ctrl+shift+s",
                "temp_dir": "./temp_screenshots",
                "watch_clipboard": True
            },
            "tts": {
                "enabled": False,
                "base_url": "https://api.stepfun.com/v1/audio/speech",
                "api_key": "",
                "model": "step-tts",
                "speed": 1.0
            },
            "reminder": {
                "advance_hours": 24,
                "work_duration_minutes": 60,
                "interval_minutes": 30
            },
            "database": {
                "path": "./glance_tasks.db"
            }
        }

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f)
                    # 合并配置
                    for key, value in user_config.items():
                        if isinstance(value, dict) and key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
                print(f"[Glance] 已加载配置: {config_path}")
            except Exception as e:
                print(f"[Glance] 配置加载失败，使用默认配置: {e}")
        else:
            print(f"[Glance] 配置文件不存在，使用默认配置: {config_path}")

        default_config["llm"]["api_key"] = os.getenv("GLANCE_LLM_API_KEY", default_config["llm"]["api_key"])
        default_config["tts"]["api_key"] = os.getenv("GLANCE_TTS_API_KEY", default_config["tts"]["api_key"])
        default_config["mqtt"]["broker"] = os.getenv("GLANCE_MQTT_BROKER", default_config["mqtt"]["broker"])
        default_config["mqtt"]["port"] = int(os.getenv("GLANCE_MQTT_PORT", default_config["mqtt"]["port"]))

        return default_config

    def _on_screenshot(self, image_path: str):
        """
        截图回调函数

        Args:
            image_path: 截图文件路径
        """
        print(f"[Glance] 处理截图: {image_path}")

        try:
            # 使用大模型解析截图
            tasks = self.llm_parser.parse_screenshot(image_path)

            if tasks:
                print(f"[Glance] 解析到 {len(tasks)} 个任务")

                # 添加到任务管理器
                added_tasks = self.task_manager.add_tasks_from_llm(tasks)

                # 同步到硬件端
                self._sync_to_hardware()

                # TTS 提醒
                for task in added_tasks:
                    task_name = task.get("task", "新任务")
                    deadline = task.get("deadline", "")
                    if deadline:
                        self.tts_client.speak_task_reminder(task_name, deadline)
                    else:
                        self.tts_client.speak_async(f"已添加新任务：{task_name}")
            else:
                print("[Glance] 未从截图中提取到任务")

        except Exception as e:
            print(f"[Glance] 截图处理错误: {e}")

    def _sync_to_hardware(self):
        """同步任务列表到硬件端"""
        if self.mqtt_manager.is_connected():
            tasks = self.task_manager.get_tasks_for_sync()
            self.mqtt_manager.sync_tasks(tasks)
        else:
            print("[Glance] MQTT 未连接，跳过同步")

    def _reminder_loop(self):
        """提醒循环"""
        reminder_config = self.config.get("reminder", {})
        advance_hours = reminder_config.get("advance_hours", 24)
        interval_minutes = reminder_config.get("interval_minutes", 30)

        last_reminder_time = {}

        while self._running:
            try:
                # 检查即将到期的任务
                upcoming_tasks = self.task_manager.get_upcoming_tasks(advance_hours)

                for task in upcoming_tasks:
                    task_id = task.get("id")
                    task_name = task.get("task", "")
                    deadline = task.get("deadline", "")

                    # 避免重复提醒
                    if task_id not in last_reminder_time or \
                       (datetime.now() - last_reminder_time[task_id]).total_seconds() > interval_minutes * 60:

                        print(f"[提醒] 任务即将到期: {task_name} ({deadline})")
                        self.tts_client.speak_task_reminder(task_name, deadline)
                        last_reminder_time[task_id] = datetime.now()

                # 检查今日任务
                today_tasks = self.task_manager.get_today_tasks()
                if today_tasks:
                    high_priority = [t for t in today_tasks if t.get("priority") == 1]
                    if high_priority:
                        print(f"[提醒] 今日有 {len(high_priority)} 个高优先级任务")

            except Exception as e:
                print(f"[提醒] 循环错误: {e}")

            # 每分钟检查一次
            time.sleep(60)

    def start(self):
        """启动应用"""
        if self._running:
            print("[Glance] 应用已在运行")
            return

        self._running = True
        print("[Glance] 启动中...")

        # 连接 MQTT
        if self.mqtt_manager.start():
            print("[Glance] MQTT 连接成功")
        else:
            print("[Glance] MQTT 连接失败，将继续运行但无法同步")

        # 启动截图监听
        self.screenshot_listener.start()

        # 启动提醒线程
        self._reminder_thread = threading.Thread(
            target=self._reminder_loop,
            daemon=True
        )
        self._reminder_thread.start()

        print("[Glance] 已启动")
        print(f"[Glance] 快捷键: {self.config.get('screenshot', {}).get('hotkey', 'ctrl+shift+s')}")
        print("[Glance] 按 Ctrl+C 退出")

    def stop(self):
        """停止应用"""
        self._running = False

        # 停止截图监听
        self.screenshot_listener.stop()

        # 断开 MQTT
        self.mqtt_manager.stop()

        print("[Glance] 已停止")

    def add_task_manually(self, task: str, deadline: Optional[str] = None, priority: int = 2):
        """
        手动添加任务

        Args:
            task: 任务描述
            deadline: 截止时间
            priority: 优先级
        """
        new_task = self.task_manager.add_task(task, deadline, priority)
        self._sync_to_hardware()
        print(f"[Glance] 已添加任务: {task}")
        return new_task

    def complete_task(self, task_id: str):
        """标记任务为已完成"""
        self.task_manager.complete_task(task_id)
        self._sync_to_hardware()

    def delete_task(self, task_id: str):
        """删除任务"""
        self.task_manager.delete_task(task_id)
        self._sync_to_hardware()

    def list_tasks(self):
        """列出所有任务"""
        tasks = self.task_manager.get_all_tasks()
        print("\n=== 任务列表 ===")
        for i, task in enumerate(tasks, 1):
            status = "✓" if task["status"] == "completed" else "○"
            priority = "!" * task["priority"]
            deadline = task.get("deadline") or "无截止时间"
            print(f"{i}. [{status}] {priority} {task['task']} - {deadline}")
        print("================\n")
        return tasks

    def run(self):
        """运行主循环"""
        self.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Glance] 收到退出信号")
        finally:
            self.stop()


def main():
    """主函数"""
    # 获取配置文件路径
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    # 创建应用实例
    app = GlanceApp(config_path)

    # 设置信号处理
    def signal_handler(sig, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 运行应用
    app.run()


if __name__ == "__main__":
    main()
