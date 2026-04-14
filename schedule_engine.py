"""
日程整理模块
将任务数据与近期活动整理为可读的今日计划摘要。
"""

from datetime import datetime
from typing import Dict, List


class ScheduleEngine:
    """基于任务与活动的轻量日程整理器。"""

    def build_daily_digest(self, tasks: List[Dict], activities: List[Dict]) -> Dict[str, List[str]]:
        """
        生成今日日程摘要。

        Args:
            tasks: List[Dict] - 当前任务列表。
            activities: List[Dict] - 近期活动列表。

        Returns:
            Dict[str, List[str]] - 含概览、今日安排、活动洞察的摘要结果。
        """
        pending_tasks = [task for task in tasks if task.get("status") != "completed"]
        today_tasks = [task for task in pending_tasks if self._is_today(task.get("deadline"))]
        high_priority = [task for task in pending_tasks if task.get("priority") == 1]
        no_deadline = [task for task in pending_tasks if not task.get("deadline")]

        overview = [
            f"待处理任务 {len(pending_tasks)} 条，高优先级 {len(high_priority)} 条。",
            f"今日截止 {len(today_tasks)} 条，未设截止时间 {len(no_deadline)} 条。",
        ]

        schedule_lines = []
        if today_tasks:
            for task in today_tasks[:5]:
                deadline = task.get("deadline") or "今日待定"
                schedule_lines.append(f"{deadline} 前优先完成「{task.get('task', '未命名任务')}」")

        if not schedule_lines and high_priority:
            for task in high_priority[:3]:
                deadline = task.get("deadline") or "尽快"
                schedule_lines.append(f"{deadline} 安排处理「{task.get('task', '未命名任务')}」")

        if not schedule_lines and pending_tasks:
            for task in pending_tasks[:3]:
                schedule_lines.append(f"抽出专注时间推进「{task.get('task', '未命名任务')}」")

        if not schedule_lines:
            schedule_lines.append("当前没有待处理事项，可以开始收集新的任务或灵感。")

        insights = self._build_activity_insights(activities)
        return {
            "overview": overview,
            "schedule": schedule_lines,
            "insights": insights,
        }

    def _build_activity_insights(self, activities: List[Dict]) -> List[str]:
        """
        从近期活动中生成洞察摘要。

        Args:
            activities: List[Dict] - 近期活动列表。

        Returns:
            List[str] - 活动洞察文本列表。
        """
        if not activities:
            return ["最近还没有活动记录，截图识别、语音和手动录入都会沉淀在这里。"]

        source_counter = {}
        for activity in activities:
            source = activity.get("source", "unknown")
            source_counter[source] = source_counter.get(source, 0) + 1

        source_alias = {
            "screenshot": "屏幕识别",
            "manual": "手动录入",
            "voice": "语音交互",
            "planner": "日程整理",
            "system": "系统状态",
            "capture": "窗口采集",
            "snapshot": "屏幕快照",
        }

        ranked_sources = sorted(source_counter.items(), key=lambda item: item[1], reverse=True)
        insights = []
        for source, count in ranked_sources[:3]:
            insights.append(f"最近主要活动来源：{source_alias.get(source, source)} {count} 次。")

        latest = activities[0]
        insights.append(f"最近一条记录是「{latest.get('title', '未命名活动')}」。")

        capture_items = [item for item in activities if item.get("source") == "capture" and item.get("details")]
        if capture_items:
            insights.append(f"最近关注窗口：{capture_items[0].get('details', '未知窗口')}。")

        snapshot_items = [item for item in activities if item.get("source") == "snapshot" and item.get("details")]
        if snapshot_items:
            insights.append(f"最近已记录屏幕快照：{snapshot_items[0].get('details', '未知上下文')}。")
        return insights

    def _is_today(self, deadline_text: str) -> bool:
        """
        判断截止时间是否落在今天。

        Args:
            deadline_text: str - 截止时间文本。

        Returns:
            bool - 是否为今天。
        """
        if not deadline_text:
            return False

        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(deadline_text, fmt).date() == datetime.now().date()
            except ValueError:
                continue
        return False
