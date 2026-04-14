"""
像素猫桌面主界面
整合截图识别、活动流记录、日程整理和语音交互能力。
"""

import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import yaml
from PIL import Image, ImageTk

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

from activity_manager import ActivityManager
from foreground_window_watcher import ForegroundWindowWatcher
from llm_parser import LLMParser
from mqtt_client import MQTTManager
from schedule_engine import ScheduleEngine
from screenshot_listener import take_manual_screenshot
from task_manager import TaskManager
from task_suggestion_engine import TaskSuggestionEngine
from timeline_snapshot_manager import TimelineSnapshotManager
from tts_stepfun import TTSClient
from voice_assistant import VoiceAssistant


class FloatingWidget:
    """像素猫桌面助手主窗口。"""

    def __init__(self):
        """
        初始化桌面应用。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.root = tk.Tk()
        self.config = self.load_config()
        self.is_topmost = True
        self.voice_busy = False
        self.screenshot_busy = False
        self.cat_mood = "idle"
        self.active_window_summary = "未开始采集"
        self.latest_snapshot_payload = {}
        self.timeline_photo = None
        self.snapshot_activity_items = []
        self.candidate_tasks = []

        db_path = self.config.get("database", {}).get("path", "./glance_tasks.db")
        self.task_manager = TaskManager(db_path=db_path)
        self.activity_manager = ActivityManager(db_path=db_path)
        self.schedule_engine = ScheduleEngine()
        self.task_suggestion_engine = TaskSuggestionEngine()
        self.llm_parser = LLMParser(
            base_url=self.config.get("llm", {}).get("base_url", ""),
            api_key=self.config.get("llm", {}).get("api_key", ""),
            model=self.config.get("llm", {}).get("model", "step-1o-turbo-vision"),
            use_vision=True,
        )
        self.tts_client = TTSClient(
            base_url=self.config.get("tts", {}).get("base_url", "https://api.stepfun.com/v1/audio/speech"),
            api_key=self.config.get("tts", {}).get("api_key", ""),
            model=self.config.get("tts", {}).get("model", "step-tts-2"),
            voice=self.config.get("tts", {}).get("voice", "elegantgentle-female"),
            output_format=self.config.get("tts", {}).get("output_format", "mp3"),
            speed=self.config.get("tts", {}).get("speed", 1.0),
            enabled=self.config.get("tts", {}).get("enabled", True),
        )
        self.mqtt_manager = MQTTManager(config=self.config.get("mqtt", {}))
        self.voice_assistant = self.create_voice_assistant()
        self.window_watcher = ForegroundWindowWatcher(
            on_change=self.on_window_context_change,
            poll_interval_seconds=self.config.get("capture", {}).get("poll_interval_seconds", 6),
        )
        self.snapshot_manager = TimelineSnapshotManager(
            snapshot_dir=self.config.get("capture", {}).get("snapshot_dir", "./timeline_snapshots"),
            thumbnail_size=(
                self.config.get("capture", {}).get("thumbnail_width", 320),
                self.config.get("capture", {}).get("thumbnail_height", 180),
            ),
            max_snapshots=self.config.get("capture", {}).get("max_snapshots", 24),
            min_interval_seconds=self.config.get("capture", {}).get("snapshot_interval_seconds", 20),
        )

        self.setup_window()
        self.configure_styles()
        self.build_layout()
        self.refresh_all_views()
        self.append_chat("系统", "像素猫助手已上线，可以截图识别、整理日程或语音交互。")
        self.log_activity("system", "应用启动", "像素猫桌宠界面已加载完成。")
        self.try_connect_mqtt()
        self.start_activity_capture()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    def load_config(self) -> dict:
        """
        加载配置文件并合并默认值。

        Args:
            无。

        Returns:
            dict - 完整配置字典。
        """
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        load_dotenv(env_path)

        default_config = {
            "llm": {
                "base_url": "https://api.stepfun.com/v1",
                "api_key": "",
                "model": "step-1o-turbo-vision",
            },
            "tts": {
                "enabled": True,
                "base_url": "https://api.stepfun.com/v1/audio/speech",
                "api_key": "",
                "model": "step-tts-2",
                "voice": "elegantgentle-female",
                "output_format": "mp3",
                "speed": 1.0,
            },
            "mqtt": {
                "broker": "broker.emqx.io",
                "port": 1883,
                "topic": "glance/tasks",
                "client_id": "glance_desktop_client",
            },
            "database": {
                "path": "./glance_tasks.db",
            },
            "voice": {
                "enabled": True,
                "listen_timeout_seconds": 8,
            },
            "screenshot": {
                "temp_dir": "./temp_screenshots",
            },
            "capture": {
                "enabled": True,
                "poll_interval_seconds": 6,
                "snapshot_enabled": True,
                "snapshot_dir": "./timeline_snapshots",
                "thumbnail_width": 320,
                "thumbnail_height": 180,
                "max_snapshots": 24,
                "snapshot_interval_seconds": 20,
            },
        }

        if not os.path.exists(config_path):
            return default_config

        with open(config_path, "r", encoding="utf-8") as file:
            user_config = yaml.safe_load(file) or {}

        for key, value in user_config.items():
            if isinstance(value, dict) and key in default_config:
                default_config[key].update(value)
            else:
                default_config[key] = value

        default_config["llm"]["api_key"] = os.getenv("GLANCE_LLM_API_KEY", default_config["llm"]["api_key"])
        default_config["tts"]["api_key"] = os.getenv("GLANCE_TTS_API_KEY", default_config["tts"]["api_key"])
        default_config["mqtt"]["broker"] = os.getenv("GLANCE_MQTT_BROKER", default_config["mqtt"]["broker"])
        default_config["mqtt"]["port"] = int(os.getenv("GLANCE_MQTT_PORT", default_config["mqtt"]["port"]))
        return default_config

    def create_voice_assistant(self):
        """
        根据配置创建语音助手实例。

        Args:
            无。

        Returns:
            object - 语音助手实例或 None。
        """
        if not self.config.get("voice", {}).get("enabled", True):
            return None

        api_key = self.config.get("llm", {}).get("api_key", "")
        if not api_key:
            return None

        return VoiceAssistant(
            base_url=self.config.get("llm", {}).get("base_url", ""),
            api_key=api_key,
            model=self.config.get("llm", {}).get("model", "step-1o-turbo-vision"),
            tts_client=self.tts_client,
            timeout_seconds=self.config.get("voice", {}).get("listen_timeout_seconds", 8),
        )

    def setup_window(self):
        """
        初始化窗口基础属性。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.root.title("Pixel Cat Glance")
        self.root.geometry("1280x860")
        self.root.minsize(1120, 760)
        self.root.configure(bg="#1c1326")
        self.root.attributes("-topmost", self.is_topmost)

    def configure_styles(self):
        """
        配置 ttk 样式。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(
            "Task.Treeview",
            background="#241835",
            foreground="#fef3c7",
            fieldbackground="#241835",
            rowheight=34,
            borderwidth=0,
            font=("Consolas", 10),
        )
        self.style.configure(
            "Task.Treeview.Heading",
            background="#3a2552",
            foreground="#ffd166",
            relief="flat",
            font=("Consolas", 10, "bold"),
        )
        self.style.map(
            "Task.Treeview",
            background=[("selected", "#ff7f50")],
            foreground=[("selected", "#1b1023")],
        )

    def build_layout(self):
        """
        构建整体布局。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        root_frame = tk.Frame(self.root, bg="#1c1326")
        root_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self.build_header(root_frame)

        content = tk.Frame(root_frame, bg="#1c1326")
        content.pack(fill="both", expand=True, pady=(14, 0))
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        left_panel = tk.Frame(
            content,
            bg="#2a1d3f",
            width=340,
            highlightthickness=4,
            highlightbackground="#5b3f7c",
        )
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 16))
        left_panel.grid_propagate(False)

        right_panel = tk.Frame(
            content,
            bg="#241835",
            highlightthickness=4,
            highlightbackground="#5b3f7c",
        )
        right_panel.grid(row=0, column=1, sticky="nsew")

        self.build_cat_panel(left_panel)
        self.build_workspace_panel(right_panel)

    def build_header(self, parent):
        """
        构建顶部信息栏。

        Args:
            parent: object - 父级容器。

        Returns:
            None - 无返回值。
        """
        header = tk.Frame(
            parent,
            bg="#2a1d3f",
            height=82,
            highlightthickness=4,
            highlightbackground="#5b3f7c",
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        title_wrap = tk.Frame(header, bg="#2a1d3f")
        title_wrap.pack(side="left", padx=20, pady=14)

        tk.Label(
            title_wrap,
            text="Pixel Cat Glance",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_wrap,
            text="BongoCat 风格桌宠 + screenpipe 思路的日程整理台",
            bg="#2a1d3f",
            fg="#f9a8d4",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w", pady=(4, 0))

        action_wrap = tk.Frame(header, bg="#2a1d3f")
        action_wrap.pack(side="right", padx=14, pady=16)

        self.pin_button = self.create_header_button(action_wrap, "取消置顶", self.toggle_topmost, "#8b5cf6")
        self.pin_button.pack(side="left", padx=6)
        self.create_header_button(action_wrap, "最小化", self.root.iconify, "#6366f1").pack(side="left", padx=6)
        self.create_header_button(action_wrap, "退出", self.quit_app, "#ef4444").pack(side="left", padx=6)

    def create_header_button(self, parent, text: str, command, color: str):
        """
        创建顶部按钮。

        Args:
            parent: object - 父级容器。
            text: str - 按钮文本。
            command: callable - 点击回调。
            color: str - 按钮背景色。

        Returns:
            object - 按钮实例。
        """
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="#fff8e7",
            activebackground=color,
            activeforeground="#fff8e7",
            relief="flat",
            padx=14,
            pady=8,
            font=("Consolas", 10, "bold"),
        )

    def build_cat_panel(self, parent):
        """
        构建左侧像素猫面板。

        Args:
            parent: object - 父级容器。

        Returns:
            None - 无返回值。
        """
        hero = tk.Frame(parent, bg="#2a1d3f")
        hero.pack(fill="x", padx=18, pady=18)

        self.avatar_canvas = tk.Canvas(
            hero,
            width=250,
            height=230,
            bg="#2a1d3f",
            highlightthickness=0,
        )
        self.avatar_canvas.pack()
        self.draw_pixel_cat()

        self.status_title = tk.Label(
            hero,
            text="像素猫待命中",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 15, "bold"),
        )
        self.status_title.pack(pady=(12, 4))

        self.status_subtitle = tk.Label(
            hero,
            text="准备接收屏幕内容并整理为日程",
            bg="#2a1d3f",
            fg="#fbcfe8",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.status_subtitle.pack()

        self.status_chip = tk.Label(
            hero,
            text="IDLE",
            bg="#22c55e",
            fg="#1b1023",
            padx=14,
            pady=6,
            font=("Consolas", 10, "bold"),
        )
        self.status_chip.pack(pady=12)

        metrics = tk.Frame(parent, bg="#2a1d3f")
        metrics.pack(fill="x", padx=18, pady=(0, 8))

        self.metric_tasks = self.create_metric_card(metrics, "待办数量", "0", "#facc15")
        self.metric_today = self.create_metric_card(metrics, "今日截止", "0", "#fb7185")
        self.metric_voice = self.create_metric_card(metrics, "语音状态", "关闭", "#38bdf8")
        self.metric_activity = self.create_metric_card(metrics, "活动流", "0", "#a78bfa")
        self.metric_window = self.create_metric_card(metrics, "当前窗口", "未开始", "#34d399")

        actions = tk.Frame(parent, bg="#2a1d3f")
        actions.pack(fill="x", padx=18, pady=8)

        self.create_action_button(actions, "截图识别", "#ff7f50", self.handle_screenshot)
        self.create_action_button(actions, "整理日程", "#f59e0b", self.generate_schedule_digest)
        self.create_action_button(actions, "识别选中快照", "#14b8a6", self.recognize_selected_snapshot)
        self.create_action_button(actions, "按下说话", "#22c55e", self.handle_voice)
        self.create_action_button(actions, "同步硬件", "#3b82f6", self.sync_tasks_to_hardware)

        task_input = tk.Frame(parent, bg="#2a1d3f")
        task_input.pack(fill="x", padx=18, pady=(10, 0))

        tk.Label(
            task_input,
            text="快速添加任务",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")

        self.task_entry = tk.Entry(
            task_input,
            bg="#241835",
            fg="#fff8e7",
            insertbackground="#fff8e7",
            relief="flat",
            font=("Microsoft YaHei UI", 10),
        )
        self.task_entry.pack(fill="x", pady=(10, 8), ipady=10)

        self.deadline_entry = tk.Entry(
            task_input,
            bg="#241835",
            fg="#f9a8d4",
            insertbackground="#fff8e7",
            relief="flat",
            font=("Microsoft YaHei UI", 10),
        )
        self.deadline_entry.pack(fill="x", pady=(0, 8), ipady=10)
        self.deadline_entry.insert(0, "截止时间：YYYY-MM-DD HH:MM，可留空")

        self.priority_box = ttk.Combobox(
            task_input,
            values=["高优先级", "中优先级", "低优先级"],
            state="readonly",
        )
        self.priority_box.current(1)
        self.priority_box.pack(fill="x", pady=(0, 10))

        tk.Button(
            task_input,
            text="加入任务池",
            command=self.add_manual_task,
            bg="#8b5cf6",
            fg="#fff8e7",
            activebackground="#8b5cf6",
            activeforeground="#fff8e7",
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 10, "bold"),
        ).pack(fill="x")

        note_wrap = tk.Frame(parent, bg="#2a1d3f")
        note_wrap.pack(fill="x", padx=18, pady=(16, 0))

        tk.Label(
            note_wrap,
            text="灵感/上下文速记",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")

        self.note_entry = tk.Entry(
            note_wrap,
            bg="#241835",
            fg="#fff8e7",
            insertbackground="#fff8e7",
            relief="flat",
            font=("Microsoft YaHei UI", 10),
        )
        self.note_entry.pack(fill="x", pady=(10, 8), ipady=10)

        tk.Button(
            note_wrap,
            text="写入活动流",
            command=self.add_manual_note,
            bg="#ec4899",
            fg="#fff8e7",
            activebackground="#ec4899",
            activeforeground="#fff8e7",
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 10, "bold"),
        ).pack(fill="x")

        suggestion_wrap = tk.Frame(parent, bg="#2a1d3f")
        suggestion_wrap.pack(fill="both", expand=True, padx=18, pady=(16, 18))

        tk.Label(
            suggestion_wrap,
            text="候选任务",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")

        self.suggestion_listbox = tk.Listbox(
            suggestion_wrap,
            height=8,
            bg="#241835",
            fg="#fff8e7",
            selectbackground="#f59e0b",
            selectforeground="#1b1023",
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        self.suggestion_listbox.pack(fill="both", expand=True, pady=(10, 8))

        suggestion_actions = tk.Frame(suggestion_wrap, bg="#2a1d3f")
        suggestion_actions.pack(fill="x")
        self.create_secondary_button(suggestion_actions, "刷新候选", self.refresh_candidate_suggestions).pack(side="left", padx=(0, 8))
        self.create_secondary_button(suggestion_actions, "采纳候选", self.adopt_selected_candidate).pack(side="left")

    def build_workspace_panel(self, parent):
        """
        构建右侧工作区面板。

        Args:
            parent: object - 父级容器。

        Returns:
            None - 无返回值。
        """
        top_bar = tk.Frame(parent, bg="#241835")
        top_bar.pack(fill="x", padx=18, pady=(18, 12))

        self.capture_status_label = tk.Label(
            top_bar,
            text="任务总览 / 活动流 / 时间轴 / 今日整理日程",
            bg="#241835",
            fg="#fff3b0",
            font=("Consolas", 15, "bold"),
        )
        self.capture_status_label.pack(side="left")

        self.task_hint = tk.Label(
            top_bar,
            text="双击任务查看详情",
            bg="#241835",
            fg="#f9a8d4",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.task_hint.pack(side="left", padx=12)

        board_wrap = tk.Frame(parent, bg="#241835")
        board_wrap.pack(fill="x", padx=18)

        self.overview_text = tk.Label(
            board_wrap,
            text="像素猫正在分析今天的优先事项...",
            bg="#3a2552",
            fg="#fff8e7",
            justify="left",
            anchor="w",
            padx=16,
            pady=14,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.overview_text.pack(fill="x")

        table_wrap = tk.Frame(parent, bg="#241835")
        table_wrap.pack(fill="both", expand=True, padx=18, pady=(14, 0))

        columns = ("task", "deadline", "priority", "status")
        self.task_tree = ttk.Treeview(table_wrap, columns=columns, show="headings", style="Task.Treeview")
        self.task_tree.heading("task", text="任务")
        self.task_tree.heading("deadline", text="截止时间")
        self.task_tree.heading("priority", text="优先级")
        self.task_tree.heading("status", text="状态")
        self.task_tree.column("task", width=360, anchor="w")
        self.task_tree.column("deadline", width=180, anchor="center")
        self.task_tree.column("priority", width=90, anchor="center")
        self.task_tree.column("status", width=100, anchor="center")
        self.task_tree.pack(fill="both", expand=True, side="left")
        self.task_tree.bind("<Double-1>", self.show_task_detail)

        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.task_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.task_tree.configure(yscrollcommand=scrollbar.set)

        task_actions = tk.Frame(parent, bg="#241835")
        task_actions.pack(fill="x", padx=18, pady=12)

        self.create_secondary_button(task_actions, "标记完成", self.complete_selected_task).pack(side="left", padx=(0, 8))
        self.create_secondary_button(task_actions, "删除任务", self.delete_selected_task).pack(side="left", padx=8)
        self.create_secondary_button(task_actions, "朗读任务", self.speak_selected_task).pack(side="left", padx=8)
        self.create_secondary_button(task_actions, "刷新面板", self.refresh_all_views).pack(side="left", padx=8)

        lower = tk.Frame(parent, bg="#241835")
        lower.pack(fill="both", expand=False, padx=18, pady=(0, 18))
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_columnconfigure(2, weight=1)

        activity_wrap = tk.Frame(
            lower,
            bg="#2a1d3f",
            highlightthickness=3,
            highlightbackground="#5b3f7c",
        )
        activity_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tk.Label(
            activity_wrap,
            text="活动流",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.activity_text = ScrolledText(
            activity_wrap,
            height=12,
            bg="#1b1023",
            fg="#fde68a",
            insertbackground="#fff8e7",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
        )
        self.activity_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.activity_text.configure(state="disabled")

        timeline_wrap = tk.Frame(
            lower,
            bg="#2a1d3f",
            highlightthickness=3,
            highlightbackground="#5b3f7c",
        )
        timeline_wrap.grid(row=0, column=1, sticky="nsew", padx=8)

        tk.Label(
            timeline_wrap,
            text="窗口时间轴",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.timeline_preview_label = tk.Label(
            timeline_wrap,
            text="最新快照会显示在这里",
            bg="#1b1023",
            fg="#86efac",
            width=36,
            height=10,
            relief="flat",
            justify="center",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.timeline_preview_label.pack(fill="x", padx=14, pady=(0, 10))

        preview_actions = tk.Frame(timeline_wrap, bg="#2a1d3f")
        preview_actions.pack(fill="x", padx=14, pady=(0, 8))
        self.create_secondary_button(preview_actions, "打开快照", self.open_selected_snapshot).pack(side="left", padx=(0, 8))
        self.create_secondary_button(preview_actions, "识别快照", self.recognize_selected_snapshot).pack(side="left")

        self.snapshot_listbox = tk.Listbox(
            timeline_wrap,
            height=5,
            bg="#241835",
            fg="#fff8e7",
            selectbackground="#14b8a6",
            selectforeground="#1b1023",
            relief="flat",
            font=("Consolas", 9),
        )
        self.snapshot_listbox.pack(fill="x", padx=14, pady=(0, 10))
        self.snapshot_listbox.bind("<<ListboxSelect>>", self.handle_snapshot_selection)

        self.timeline_text = ScrolledText(
            timeline_wrap,
            height=4,
            bg="#1b1023",
            fg="#86efac",
            insertbackground="#fff8e7",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
        )
        self.timeline_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.timeline_text.configure(state="disabled")

        digest_wrap = tk.Frame(
            lower,
            bg="#2a1d3f",
            highlightthickness=3,
            highlightbackground="#5b3f7c",
        )
        digest_wrap.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        tk.Label(
            digest_wrap,
            text="今日整理日程",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.schedule_text = ScrolledText(
            digest_wrap,
            height=12,
            bg="#1b1023",
            fg="#bfdbfe",
            insertbackground="#fff8e7",
            relief="flat",
            wrap="word",
            font=("Microsoft YaHei UI", 10),
        )
        self.schedule_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.schedule_text.configure(state="disabled")

        chat_wrap = tk.Frame(
            parent,
            bg="#2a1d3f",
            highlightthickness=3,
            highlightbackground="#5b3f7c",
        )
        chat_wrap.pack(fill="x", padx=18, pady=(0, 18))

        tk.Label(
            chat_wrap,
            text="对话记录",
            bg="#2a1d3f",
            fg="#fff3b0",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.chat_text = ScrolledText(
            chat_wrap,
            height=8,
            bg="#1b1023",
            fg="#fbcfe8",
            insertbackground="#fff8e7",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
        )
        self.chat_text.pack(fill="x", padx=14, pady=(0, 14))
        self.chat_text.configure(state="disabled")

    def draw_pixel_cat(self):
        """
        绘制像素风小猫形象。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        palette = {
            "idle": {"fur": "#f9c74f", "eye": "#1b1023", "accent": "#ec4899"},
            "busy": {"fur": "#f97316", "eye": "#fff8e7", "accent": "#ef4444"},
            "listen": {"fur": "#60a5fa", "eye": "#1b1023", "accent": "#22c55e"},
            "happy": {"fur": "#fde68a", "eye": "#1b1023", "accent": "#8b5cf6"},
            "error": {"fur": "#fb7185", "eye": "#1b1023", "accent": "#7f1d1d"},
        }
        colors = palette.get(self.cat_mood, palette["idle"])
        canvas = self.avatar_canvas
        canvas.delete("all")

        def pixel(x: int, y: int, color: str, scale: int = 10):
            """
            绘制一个像素块。

            Args:
                x: int - 像素列坐标。
                y: int - 像素行坐标。
                color: str - 填充颜色。
                scale: int - 单个像素块缩放大小。

            Returns:
                None - 无返回值。
            """
            left = 20 + x * scale
            top = 12 + y * scale
            canvas.create_rectangle(left, top, left + scale, top + scale, fill=color, outline=color)

        fur = colors["fur"]
        eye = colors["eye"]
        accent = colors["accent"]

        body_pixels = {
            (7, 0), (8, 0), (12, 0), (13, 0),
            (6, 1), (7, 1), (8, 1), (9, 1), (11, 1), (12, 1), (13, 1), (14, 1),
            (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2), (14, 2), (15, 2),
            (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3), (13, 3), (14, 3), (15, 3), (16, 3),
            (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4), (10, 4), (11, 4), (12, 4), (13, 4), (14, 4), (15, 4), (16, 4),
            (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (9, 5), (10, 5), (11, 5), (12, 5), (13, 5), (14, 5), (15, 5), (16, 5),
            (5, 6), (6, 6), (7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6), (13, 6), (14, 6), (15, 6),
            (6, 7), (7, 7), (8, 7), (9, 7), (10, 7), (11, 7), (12, 7), (13, 7), (14, 7),
            (7, 8), (8, 8), (9, 8), (10, 8), (11, 8), (12, 8), (13, 8),
            (8, 9), (9, 9), (10, 9), (11, 9), (12, 9),
        }

        paws = {(7, 10), (8, 10), (12, 10), (13, 10), (6, 11), (7, 11), (13, 11), (14, 11)}
        for point in body_pixels.union(paws):
            pixel(point[0], point[1], fur)

        outline_pixels = {
            (7, 0), (8, 0), (12, 0), (13, 0), (6, 1), (14, 1), (5, 2), (15, 2), (4, 3), (16, 3),
            (4, 4), (16, 4), (4, 5), (16, 5), (5, 6), (15, 6), (6, 7), (14, 7), (7, 8), (13, 8),
            (8, 9), (12, 9), (6, 11), (7, 11), (13, 11), (14, 11),
        }
        for point in outline_pixels:
            pixel(point[0], point[1], "#1b1023")

        for point in {(8, 4), (12, 4)}:
            pixel(point[0], point[1], eye)
            pixel(point[0], point[1] + 1, eye)

        for point in {(10, 5), (9, 6), (10, 6), (11, 6), (10, 7)}:
            pixel(point[0], point[1], accent)

        for point in {(5, 9), (15, 9), (4, 10), (16, 10)}:
            pixel(point[0], point[1], accent)

        canvas.create_text(
            126,
            202,
            text="=^.^=" if self.cat_mood != "busy" else "=o.o=",
            fill="#fff8e7",
            font=("Consolas", 14, "bold"),
        )

    def create_metric_card(self, parent, title: str, value: str, color: str):
        """
        创建像素风指标卡。

        Args:
            parent: object - 父级容器。
            title: str - 卡片标题。
            value: str - 数值文本。
            color: str - 高亮颜色。

        Returns:
            dict - 数值标签引用集合。
        """
        card = tk.Frame(parent, bg="#241835", highlightthickness=3, highlightbackground="#5b3f7c")
        card.pack(fill="x", pady=6)
        tk.Label(card, text=title, bg="#241835", fg="#f9a8d4", font=("Microsoft YaHei UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        value_label = tk.Label(card, text=value, bg="#241835", fg=color, font=("Consolas", 16, "bold"))
        value_label.pack(anchor="w", padx=12, pady=(0, 10))
        return {"frame": card, "value": value_label}

    def create_action_button(self, parent, text: str, color: str, command):
        """
        创建左侧主操作按钮。

        Args:
            parent: object - 父级容器。
            text: str - 按钮文案。
            color: str - 背景色。
            command: callable - 点击回调。

        Returns:
            None - 无返回值。
        """
        tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="#1b1023",
            activebackground=color,
            activeforeground="#1b1023",
            relief="flat",
            padx=10,
            pady=12,
            font=("Consolas", 10, "bold"),
        ).pack(fill="x", pady=5)

    def create_secondary_button(self, parent, text: str, command):
        """
        创建次级操作按钮。

        Args:
            parent: object - 父级容器。
            text: str - 按钮文本。
            command: callable - 点击回调。

        Returns:
            object - 按钮实例。
        """
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#3a2552",
            fg="#fff8e7",
            activebackground="#5b3f7c",
            activeforeground="#fff8e7",
            relief="flat",
            padx=12,
            pady=8,
            font=("Consolas", 10, "bold"),
        )

    def toggle_topmost(self):
        """
        切换窗口置顶状态。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.is_topmost = not self.is_topmost
        self.root.attributes("-topmost", self.is_topmost)
        self.pin_button.configure(text="取消置顶" if self.is_topmost else "窗口置顶")

    def set_status(self, title: str, subtitle: str, chip_text: str, chip_bg: str, mood: str = "idle"):
        """
        更新状态与猫咪情绪。

        Args:
            title: str - 标题文本。
            subtitle: str - 描述文本。
            chip_text: str - 状态标签。
            chip_bg: str - 标签背景色。
            mood: str - 像素猫情绪状态。

        Returns:
            None - 无返回值。
        """
        self.status_title.config(text=title)
        self.status_subtitle.config(text=subtitle)
        self.status_chip.config(text=chip_text, bg=chip_bg)
        self.cat_mood = mood
        self.draw_pixel_cat()

    def append_chat(self, role: str, content: str):
        """
        追加一条聊天记录。

        Args:
            role: str - 角色名称。
            content: str - 消息内容。

        Returns:
            None - 无返回值。
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", f"[{timestamp}] {role}: {content}\n")
        self.chat_text.see("end")
        self.chat_text.configure(state="disabled")

    def log_activity(self, source: str, title: str, details: str = "", payload: dict = None):
        """
        写入一条活动流记录并刷新活动面板。

        Args:
            source: str - 活动来源。
            title: str - 活动标题。
            details: str - 活动详情。
            payload: dict - 结构化数据。

        Returns:
            None - 无返回值。
        """
        self.activity_manager.add_activity(source=source, title=title, details=details, payload=payload or {})
        self.refresh_activity_feed()

    def try_connect_mqtt(self):
        """
        尝试建立 MQTT 连接。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if self.mqtt_manager.start():
            self.append_chat("系统", "MQTT 连接成功，桌宠任务可同步到硬件端。")
            self.log_activity("system", "MQTT 已连接", "任务同步链路已就绪。")
        else:
            self.append_chat("系统", "MQTT 暂未连接，桌面端仍可独立工作。")
            self.log_activity("system", "MQTT 未连接", "继续以本地模式运行。")

    def start_activity_capture(self):
        """
        启动持续活动采集。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if not self.config.get("capture", {}).get("enabled", True):
            self.capture_status_label.config(text="任务总览 / 活动流 / 时间轴 / 今日整理日程（自动采集已关闭）")
            self.metric_window["value"].config(text="关闭")
            return

        self.window_watcher.start()
        self.append_chat("系统", "已开启前台窗口采集，像素猫会持续记录最近工作上下文。")
        self.log_activity("capture", "启动持续采集", "开始记录前台窗口变化。")

    def on_window_context_change(self, snapshot: dict):
        """
        处理前台窗口变化事件。

        Args:
            snapshot: dict - 当前窗口快照。

        Returns:
            None - 无返回值。
        """
        process_name = snapshot.get("process_name", "unknown")
        window_title = snapshot.get("window_title", "")
        if not window_title:
            return

        title_text = f"{process_name} | {window_title}"
        self.active_window_summary = title_text
        self.activity_manager.add_activity(
            source="capture",
            title="窗口焦点变化",
            details=title_text,
            payload=snapshot,
        )
        self.capture_timeline_snapshot(snapshot)
        self.root.after(0, self.refresh_capture_views)

    def capture_timeline_snapshot(self, snapshot: dict):
        """
        根据窗口上下文抓取时间轴快照。

        Args:
            snapshot: dict - 当前窗口快照。

        Returns:
            None - 无返回值。
        """
        if not self.config.get("capture", {}).get("snapshot_enabled", True):
            return

        payload = self.snapshot_manager.capture_snapshot(
            signature=snapshot.get("signature", ""),
            window_title=snapshot.get("window_title", ""),
            process_name=snapshot.get("process_name", ""),
        )
        if not payload:
            return

        self.activity_manager.add_activity(
            source="snapshot",
            title="记录屏幕快照",
            details=f"{payload.get('process_name', 'unknown')} | {payload.get('window_title', '')}",
            payload=payload,
        )
        self.latest_snapshot_payload = payload

    def refresh_capture_views(self):
        """
        刷新采集相关视图。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        short_text = self.active_window_summary[:16] + "..." if len(self.active_window_summary) > 19 else self.active_window_summary
        self.metric_window["value"].config(text=short_text or "未知")
        self.capture_status_label.config(text=f"任务总览 / 活动流 / 时间轴 / 今日整理日程 | {self.active_window_summary}")
        self.refresh_activity_feed()
        self.refresh_timeline_feed()
        self.refresh_candidate_suggestions()
        self.refresh_schedule_digest()

    def refresh_all_views(self):
        """
        刷新所有主要视图。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.refresh_tasks()
        self.refresh_activity_feed()
        self.refresh_timeline_feed()
        self.refresh_schedule_digest()

    def refresh_tasks(self):
        """
        刷新任务表格和指标卡。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = self.task_manager.get_all_tasks()
        for item_id in self.task_tree.get_children():
            self.task_tree.delete(item_id)

        today_count = 0
        pending_count = 0
        for task in tasks:
            if task.get("status") != "completed":
                pending_count += 1
            if task.get("deadline", "")[:10] == datetime.now().strftime("%Y-%m-%d"):
                today_count += 1
            self.task_tree.insert(
                "",
                "end",
                iid=task["id"],
                values=(
                    task.get("task", ""),
                    task.get("deadline") or "未设置",
                    self.priority_to_text(task.get("priority", 2)),
                    "已完成" if task.get("status") == "completed" else "待处理",
                ),
            )

        self.metric_tasks["value"].config(text=str(pending_count))
        self.metric_today["value"].config(text=str(today_count))
        self.metric_voice["value"].config(text="可用" if self.voice_assistant else "未配置")
        self.metric_activity["value"].config(text=str(len(self.activity_manager.get_recent_activities(limit=50))))

    def refresh_timeline_feed(self):
        """
        刷新窗口时间轴展示。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        activities = self.activity_manager.get_recent_activities_by_source("snapshot", limit=8)
        self.snapshot_activity_items = activities
        self.snapshot_listbox.delete(0, "end")
        self.timeline_text.configure(state="normal")
        self.timeline_text.delete("1.0", "end")

        if not activities:
            self.timeline_text.insert("end", "自动采集开始后，最近窗口切换会显示在这里。\n")
            self.timeline_preview_label.configure(text="最新快照会显示在这里", image="")
            self.timeline_photo = None
        else:
            for index, item in enumerate(activities):
                payload = item.get("payload", {})
                process_name = payload.get("process_name", "unknown")
                self.snapshot_listbox.insert("end", f"[{item['created_at'][11:16]}] {process_name}")
                if index == 0:
                    self.snapshot_listbox.selection_set(0)
                    self.update_snapshot_detail(item)

        self.timeline_text.configure(state="disabled")

    def handle_snapshot_selection(self, event=None):
        """
        处理历史快照选择事件。

        Args:
            event: object - 事件对象。

        Returns:
            None - 无返回值。
        """
        index = self.get_selected_snapshot_index()
        if index < 0 or index >= len(self.snapshot_activity_items):
            return
        self.update_snapshot_detail(self.snapshot_activity_items[index])

    def get_selected_snapshot_index(self) -> int:
        """
        获取当前选中的快照索引。

        Args:
            无。

        Returns:
            int - 选中索引，未选中返回 -1。
        """
        selection = self.snapshot_listbox.curselection()
        return selection[0] if selection else -1

    def get_selected_snapshot_payload(self) -> dict:
        """
        获取当前选中的快照负载。

        Args:
            无。

        Returns:
            dict - 快照负载信息。
        """
        index = self.get_selected_snapshot_index()
        if index < 0 or index >= len(self.snapshot_activity_items):
            return self.latest_snapshot_payload
        return self.snapshot_activity_items[index].get("payload", {})

    def update_snapshot_detail(self, activity: dict):
        """
        更新选中快照的详情与预览。

        Args:
            activity: dict - 活动记录。

        Returns:
            None - 无返回值。
        """
        payload = activity.get("payload", {})
        self.latest_snapshot_payload = payload
        self.update_timeline_preview(payload)

        self.timeline_text.configure(state="normal")
        self.timeline_text.delete("1.0", "end")
        self.timeline_text.insert("end", f"时间：{activity.get('created_at', '未知')}\n")
        self.timeline_text.insert("end", f"进程：{payload.get('process_name', 'unknown')}\n")
        self.timeline_text.insert("end", f"窗口：{payload.get('window_title', '未知窗口')}\n")
        self.timeline_text.insert("end", f"原图：{payload.get('image_path', '无')}\n")
        self.timeline_text.configure(state="disabled")

    def update_timeline_preview(self, payload: dict):
        """
        更新最新时间轴快照预览。

        Args:
            payload: dict - 快照负载信息。

        Returns:
            None - 无返回值。
        """
        thumb_path = payload.get("thumbnail_path", "")
        if not thumb_path or not os.path.exists(thumb_path):
            self.timeline_preview_label.configure(text="暂无可预览快照", image="")
            self.timeline_photo = None
            return

        try:
            image = Image.open(thumb_path)
            self.timeline_photo = ImageTk.PhotoImage(image)
            self.timeline_preview_label.configure(image=self.timeline_photo, text="")
        except Exception:
            self.timeline_preview_label.configure(text="快照预览加载失败", image="")
            self.timeline_photo = None

    def open_selected_snapshot(self):
        """
        打开当前选中的时间轴快照原图。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        image_path = self.get_selected_snapshot_payload().get("image_path", "")
        if not image_path or not os.path.exists(image_path):
            messagebox.showinfo("提示", "当前还没有可打开的时间轴快照。")
            return

        os.startfile(image_path)

    def recognize_selected_snapshot(self):
        """
        对当前选中的时间轴快照执行任务识别。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        payload = self.get_selected_snapshot_payload()
        image_path = payload.get("image_path", "")
        if not image_path or not os.path.exists(image_path):
            messagebox.showinfo("提示", "当前还没有可识别的时间轴快照。")
            return

        self.set_status("解析最新快照", "像素猫正在把最近屏幕上下文整理成任务。", "AUTO", "#14b8a6", mood="busy")
        self.append_chat("系统", "开始识别最新时间轴快照。")
        self.run_async(self.process_snapshot_recognition, image_path)

    def process_snapshot_recognition(self, image_path: str):
        """
        在后台线程中解析最新时间轴快照。

        Args:
            image_path: str - 快照原图路径。

        Returns:
            None - 无返回值。
        """
        try:
            tasks = self.llm_parser.parse_screenshot(image_path)
            if not tasks:
                self.root.after(0, lambda: self.finish_snapshot_recognition("最新快照没有识别出明确任务。", False))
                return

            added_tasks = self.task_manager.add_tasks_from_llm(tasks)
            summary = f"已从最新快照中提取 {len(added_tasks)} 条任务。"
            self.log_activity("snapshot", "识别时间轴快照", summary, {"tasks": added_tasks, "image_path": image_path})
            self.sync_tasks_to_hardware(silent=True)
            self.root.after(0, lambda: self.finish_snapshot_recognition(summary, True))
        except Exception as exc:
            self.root.after(0, lambda: self.finish_snapshot_recognition(f"时间轴快照识别失败：{exc}", False))

    def finish_snapshot_recognition(self, message: str, success: bool):
        """
        收尾时间轴快照识别流程。

        Args:
            message: str - 结果信息。
            success: bool - 是否成功。

        Returns:
            None - 无返回值。
        """
        if success:
            self.set_status("快照识别完成", message, "OK", "#22c55e", mood="happy")
        else:
            self.set_status("快照识别结束", message, "INFO", "#f59e0b", mood="idle")
        self.append_chat("系统", message)
        self.refresh_all_views()

    def refresh_candidate_suggestions(self):
        """
        刷新候选任务列表。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = self.task_manager.get_all_tasks()
        activities = self.activity_manager.get_recent_activities(limit=24)
        self.candidate_tasks = self.task_suggestion_engine.build_candidates(tasks, activities, limit=8)

        self.suggestion_listbox.delete(0, "end")
        if not self.candidate_tasks:
            self.suggestion_listbox.insert("end", "暂无候选任务")
            return

        for item in self.candidate_tasks:
            priority_text = self.priority_to_text(item.get("priority", 2))
            self.suggestion_listbox.insert("end", f"[{priority_text}] {item.get('task', '')}")

    def adopt_selected_candidate(self):
        """
        采纳当前选中的候选任务。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        selection = self.suggestion_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一条候选任务")
            return

        index = selection[0]
        if index >= len(self.candidate_tasks):
            return

        candidate = self.candidate_tasks[index]
        self.task_manager.add_task(
            task=candidate.get("task", "未命名候选任务"),
            deadline=None,
            priority=candidate.get("priority", 2),
        )
        self.log_activity(
            "planner",
            "采纳候选任务",
            candidate.get("task", ""),
            {"reason": candidate.get("reason", ""), "source": candidate.get("source", "")},
        )
        self.append_chat("系统", f"已采纳候选任务：{candidate.get('task', '')}")
        self.sync_tasks_to_hardware(silent=True)
        self.refresh_all_views()
        self.set_status("候选已采纳", candidate.get("reason", "已加入任务池。"), "PLAN", "#f59e0b", mood="happy")

    def refresh_activity_feed(self):
        """
        刷新活动流展示区域。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        activities = self.activity_manager.get_recent_activities(limit=12)
        self.activity_text.configure(state="normal")
        self.activity_text.delete("1.0", "end")

        if not activities:
            self.activity_text.insert("end", "还没有活动记录。\n")
        else:
            for item in activities:
                line = f"[{item['created_at'][11:16]}] {item['source'].upper()} | {item['title']}\n"
                self.activity_text.insert("end", line)
                if item.get("details"):
                    self.activity_text.insert("end", f"  {item['details']}\n")
                self.activity_text.insert("end", "\n")

        self.activity_text.configure(state="disabled")

    def refresh_schedule_digest(self):
        """
        刷新今日整理日程内容。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        tasks = self.task_manager.get_all_tasks()
        activities = self.activity_manager.get_recent_activities(limit=20)
        digest = self.schedule_engine.build_daily_digest(tasks, activities)

        overview_line = " | ".join(digest.get("overview", []))
        self.overview_text.config(text=overview_line or "像素猫还没有足够信息来整理日程。")

        self.schedule_text.configure(state="normal")
        self.schedule_text.delete("1.0", "end")
        self.schedule_text.insert("end", "【今日安排】\n")
        for line in digest.get("schedule", []):
            self.schedule_text.insert("end", f"- {line}\n")

        self.schedule_text.insert("end", "\n【活动洞察】\n")
        for line in digest.get("insights", []):
            self.schedule_text.insert("end", f"- {line}\n")
        self.schedule_text.configure(state="disabled")

    def generate_schedule_digest(self):
        """
        主动整理一次日程摘要。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.refresh_schedule_digest()
        self.set_status("日程已整理", "像素猫已根据任务与活动流生成今日建议。", "PLAN", "#f59e0b", mood="happy")
        self.append_chat("系统", "已基于近期活动和任务池整理今日日程。")
        self.log_activity("planner", "整理今日日程", "已刷新建议安排与活动洞察。")

    def priority_to_text(self, priority: int) -> str:
        """
        将数字优先级转换为中文描述。

        Args:
            priority: int - 优先级数值。

        Returns:
            str - 中文优先级文本。
        """
        return {1: "高", 2: "中", 3: "低"}.get(priority, "中")

    def selected_task_id(self):
        """
        获取当前选中的任务 ID。

        Args:
            无。

        Returns:
            str - 任务 ID，未选择时返回空字符串。
        """
        selection = self.task_tree.selection()
        return selection[0] if selection else ""

    def show_task_detail(self, event=None):
        """
        显示选中任务详情。

        Args:
            event: object - 事件对象。

        Returns:
            None - 无返回值。
        """
        task_id = self.selected_task_id()
        if not task_id:
            return

        task = self.task_manager.get_task(task_id)
        if not task:
            return

        detail = (
            f"任务：{task.get('task', '')}\n"
            f"截止时间：{task.get('deadline') or '未设置'}\n"
            f"优先级：{self.priority_to_text(task.get('priority', 2))}\n"
            f"状态：{'已完成' if task.get('status') == 'completed' else '待处理'}"
        )
        messagebox.showinfo("任务详情", detail)

    def add_manual_task(self):
        """
        手动添加任务并写入活动流。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task_text = self.task_entry.get().strip()
        deadline = self.deadline_entry.get().strip()
        priority_text = self.priority_box.get()

        if not task_text:
            messagebox.showwarning("提示", "请输入任务内容")
            return

        if deadline == "截止时间：YYYY-MM-DD HH:MM，可留空":
            deadline = ""

        priority = {"高优先级": 1, "中优先级": 2, "低优先级": 3}.get(priority_text, 2)
        self.task_manager.add_task(task_text, deadline or None, priority)
        self.task_entry.delete(0, "end")
        self.deadline_entry.delete(0, "end")
        self.deadline_entry.insert(0, "截止时间：YYYY-MM-DD HH:MM，可留空")
        self.append_chat("系统", f"已手动添加任务：{task_text}")
        self.log_activity("manual", "添加手动任务", task_text, {"deadline": deadline, "priority": priority})
        self.sync_tasks_to_hardware(silent=True)
        self.refresh_all_views()
        self.set_status("任务已加入", f"新任务「{task_text}」已进入任务池。", "ADD", "#8b5cf6", mood="happy")

    def add_manual_note(self):
        """
        手动写入一条灵感或上下文记录。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        note_text = self.note_entry.get().strip()
        if not note_text:
            messagebox.showwarning("提示", "请输入需要记录的内容")
            return

        self.note_entry.delete(0, "end")
        self.log_activity("manual", "记录灵感", note_text)
        self.append_chat("系统", f"已写入活动流：{note_text}")
        self.refresh_schedule_digest()
        self.set_status("灵感已保存", "新上下文已经进入活动流，可参与后续日程整理。", "NOTE", "#ec4899", mood="happy")

    def complete_selected_task(self):
        """
        标记选中任务为完成。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task_id = self.selected_task_id()
        if not task_id:
            messagebox.showinfo("提示", "请先选择任务")
            return

        task = self.task_manager.get_task(task_id)
        self.task_manager.complete_task(task_id)
        self.append_chat("系统", "已将选中任务标记为完成。")
        self.log_activity("manual", "完成任务", task.get("task", "") if task else "")
        self.sync_tasks_to_hardware(silent=True)
        self.refresh_all_views()
        self.set_status("任务已完成", "像素猫已经帮你更新任务状态。", "DONE", "#22c55e", mood="happy")

    def delete_selected_task(self):
        """
        删除选中任务。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task_id = self.selected_task_id()
        if not task_id:
            messagebox.showinfo("提示", "请先选择任务")
            return

        task = self.task_manager.get_task(task_id)
        if not messagebox.askyesno("确认删除", "确定删除这条任务吗？"):
            return

        self.task_manager.delete_task(task_id)
        self.append_chat("系统", "已删除选中任务。")
        self.log_activity("manual", "删除任务", task.get("task", "") if task else "")
        self.sync_tasks_to_hardware(silent=True)
        self.refresh_all_views()
        self.set_status("任务已删除", "任务池已更新。", "DEL", "#ef4444", mood="idle")

    def speak_selected_task(self):
        """
        朗读选中任务。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        task_id = self.selected_task_id()
        if not task_id:
            messagebox.showinfo("提示", "请先选择任务")
            return

        task = self.task_manager.get_task(task_id)
        if not task:
            return

        deadline = task.get("deadline") or "未设置截止时间"
        self.tts_client.speak_async(f"任务：{task.get('task', '')}，截止时间：{deadline}", force=True)
        self.append_chat("系统", f"已朗读任务：{task.get('task', '')}")
        self.log_activity("system", "朗读任务", task.get("task", ""))

    def run_async(self, target, *args):
        """
        在后台线程中执行任务。

        Args:
            target: callable - 目标函数。
            args: tuple - 参数列表。

        Returns:
            None - 无返回值。
        """
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def handle_screenshot(self):
        """
        触发截图识别流程。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if self.screenshot_busy:
            return

        self.screenshot_busy = True
        self.set_status("猫咪看屏中", "窗口会短暂隐藏，随后分析当前屏幕内容。", "SCAN", "#ff7f50", mood="busy")
        self.root.withdraw()
        self.root.after(350, self.capture_screenshot)

    def capture_screenshot(self):
        """
        执行截图并转入识别线程。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        image_path = take_manual_screenshot(self.config.get("screenshot", {}).get("temp_dir", "./temp_screenshots"))
        self.root.deiconify()

        if not image_path:
            self.screenshot_busy = False
            self.set_status("截图失败", "这次没有成功截到屏幕，请重试。", "ERR", "#ef4444", mood="error")
            return

        self.append_chat("系统", f"已完成截图：{image_path}")
        self.log_activity("screenshot", "捕获屏幕", image_path)
        self.run_async(self.process_screenshot, image_path)

    def process_screenshot(self, image_path: str):
        """
        调用大模型解析截图并写入任务池。

        Args:
            image_path: str - 截图文件路径。

        Returns:
            None - 无返回值。
        """
        try:
            tasks = self.llm_parser.parse_screenshot(image_path)
            if not tasks:
                self.root.after(
                    0,
                    lambda: self.finish_screenshot(
                        "没有识别到有效任务，可以换一张更清晰的截图再试。",
                        success=False,
                    ),
                )
                return

            added_tasks = self.task_manager.add_tasks_from_llm(tasks)
            for task in added_tasks:
                self.tts_client.speak_async(f"已添加任务：{task.get('task', '未命名任务')}")

            task_names = "、".join(task.get("task", "未命名任务") for task in added_tasks[:4])
            self.log_activity(
                "screenshot",
                "识别截图任务",
                f"新增 {len(added_tasks)} 条任务：{task_names}",
                {"tasks": added_tasks},
            )
            self.sync_tasks_to_hardware(silent=True)
            summary = f"识别完成，新增 {len(added_tasks)} 条任务。"
            self.root.after(0, lambda: self.finish_screenshot(summary, success=True))
        except Exception as exc:
            self.root.after(0, lambda: self.finish_screenshot(f"截图解析失败：{exc}", success=False))

    def finish_screenshot(self, message: str, success: bool):
        """
        收尾截图识别流程。

        Args:
            message: str - 结果提示。
            success: bool - 是否成功。

        Returns:
            None - 无返回值。
        """
        self.screenshot_busy = False
        if success:
            self.set_status("识别完成", message, "OK", "#22c55e", mood="happy")
        else:
            self.set_status("识别失败", message, "ERR", "#ef4444", mood="error")
        self.append_chat("系统", message)
        self.refresh_all_views()

    def handle_voice(self):
        """
        触发一次语音交互。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if self.voice_busy:
            return

        if not self.voice_assistant:
            messagebox.showwarning("提示", "当前未配置可用的语音交互能力，请先检查 llm.api_key 和 voice.enabled。")
            return

        self.voice_busy = True
        self.set_status("正在聆听", "请直接对着麦克风说话。", "LISTEN", "#22c55e", mood="listen")
        self.append_chat("系统", "开始语音监听，请说话。")
        self.run_async(self.process_voice)

    def process_voice(self):
        """
        在后台线程中执行语音识别与回复。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        try:
            result = self.voice_assistant.interact_once()
            self.root.after(0, lambda: self.finish_voice(result))
        except Exception as exc:
            self.root.after(0, lambda: self.fail_voice(str(exc)))

    def finish_voice(self, result: dict):
        """
        收尾语音交互并执行本地动作。

        Args:
            result: dict - 语音交互结果。

        Returns:
            None - 无返回值。
        """
        self.voice_busy = False
        user_text = result.get("text", "")
        action = result.get("action", "")
        reply = result.get("reply", "")

        self.set_status("语音完成", reply or "本轮语音已结束。", "VOICE", "#38bdf8", mood="happy")

        if user_text:
            self.append_chat("你", user_text)
            self.log_activity("voice", "收到语音输入", user_text, {"action": action})
        if reply:
            self.append_chat("猫咪", reply)

        self.execute_voice_action(action)
        self.refresh_schedule_digest()

    def fail_voice(self, error_message: str):
        """
        处理语音交互失败场景。

        Args:
            error_message: str - 错误信息。

        Returns:
            None - 无返回值。
        """
        self.voice_busy = False
        self.set_status("语音失败", error_message, "ERR", "#ef4444", mood="error")
        self.append_chat("系统", f"语音交互失败：{error_message}")
        self.log_activity("voice", "语音失败", error_message)

    def execute_voice_action(self, action: str):
        """
        根据语音动作执行本地操作。

        Args:
            action: str - 动作名称。

        Returns:
            None - 无返回值。
        """
        if action == "take_screenshot":
            self.handle_screenshot()
        elif action == "show_tasks":
            self.task_tree.focus_set()
        elif action == "refresh_tasks":
            self.refresh_all_views()
        elif action == "hide_window":
            self.root.iconify()
        elif action == "exit_app":
            self.quit_app()

    def sync_tasks_to_hardware(self, silent: bool = False):
        """
        将待办任务同步到 MQTT 硬件端。

        Args:
            silent: bool - 是否静默同步。

        Returns:
            bool - 同步是否成功。
        """
        tasks = self.task_manager.get_tasks_for_sync()
        success = self.mqtt_manager.sync_tasks(tasks)
        if success:
            if not silent:
                self.append_chat("系统", "已将任务同步到硬件端。")
            self.log_activity("system", "同步任务到硬件", f"同步 {len(tasks)} 条待办任务。")
        else:
            if not silent:
                self.append_chat("系统", "任务同步未成功，可能是 MQTT 尚未连接。")
        return success

    def quit_app(self):
        """
        退出程序并清理连接。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        self.window_watcher.stop()
        self.mqtt_manager.stop()
        self.root.destroy()


if __name__ == "__main__":
    FloatingWidget()
