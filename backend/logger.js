const LEVELS = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  ERROR: 'ERROR',
};

/**
 * 创建模块日志器。
 * @param {string} moduleName - 模块名称。
 * @returns {{debug: Function, info: Function, error: Function}} - 日志方法集合。
 */
function createLogger(moduleName) {
  /**
   * 输出标准格式日志。
   * @param {string} level - 日志级别。
   * @param {string} message - 日志消息。
   * @param {unknown} [payload] - 可选附加数据。
   * @returns {void} - 无返回值。
   */
  function log(level, message, payload) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${level}] [${moduleName}]`;

    if (payload === undefined) {
      console.log(`${prefix} ${message}`);
      return;
    }

    console.log(`${prefix} ${message}`, payload);
  }

  return {
    /**
     * 输出调试日志。
     * @param {string} message - 日志消息。
     * @param {unknown} [payload] - 可选附加数据。
     * @returns {void} - 无返回值。
     */
    debug(message, payload) {
      log(LEVELS.DEBUG, message, payload);
    },

    /**
     * 输出信息日志。
     * @param {string} message - 日志消息。
     * @param {unknown} [payload] - 可选附加数据。
     * @returns {void} - 无返回值。
     */
    info(message, payload) {
      log(LEVELS.INFO, message, payload);
    },

    /**
     * 输出错误日志。
     * @param {string} message - 日志消息。
     * @param {unknown} [payload] - 可选附加数据。
     * @returns {void} - 无返回值。
     */
    error(message, payload) {
      log(LEVELS.ERROR, message, payload);
    },
  };
}

module.exports = {
  createLogger,
};
