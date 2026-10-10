/**
 * 算法层导出。
 *
 * ⚠️ 这里只应有**纯函数且学科无关**的东西。
 * 原先的 `daily-task.ts`（客户端生成今日任务）已删除：每日任务由服务端生成
 * （`GET /learning/daily-task`、`state.daily_task`），客户端再算一份没有意义，
 * 而且会和服务端选出的字不一致 —— 孩子今天该学哪几个字不应该取决于用哪台设备。
 */
export * from './srs';
export * from './lessons';
