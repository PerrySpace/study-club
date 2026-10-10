/**
 * 接口通用契约 —— 见 04-1 §1.2 / §1.3 / §1.6。
 */

export interface ApiSuccess<T> {
  code: 0;
  message: string;
  data: T;
  request_id: string;
}

export interface ApiFailure {
  code: number;
  message: string;
  errors?: Array<{ field: string; reason: string }>;
  request_id: string;
}

export type ApiEnvelope<T> = ApiSuccess<T> | ApiFailure;

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Paged<T> {
  items: T[];
  pagination: Pagination;
}

/** 客户端标识请求头（由各端 HttpAdapter 统一注入，业务代码不感知）。 */
export interface ClientHeaders {
  'X-Client-Client': string;
  'X-Client-Platform': string;
  'X-Client-Form': string;
  'X-Client-Version': string;
  'X-Client-Capabilities'?: string;
}

/** 运行时可用的客户端能力集（用于服务端降级与前端降级路径）。 */
export interface ClientCapabilities {
  record: boolean;
  local_asr: boolean;
  realtime_audio: boolean;
  handwriting: boolean;
  offline: boolean;
  push: boolean;
  /**
   * 浏览器原生朗读（TTS）可用。**免费能力**，Android/iOS/桌面主流内核均支持。
   * 缺失时「朗读」按钮整块不渲染（而不是渲染一个点了没反应的按钮）。
   */
  speech_synthesis: boolean;
  /**
   * 浏览器原生语音识别（ASR）可用。
   * Firefox 与部分国产内核**不支持**（`SpeechRecognition` 不存在），
   * 这类环境里「跟读」必须降级为「我听过了」确认，不能安静地什么都不做。
   */
  speech_recognition: boolean;
}

/** 新建孩子档案时写入 child 文档的初值（家长可在客户端再单独改）。 */
export interface SiteDefaults {
  daily_new_char_target: number;
  daily_review_target: number;
  daily_time_limit_min: number;
}

/**
 * 玩法配置 —— **后台可热改的全体玩法开关**。
 *
 * 这是「后台控制与客户端玩法同步」的唯一契约：客户端不自己写死一套玩法表，
 * 而是启动时读它并照此渲染。因此它的字段就是后台运营能控制的东西：
 * 题型开关、阶段检测节奏、跟读开关、字源图、朗读语速。
 *
 * 取值合法性由服务端 `core/runtime_config.py` 统一收口（越界 clamp、
 * 未知题型丢弃），客户端只按收到的值执行，不重复校验。
 */
export interface GameplayConfig {
  /** 每学 N 个新字插入一次「旧字抽查」（阶段检测）。只推新字不回头是识字最大的坑。 */
  stage_test_every: number;
  /** 允许出现的题型（取值见后端 QUESTION_STEMS 的键集）。 */
  enabled_question_types: string[];
  /** 跟读开关；关闭后跟读题型整块不出现。 */
  enable_speak: boolean;
  /** 是否展示字源图（象形 emoji / 绑定图片）。 */
  show_pictograph: boolean;
  /** 朗读语速（0.6–1.2）。 */
  speak_rate: number;
}

/**
 * 一个年级档位。
 *
 * ⛔ 年级**不再是写死 1–6**：后台可任意增删（幼小衔接、七年级甚至更高），
 * 因此 `id` 是数值而非枚举成员，`label` 由运营自定义。
 * 上界 30 见服务端 `GRADE_MAX`，只是防脏数据的守卫，不构成业务限制。
 */
export interface GradeOption {
  id: number;
  label: string;
  enabled: boolean;
}

/** 站点公开配置（`GET /config` 出参，无需登录）。 */
export interface SitePublicConfig {
  require_invite: boolean;
  registration_open: boolean;
  announcement: string;
  defaults: SiteDefaults;
  gameplay: GameplayConfig;
  /**
   * 年级表。免登录下发 —— 注册页与引导页在**登录前**就要选年级，
   * 那时还没有账号能带 token。
   */
  grades: GradeOption[];
}
