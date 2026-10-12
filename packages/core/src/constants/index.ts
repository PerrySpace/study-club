export * from './enums';
export * from './error-codes';

// ⚠️ `export *` 不会在本模块内建立局部绑定，下面要用到 ERROR_CODE 必须显式 import。
import { ERROR_CODE } from './error-codes';

/**
 * 导出包 Schema 版本（数据可迁移性用）。
 *
 * ⚠️ 已不再有「本地数据 Schema 版本」—— 学习数据只在服务端，
 * 浏览器不持有任何业务数据，因此不存在本地迁移问题。
 * 本常量现在只用于 `/learning/export` 导出包的兼容判定。
 */
export const EXPORT_SCHEMA_VERSION = 1;

/** localStorage 仅存这一个键：会话 Token（业务数据一律不落浏览器）。 */
export const SESSION_STORAGE_KEY = 'sc.session';

/**
 * 「Token 已死」的两个错误码：过期与失效。
 *
 * 只有这两个码才代表**凭据本身**不可用 —— 其余错误（网络异常、参数错误、
 * 账号密码错误 40107 等）都不该清会话，也不该触发静默刷新。
 * 由 api 层（决定要不要刷新重试）与 auth store（决定要不要清会话）共用，
 * 定义在这里是为了避免两处各写一份、日后改一处漏一处。
 */
export const TOKEN_DEAD_CODES: readonly number[] = [
  ERROR_CODE.TOKEN_EXPIRED,
  ERROR_CODE.TOKEN_INVALID,
];

/** 刷新接口自身的路径：它返回 40102 时**不能**再触发刷新，否则递归。 */
export const AUTH_REFRESH_PATH = '/auth/refresh';
