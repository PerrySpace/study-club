/**
 * 年级 Tab —— 从**站点配置**派生，而不是各页各写一份清单。
 *
 * ## 为什么
 * 年级是**运营可配置**的：后台设置页能随便增删（本仓已从 0–6 扩到 7/8/9）。
 * 但字库页与内容页曾各自硬编码了一份 0–6 的清单，于是「设置里加了七年级」
 * 在内容页根本不出现 —— 而数据侧完全正常（`grade=7` 的字就在库里），
 * 表现出来像「导入没生效」，排查方向会被带偏。
 *
 * 现在统一走这里：读一次 `/admin/config` 的 `grades`，按 id 升序生成 Tab。
 * 与客户端一致 —— 学生端的年级下拉本来就来自同一份配置（core 的 siteConfig）。
 */
import { ref, type Ref } from 'vue';

import { adminApi } from '@/api/admin';
import { GRADE_TABS, gradeTabsFrom, type GradeTab } from '@/components/content-fields';

export function useGradeTabs(): {
  gradeTabs: Ref<readonly GradeTab[]>;
  loadGradeTabs: () => Promise<void>;
} {
  const gradeTabs = ref<readonly GradeTab[]>(GRADE_TABS);

  /**
   * 拉一次站点配置，把年级清单换成配置里的那一份。
   *
   * 失败时**静默沿用兜底**：年级 Tab 只是筛选器，不该因为配置读不到就把整个
   * 内容页变成错误态 —— 列表与编辑仍然可用，只是年级档位退回内置的 0–6。
   */
  async function loadGradeTabs(): Promise<void> {
    try {
      const cfg = await adminApi.getConfig();
      if (cfg.grades?.length) gradeTabs.value = gradeTabsFrom(cfg.grades);
    } catch {
      gradeTabs.value = GRADE_TABS;
    }
  }

  return { gradeTabs, loadGradeTabs };
}
