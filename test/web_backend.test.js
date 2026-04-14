const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildTaskStats,
  createTask,
  filterTasks,
  sortTasks,
  updateTask,
} = require('../backend/services/taskService');
const { buildCandidates, buildDailyDigest } = require('../backend/services/insightService');
const { analyzeScreenshot } = require('../backend/services/screenshotService');
const { mergeStates, normalizeImportedState } = require('../backend/services/stateService');

/**
 * 构造今天的 ISO 时间。
 * @returns {string} - 当前日期时间字符串。
 */
function buildTodayIso() {
  const now = new Date();
  now.setHours(18, 0, 0, 0);
  return now.toISOString();
}

test('任务服务会标准化任务并允许更新状态', () => {
  const task = createTask({
    task: '完成网页重构',
    priority: 9,
  });

  assert.equal(task.priority, 3);
  assert.equal(task.status, 'pending');

  const completedTask = updateTask(task, {
    status: 'completed',
  });

  assert.equal(completedTask.status, 'completed');
  assert.equal(completedTask.created_at, task.created_at);
});

test('任务排序会优先展示待办和高优先级任务', () => {
  const tasks = sortTasks([
    createTask({ task: '已完成事项', priority: 1, status: 'completed' }),
    createTask({ task: '普通任务', priority: 2 }),
    createTask({ task: '紧急任务', priority: 1 }),
  ]);

  assert.equal(tasks[0].task, '紧急任务');
  assert.equal(tasks[1].task, '普通任务');
  assert.equal(tasks[2].task, '已完成事项');
});

test('日程摘要会统计今日任务与活动洞察', () => {
  const digest = buildDailyDigest(
    [
      createTask({ task: '今日收尾', priority: 1, deadline: buildTodayIso() }),
      createTask({ task: '后续优化', priority: 2 }),
    ],
    [
      {
        id: 'a1',
        source: 'manual',
        title: '记录灵感',
        details: '整理首页区块',
        created_at: new Date().toISOString(),
      },
    ],
  );

  assert.ok(digest.overview[0].includes('待处理任务 2 条'));
  assert.ok(digest.schedule.some((item) => item.includes('今日收尾')));
  assert.ok(digest.insights.some((item) => item.includes('记录灵感')));
});

test('候选任务会从高优任务和活动流中生成建议', () => {
  const candidates = buildCandidates(
    [
      createTask({ id: 't1', task: '修复接口异常', priority: 1 }),
    ],
    [
      {
        id: 'a1',
        source: 'screenshot',
        title: '录入截图',
        details: '登录页面报错信息',
        created_at: new Date().toISOString(),
      },
    ],
  );

  assert.equal(candidates.length, 2);
  assert.ok(candidates[0].task.includes('补充明确截止时间'));
  assert.ok(candidates[1].task.includes('登录页面报错信息'));
});

test('截图分析会根据备注拆出启发式任务', () => {
  const tasks = analyzeScreenshot({
    notes: '修复登录按钮；整理评审意见',
  });

  assert.equal(tasks.length, 2);
  assert.equal(tasks[0].priority, 1);
  assert.ok(tasks[0].task.includes('修复登录按钮'));
});

test('任务服务支持按状态和关键词过滤并生成统计', () => {
  const tasks = [
    createTask({ task: '整理接口文档', priority: 1 }),
    createTask({ task: '补充测试用例', priority: 2, status: 'completed' }),
    createTask({ task: '修复导入异常', priority: 1 }),
  ];

  const filtered = filterTasks(tasks, {
    status: 'pending',
    query: '导入',
  });
  const stats = buildTaskStats(tasks);

  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].task, '修复导入异常');
  assert.equal(stats.total, 3);
  assert.equal(stats.pending, 2);
  assert.equal(stats.completed, 1);
  assert.equal(stats.highPriority, 2);
});

test('导入状态服务会规范化并合并数据', () => {
  const imported = normalizeImportedState({
    tasks: [{ task: '新导入任务', priority: 5 }],
    activities: [{ source: 'manual', title: '导入活动', details: '测试导入' }],
  });

  const merged = mergeStates(
    {
      tasks: [createTask({ id: 'fixed-task', task: '原任务', priority: 2 })],
      activities: [],
    },
    imported,
  );

  assert.equal(imported.tasks[0].priority, 3);
  assert.equal(merged.tasks.length, 2);
  assert.equal(merged.activities.length, 1);
  assert.equal(merged.activities[0].title, '导入活动');
});
