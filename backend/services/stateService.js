const { normalizeTask } = require('./taskService');
const { createActivity, sortActivities } = require('./activityService');

/**
 * 规范化导入状态。
 * @param {Record<string, any>} input - 原始导入对象。
 * @returns {{tasks: Array, activities: Array}} - 清洗后的状态。
 */
function normalizeImportedState(input) {
  const tasks = Array.isArray(input?.tasks) ? input.tasks.map((task) => normalizeTask(task)) : [];
  const activities = Array.isArray(input?.activities)
    ? input.activities.map((activity) => createActivity(activity))
    : [];

  return {
    tasks,
    activities: sortActivities(activities),
  };
}

/**
 * 合并当前状态与导入状态。
 * @param {{tasks: Array, activities: Array}} currentState - 当前状态。
 * @param {{tasks: Array, activities: Array}} importedState - 导入状态。
 * @returns {{tasks: Array, activities: Array}} - 合并结果。
 */
function mergeStates(currentState, importedState) {
  const taskMap = new Map();
  [...currentState.tasks, ...importedState.tasks].forEach((task) => {
    taskMap.set(task.id, normalizeTask(task));
  });

  const activityMap = new Map();
  [...currentState.activities, ...importedState.activities].forEach((activity) => {
    activityMap.set(activity.id, createActivity(activity));
  });

  return {
    tasks: [...taskMap.values()],
    activities: sortActivities([...activityMap.values()]).slice(0, 500),
  };
}

/**
 * 构造可导出的数据包。
 * @param {{tasks: Array, activities: Array}} state - 当前状态。
 * @returns {{meta: Record<string, any>, tasks: Array, activities: Array}} - 导出数据。
 */
function buildExportPayload(state) {
  return {
    meta: {
      exportedAt: new Date().toISOString(),
      app: 'glance-web',
      version: 2,
    },
    tasks: state.tasks,
    activities: state.activities,
  };
}

module.exports = {
  buildExportPayload,
  mergeStates,
  normalizeImportedState,
};
