/**
 * 后台接口的类型与调用封装 —— 逐字对齐 apps/api/app/routers/admin.py。
 *
 * 出参一律 snake_case、ObjectId 以字符串传输、时间为 ISO 8601 UTC（06-1 §四）。
 */

import { request } from './client';

// ---------------------------------------------------------------------------
// 通用
// ---------------------------------------------------------------------------
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

export interface PageQuery {
  page?: number;
  page_size?: number;
}

// ---------------------------------------------------------------------------
// 登录
// ---------------------------------------------------------------------------
export interface AdminLoginResult {
  access_token: string;
  expires_in: number;
  token_type: string;
  role: string;
}

// ---------------------------------------------------------------------------
// 概览
// ---------------------------------------------------------------------------
export interface AdminOverview {
  characters: {
    total: number;
    by_status: Record<string, number>;
    by_grade: Record<string, number>;
    assets: { audio: number; image: number; stroke_order: number };
  };
  content: {
    poems: number;
    curriculum_units: number;
    lessons: number;
    stories: number;
    badges: number;
    assets: number;
  };
  invites: {
    total: number;
    active: number;
    revoked: number;
    used_count: number;
    capacity: number;
    batches: number;
  };
  accounts: number;
  audit_logs: number;
}

// ---------------------------------------------------------------------------
// 邀请码
// ---------------------------------------------------------------------------
export type InviteChannel = 'self' | 'friend' | 'community' | 'test';

export interface AdminInvite {
  _id: string;
  code_hint: string;
  batch_id: string;
  channel: InviteChannel;
  max_uses: number;
  used_count: number;
  bound_account_ids?: string[];
  expires_at: string | null;
  revoked_at: string | null;
  note?: string | null;
  created_at: string | null;
}

export interface InviteBatchInput {
  count: number;
  /**
   * ⚠️ 恒为 1，且后端只接受 1（`le=1`，越界返回 422）。
   *
   * 邀请码就是账号的登录标识：`accounts.invite_code_hash` 上有唯一索引，
   * 一个码只能激活一个账号（02-5 §2.2 / 03-1 §3.1）。家庭内部共用
   * 「同一码 + 同一密码」进同一个档案空间；需要数据隔离就再发一个码。
   *
   * 字段保留在契约里是为了不破坏「字段只增不改不删」，但**不再由界面设置**。
   */
  max_uses?: number;
  channel: InviteChannel;
  expires_in_days?: number | null;
  batch_id?: string | null;
  note?: string | null;
}

export interface IssuedCode {
  code: string;
  code_hint: string;
}

export interface InviteBatchResult {
  batch_id: string;
  count: number;
  expires_at: string | null;
  codes: IssuedCode[];
}

export interface InviteListQuery extends PageQuery {
  batch_id?: string;
  channel?: string;
}

// ---------------------------------------------------------------------------
// 汉字
// ---------------------------------------------------------------------------
export interface AdminCharacter {
  _id: string;
  char?: string;
  pinyin?: string;
  pinyin_plain?: string;
  tone?: number;
  is_polyphone?: boolean;
  radical?: string;
  stroke_count?: number;
  structure?: string;
  meaning?: string;
  words?: string[];
  sentences?: string[];
  pictograph?: string;
  /**
   * 字源图（象形 emoji）。
   *
   * 为什么用 emoji 而不是图片：识字启蒙阶段「看图选字」的图**必须是字义联想**，
   * 而不是任意装饰图。emoji 零素材成本、跨端一致、可随字库一起进 git；
   * 需要更精细的配图时再走 `image_ref` 绑定素材（两者并存，客户端优先图片）。
   */
  glyph?: string | null;
  image_ref?: string | null;
  audio_ref?: string | null;
  stroke_order_ref?: string | null;
  grade?: number;
  level?: string;
  difficulty?: number;
  tags?: string[];
  similar_chars?: string[];
  status?: string;
  version?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

/** 写入载荷：后端 `CharacterWrite` 为 `extra="allow"`，字段可原样导出回 JSON。 */
export type CharacterWritePayload = Partial<
  Omit<AdminCharacter, '_id' | 'created_at' | 'updated_at' | 'version'>
>;

export interface CharacterListQuery extends PageQuery {
  status?: string;
  keyword?: string;
  grade?: number;
  level?: string;
}

export interface CharacterGradeCounts {
  total: number;
  by_grade: Record<string, number>;
  by_status: Record<string, number>;
}

export interface ContentExportResult<T = unknown> {
  collection: string;
  label: string;
  count: number;
  documents: T[];
}

/**
 * 导入模板（后端 `/admin/content/{collection}/template`）。
 *
 * 为什么后台要自己生成模板而不是让运营去看 `content/schema/*.json`：
 * schema 在仓库里，**不会进前端产物**，运营同学拿不到；
 * 而导入本身是宽松的（只校验必填），真正需要告知的是
 * 「每字段什么意思、哪些必填、哪些是导入时自动生成的派生字段（手改无效）」。
 */
export interface ContentTemplateField {
  name: string;
  required: boolean;
  desc: string;
  /** 导入时自动重算，改了会被正文覆盖 */
  derived: boolean;
}

export interface ContentTemplate {
  collection: string;
  label: string;
  _comment: string;
  fields: ContentTemplateField[];
  items: Array<Record<string, unknown>>;
}

export interface ContentImportPayload {
  source: 'upload';
  collections: string[];
  payload: Record<string, unknown[]>;
  publish?: boolean;
  dry_run?: boolean;
}

export interface ContentImportResult {
  results: Array<{
    collection: string;
    total: number;
    created: number;
    updated: number;
    /** 派生型集合（lessons）重算时清掉的旧关数 */
    stale_removed?: number;
    /** 镜像型集合的导入模式：repo-first（初始化灌入）/ db-first（库优先，只补缺） */
    mode?: string;
  }>;
  total: number;
  created: number;
  updated: number;
  dry_run: boolean;
}

/** 删除结果 —— `hard` 区分「下架（软删）」与「物理删除」。 */
export interface ContentDeleteResult {
  deleted: boolean;
  id: string;
  /** true = 物理删除（不可恢复）；false = 下架（status → offline） */
  hard: boolean;
  /** 物理删除时命中的引用；仅在 `force=true` 真正删掉后才有内容 */
  references: Array<{ collection: string; label: string; count: number }>;
}

// ---------------------------------------------------------------------------
// 通用内容文档（与 `AdminCharacter` 同构，字段随集合而异）
// ---------------------------------------------------------------------------
/**
 * 通用内容行 —— 字库/古诗/短文等都用它。
 *
 * 刻意不按集合拆出多个 interface：6 类内容的字段差异由后端
 * `GET /admin/registry` 下发的 schema 描述驱动，后台据此渲染表格与表单
 * （见 05-1 §3.2）。这里给一个宽松形状，字段用可选的 unknown 承接。
 */
export interface ContentDoc {
  _id: string;
  status?: string;
  version?: number;
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

/** 集合的筛选维度 —— 与后端 `ContentTypeSpec.filters` 对应。 */
export interface ContentListQuery extends PageQuery {
  status?: string;
  keyword?: string;
  grade?: number;
  level?: string;
  grade_num?: number;
  source?: string;
}

// ---------------------------------------------------------------------------
// 素材
// ---------------------------------------------------------------------------
/**
 * 素材（元数据 + 下发地址）。
 *
 * 短文配图、字库精细配图、笔顺数据都通过 `image_ref` / `stroke_order_ref`
 * 绑到这里的 `_id`。`url` 是**可直接放进 `<img src>` 的路径**：
 * 素材下发端点是公开的（`<img>`/`<audio>` 无法携带 Authorization）。
 */
export interface AdminAsset {
  _id: string;
  type: 'image' | 'audio' | 'stroke';
  subtype: string | null;
  mime: string;
  bytes: number;
  width: number | null;
  height: number | null;
  original_name: string;
  storage_key: string;
  url: string;
  source: string;
  status: string;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// 用户（账号级）
// ---------------------------------------------------------------------------
export type AccountStatus = 'active' | 'disabled' | 'deleted';

export interface AdminUser {
  _id: string;
  username: string | null;
  phone_masked: string | null;
  has_phone: boolean;
  display_name: string | null;
  avatar_key: string | null;
  role: string;
  status: AccountStatus;
  access_tier: string;
  last_login_at: string | null;
  created_at: string | null;
  children_count?: number;
}

export interface UserListQuery extends PageQuery {
  keyword?: string;
  status?: string;
  role?: string;
  /** 是否有孩子档案；undefined = 不筛 */
  has_children?: boolean;
  /** 注册时间区间（YYYY-MM-DD）。上界含当天。 */
  registered_from?: string;
  registered_to?: string;
}

/**
 * 可编辑的账号字段 —— 刻意**不含**登录标识与 `role`。
 *
 * 与后端 `UserProfileUpdate`（`extra="forbid"`）逐字对应：
 * 用户名/手机号是登录标识（带唯一索引，改动等于换账号），
 * `role` 在单管理员体系里无意义（05-1 §1.3）。
 */
export interface UserProfilePayload {
  display_name?: string | null;
  avatar_key?: string | null;
  access_tier?: 'open' | 'invite_only';
}

export interface UserBulkStatusResult {
  succeeded: string[];
  failed: Array<{ id: string; reason: string }>;
  status: string;
}

export interface UserStats {
  total: number;
  by_status: Record<string, number>;
  with_phone: number;
  with_username: number;
  children: number;
}

// ---------------------------------------------------------------------------
// 站点配置（配置中心）
// ---------------------------------------------------------------------------
/**
 * 玩法配置 —— 全体孩子生效的行为开关。
 *
 * 与 `defaults` 的分工（不要混淆）：
 * - `defaults`：**新建档案时**写入孩子的初值，之后每个孩子可各自改。
 * - `gameplay`：**运行期全体生效**，客户端每次启动读它并据此渲染。
 *
 * 改这里等于给所有孩子换一套玩法，是「后台控制与客户端玩法同步」的唯一真源
 * （客户端不再自带一份写死的玩法表）。字段形状逐字对齐
 * `apps/api/app/core/runtime_config.py::default_gameplay()`。
 */
export interface GameplayConfig {
  /** 每学 N 个新字，插入一次「旧字抽查」（阶段检测）。后端 clamp 到 3–10。 */
  stage_test_every: number;
  /** 允许出现的题型；客户端据此过滤。取值见 GAMEPLAY_QUESTION_TYPE_OPTIONS。 */
  enabled_question_types: string[];
  /** 跟读（浏览器原生语音识别）。关闭后跟读题型整块不出现。 */
  enable_speak: boolean;
  /** 展示字源图（象形 emoji / 绑定图片）。 */
  show_pictograph: boolean;
  /** 朗读语速。后端 clamp 到 0.6–1.2，越小越慢。 */
  speak_rate: number;
}

/**
 * 一个年级档位。
 *
 * ⛔ 年级可任意增删（不再写死 1–6），因此 id 是数值而非枚举成员。
 * 上界 30 见后端 `GRADE_MAX`，只是防脏数据的守卫，不构成业务限制。
 */
export interface GradeOption {
  id: number;
  label: string;
  enabled: boolean;
}

export interface SiteConfig {
  require_invite: boolean;
  registration_open: boolean;
  announcement: string;
  defaults: {
    daily_new_char_target: number;
    daily_review_target: number;
    daily_time_limit_min: number;
  };
  gameplay: GameplayConfig;
  grades: GradeOption[];
}

export type SiteConfigPatch = Partial<SiteConfig>;

/**
 * 玩法可选题型 —— 与后端 `runtime_config.GAMEPLAY_QUESTION_TYPES` 逐字对齐。
 *
 * ⚠️ 与后端 `content_controller.QUESTION_STEMS` 的差异是**刻意的**：
 * `stroke`（笔顺书写）在 QUESTION_STEMS 里有，但未进玩法开关 ——
 * 书写素材（笔顺 JSON）尚未入库，先不开放这个开关，避免后台能开、客户端没得玩。
 * 后端 `_allowed_types` 也会把不认识的题型丢掉，两边互为双保险。
 */
export const GAMEPLAY_QUESTION_TYPE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'image-choice', label: '看图选字' },
  { value: 'audio-choice', label: '听音选字' },
  { value: 'pinyin-match', label: '拼音配对' },
  { value: 'word-build', label: '组词拼搭' },
  { value: 'meaning-choice', label: '释义选择' },
  { value: 'speak', label: '跟读发音' },
];

// ---------------------------------------------------------------------------
// 学习报告（账号级）
// ---------------------------------------------------------------------------
/** 单个孩子档案的报告行。 */
export interface ReportChildRow {
  _id: string;
  nickname: string | null;
  grade: number | null;
  status: string;
  /** 已认汉字数 = review_states 里有记录的字（见过面）。 */
  learned: number;
  /** 掌握汉字数 = 连续答对 ≥3 或复习间隔 > 60 天（已经稳了）。 */
  mastered: number;
  reviewing: number;
  learning: number;
  /** mastered / learned，0–1。 */
  mastery_rate: number;
  /** 答题正确率，0–1。 */
  accuracy: number;
  wrong_count: number;
  lesson_count: number;
  poem_count: number;
  badge_count: number;
  streak_days: number;
  last_study_at: string | null;
}

/** 账号内所有档案的合计。 */
export interface ReportTotals {
  learned: number;
  mastered: number;
  reviewing: number;
  learning: number;
  wrong: number;
  lessons: number;
  poems: number;
  badges: number;
  children: number;
  mastery_rate: number;
}

/** 按天聚合的答题趋势（同一账号多档案相加）。 */
export interface ReportTrendPoint {
  /** YYYY-MM-DD */
  date: string;
  total: number;
  correct: number;
  accuracy: number;
}

export interface AdminUserReport {
  account: AdminUser;
  children: ReportChildRow[];
  totals: ReportTotals;
  trend: ReportTrendPoint[];
  window_days: number;
}

// ---------------------------------------------------------------------------
// 接口
// ---------------------------------------------------------------------------
export const adminApi = {
  // 登录（密码 → admin JWT）
  login: (password: string) =>
    request<AdminLoginResult>('POST', '/admin/login', { data: { password } }),

  // 概览
  overview: () => request<AdminOverview>('GET', '/admin/overview'),

  // 用户
  listUsers: (query: UserListQuery) =>
    request<Paged<AdminUser>>('GET', '/admin/users', { params: { ...query } }),

  userStats: () => request<UserStats>('GET', '/admin/users/stats'),

  getUser: (id: string) => request<AdminUser>('GET', `/admin/users/${encodeURIComponent(id)}`),

  /** 编辑账号资料。只能改展示性字段；越权字段后端 422。 */
  updateUser: (id: string, payload: UserProfilePayload) =>
    request<AdminUser>('PATCH', `/admin/users/${encodeURIComponent(id)}`, { data: payload }),

  /** 注销账号（软删）：释放邀请码、使会话失效，但保留学习数据。 */
  deleteUser: (id: string) =>
    request<{ deleted: boolean; id: string; children_preserved: boolean }>(
      'DELETE',
      `/admin/users/${encodeURIComponent(id)}`,
    ),

  /** 批量启用 / 禁用。返回成功与失败的 id，不静默吞掉失败项。 */
  bulkUserStatus: (accountIds: string[], status: 'active' | 'disabled') =>
    request<UserBulkStatusResult>('POST', '/admin/users/bulk/status', {
      data: { account_ids: accountIds, status },
    }),

  /** 账号级学习报告。`days` 为趋势窗口长度，后端限制 1–90。 */
  userReport: (id: string, days = 7) =>
    request<AdminUserReport>('GET', `/admin/users/${encodeURIComponent(id)}/report`, {
      params: { days },
    }),

  setUserStatus: (id: string, status: 'active' | 'disabled') =>
    request<{ id: string; status: string }>('POST', `/admin/users/${encodeURIComponent(id)}/status`, {
      data: { status },
    }),

  // 站点配置
  getConfig: () => request<SiteConfig>('GET', '/admin/config'),

  updateConfig: (patch: SiteConfigPatch) =>
    request<SiteConfig>('PUT', '/admin/config', { data: patch }),

  // 邀请码
  listInvites: (query: InviteListQuery) => request<Paged<AdminInvite>>('GET', '/admin/invites', { params: { ...query } }),

  createInvites: (input: InviteBatchInput) =>
    request<InviteBatchResult>('POST', '/admin/invites/batch', { data: input }),

  revokeInvite: (id: string) =>
    request<{ revoked: boolean; id: string }>('POST', `/admin/invites/${encodeURIComponent(id)}/revoke`),

  // 汉字 —— 走数据驱动的通用 CRUD（/admin/content/characters），与其余内容类型同构
  listCharacters: (query: CharacterListQuery) =>
    request<Paged<AdminCharacter>>('GET', '/admin/content/characters', { params: { ...query } }),

  characterGradeCounts: () =>
    request<CharacterGradeCounts>('GET', '/admin/characters/grade-counts'),

  createCharacter: (payload: CharacterWritePayload) =>
    request<AdminCharacter>('POST', '/admin/content/characters', { data: payload }),

  updateCharacter: (id: string, payload: CharacterWritePayload) =>
    request<AdminCharacter>('PATCH', `/admin/content/characters/${encodeURIComponent(id)}`, {
      data: payload,
    }),

  /** 下架（软删）：后端只把 status 置为 offline，不物理删除。 */
  offlineCharacter: (id: string) =>
    request<{ deleted: boolean; id: string }>(
      'DELETE',
      `/admin/content/characters/${encodeURIComponent(id)}`,
    ),

  /**
   * 真删（物理删除，**不可恢复**）。
   *
   * 与 `offlineCharacter` 的差别是语义不是路径：靠 `hard=true` 显式声明意图，
   * 后端默认行为（不带参数）仍然是下架。被关卡 / 单元 / 短文引用时后端回复
   * `CONTENT_IN_USE(40903)`；此时要么放弃，要么显式 `force: true` 强制删
   * ——强制删除会留下悬空引用（关卡指向不存在的字），后果由操作者承担。
   */
  deleteCharacter: (id: string, options?: { force?: boolean }) =>
    request<ContentDeleteResult>('DELETE', `/admin/content/characters/${encodeURIComponent(id)}`, {
      params: { hard: true, force: options?.force ?? false },
    }),

  // 导入 / 导出（字库按年级）
  exportCharacters: (query: { grade?: number; status?: string; keyword?: string }) =>
    request<ContentExportResult<AdminCharacter>>('GET', '/admin/content/characters/export', {
      params: { ...query },
    }),

  importCharacters: (documents: unknown[], options?: { publish?: boolean; dry_run?: boolean }) =>
    request<ContentImportResult>('POST', '/admin/content/import', {
      data: {
        source: 'upload',
        collections: ['characters'],
        payload: { characters: documents },
        publish: options?.publish ?? true,
        dry_run: options?.dry_run ?? false,
      } satisfies ContentImportPayload,
    }),

  // ---------------------------------------------------------------------
  // 通用内容 CRUD —— 字库 / 古诗 / 短文 / 单元 / 关卡 / 故事 / 徽章共用
  // 差异由后端 `GET /admin/registry` 下发的 schema 描述驱动。
  // ---------------------------------------------------------------------
  listContent: <T = ContentDoc>(collection: string, query: ContentListQuery) =>
    request<Paged<T>>('GET', `/admin/content/${encodeURIComponent(collection)}`, {
      params: { ...query },
    }),

  createContent: <T = ContentDoc>(collection: string, payload: Record<string, unknown>) =>
    request<T>('POST', `/admin/content/${encodeURIComponent(collection)}`, { data: payload }),

  updateContent: <T = ContentDoc>(
    collection: string,
    id: string,
    payload: Record<string, unknown>,
  ) =>
    request<T>('PATCH', `/admin/content/${encodeURIComponent(collection)}/${encodeURIComponent(id)}`, {
      data: payload,
    }),

  /** 下架（软删）：后端只把 status 置为 offline，不物理删除。 */
  offlineContent: (collection: string, id: string) =>
    request<{ deleted: boolean; id: string }>(
      'DELETE',
      `/admin/content/${encodeURIComponent(collection)}/${encodeURIComponent(id)}`,
    ),

  /** 真删（物理删除，**不可恢复**）；被引用时后端回复 40903，可 `force` 强制。 */
  deleteContent: (collection: string, id: string, options?: { force?: boolean }) =>
    request<ContentDeleteResult>(
      'DELETE',
      `/admin/content/${encodeURIComponent(collection)}/${encodeURIComponent(id)}`,
      { params: { hard: true, force: options?.force ?? false } },
    ),

  exportContent: <T = ContentDoc>(collection: string, query: ContentListQuery) =>
    request<ContentExportResult<T>>(
      'GET',
      `/admin/content/${encodeURIComponent(collection)}/export`,
      { params: { ...query } },
    ),

  /** 导入模板：字段说明 + 一条示例，供运营照着填。 */
  contentTemplate: (collection: string) =>
    request<ContentTemplate>('GET', `/admin/content/${encodeURIComponent(collection)}/template`),

  importContent: (
    collection: string,
    documents: unknown[],
    options?: { publish?: boolean; dry_run?: boolean },
  ) =>
    request<ContentImportResult>('POST', '/admin/content/import', {
      data: {
        source: 'upload',
        collections: [collection],
        payload: { [collection]: documents },
        publish: options?.publish ?? true,
        dry_run: options?.dry_run ?? false,
      } satisfies ContentImportPayload,
    }),

  // ----------------------------- 素材 -----------------------------
  listAssets: (query: { type?: string; page?: number; page_size?: number }) =>
    request<Paged<AdminAsset>>('GET', '/admin/assets', { params: { ...query } }),

  uploadAsset: (file: File, opts?: { type?: string; subtype?: string }) => {
    const form = new FormData();
    form.append('file', file);
    if (opts?.type) form.append('type', opts.type);
    if (opts?.subtype) form.append('subtype', opts.subtype);
    return request<AdminAsset>('POST', '/admin/assets', { data: form });
  },
};
