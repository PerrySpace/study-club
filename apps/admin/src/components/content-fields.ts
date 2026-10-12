/**
 * 通用内容维护页的**类型契约**。
 *
 * 为什么单独成文件：`<script setup>` 里不能 `export`，而 `ContentManager.vue`
 * 的 props 类型要被 `ContentFieldEditor.vue` 与各类型页面共同引用。
 * 字段名/结构与后端模板下载（`/admin/content/{collection}/template`）返回的
 * `fields` 对齐，保证「页面展示的字段说明」与「下载的模板」是同一份来源。
 */

/** 字段类型 —— 决定用哪种输入控件。 */
export type FieldKind =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'tags'
  | 'list'
  | 'image'
  | 'audio'
  | 'stroke'
  | 'poem-lines'
  | 'reading-sentences';

export interface FieldDef {
  /** 字段名（snake_case，与内容包一致） */
  name: string;
  label: string;
  kind: FieldKind;
  hint?: string;
  required?: boolean;
  /** 导入时自动重算，表单里只读展示并说明 */
  derived?: boolean;
  /**
   * 下拉选项。
   *
   * 声明成 `ReadonlyArray`：`LEVEL_OPTIONS` 等是模块级 `const` 常量，
   * 展开成新数组（`[...LEVEL_OPTIONS]`）虽然能过，但**直接传常量**时会撞 TS4104。
   * 与其要求每个调用方记得展开，不如接收端放宽 —— 选项本来就是只读的。
   */
  options?: ReadonlyArray<{ value: string; label: string }>;
  placeholder?: string;
  maxlength?: number;
  rows?: number;
}

export interface ColumnDef {
  /** 表格列取值路径，支持 a.b.c */
  prop: string;
  label: string;
  width?: number;
  /** 自适应宽度（与 width 二选一；两者都不给则用默认） */
  minWidth?: number;
  align?: 'left' | 'center' | 'right';
  formatter?: 'text' | 'time' | 'status' | 'grade' | 'count' | 'image';
}

export interface GradeTab {
  value: number | undefined;
  label: string;
}

/** 内容状态选项 —— 与内容包 `status` 取值一致（05-1 §七）。 */
export const STATUS_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'draft', label: '草稿' },
  { value: 'pending_review', label: '待审核' },
  { value: 'published', label: '已上架' },
  { value: 'offline', label: '已下架' },
];

/** 一年级 Tab：0 = 学龄前；`undefined` = 全部（未分级的条目也包含在内）。 */
/**
 * 年级 Tab 的**兜底清单**。
 *
 * ⛔ 正常情况下不要直接用它渲染 —— 年级是**运营可配置**的（设置页能增删，
 * 本仓已扩到 7/8/9），写死清单会让「设置里加了七年级」在内容页根本不出现，
 * 而数据侧完全正常（`grade=7` 的字确实在库里），看起来像导入失败。
 *
 * 真正的来源是站点配置：见 `composables/useGradeTabs.ts` + `gradeTabsFrom()`。
 * 这里只为「配置读不到」时兜底，取值与后端 `DEFAULT_GRADES` 一致。
 */
export const GRADE_TABS: readonly GradeTab[] = [
  { value: undefined, label: '全部' },
  { value: 0, label: '学龄前' },
  { value: 1, label: '一年级' },
  { value: 2, label: '二年级' },
  { value: 3, label: '三年级' },
  { value: 4, label: '四年级' },
  { value: 5, label: '五年级' },
  { value: 6, label: '六年级' },
];

/**
 * 由站点配置的年级列表派生年级 Tab（含最前面的「全部」）。
 *
 * - 只取**启用**的年级（`enabled !== false`）—— 停用的年级不该出现在筛选里；
 * - 按 `id` 升序，不沿用配置数组顺序：运营增删年级时的排列顺序与「年级大小」
 *   无关，直接沿用会出现「七年级排在一年级前面」。
 */
export function gradeTabsFrom(grades: readonly GradeOptionLike[]): GradeTab[] {
  const enabled = grades
    .filter((g) => g.enabled !== false)
    .slice()
    .sort((a, b) => a.id - b.id);
  return [{ value: undefined, label: '全部' }, ...enabled.map((g) => ({ value: g.id, label: g.label }))];
}

/** `gradeTabsFrom` 的结构入参（避免本文件反向依赖 api 层的类型）。 */
export interface GradeOptionLike {
  id: number;
  label: string;
  enabled?: boolean;
}

/**
 * 年级的展示文案。
 *
 * ⛔ `grade=0` 是**学龄前**这个合法取值，不是「没填」——
 * 写成 `row.grade ? \`${row.grade} 年级\` : '—'` 会把它显示成「—」，
 * 与「未分级」混为一谈，运营会以为数据没导进来。
 * 同理 `Number(raw ?? 0)` 那种「null 兜成 0」的写法会把未分级显示成学龄前。
 */
export function gradeText(grade: unknown): string {
  if (grade === null || grade === undefined || grade === '') return '未分级';
  const n = Number(grade);
  if (!Number.isFinite(n)) return '未分级';
  return n <= 0 ? '学龄前' : `${n} 年级`;
}

export const LEVEL_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'easy', label: '简单' },
  { value: 'mid', label: '中等' },
  { value: 'hard', label: '较难' },
];
