/**
 * siteConfig store —— 站点公开配置 + **玩法配置**（服务端真源）。
 *
 * 为什么要它：邀请码是否必填、是否开放注册、公告、默认学习目标、以及
 * **玩法开关**（题型 / 阶段检测节奏 / 跟读 / 字源图 / 朗读语速）都是**运营参数**，
 * 存在服务端 `app_settings` 里、后台可热改（见 core/runtime_config.py）。
 *
 * 分工（别混淆）：
 *   - 构建期开关（`import.meta.env.VITE_*`）决定代码是否打包、路由是否注册；
 *   - 本 store 决定**运行期行为**（如邀请码输入框是否必填、题目按什么玩法出），以服务端为准。
 *
 * 玩法配置刻意**不给空实现**：`gameplay` 永远是完整对象（未加载时用默认值），
 * 于是消费点（如 LessonView）不必到处写 `?.` 与 `?? 兜底值`；
 * 这也让「后台把某题型关掉」与「离线没读到配置」这两种情况不会互相伪装。
 *
 * 读取失败（网络异常）时静默降级：`loaded=false`，行为回落到默认玩法。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import type { GameplayConfig, GradeOption, SitePublicConfig } from '../types/api';
import { useCore } from './context';

/**
 * 玩法默认值 —— 必须与后端 `runtime_config.default_gameplay()` 保持一致。
 */
export const DEFAULT_GAMEPLAY: GameplayConfig = {
  stage_test_every: 5,
  enabled_question_types: [
    'image-choice',
    'audio-choice',
    'pinyin-match',
    'word-build',
    'meaning-choice',
    'speak',
  ],
  enable_speak: true,
  show_pictograph: true,
  speak_rate: 0.8,
};

/**
 * 年级默认值 —— 必须与后端 `runtime_config.DEFAULT_GRADES` 保持一致。
 *
 * 只在「配置还没加载」或「服务端没给 grades」时使用。刻意不做空：
 * 年级下拉是注册引导的必经界面，空数组会让用户选不了年级、注册流程直接卡死。
 */
export const DEFAULT_GRADES: GradeOption[] = [
  { id: 0, label: '学龄前', enabled: true },
  { id: 1, label: '一年级', enabled: true },
  { id: 2, label: '二年级', enabled: true },
  { id: 3, label: '三年级', enabled: true },
  { id: 4, label: '四年级', enabled: true },
  { id: 5, label: '五年级', enabled: true },
  { id: 6, label: '六年级', enabled: true },
];

export const useSiteConfigStore = defineStore('siteConfig', () => {
  const config = ref<SitePublicConfig | null>(null);
  const loaded = ref(false);

  /** 邀请码是否必填：以服务端为准；未加载时回落到构建期开关。 */
  const inviteRequired = computed(() =>
    config.value ? config.value.require_invite : useCore().flags.enableInviteRequired,
  );

  const registrationOpen = computed(() => config.value?.registration_open ?? true);
  const announcement = computed(() => config.value?.announcement ?? '');

  /**
   * 全部年级档位（含停用）—— 后台管理视图用。
   */
  const allGrades = computed<GradeOption[]>(() => {
    const raw = config.value?.grades;
    return Array.isArray(raw) && raw.length ? raw : DEFAULT_GRADES;
  });

  /**
   * 启用的年级，**按 id 升序** —— 建档页与设置的年级下拉用它。
   *
   * 为什么要排序：运营在后台增删年级时的排列顺序可能与「年级大小」无关
   * （比如新加的「幼小衔接」被放在最前）。如果直接沿用配置顺序，
   * 会出现「七年级排在一年级前面」这种明显错乱的下拉。
   */
  const grades = computed<GradeOption[]>(() =>
    allGrades.value
      .filter((g) => g.enabled)
      .slice()
      .sort((a, b) => a.id - b.id),
  );

  /** `{id: label}`，文案回退用（如档案列表、历史数据里的 grade）。 */
  const gradeLabels = computed<Record<number, string>>(() => {
    const map: Record<number, string> = {};
    for (const g of grades.value) map[g.id] = g.label;
    return map;
  });

  /**
   * 玩法配置（永远可用）。
   *
   * 服务端只下发**认识的**题型，但不保证非空；这里再兜一层：
   * 空数组会让孩子进去一道题都答不出来，那比用默认玩法糟得多。
   */
  const gameplay = computed<GameplayConfig>(() => {
    const raw = config.value?.gameplay;
    if (!raw) return DEFAULT_GAMEPLAY;
    const types = Array.isArray(raw.enabled_question_types)
      ? raw.enabled_question_types.filter((t) => typeof t === 'string' && t)
      : [];
    return {
      stage_test_every: Number(raw.stage_test_every) || DEFAULT_GAMEPLAY.stage_test_every,
      enabled_question_types: types.length ? types : DEFAULT_GAMEPLAY.enabled_question_types,
      enable_speak: raw.enable_speak !== false,
      show_pictograph: raw.show_pictograph !== false,
      speak_rate: Number(raw.speak_rate) || DEFAULT_GAMEPLAY.speak_rate,
    };
  });

  /** 某个题型是否开启（题目过滤与「跟读」入口共用）。 */
  function isTypeEnabled(type: string): boolean {
    return gameplay.value.enabled_question_types.includes(type);
  }

  /**
   * 让「内容包」也带回的 gameplay 生效。
   *
   * 为什么需要它：`/content/bootstrap` 已经把 gameplay 一起下发了（省一次请求），
   * 但它的加载时机在 `/config` 之后。若此时 `/config` 还没回来，就把 bootstrap 里的
   * 那份用上 —— 两者同源（都读服务端 runtime_config），不会冲突。
   *
   * ⚠️ 这里必须补齐 `SitePublicConfig` 的**全部**字段：少一个 grades，
   * TS 就报「对象不可赋值给该类型」，而运行时表现为年级下拉突然变空。
   * 新增配置项时记得同步这里。
   */
  function applyFromBundle(next: GameplayConfig | null | undefined): void {
    if (loaded.value || !next) return;
    config.value = {
      require_invite: config.value?.require_invite ?? false,
      registration_open: config.value?.registration_open ?? true,
      announcement: config.value?.announcement ?? '',
      defaults: config.value?.defaults ?? {
        daily_new_char_target: 8,
        daily_review_target: 20,
        daily_time_limit_min: 20,
      },
      gameplay: next,
      // 年级表不在 bootstrap 的下发范围内，这里给默认表兜底；
      // 真正生效的版本由随后的 /config 覆盖。
      grades: config.value?.grades ?? DEFAULT_GRADES,
    };
  }

  async function load(): Promise<void> {
    const { api } = useCore();
    if (!api) return;
    try {
      config.value = await api.publicConfig();
      loaded.value = true;
    } catch {
      // 静默降级：离线/后端不可达时保留构建期开关与默认玩法的行为
    }
  }

  return {
    config,
    loaded,
    inviteRequired,
    registrationOpen,
    announcement,
    allGrades,
    grades,
    gradeLabels,
    gameplay,
    isTypeEnabled,
    applyFromBundle,
    load,
  };
});
