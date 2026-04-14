const fs = require('fs');
const path = require('path');

const { createLogger } = require('./logger');

const logger = createLogger('store');
const defaultDataFile = path.join(process.cwd(), 'data', 'web-data.json');

/**
 * 生成默认数据结构。
 * @returns {{tasks: Array, activities: Array}} - 默认状态对象。
 */
function createDefaultState() {
  return {
    tasks: [],
    activities: [],
  };
}

/**
 * 获取数据文件路径。
 * @returns {string} - 绝对路径。
 */
function getDataFilePath() {
  return process.env.GLANCE_DATA_FILE
    ? path.resolve(process.cwd(), process.env.GLANCE_DATA_FILE)
    : defaultDataFile;
}

/**
 * 确保存储目录与文件存在。
 * @returns {string} - 数据文件路径。
 */
function ensureStoreReady() {
  const filePath = getDataFilePath();
  const directory = path.dirname(filePath);

  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, { recursive: true });
  }

  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(createDefaultState(), null, 2), 'utf8');
    logger.info('已创建初始数据文件', { filePath });
  }

  return filePath;
}

/**
 * 读取当前应用状态。
 * @returns {{tasks: Array, activities: Array}} - 当前状态。
 */
function readState() {
  const filePath = ensureStoreReady();
  const text = fs.readFileSync(filePath, 'utf8');

  try {
    const parsed = JSON.parse(text);
    return {
      tasks: Array.isArray(parsed.tasks) ? parsed.tasks : [],
      activities: Array.isArray(parsed.activities) ? parsed.activities : [],
    };
  } catch (error) {
    logger.error('数据文件解析失败，已回退为空状态', error.message);
    return createDefaultState();
  }
}

/**
 * 写回完整应用状态。
 * @param {{tasks: Array, activities: Array}} nextState - 新状态。
 * @returns {{tasks: Array, activities: Array}} - 已写入状态。
 */
function writeState(nextState) {
  const filePath = ensureStoreReady();
  const safeState = {
    tasks: Array.isArray(nextState.tasks) ? nextState.tasks : [],
    activities: Array.isArray(nextState.activities) ? nextState.activities : [],
  };

  fs.writeFileSync(filePath, JSON.stringify(safeState, null, 2), 'utf8');
  return safeState;
}

/**
 * 基于回调更新应用状态。
 * @param {(state: {tasks: Array, activities: Array}) => {tasks: Array, activities: Array}} updater - 状态更新器。
 * @returns {{tasks: Array, activities: Array}} - 更新后的状态。
 */
function updateState(updater) {
  const currentState = readState();
  const nextState = updater(currentState);
  return writeState(nextState);
}

module.exports = {
  createDefaultState,
  ensureStoreReady,
  getDataFilePath,
  readState,
  writeState,
  updateState,
};
