/**
 * 枚举常量 —— 前后端共享的唯一定义处（见 03-2 §八、06-1 §四）。
 * 纪律：禁止各端各写一份；后端 Pydantic 从同一份取值派生。
 */

export const CLIENT = {
  web: 'web',
  miniprogram: 'miniprogram',
  app: 'app',
} as const;
export type ClientType = (typeof CLIENT)[keyof typeof CLIENT];

export const PLATFORM = {
  ios: 'ios',
  android: 'android',
  harmony: 'harmony',
  web: 'web',
} as const;
export type PlatformType = (typeof PLATFORM)[keyof typeof PLATFORM];

/** 设备形态按可用宽度判定，不按设备型号。 */
export const DEVICE_FORM = {
  phone: 'phone',
  tablet: 'tablet',
  desktop: 'desktop',
} as const;
export type DeviceFormType = (typeof DEVICE_FORM)[keyof typeof DEVICE_FORM];

/**
 * 题型 —— key 与取值都以后端 `content_controller.QUESTION_STEMS` 为准。
 * 客户端按 `type` 决定渲染方式（图片 / 音频 / 语音输入 / 笔顺 / 古诗）。
 *
 * ⚠️ 与旧版的差异：`stroke-order` 已更正为 `stroke`（后端实际取值），
 * 并补上了 `meaning-choice`、`speak`。改 key/取值前先同步后端字典，
 * 否则会出现「前端能渲染但后端不下发」这类静默失效。
 */
export const QUESTION_TYPE = {
  imageChoice: 'image-choice',
  audioChoice: 'audio-choice',
  pinyinMatch: 'pinyin-match',
  wordBuild: 'word-build',
  meaningChoice: 'meaning-choice',
  /** 跟读：需麦克风权限，走 Web Speech API 识别（不支持时降级为「听过就算」）。 */
  speak: 'speak',
  /** 笔顺：客户端用 hanzi-writer 演示与判笔，不依赖服务端素材。 */
  stroke: 'stroke',

  // ---- 古诗专用（后端 content_controller 单独生成） ----
  poemFill: 'poem-fill',
  poemOrder: 'poem-order',
  poemMatch: 'poem-match',
} as const;
export type QuestionType = (typeof QUESTION_TYPE)[keyof typeof QUESTION_TYPE];

export const CONTENT_STATUS = {
  draft: 'draft',
  pendingReview: 'pending_review',
  published: 'published',
  offline: 'offline',
  deleted: 'deleted',
} as const;
export type ContentStatus = (typeof CONTENT_STATUS)[keyof typeof CONTENT_STATUS];

export const REVIEW_STATUS = {
  learning: 'learning',
  reviewing: 'reviewing',
  mastered: 'mastered',
} as const;
export type ReviewStatus = (typeof REVIEW_STATUS)[keyof typeof REVIEW_STATUS];

/** 学段标识。 */
export const LEVEL = {
  sprout: 'sprout',
  bridge: 'bridge',
  grade1: 'grade1',
  grade2: 'grade2',
  grade3: 'grade3',
  grade4: 'grade4',
  grade5: 'grade5',
  grade6: 'grade6',
} as const;
export type LevelType = (typeof LEVEL)[keyof typeof LEVEL];

export const ACCOUNT_STATUS = {
  active: 'active',
  disabled: 'disabled',
  deleted: 'deleted',
} as const;
export type AccountStatus = (typeof ACCOUNT_STATUS)[keyof typeof ACCOUNT_STATUS];

export const ACCESS_TIER = {
  inviteOnly: 'invite_only',
  open: 'open',
} as const;
export type AccessTier = (typeof ACCESS_TIER)[keyof typeof ACCESS_TIER];

export const LESSON_STATUS = {
  pending: 'pending',
  inProgress: 'in_progress',
  completed: 'completed',
} as const;
export type DailyTaskStatus = (typeof LESSON_STATUS)[keyof typeof LESSON_STATUS];

export const STRUCTURE = ['独体', '左右', '上下', '半包围', '全包围', '品字'] as const;
export type CharStructure = (typeof STRUCTURE)[number];

export const THEME_TAGS = [
  '思乡',
  '写景',
  '咏物',
  '爱国',
  '送别',
  '边塞',
  '哲理',
  '节日',
] as const;
export type ThemeTag = (typeof THEME_TAGS)[number];

export const POEM_SOURCE = ['课标必背', '蒙学经典', '拓展'] as const;
export type PoemSource = (typeof POEM_SOURCE)[number];

/**
 * 学习伙伴头像 key。
 *
 * 规则：**默认兔子**；用户若选过动物（或上传过自定义图片），则沿用其选择。
 * 取值与 `content/avatars` 的素材 id 后缀一致，前端按 `/avatars/<key>.svg` 取图；
 * 自定义上传的图片走素材中心，此时 `avatar_key` 存 `asset:<asset_id>`，前端优先按图片渲染。
 *
 * 已移除：`IDENTITY_MODE`（`local` / `invite`）。存储口径改为「彻底服务端、必须先登录」后
 * 「先不注册也能用」的本地身份模式不再存在，保留它只会诱使新代码写出死分支。
 */
export const AVATAR = {
  rabbit: 'rabbit',
  panda: 'panda',
  fox: 'fox',
  cat: 'cat',
  dog: 'dog',
  bear: 'bear',
  penguin: 'penguin',
  owl: 'owl',
} as const;
export type AvatarKey = (typeof AVATAR)[keyof typeof AVATAR];

/** 默认头像：兔子。任何「没选过」的分支都落到它。 */
export const DEFAULT_AVATAR: AvatarKey = AVATAR.rabbit;

/** 自定义上传头像的前缀；`avatar_key` 形如 `asset:as_xxxxxxxxxxxxxxxx`。 */
export const AVATAR_ASSET_PREFIX = 'asset:';

/** 判断是否为用户上传的自定义头像，是则返回素材 id。 */
export function customAvatarAssetId(avatarKey: string | null | undefined): string | null {
  if (!avatarKey || !avatarKey.startsWith(AVATAR_ASSET_PREFIX)) return null;
  const id = avatarKey.slice(AVATAR_ASSET_PREFIX.length).trim();
  return id || null;
}
