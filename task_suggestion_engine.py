"""
候选任务整理模块
根据活动流与现有任务，生成可快速采纳的候选待办。
"""

import re
import uuid
from typing import Dict, List


class TaskSuggestionEngine:
    """候选任务整理器，负责从上下文中生成待办建议。"""

    ACTION_KEYWORDS = (
        "完成",
        "整理",
        "准备",
        "提交",
        "修复",
        "更新",
        "设计",
        "实现",
        "安排",
        "联系",
        "同步",
        "复盘",
        "测试",
        "编写",
        "修改",
        "优化",
    )

    def build_candidates(self, tasks: List[Dict], activities: List[Dict], limit: int = 6) -> List[Dict]:
        """
        生成候选任务列表。

        Args:
            tasks: List[Dict] - 当前任务列表。
            activities: List[Dict] - 最近活动列表。
            limit: int - 返回候选数量上限。

        Returns:
            List[Dict] - 候选任务列表。
        """
        existing_names = {self._normalize_text(task.get("task", "")) for task in tasks if task.get("task")}
        suggestions = []

        for task in tasks:
            if task.get("status") == "completed":
                continue
            if task.get("priority") == 1 and not task.get("deadline"):
                suggestions.append(
                    self._build_candidate(
                        task=f"为「{task.get('task', '未命名任务')}」补充明确截止时间",
                        reason="高优先级任务尚未设定时间边界。",
                        source="task",
                        priority=1,
                    )
                )

        for activity in activities:
            candidate = self._suggest_from_activity(activity)
            if not candidate:
                continue
            normalized = self._normalize_text(candidate["task"])
            if normalized in existing_names:
                continue
            if any(self._normalize_text(item["task"]) == normalized for item in suggestions):
                continue
            suggestions.append(candidate)

        return suggestions[: max(1, limit)]

    def _suggest_from_activity(self, activity: Dict) -> Dict:
        """
        从单条活动中推导候选任务。

        Args:
            activity: Dict - 活动数据。

        Returns:
            Dict - 候选任务对象，无法推导时返回空字典。
        """
        source = activity.get("source", "")
        title = activity.get("title", "")
        details = (activity.get("details", "") or "").strip()
        payload = activity.get("payload", {}) or {}

        if source == "manual" and title == "记录灵感" and details:
            task_text = self._to_actionable_task(details)
            return self._build_candidate(task_text, "来自手动记录的灵感上下文。", source, 2)

        if source == "voice" and title == "收到语音输入" and details:
            task_text = self._to_actionable_task(details)
            return self._build_candidate(task_text, "来自语音输入，可能是即时想到的事项。", source, 2)

        if source == "snapshot":
            window_title = payload.get("window_title", details)
            if window_title:
                short_title = self._shorten_text(window_title, 24)
                return self._build_candidate(
                    f"回看并整理「{short_title}」中的待办信息",
                    "来自时间轴快照，适合二次识别或人工提炼。",
                    source,
                    2,
                )

        if source == "capture":
            window_title = payload.get("window_title", details)
            if window_title and self._looks_actionable(window_title):
                short_title = self._shorten_text(window_title, 24)
                return self._build_candidate(
                    f"跟进窗口「{short_title}」中的当前工作",
                    "来自持续窗口采集，说明该上下文近期被关注。",
                    source,
                    3,
                )

        return {}

    def _to_actionable_task(self, text: str) -> str:
        """
        将自由文本转为更像待办的任务文本。

        Args:
            text: str - 原始文本。

        Returns:
            str - 任务化后的文本。
        """
        cleaned = re.sub(r"\s+", " ", text).strip(" ，。；;")
        if not cleaned:
            return "跟进最近记录的内容"
        if self._looks_actionable(cleaned):
            return cleaned
        return f"跟进：{self._shorten_text(cleaned, 28)}"

    def _looks_actionable(self, text: str) -> bool:
        """
        判断文本是否具有明显行动语义。

        Args:
            text: str - 待判断文本。

        Returns:
            bool - 是否像待办描述。
        """
        return any(keyword in text for keyword in self.ACTION_KEYWORDS)

    def _build_candidate(self, task: str, reason: str, source: str, priority: int) -> Dict:
        """
        构建标准候选任务对象。

        Args:
            task: str - 候选任务文本。
            reason: str - 生成原因。
            source: str - 来源类型。
            priority: int - 建议优先级。

        Returns:
            Dict - 候选任务对象。
        """
        return {
            "id": str(uuid.uuid4()),
            "task": task,
            "reason": reason,
            "source": source,
            "priority": max(1, min(3, priority)),
        }

    def _shorten_text(self, text: str, max_length: int) -> str:
        """
        截断过长文本。

        Args:
            text: str - 原始文本。
            max_length: int - 最大长度。

        Returns:
            str - 截断后的文本。
        """
        return text if len(text) <= max_length else f"{text[:max_length]}..."

    def _normalize_text(self, text: str) -> str:
        """
        标准化文本用于去重。

        Args:
            text: str - 原始文本。

        Returns:
            str - 标准化文本。
        """
        return re.sub(r"\s+", "", (text or "").strip().lower())
