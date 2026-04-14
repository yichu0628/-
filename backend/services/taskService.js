const crypto = require('crypto');

/**
 * 获取当前时间字符串。
 * @returns {string} - 标准时间字符串。
 */
function getNowText() {
  return new Date().toISOString();
}

/**
 * 生成唯一标识。
 * @returns {string} - 唯一 ID。
 */
function createId() {
  return crypto.randomUUID();
}

/**
 * 对优先级做边界修正。
 * @param {number} priority - 原始优先级。
 * @returns {number} - 1 到 3 之间的优先级。
 */
function normalizePriority(priority) {
  const value = Number(priority || 2);
  return Math.max(1, Math.min(3, value));
}

/**
 * 对任务状态做兜底处理。
 * @param {string} status - 原始状态。
 * @returns {string} - 合法状态值。
 */
function normalizeStatus(status) {
  return status === 'completed' ? 'completed' : 'pending';
}

/**
 * 规范化截止时间文本。
 * @param {string} deadline - 原始截止时间。
 * @returns {string} - 合法的 ISO 时间或空字符串。
 */
function normalizeDeadline(deadline) {
  if (!deadline) {
    return '';
  }

  const date = new Date(deadline);
  return Number.isNaN(date.getTime()) ? '' : date.toISOString();
}

/**
 * 规范化任务对象。
 * @param {Record<string, any>} input - 原始任务数据。
 * @returns {Record<string, any>} - 标准任务对象。
 */
function normalizeTask(input) {
  return {
    id: input.id || createId(),
    task: String(input.task || '').trim(),
    deadline: normalizeDeadline(input.deadline),
    priority: normalizePriority(input.priority),
    status: normalizeStatus(input.status),
    source: input.source ? String(input.source) : 'manual',
    screenshot: input.screenshot || '',
    created_at: input.created_at || getNowText(),
    updated_at: input.updated_at || getNowText(),
  };
}

/**
 * 创建新任务。
 * @param {Record<string, any>} payload - 任务输入数据。
 * @returns {Record<string, any>} - 新任务对象。
 */
function createTask(payload) {
  return normalizeTask(payload);
}

/**
 * 更新已有任务。
 * @param {Record<string, any>} task - 原任务对象。
 * @param {Record<string, any>} patch - 更新字段。
 * @returns {Record<string, any>} - 更新后的任务对象。
 */
function updateTask(task, patch) {
  return normalizeTask({
    ...task,
    ...patch,
    id: task.id,
    created_at: task.created_at,
    updated_at: getNowText(),
  });
}

/**
 * 对任务列表排序。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @returns {Array<Record<string, any>>} - 排序后的任务列表。
 */
function sortTasks(tasks) {
  return [...tasks].sort((left, right) => {
    if (left.status !== right.status) {
      return left.status === 'pending' ? -1 : 1;
    }

    if (left.priority !== right.priority) {
      return left.priority - right.priority;
    }

    if (!left.deadline && right.deadline) {
      return 1;
    }

    if (left.deadline && !right.deadline) {
      return -1;
    }

    const deadlineCompare = String(left.deadline || '').localeCompare(String(right.deadline || ''));
    if (deadlineCompare !== 0) {
      return deadlineCompare;
    }

    return String(right.updated_at || '').localeCompare(String(left.updated_at || ''));
  });
}

/**
 * 过滤待办任务。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @returns {Array<Record<string, any>>} - 待办任务列表。
 */
function getPendingTasks(tasks) {
  return tasks.filter((task) => task.status !== 'completed');
}

/**
 * 判断任务文本是否有效。
 * @param {string} text - 原始任务文本。
 * @returns {boolean} - 是否有效。
 */
function isValidTaskText(text) {
  return String(text || '').trim().length > 0;
}

/**
 * 按条件过滤任务。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @param {{status?: string, priority?: string | number, query?: string}} filters - 过滤条件。
 * @returns {Array<Record<string, any>>} - 过滤后的任务列表。
 */
function filterTasks(tasks, filters = {}) {
  const status = String(filters.status || 'all');
  const priority = String(filters.priority || 'all');
  const query = String(filters.query || '').trim().toLowerCase();

  return tasks.filter((task) => {
    if (status !== 'all' && task.status !== status) {
      return false;
    }

    if (priority !== 'all' && String(task.priority) !== priority) {
      return false;
    }

    if (query) {
      const haystack = `${task.task} ${task.deadline} ${task.source}`.toLowerCase();
      return haystack.includes(query);
    }

    return true;
  });
}

/**
 * 统计任务概览数据。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @returns {{total: number, pending: number, completed: number, highPriority: number}} - 统计结果。
 */
function buildTaskStats(tasks) {
  return {
    total: tasks.length,
    pending: tasks.filter((task) => task.status !== 'completed').length,
    completed: tasks.filter((task) => task.status === 'completed').length,
    highPriority: tasks.filter((task) => task.status !== 'completed' && task.priority === 1).length,
  };
}

module.exports = {
  buildTaskStats,
  createTask,
  filterTasks,
  getNowText,
  getPendingTasks,
  isValidTaskText,
  normalizeDeadline,
  normalizeTask,
  sortTasks,
  updateTask,
};
