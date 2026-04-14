/**
 * 基于截图上下文生成启发式任务。
 * @param {{notes?: string, imageData?: string}} payload - 截图录入数据。
 * @returns {Array<{task: string, priority: number}>} - 任务建议列表。
 */
function analyzeScreenshot(payload) {
  const noteText = String(payload.notes || '').trim();

  if (noteText) {
    return buildTasksFromNotes(noteText);
  }

  return [
    {
      task: '查看刚上传的截图并整理其中的待办信息',
      priority: 2,
    },
  ];
}

/**
 * 根据备注文本拆解截图任务。
 * @param {string} noteText - 用户填写的备注。
 * @returns {Array<{task: string, priority: number}>} - 任务建议列表。
 */
function buildTasksFromNotes(noteText) {
  const segments = noteText
    .split(/[；;。！？\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (segments.length === 0) {
    return [
      {
        task: '回看截图并补充待办描述',
        priority: 2,
      },
    ];
  }

  return segments.slice(0, 3).map((item, index) => {
    return {
      task: item.startsWith('跟进') || item.startsWith('完成') ? item : `跟进：${item}`,
      priority: index === 0 ? 1 : 2,
    };
  });
}

module.exports = {
  analyzeScreenshot,
};
