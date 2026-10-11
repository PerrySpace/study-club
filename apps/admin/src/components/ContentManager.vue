<script setup lang="ts">
/**
 * ContentManager —— 通用「内容类型维护」页（古诗 / 识字短文）。
 *
 * 为什么做成通用组件而不是每个类型各写一页：
 *   后端已经是**数据驱动**的（`/admin/content/{collection}` + `GET /admin/registry`
 *   下发 schema 描述），字库页若单独硬编码一份表格与表单，那么「再加一类内容」
 *   就要复制 600 行 —— 这正是 05-1 §三 说的「后台由数据驱动」的落点。
 *   本组件把「年级 Tab + 列表 + 编辑 + 导入导出 + 模板下载」这套流程做一次，
 *   各类型只提供**字段定义**（`fields`）与**表格列**（`columns`）。
 *
 * 字段定义的数据结构与后端模板下载返回的 `fields` 对齐（字段名 / 必填 / 派生 /
 * 说明），所以「下载模板」按钮与本页展示的字段说明永远是同一份来源。
 */
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { adminApi, type ContentDoc, type ContentTemplate } from '@/api/admin';
import { reportError } from '@/utils/error';
import ContentFieldEditor from './ContentFieldEditor.vue';
import {
  STATUS_OPTIONS,
  type ColumnDef,
  type FieldDef,
  type GradeTab,
} from './content-fields';

const props = withDefaults(
  defineProps<{
    collection: string;
    title: string;
    /** 内容类型的中文名，用于按钮与提示文案 */
    label: string;
    /**
     * 字段定义与表格列一律声明成 `readonly`。
     *
     * 各类型页面传给它们的是 `content-fields.ts` 里的模块级 `const` 常量
     * （`GRADE_TABS` 等），其类型是 `readonly T[]`。props 若写成 `T[]`，
     * vue-tsc 会以 TS4104 拒绝 —— 让**调用方**去掉 readonly 是错的：
     * 共享常量本就不该被就地修改。正确做法是接收端放宽为 `readonly T[]`。
     */
    fields: readonly FieldDef[];
    columns: readonly ColumnDef[];
    gradeTabs?: readonly GradeTab[];
    /** 是否提供年级 Tab（关卡/徽章等无年级概念的类型传 false） */
    withGrade?: boolean;
    hint?: string;
    /** 新建时默认状态 */
    defaultStatus?: string;
  }>(),
  {
    gradeTabs: () => [],
    withGrade: true,
    hint: '',
    defaultStatus: 'draft',
  },
);

const loading = ref(false);
const items = ref<ContentDoc[]>([]);
const total = ref(0);
const gradeCounts = ref<Record<string, number>>({});
const activeGrade = ref<number | undefined>(undefined);

const query = reactive({
  status: '',
  keyword: '',
  page: 1,
  page_size: 20,
});

// ---------------------------------------------------------------------------
// 列表
// ---------------------------------------------------------------------------
async function load(): Promise<void> {
  loading.value = true;
  try {
    const data = await adminApi.listContent<ContentDoc>(props.collection, {
      page: query.page,
      page_size: query.page_size,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
      grade: activeGrade.value,
    });
    items.value = data.items;
    total.value = data.pagination.total;
  } catch (err) {
    reportError(err, `加载${props.label}失败`);
  } finally {
    loading.value = false;
  }
}

/** 年级计数：借用字库页已有的 grade-counts 端点之外的通用聚合。 */
async function loadGradeCounts(): Promise<void> {
  if (!props.withGrade) return;
  try {
    // 列表总数即该年级的基数；这里只用已加载页的统计不可靠，
    // 因此按年级各取一次 total（内容类型都不大，且有缓存语义）。
    const counts: Record<string, number> = {};
    for (const tab of props.gradeTabs) {
      if (tab.value === undefined) continue;
      const data = await adminApi.listContent<ContentDoc>(props.collection, {
        page: 1,
        page_size: 1,
        grade: tab.value,
      });
      counts[String(tab.value)] = data.pagination.total;
    }
    const all = await adminApi.listContent<ContentDoc>(props.collection, {
      page: 1,
      page_size: 1,
    });
    counts.all = all.pagination.total;
    gradeCounts.value = counts;
  } catch {
    // 年级统计是锦上添花，失败不阻塞列表
    gradeCounts.value = {};
  }
}

function tabCount(tab: GradeTab): number {
  if (tab.value === undefined) return gradeCounts.value.all ?? 0;
  return gradeCounts.value[String(tab.value)] ?? 0;
}

function selectGrade(grade: number | undefined): void {
  activeGrade.value = grade;
  query.page = 1;
  void load();
}

function handleSearch(): void {
  query.page = 1;
  void load();
}

function handleReset(): void {
  query.status = '';
  query.keyword = '';
  query.page = 1;
  activeGrade.value = undefined;
  void load();
}

function handlePageChange(page: number): void {
  query.page = page;
  void load();
}

function handleSizeChange(size: number): void {
  query.page_size = size;
  query.page = 1;
  void load();
}

// ---------------------------------------------------------------------------
// 单元格取值与格式化
// ---------------------------------------------------------------------------
function cell(row: ContentDoc, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object') return (acc as Record<string, unknown>)[key];
    return undefined;
  }, row);
}

function displayValue(row: ContentDoc, col: ColumnDef): string {
  const raw = cell(row, col.prop);
  switch (col.formatter) {
    case 'time':
      return formatTime(raw as string | null | undefined);
    case 'status':
      return statusLabel(raw as string | undefined);
    case 'grade': {
      const grade = Number(raw ?? 0);
      return grade > 0 ? `${grade} 年级` : '未分级';
    }
    case 'count': {
      const arr = raw;
      return Array.isArray(arr) ? String(arr.length) : raw ? String(raw) : '—';
    }
    default: {
      if (raw === null || raw === undefined || raw === '') return '—';
      if (Array.isArray(raw)) return raw.join('、') || '—';
      if (typeof raw === 'object') return JSON.stringify(raw);
      return String(raw);
    }
  }
}

function formatTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('zh-CN', { hour12: false });
}

function statusLabel(status?: string): string {
  return STATUS_OPTIONS.find((s) => s.value === status)?.label ?? status ?? '—';
}

function statusTagType(status?: string): 'success' | 'info' | 'warning' | 'danger' {
  switch (status) {
    case 'published':
      return 'success';
    case 'pending_review':
      return 'warning';
    case 'offline':
      return 'danger';
    default:
      return 'info';
  }
}

/** 图片单元格：素材 id 或 emoji 都能显示。 */
function imagePreview(row: ContentDoc, prop: string): { url: string; title: string } | null {
  const value = cell(row, prop);
  if (typeof value !== 'string' || !value) return null;
  if (value.startsWith('as_')) {
    return { url: `/api/v1/assets/${value}`, title: value };
  }
  // emoji / 文字：直接当文本展示
  return { url: '', title: value };
}

// ---------------------------------------------------------------------------
// 模板下载
// ---------------------------------------------------------------------------
async function downloadTemplate(): Promise<void> {
  try {
    const template: ContentTemplate = await adminApi.contentTemplate(props.collection);
    // 只保留 items 与说明 —— 直接把整个 fields 塞进 JSON 会让「照着填」变难，
    // 但字段说明以注释块形式放在 _field_guide 里，运营看得到。
    const payload = {
      _comment: template._comment,
      _field_guide: template.fields
        .map((f) => `${f.name}（${f.required ? '必填' : '选填'}${f.derived ? '，导入时自动生成' : ''}）：${f.desc}`)
        .join('\n'),
      items: template.items,
    };
    downloadJson(payload, `${props.collection}-template.json`);
    ElMessage.success('模板已下载');
  } catch (err) {
    reportError(err, '下载模板失败');
  }
}

function downloadJson(payload: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// 导出 / 导入
// ---------------------------------------------------------------------------
async function exportJson(): Promise<void> {
  try {
    const data = await adminApi.exportContent<ContentDoc>(props.collection, {
      grade: activeGrade.value,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
    });
    const gradePart = activeGrade.value !== undefined ? `grade-${activeGrade.value}` : 'all';
    downloadJson({ items: data.documents }, `${props.collection}-${gradePart}.json`);
    ElMessage.success(`已导出 ${data.count} 条`);
  } catch (err) {
    reportError(err, '导出失败');
  }
}

const importing = ref(false);
const fileInput = ref<HTMLInputElement>();

function triggerImport(): void {
  fileInput.value?.click();
}

/** 读取上传的 JSON（支持裸数组 / {items:[...]} / {documents:[...]} 三种形态）。 */
function extractDocuments(text: string): unknown[] {
  const parsed = JSON.parse(text) as unknown;
  if (Array.isArray(parsed)) return parsed;
  if (parsed && typeof parsed === 'object') {
    const obj = parsed as Record<string, unknown>;
    if (Array.isArray(obj.items)) return obj.items;
    if (Array.isArray(obj.documents)) return obj.documents;
  }
  throw new Error('JSON 结构不识别');
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  importing.value = true;
  try {
    const docs = extractDocuments(await file.text());
    if (docs.length === 0) {
      ElMessage.warning('文件中没有可导入的内容');
      return;
    }
    const res = await adminApi.importContent(props.collection, docs, { publish: true });
    ElMessage.success(`导入完成：新增 ${res.created} / 更新 ${res.updated}`);
    await Promise.all([load(), loadGradeCounts()]);
  } catch (err) {
    reportError(err, '导入失败（请检查 JSON 格式与字段）');
  } finally {
    importing.value = false;
  }
}

// ---------------------------------------------------------------------------
// 新建 / 编辑 / 下架
// ---------------------------------------------------------------------------
const editorVisible = ref(false);
const submitting = ref(false);
const editingId = ref<string | null>(null);
const formValues = ref<Record<string, unknown>>({});

const isEditing = computed(() => editingId.value !== null);

const requiredMissing = computed(() =>
  props.fields
    .filter((f) => f.required && !f.derived)
    .filter((f) => {
      const v = formValues.value[f.name];
      if (v === null || v === undefined) return true;
      if (typeof v === 'string') return v.trim() === '';
      if (Array.isArray(v)) return v.length === 0;
      return false;
    })
    .map((f) => f.label),
);

function openCreate(): void {
  editingId.value = null;
  formValues.value = {
    status: props.defaultStatus,
    grade: activeGrade.value,
  };
  // 非派生字段给空初值，避免 v-model 绑 undefined
  for (const f of props.fields) {
    if (f.name in formValues.value) continue;
    if (f.derived) continue;
    formValues.value[f.name] = f.kind === 'list' || f.kind === 'poem-lines' || f.kind === 'reading-sentences' ? [] : '';
  }
  editorVisible.value = true;
}

function openEdit(row: ContentDoc): void {
  editingId.value = row._id;
  formValues.value = {};
  for (const f of props.fields) {
    const v = row[f.name];
    formValues.value[f.name] = v === undefined || v === null ? '' : v;
  }
  formValues.value.status = row.status ?? 'draft';
  editorVisible.value = true;
}

function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const f of props.fields) {
    // 派生字段不让改：导入时会按正文重算，手改只会造成不一致
    if (f.derived) continue;
    const v = formValues.value[f.name];
    if (v === '' || v === undefined) {
      payload[f.name] = f.kind === 'list' || f.kind === 'poem-lines' || f.kind === 'reading-sentences' ? [] : null;
      continue;
    }
    payload[f.name] = f.kind === 'number' ? Number(v) : v;
  }
  payload.status = formValues.value.status ?? props.defaultStatus;
  return payload;
}

async function submit(): Promise<void> {
  if (requiredMissing.value.length) {
    ElMessage.warning(`请填写：${requiredMissing.value.join('、')}`);
    return;
  }
  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await adminApi.updateContent(props.collection, editingId.value, buildPayload());
      ElMessage.success('已保存');
    } else {
      await adminApi.createContent(props.collection, buildPayload());
      ElMessage.success('已创建');
    }
    editorVisible.value = false;
    await Promise.all([load(), loadGradeCounts()]);
  } catch (err) {
    reportError(err, '保存失败');
  } finally {
    submitting.value = false;
  }
}

async function offline(row: ContentDoc): Promise<void> {
  try {
    await adminApi.offlineContent(props.collection, row._id);
    ElMessage.success(`已下架「${displayValue(row, { prop: 'title', label: '标题' })}」`);
    await Promise.all([load(), loadGradeCounts()]);
  } catch (err) {
    reportError(err, '下架失败');
  }
}

// 素材选择回调：把选中的素材 id 写回表单
function onAssetPicked(fieldName: string, assetId: string | null): void {
  formValues.value[fieldName] = assetId ?? '';
}

/**
 * 字段值回写。
 *
 * 刻意走 `:model-value` + `@update:model-value` 而不是 `v-model="formValues[f.name]"`：
 * 后者要求 `Record<string, unknown>` 的索引签名在 `v-model` 语境下可写，
 * 泛型索引与 `unknown` 组合时 vue-tsc 会拒绝。显式回写既过类型检查，
 * 也让「一个字段改动写到哪里」是显式的。
 */
function onFieldChange(fieldName: string, value: unknown): void {
  formValues.value[fieldName] = value;
}

onMounted(() => {
  void load();
  void loadGradeCounts();
});

defineExpose({ load, loadGradeCounts });
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ title }}</h2>
      <div class="header-actions">
        <el-button :loading="importing" @click="triggerImport">导入 JSON</el-button>
        <el-button @click="downloadTemplate">下载模板</el-button>
        <el-button @click="exportJson">导出 JSON</el-button>
        <el-button type="primary" @click="openCreate">新建{{ label }}</el-button>
        <input
          ref="fileInput"
          type="file"
          accept="application/json,.json"
          style="display: none"
          @change="onFileChange"
        />
      </div>
    </div>

    <p class="page-hint">
      {{ hint }}
      导入按 <span class="mono">_id</span> 幂等 upsert，可放心重跑；导出的文件可直接再次导入或进 git。
      点「下载模板」可拿到字段说明与一条示例。
    </p>

    <div v-if="withGrade && gradeTabs.length" class="grade-tabs">
      <button
        v-for="tab in gradeTabs"
        :key="String(tab.value)"
        type="button"
        class="grade-tab"
        :class="{ 'grade-tab--active': activeGrade === tab.value }"
        @click="selectGrade(tab.value)"
      >
        {{ tab.label }}
        <span class="grade-tab__count">{{ tabCount(tab) }}</span>
      </button>
    </div>

    <div class="filter-bar">
      <el-input v-model="query.keyword" placeholder="搜索" clearable style="width: 220px" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px">
        <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe size="small">
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth ?? (col.width ? undefined : 140)"
        :align="col.align ?? 'left'"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <template v-if="col.formatter === 'status'">
            <el-tag size="small" effect="plain" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
          <template v-else-if="col.formatter === 'image'">
            <img
              v-if="imagePreview(row, col.prop)?.url"
              :src="imagePreview(row, col.prop)!.url"
              :alt="col.label"
              class="cell-image"
            />
            <span v-else class="cell-text">{{ displayValue(row, col) }}</span>
          </template>
          <span v-else>{{ displayValue(row, col) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm
            title="下架后该内容不再下发到客户端（状态置为 offline，不物理删除）。确认下架？"
            confirm-button-text="下架"
            cancel-button-text="取消"
            @confirm="offline(row)"
          >
            <template #reference>
              <el-button link type="danger" :disabled="row.status === 'offline'">下架</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 新建 / 编辑 -->
    <el-dialog
      v-model="editorVisible"
      :title="isEditing ? `编辑${label}` : `新建${label}`"
      width="820px"
      top="6vh"
    >
      <el-form label-width="96px">
        <el-form-item
          v-for="f in fields"
          :key="f.name"
          :label="f.label"
          :required="f.required && !f.derived"
        >
          <ContentFieldEditor
            :model-value="formValues[f.name]"
            :field="f"
            @update:model-value="(v: unknown) => onFieldChange(f.name, v)"
            @pick-asset="(id: string | null) => onAssetPicked(f.name, id)"
          />
          <div v-if="f.hint || f.derived" class="form-tip">
            <template v-if="f.derived">⚠️ 导入时会按正文自动重算，手改无效。</template>
            <template v-if="f.hint"> {{ f.hint }}</template>
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="formValues.status">
            <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.grade-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.grade-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 999px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.grade-tab:hover {
  border-color: #c6b9ff;
  color: #6b4fd8;
}

.grade-tab--active {
  border-color: #7a5af8;
  background: #f2eeff;
  color: #5b34d6;
  font-weight: 600;
}

.grade-tab__count {
  color: #a8abb2;
  font-size: 12px;
}

.grade-tab--active .grade-tab__count {
  color: #7a5af8;
}

.cell-image {
  max-width: 64px;
  max-height: 40px;
  border-radius: 4px;
  object-fit: cover;
}

.cell-text {
  color: #c0c4cc;
}

.form-tip {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
