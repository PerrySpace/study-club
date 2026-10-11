/**
 * 能力开关（Feature Flag）—— 前端「掩藏」的唯一实现机制。
 *
 * 权威清单见 docs/02-系统架构/03-存储与后端策略.md §六，本文件是其代码落点。
 * 三条编码纪律（见 06-1 §2.8.1）：
 *   ① 开关值只读一次（启动时求值），运行中不散落读取；
 *   ② 关闭的能力：路由不注册 + 组件不渲染 + API 抛 FeatureDisabledError + 类型保留；
 *   ③ 禁止伪隐藏（不得用 CSS display:none 或隐藏入口但接口可调）。
 */

export interface FeatureFlags {
  /** 邀请码身份（注册/登入） */
  enableInviteAuth: boolean;
  /** 是否强制凭码注册（准入放量控制）；关闭即「免码开放」 */
  enableInviteRequired: boolean;
  /** 邀请码离线签名校验（Ed25519 纯前端） */
  enableInviteOfflineVerify: boolean;
  /** 云端家庭档案与跨设备同步 */
  enableCloudProfile: boolean;
  /** 端到端加密同步 */
  enableE2EEncryption: boolean;
  /** 后端内容接口 */
  enableContentApi: boolean;
  /** 远端静态内容覆盖 */
  enableRemoteContent: boolean;
  /** 匿名统计上报 */
  enableStats: boolean;
  /** 云端语音评测（可选付费；无 Key 时整块隐藏，绝不显示假分数） */
  enableCloudAssessment: boolean;
  /** ⛔ 手机号 / 微信账号（需企业主体） */
  enableAccountAuth: boolean;
  /** ⛔ 支付与订阅（需企业主体） */
  enablePayment: boolean;
  /** ⛔ 微信小程序（需企业主体） */
  enableMiniprogram: boolean;
  /** ⛔ iOS / Android App（需企业主体） */
  enableNativeApp: boolean;
}

/** 默认值：掩藏项一律 false；主流程可用的项默认开启。 */
export const DEFAULT_FLAGS: FeatureFlags = {
  enableInviteAuth: true,
  enableInviteRequired: true,
  enableInviteOfflineVerify: true,
  enableCloudProfile: false,
  enableE2EEncryption: true,
  enableContentApi: true,
  enableRemoteContent: true,
  enableStats: true,
  enableCloudAssessment: false,
  enableAccountAuth: false,
  enablePayment: false,
  enableMiniprogram: false,
  enableNativeApp: false,
};

/** 需企业主体、永久掩藏的四项（CI 需校验构建产物不含相关代码）。 */
export const HIDDEN_FLAGS = [
  'enableAccountAuth',
  'enablePayment',
  'enableMiniprogram',
  'enableNativeApp',
] as const satisfies ReadonlyArray<keyof FeatureFlags>;

/** 环境变量名 ↔ 开关名 的映射（构建期静态求值，见 02-4 §4.1 三层开关之①）。 */
export const FLAG_ENV_KEYS: Record<string, keyof FeatureFlags> = {
  VITE_ENABLE_INVITE_AUTH: 'enableInviteAuth',
  VITE_ENABLE_INVITE_REQUIRED: 'enableInviteRequired',
  VITE_ENABLE_INVITE_OFFLINE_VERIFY: 'enableInviteOfflineVerify',
  VITE_ENABLE_CLOUD_PROFILE: 'enableCloudProfile',
  VITE_ENABLE_E2E_ENCRYPTION: 'enableE2EEncryption',
  VITE_ENABLE_CONTENT_API: 'enableContentApi',
  VITE_ENABLE_REMOTE_CONTENT: 'enableRemoteContent',
  VITE_ENABLE_STATS: 'enableStats',
  VITE_ENABLE_CLOUD_ASSESSMENT: 'enableCloudAssessment',
  VITE_ENABLE_ACCOUNT_AUTH: 'enableAccountAuth',
  VITE_ENABLE_PAYMENT: 'enablePayment',
  VITE_ENABLE_MINIPROGRAM: 'enableMiniprogram',
  VITE_ENABLE_NATIVE_APP: 'enableNativeApp',
};

const ENV_KEY_BY_FLAG = Object.fromEntries(
  Object.entries(FLAG_ENV_KEYS).map(([env, flag]) => [flag, env]),
) as Record<keyof FeatureFlags, string>;

/**
 * 从构建期环境变量 + 远端配置解析开关。
 * 优先级：远端配置（已知项）覆盖构建期默认；未知项忽略（不抛错，见 02-4 §4.5）。
 */
export function resolveFlags(
  buildEnv: Partial<Record<string, string | undefined>> = {},
  remote: Partial<Record<string, unknown>> = {},
): FeatureFlags {
  const flags: FeatureFlags = { ...DEFAULT_FLAGS };

  for (const [envKey, flagKey] of Object.entries(FLAG_ENV_KEYS)) {
    const raw = buildEnv[envKey];
    if (raw !== undefined) flags[flagKey] = raw === 'true' || raw === '1';
  }

  for (const key of Object.keys(DEFAULT_FLAGS) as Array<keyof FeatureFlags>) {
    const v = remote[key];
    if (typeof v === 'boolean') flags[key] = v;
  }

  // 掩藏项不可被远端配置打开：企业能力必须由构建期决定
  for (const key of HIDDEN_FLAGS) {
    if (buildEnv[ENV_KEY_BY_FLAG[key]] === undefined) flags[key] = DEFAULT_FLAGS[key];
  }

  return flags;
}

/** 开关容器：全局只读，避免运行中散落读取（纪律 ①）。 */
export class FlagRegistry {
  private flags: FeatureFlags;

  constructor(flags: FeatureFlags = DEFAULT_FLAGS) {
    this.flags = Object.freeze({ ...flags });
  }

  all(): Readonly<FeatureFlags> {
    return this.flags;
  }

  isEnabled(key: keyof FeatureFlags): boolean {
    return this.flags[key];
  }
}
