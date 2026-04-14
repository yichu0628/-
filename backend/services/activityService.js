const crypto = require('crypto');

/**
 * 获取当前时间字符串。
 * @returns {string} - 时间字符串。
 */
function getCreatedAt() {
  return new Date().toISOString();
}

/**
 * 生成活动唯一标识。
 * @returns {string} - 活动 ID。
 */
function createActivityId() {
  return crypto.randomUUID();
}

/**
 * 构建标准活动对象。
 * @param {Record<string, any>} payload - 原始活动数据。
 * @returns {Record<string, any>} - 活动对象。
 */
function createActivity(payload) {
  return {
    id: payload.id || createActivityId(),
    source: String(payload.source || 'system'),
    title: String(payload.title || '未命名活动'),
    details: String(payload.details || ''),
    payload: payload.payload && typeof payload.payload === 'object' ? payload.payload : {},
    created_at: payload.created_at || getCreatedAt(),
  };
}

/**
 * 对活动列表按时间倒序排序。
 * @param {Array<Record<string, any>>} activities - 活动列表。
 * @returns {Array<Record<string, any>>} - 排序后的活动列表。
 */
function sortActivities(activities) {
  return [...activities].sort((left, right) => {
    return String(right.created_at).localeCompare(String(left.created_at));
  });
}

module.exports = {
  createActivity,
  sortActivities,
};
