const express = require('express');
const path = require('path');

require('dotenv').config();

const { createLogger } = require('./logger');
const { readState, updateState, ensureStoreReady, getDataFilePath, writeState } = require('./store');
const {
  buildTaskStats,
  createTask,
  filterTasks,
  isValidTaskText,
  sortTasks,
  updateTask,
} = require('./services/taskService');
const { createActivity, sortActivities } = require('./services/activityService');
const { buildCandidates, buildDailyDigest } = require('./services/insightService');
const { analyzeScreenshot } = require('./services/screenshotService');
const { buildExportPayload, mergeStates, normalizeImportedState } = require('./services/stateService');

const logger = createLogger('server');
const preferredPort = Number(process.env.PORT || 3000);
const projectRoot = path.resolve(__dirname, '..');
let runtimePort = preferredPort;

/**
 * 生成仪表盘数据。
 * @param {{tasks: Array, activities: Array}} [state] - 可选状态对象。
 * @returns {{tasks: Array, activities: Array, candidates: Array, digest: Record<string, string[]>, stats: Record<string, number>}} - 页面初始化数据。
 */
function buildDashboard(state = readState()) {
  const tasks = sortTasks(state.tasks);
  const activities = sortActivities(state.activities);

  return {
    tasks,
    activities,
    candidates: buildCandidates(tasks, activities),
    digest: buildDailyDigest(tasks, activities),
    stats: {
      ...buildTaskStats(tasks),
      activities: activities.length,
    },
  };
}

/**
 * 查询单个任务。
 * @param {Array<Record<string, any>>} tasks - 任务列表。
 * @param {string} taskId - 任务 ID。
 * @returns {Record<string, any> | undefined} - 匹配任务。
 */
function findTask(tasks, taskId) {
  return tasks.find((task) => task.id === taskId);
}

/**
 * 新增活动记录。
 * @param {{tasks: Array, activities: Array}} state - 当前状态。
 * @param {Record<string, any>} payload - 活动输入。
 * @returns {{tasks: Array, activities: Array}} - 更新后的状态。
 */
function appendActivityToState(state, payload) {
  const activity = createActivity(payload);
  return {
    ...state,
    activities: [activity, ...state.activities].slice(0, 500),
  };
}

/**
 * 创建 Express 应用。
 * @returns {import('express').Express} - Express 应用实例。
 */
function createApp() {
  const app = express();

  app.use(express.json({ limit: '8mb' }));
  app.use(express.static(projectRoot));

  app.get('/api/health', (request, response) => {
    response.json({
      status: 'ok',
      port: runtimePort,
      dataFile: getDataFilePath(),
    });
  });

  app.get('/api/dashboard', (request, response) => {
    response.json(buildDashboard());
  });

  app.get('/api/tasks', (request, response) => {
    const dashboard = buildDashboard();
    response.json(
      filterTasks(dashboard.tasks, {
        status: request.query.status,
        priority: request.query.priority,
        query: request.query.q,
      }),
    );
  });

  app.post('/api/tasks', (request, response) => {
    const taskText = String(request.body.task || '').trim();
    if (!isValidTaskText(taskText)) {
      response.status(400).json({ message: '任务内容不能为空。' });
      return;
    }

    let createdTask;
    const nextState = updateState((state) => {
      createdTask = createTask({
        task: taskText,
        deadline: request.body.deadline || '',
        priority: request.body.priority || 2,
        status: request.body.status || 'pending',
        source: request.body.source || 'manual',
        screenshot: request.body.screenshot || '',
      });

      return appendActivityToState(
        {
          ...state,
          tasks: [...state.tasks, createdTask],
        },
        {
          source: request.body.source || 'manual',
          title: '新增任务',
          details: createdTask.task,
          payload: {
            taskId: createdTask.id,
          },
        },
      );
    });

    logger.info('已新增任务', { id: createdTask.id });
    response.status(201).json({
      task: createdTask,
      stats: buildDashboard(nextState).stats,
    });
  });

  app.patch('/api/tasks/:taskId', (request, response) => {
    const currentState = readState();
    const currentTask = findTask(currentState.tasks, request.params.taskId);

    if (!currentTask) {
      response.status(404).json({ message: '任务不存在。' });
      return;
    }

    if (request.body.task !== undefined && !isValidTaskText(request.body.task)) {
      response.status(400).json({ message: '任务内容不能为空。' });
      return;
    }

    let nextTask;
    const nextState = updateState((state) => {
      const nextTasks = state.tasks.map((task) => {
        if (task.id !== request.params.taskId) {
          return task;
        }

        nextTask = updateTask(task, request.body);
        return nextTask;
      });

      return appendActivityToState(
        {
          ...state,
          tasks: nextTasks,
        },
        {
          source: 'system',
          title: '更新任务',
          details: nextTask.task,
          payload: {
            taskId: nextTask.id,
            status: nextTask.status,
          },
        },
      );
    });

    response.json({
      task: nextTask,
      stats: buildDashboard(nextState).stats,
    });
  });

  app.post('/api/tasks/:taskId/toggle', (request, response) => {
    const currentState = readState();
    const currentTask = findTask(currentState.tasks, request.params.taskId);

    if (!currentTask) {
      response.status(404).json({ message: '任务不存在。' });
      return;
    }

    let nextTask;
    const nextState = updateState((state) => {
      const nextTasks = state.tasks.map((task) => {
        if (task.id !== request.params.taskId) {
          return task;
        }

        nextTask = updateTask(task, {
          status: task.status === 'completed' ? 'pending' : 'completed',
        });
        return nextTask;
      });

      return appendActivityToState(
        {
          ...state,
          tasks: nextTasks,
        },
        {
          source: 'system',
          title: nextTask.status === 'completed' ? '完成任务' : '恢复任务',
          details: nextTask.task,
          payload: {
            taskId: nextTask.id,
            status: nextTask.status,
          },
        },
      );
    });

    response.json({
      task: nextTask,
      stats: buildDashboard(nextState).stats,
    });
  });

  app.post('/api/tasks/clear-completed', (request, response) => {
    let removedCount = 0;
    const nextState = updateState((state) => {
      removedCount = state.tasks.filter((task) => task.status === 'completed').length;
      const cleanedState = {
        ...state,
        tasks: state.tasks.filter((task) => task.status !== 'completed'),
      };

      return appendActivityToState(cleanedState, {
        source: 'system',
        title: '清理已完成任务',
        details: `本次共清理 ${removedCount} 条任务`,
      });
    });

    response.json({
      removedCount,
      stats: buildDashboard(nextState).stats,
    });
  });

  app.delete('/api/tasks/:taskId', (request, response) => {
    const currentState = readState();
    const currentTask = findTask(currentState.tasks, request.params.taskId);

    if (!currentTask) {
      response.status(404).json({ message: '任务不存在。' });
      return;
    }

    updateState((state) => {
      return appendActivityToState(
        {
          ...state,
          tasks: state.tasks.filter((task) => task.id !== request.params.taskId),
        },
        {
          source: 'system',
          title: '删除任务',
          details: currentTask.task,
          payload: {
            taskId: currentTask.id,
          },
        },
      );
    });

    response.status(204).send();
  });

  app.get('/api/activities', (request, response) => {
    response.json(buildDashboard().activities);
  });

  app.post('/api/activities', (request, response) => {
    const title = String(request.body.title || '').trim();
    if (!title) {
      response.status(400).json({ message: '活动标题不能为空。' });
      return;
    }

    let createdActivity;
    updateState((state) => {
      createdActivity = createActivity(request.body);
      return {
        ...state,
        activities: [createdActivity, ...state.activities].slice(0, 500),
      };
    });

    response.status(201).json(createdActivity);
  });

  app.get('/api/candidates', (request, response) => {
    response.json(buildDashboard().candidates);
  });

  app.get('/api/digest', (request, response) => {
    response.json(buildDashboard().digest);
  });

  app.get('/api/export', (request, response) => {
    response.json(buildExportPayload(readState()));
  });

  app.post('/api/import', (request, response) => {
    const mode = request.body.mode === 'replace' ? 'replace' : 'merge';
    const importedState = normalizeImportedState(request.body.data || {});

    const finalState = mode === 'replace'
      ? importedState
      : mergeStates(readState(), importedState);

    const nextState = appendActivityToState(finalState, {
      source: 'system',
      title: '导入数据',
      details: `导入模式：${mode === 'replace' ? '覆盖' : '合并'}`,
      payload: {
        mode,
        taskCount: importedState.tasks.length,
        activityCount: importedState.activities.length,
      },
    });

    writeState(nextState);
    response.json({
      message: '数据导入完成。',
      dashboard: buildDashboard(nextState),
    });
  });

  app.post('/api/analyze-screenshot', (request, response) => {
    const noteText = String(request.body.notes || '').trim();
    const screenshotTasks = analyzeScreenshot(request.body);

    let createdTasks = [];
    const nextState = updateState((state) => {
      createdTasks = screenshotTasks.map((item) => {
        return createTask({
          task: item.task,
          priority: item.priority,
          source: 'screenshot',
          screenshot: request.body.imageData || '',
        });
      });

      return appendActivityToState(
        {
          ...state,
          tasks: [...state.tasks, ...createdTasks],
        },
        {
          source: 'screenshot',
          title: '录入截图',
          details: noteText || '未填写截图备注',
          payload: {
            taskCount: createdTasks.length,
          },
        },
      );
    });

    response.status(201).json({
      tasks: createdTasks,
      message: `已根据截图生成 ${createdTasks.length} 条任务。`,
      stats: buildDashboard(nextState).stats,
    });
  });

  app.get('/', (request, response) => {
    response.sendFile(path.join(projectRoot, 'index.html'));
  });

  app.get('/demo', (request, response) => {
    response.sendFile(path.join(projectRoot, 'demo.html'));
  });

  app.use((error, request, response, next) => {
    logger.error('未处理异常', error.message);
    response.status(500).json({
      message: '服务内部错误，请稍后重试。',
    });
  });

  return app;
}

/**
 * 尝试监听可用端口。
 * @param {import('express').Express} app - Express 应用实例。
 * @param {number} port - 目标端口。
 * @param {number} maxAttempts - 最多尝试次数。
 * @returns {Promise<{server: import('http').Server, port: number}>} - 服务实例与最终端口。
 */
function listenWithFallback(app, port, maxAttempts = 10) {
  return new Promise((resolve, reject) => {
    /**
     * 递归尝试监听端口。
     * @param {number} currentPort - 当前尝试端口。
     * @param {number} attemptsLeft - 剩余尝试次数。
     * @returns {void} - 无返回值。
     */
    function tryListen(currentPort, attemptsLeft) {
      const server = app.listen(currentPort, () => {
        resolve({
          server,
          port: currentPort,
        });
      });

      server.once('error', (error) => {
        if (error.code === 'EADDRINUSE' && attemptsLeft > 1) {
          logger.info(`端口 ${currentPort} 已占用，尝试切换到 ${currentPort + 1}`);
          tryListen(currentPort + 1, attemptsLeft - 1);
          return;
        }

        reject(error);
      });
    }

    tryListen(port, maxAttempts);
  });
}

/**
 * 启动 HTTP 服务。
 * @returns {Promise<import('http').Server>} - HTTP 服务实例。
 */
function startServer() {
  ensureStoreReady();
  logger.info('数据文件已就绪', { file: getDataFilePath() });
  const app = createApp();

  return listenWithFallback(app, preferredPort).then(({ server, port }) => {
    runtimePort = port;
    logger.info(`服务已启动：http://localhost:${port}`);
    return server;
  });
}

if (require.main === module) {
  startServer().catch((error) => {
    logger.error('服务启动失败', error.message);
    process.exit(1);
  });
}

module.exports = {
  buildDashboard,
  createApp,
  startServer,
};
