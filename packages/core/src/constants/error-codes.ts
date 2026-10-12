/**
 * 错误码 —— 前后端共享（见 04-1 §1.4）。
 * 规则：错误码不复用（同一码不得改变含义）。
 */

export const OK = 0;

export const ERROR_CODE = {
  /** 请求参数错误 */
  PARAM_INVALID: 40001,

  /** 认证失败 */
  TOKEN_EXPIRED: 40101,
  TOKEN_INVALID: 40102,
  /** 邀请码无效 / 已用尽 / 已吊销 / 已过期（统一错误信息，防枚举） */
  INVITE_INVALID: 40103,
  /** 密码错误 */
  PASSCODE_INVALID: 40104,
  /** 账号已锁定（连续错误达阈值） */
  ACCOUNT_LOCKED: 40105,
  /** 恢复码无效 */
  RECOVERY_INVALID: 40106,
  /** 账号不存在或密码错误（用户名/手机号登录的统一错误信息，防枚举） */
  ACCOUNT_INVALID: 40107,

  /** 权限不足 */
  FORBIDDEN: 40301,
  /** 能力未开启（FeatureDisabledError 的前端对应码） */
  FEATURE_DISABLED: 40302,

  /** 批量导入部分失败（成功 + 失败的混合结果，HTTP 206）。 */
  PARTIAL_CONTENT: 40601,

  /** 资源不存在 */
  CHARACTER_NOT_FOUND: 40401,
  POEM_NOT_FOUND: 40402,
  CHILD_NOT_FOUND: 40403,
  CONTENT_NOT_FOUND: 40404,
  /** 素材不存在（文件已删除或 id 拼错）。 */
  ASSET_NOT_FOUND: 40405,

  /** 状态冲突 */
  CONTENT_EXISTS: 40902,
  /** 内容仍被关卡 / 单元 / 短文引用，物理删除被拒绝（可显式 force 强制删除）。 */
  CONTENT_IN_USE: 40903,

  /** 素材超过体积上限（见 ASSET_MAX_BYTES）。 */
  ASSET_TOO_LARGE: 41301,
  /** MIME 不在白名单内（见 ASSET_ALLOWED_MIMES）。 */
  UNSUPPORTED_MEDIA_TYPE: 41501,

  /** 频率限制 */
  RATE_LIMITED: 42901,

  /** 服务端错误 */
  INTERNAL: 50001,
  UPSTREAM_UNAVAILABLE: 50002,
  /** 素材存储目录不可写 / 已满。 */
  STORAGE_UNAVAILABLE: 50003,
} as const;

export type ErrorCodeValue = (typeof ERROR_CODE)[keyof typeof ERROR_CODE];

/** 业务异常：由 api 层抛出，调用方按需提示。 */
export class BizError extends Error {
  readonly code: number;
  readonly fieldErrors?: Array<{ field: string; reason: string }>;

  constructor(
    code: number,
    message: string,
    fieldErrors?: Array<{ field: string; reason: string }>,
  ) {
    super(message);
    this.name = 'BizError';
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

/** 能力开关关闭时的调用错误（掩藏能力的统一出口，见 02-4 §4.3）。 */
export class FeatureDisabledError extends Error {
  readonly feature: string;

  constructor(feature: string) {
    super(`能力「${feature}」当前未开启`);
    this.name = 'FeatureDisabledError';
    this.feature = feature;
  }
}

/** 后端不可达（离线时属正常情况，调用方应静默降级而非报错）。 */
export class NetworkError extends Error {
  constructor(message = '网络异常') {
    super(message);
    this.name = 'NetworkError';
  }
}
