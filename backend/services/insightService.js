const ACTION_KEYWORDS = [
  '完成',
  '整理',
  '准备',
  '提交',
  '修复',
  '更新',
  '设计',
  '实现',
  '安排',
  '联系',
  '同步',
  '复盘',
  '测试',
  '编写',
  '修改',
  '优化',
];

/**
 * 判断文本是否可视为今天。
 * @param {string} deadlineText - 截止时间文本。
 * @returns {boolean} - 是否是今天。
 */
function isToday(deadlineText) {
  if (!deadlineText) {
    return false;
  }

  const deadline = new Date(deadlineText);
  if (Number.isNaN(deadline.getTime())) {
    return false;
  }

  const today = new Date();
  return deadline.toDateString() === today.toDateString();
}

/**
 * 生成日程摘要。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @param {Array<Record<string, any>>} activities - 活动列表。
 * @returns {{overview: string[], schedule: string[], insights: string[]}} - 摘要结果。
 */
function buildDailyDigest(tasks, activities) {
  const pendingTasks = tasks.filter((task) => task.status !== 'completed');
  const todayTasks = pendingTasks.filter((task) => isToday(task.deadline));
  const highPriority = pendingTasks.filter((task) => task.priority === 1);
  const noDeadline = pendingTasks.filter((task) => !task.deadline);

  const overview = [
    `待处理任务 ${pendingTasks.length} 条，高优先级 ${highPriority.length} 条。`,
    `今日截止 ${todayTasks.length} 条，未设截止时间 ${noDeadline.length} 条。`,
  ];

  const schedule = [];
  if (todayTasks.length > 0) {
    todayTasks.slice(0, 5).forEach((task) => {
      schedule.push(`${task.deadline || '今天'} 前优先完成「${task.task}」`);
    });
  }

  if (schedule.length === 0 && highPriority.length > 0) {
    highPriority.slice(0, 3).forEach((task) => {
      schedule.push(`${task.deadline || '尽快'} 安排处理「${task.task}」`);
    });
  }

  if (schedule.length === 0 && pendingTasks.length > 0) {
    pendingTasks.slice(0, 3).forEach((task) => {
      schedule.push(`抽出专注时间推进「${task.task}」`);
    });
  }

  if (schedule.length === 0) {
    schedule.push('当前没有待处理事项，可以开始收集新的任务或灵感。');
  }

  return {
    overview,
    schedule,
    insights: buildActivityInsights(activities),
  };
}

/**
 * 生成活动洞察。
 * @param {Array<Record<string, any>>} activities - 活动列表。
 * @returns {string[]} - 洞察文案。
 */
function buildActivityInsights(activities) {
  if (activities.length === 0) {
    return ['最近还没有活动记录，截图、手动录入和系统整理都会沉淀在这里。'];
  }

  const aliasMap = {
    screenshot: '截图录入',
    manual: '手动录入',
    voice: '语音交互',
    planner: '日程整理',
    system: '系统状态',
  };

  const counter = {};
  activities.forEach((activity) => {
    counter[activity.source] = (counter[activity.source] || 0) + 1;
  });

  const ranked = Object.entries(counter).sort((left, right) => right[1] - left[1]);
  const insights = ranked.slice(0, 3).map(([source, count]) => {
    return `最近主要活动来源：${aliasMap[source] || source} ${count} 次。`;
  });

  insights.push(`最近一条记录是「${activities[0].title}」。`);
  return insights;
}

/**
 * 生成候选任务。
 * @param {Array<Record<string, any>>} tasks - 当前任务列表。
 * @param {Array<Record<string, any>>} activities - 当前活动列表。
 * @returns {Array<Record<string, any>>} - 候选任务列表。
 */
function buildCandidates(tasks, activities) {
  const existing = new Set(tasks.map((task) => normalizeText(task.task)));
  const candidates = [];

  tasks
    .filter((task) => task.status !== 'completed' && task.priority === 1 && !task.deadline)
    .forEach((task) => {
      candidates.push({
        id: `task-${task.id}`,
        task: `为「${task.task}」补充明确截止时间`,
        reason: '高优先级任务尚未设定时间边界。',
        source: 'task',
        priority: 1,
      });
    });

  activities.forEach((activity) => {
    const candidate = createCandidateFromActivity(activity);
    if (!candidate) {
      return;
    }

    const key = normalizeText(candidate.task);
    if (existing.has(key)) {
      return;
    }

    if (candidates.some((item) => normalizeText(item.task) === key)) {
      return;
    }

    candidates.push(candidate);
  });

  return candidates.slice(0, 6);
}

/**
 * 从活动中提炼候选任务。
 * @param {Record<string, any>} activity - 活动对象。
 * @returns {Record<string, any> | null} - 候选任务或空值。
 */
function createCandidateFromActivity(activity) {
  const details = String(activity.details || '').trim();

  if (activity.source === 'manual' && details) {
    return {
      id: `activity-${activity.id}`,
      task: toActionableTask(details),
      reason: '来自手动记录的上下文。',
      source: activity.source,
      priority: 2,
    };
  }

  if (activity.source === 'screenshot' && details) {
    return {
      id: `activity-${activity.id}`,
      task: `回看并整理「${shortenText(details, 24)}」中的待办信息`,
      reason: '来自截图录入，适合二次整理。',
      source: activity.source,
      priority: 2,
    };
  }

  return null;
}

/**
 * 将自由文本转成待办语义。
 * @param {string} text - 原始文本。
 * @returns {string} - 可执行任务文本。
 */
function toActionableTask(text) {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) {
    return '跟进最近记录的内容';
  }

  if (ACTION_KEYWORDS.some((keyword) => cleaned.includes(keyword))) {
    return cleaned;
  }

  return `跟进：${shortenText(cleaned, 28)}`;
}

/**
 * 截断文本长度。
 * @param {string} text - 原始文本。
 * @param {number} maxLength - 最大长度。
 * @returns {string} - 截断后的文本。
 */
function shortenText(text, maxLength) {
  return text.length <= maxLength ? text : `${text.slice(0, maxLength)}...`;
}

/**
 * 标准化文本用于去重。
 * @param {string} text - 原始文本。
 * @returns {string} - 标准化后的文本。
 */
function normalizeText(text) {
  return String(text || '').replace(/\s+/g, '').trim().toLowerCase();
}

module.exports = {
  buildCandidates,
  buildDailyDigest,
};
