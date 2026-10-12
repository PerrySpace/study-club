<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus';

import {
  adminApi,
  type AdminCharacter,
  type CharacterGradeCounts,
  type CharacterWritePayload,
} from '@/api/admin';
import { ApiError, CONTENT_IN_USE } from '@/api/client';
import { gradeText } from '@/components/content-fields';
import { useGradeTabs } from '@/composables/useGradeTabs';
import { reportError } from '@/utils/error';
import GlyphPreview from '@/components/GlyphPreview.vue';

/**
 * 状态中文名与选项 —— 与内容包 status 取值对齐（05-1 §七状态流转）。
 * ⛔ 这里不做「提交审核 / 审核通过」的多角色工作流：后台是单人使用（05-1 §二）。
 */
const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'pending_review', label: '待审核' },
  { value: 'published', label: '已上架' },
  { value: 'offline', label: '已下架' },
];

const STRUCTURE_OPTIONS = ['独体', '左右', '上下', '上中下', '左中右', '半包围', '全包围', '品字'];

/** 汉字本体校验：必须是单个 CJK 统一汉字（05-1 §3.2 实时校验规则）。 */
const HANZI_PATTERN = /^[\u4e00-\u9fff]$/;

const loading = ref(false);
const items = ref<AdminCharacter[]>([]);
const total = ref(0);
const gradeCounts = ref<CharacterGradeCounts | null>(null);

/**
 * 年级分类 Tab —— 来自**站点配置**（含后台设置里新加的年级），不再在前端写死。
 *
 * 之前这里硬编码了一份 0–6 的清单，于是「设置里把年级扩到 7/8/9」在本页
 * 完全看不到，而字库里 `grade=7` 的字确实存在 —— 看起来像导入没生效。
 * 0 = 学龄前；未分级（grade 缺失）由统计接口单列。
 */
const { gradeTabs, loadGradeTabs } = useGradeTabs();

/**
 * 表单里年级可填的上限 —— 跟随站点配置。
 *
 * ⛔ 旧代码写死 `:min="1" :max="6"`：**学龄前（0）根本填不进去**，
 * 7/8/9 也填不了 —— 后台扩了年级、表单却还停在 1–6，运营只能通过导入
 * 绕过，而导入的内容在列表里又显示成「—」/「未分级」。三处都在这轮修掉了。
 */
const maxGrade = computed(() => {
  const ids = gradeTabs.value
    .map((t) => t.value)
    .filter((v): v is number => typeof v === 'number');
  return ids.length ? Math.max(...ids) : 6;
});

const activeGrade = ref<number | undefined>(undefined);

const query = reactive({
  status: '',
  keyword: '',
  page: 1,
  page_size: 20,
});

function gradeCount(grade: number | undefined): number {
  if (!gradeCounts.value) return 0;
  if (grade === undefined) return gradeCounts.value.total;
  return gradeCounts.value.by_grade[String(grade)] ?? 0;
}

interface CharacterForm {
  char: string;
  pinyin: string;
  tone: number | undefined;
  radical: string;
  stroke_count: number | undefined;
  structure: string;
  glyph: string;
  meaning: string;
  words: string;
  sentences: string;
  grade: number | undefined;
  tags: string;
  status: string;
}

const dialogVisible = ref(false);
const submitting = ref(false);
const editingId = ref<string | null>(null);
const formRef = ref<FormInstance>();
const form = reactive<CharacterForm>(emptyForm());

const isEditing = computed(() => editingId.value !== null);

const rules: FormRules<CharacterForm> = {
  char: [
    {
      validator: (_rule, value: string, callback) => {
        const text = (value ?? '').trim();
        if (!text) return callback(new Error('请填写汉字本体'));
        if (!HANZI_PATTERN.test(text)) return callback(new Error('必须是 1 个汉字（CJK 统一汉字）'));
        return callback();
      },
      trigger: 'blur',
    },
  ],
};

function emptyForm(): CharacterForm {
  return {
    char: '',
    pinyin: '',
    tone: undefined,
    radical: '',
    stroke_count: undefined,
    structure: '',
    glyph: '',
    meaning: '',
    words: '',
    sentences: '',
    grade: undefined,
    tags: '',
    status: 'draft',
  };
}

function statusLabel(status?: string): string {
  return STATUS_OPTIONS.find((item) => item.value === status)?.label ?? status ?? '—';
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

function formatTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

/** 列表用「、」或「,」分隔；提交前统一按分隔符切分。 */
function splitList(value: string): string[] {
  return value
    .split(/[、,，|]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function joinList(value?: string[]): string {
  return (value ?? []).join('、');
}

// ---------------------------------------------------------------------------
// 列表
// ---------------------------------------------------------------------------
async function load(): Promise<void> {
  loading.value = true;
  try {
    const data = await adminApi.listCharacters({
      page: query.page,
      page_size: query.page_size,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
      grade: activeGrade.value,
    });
    items.value = data.items;
    total.value = data.pagination.total;
  } catch (err) {
    reportError(err, '加载字库失败');
  } finally {
    loading.value = false;
  }
}

async function loadGradeCounts(): Promise<void> {
  try {
    gradeCounts.value = await adminApi.characterGradeCounts();
  } catch (err) {
    reportError(err, '加载年级统计失败');
  }
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

// ---------------------------------------------------------------------------
// 导入 / 导出 / 模板
// ---------------------------------------------------------------------------
const importing = ref(false);
const fileInput = ref<HTMLInputElement>();

/**
 * 下载导入模板：字段说明 + 一条可直接照抄的示例。
 *
 * 模板由后端生成（`/admin/content/characters/template`），
 * 因此「下载到的说明」与「后端真正校验的必填项」永远是同一份来源，
 * 不会出现改了文档没改校验、或反之的情况。
 */
async function downloadTemplate(): Promise<void> {
  try {
    const template = await adminApi.contentTemplate('characters');
    const payload = {
      _comment: template._comment,
      _field_guide: template.fields
        .map(
          (f) =>
            `${f.name}（${f.required ? '必填' : '选填'}${f.derived ? '，导入时自动生成' : ''}）：${f.desc}`,
        )
        .join('\n'),
      items: template.items,
    };
    downloadJson(payload, 'characters-template.json');
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

/** 导出当前筛选（含年级）下的字库为 JSON 文件。 */
async function exportJson(): Promise<void> {
  try {
    const data = await adminApi.exportCharacters({
      grade: activeGrade.value,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
    });
    const gradePart = activeGrade.value !== undefined ? `grade-${activeGrade.value}` : 'all';
    downloadJson({ items: data.documents }, `characters-${gradePart}.json`);
    ElMessage.success(`已导出 ${data.count} 条`);
  } catch (err) {
    reportError(err, '导出失败');
  }
}

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
      ElMessage.warning('文件中没有可导入的字条');
      return;
    }
    const res = await adminApi.importCharacters(docs, { publish: true });
    ElMessage.success(`导入完成：新增 ${res.created} / 更新 ${res.updated}`);
    await Promise.all([load(), loadGradeCounts()]);
  } catch (err) {
    reportError(err, '导入失败（请检查 JSON 格式与字段）');
  } finally {
    importing.value = false;
  }
}

onMounted(() => {
  void load();
  void loadGradeCounts();
  void loadGradeTabs();
});

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
// 新建 / 编辑
// ---------------------------------------------------------------------------
function openCreate(): void {
  editingId.value = null;
  Object.assign(form, emptyForm());
  // 在某个年级 Tab 下新建时，默认沿用该年级
  if (activeGrade.value !== undefined) form.grade = activeGrade.value;
  dialogVisible.value = true;
  void formRef.value?.clearValidate();
}

function openEdit(row: AdminCharacter): void {
  editingId.value = row._id;
  Object.assign(form, {
    char: row.char ?? '',
    pinyin: row.pinyin ?? '',
    tone: row.tone,
    radical: row.radical ?? '',
    stroke_count: row.stroke_count,
    structure: row.structure ?? '',
    glyph: row.glyph ?? '',
    meaning: row.meaning ?? '',
    words: joinList(row.words),
    sentences: joinList(row.sentences),
    grade: row.grade,
    tags: joinList(row.tags),
    status: row.status ?? 'draft',
  });
  dialogVisible.value = true;
  void formRef.value?.clearValidate();
}

/**
 * 组装写入载荷。
 * 说明：不发送 `char` 的更新 —— `_id` 是 `ch_<codepoint>`，改字会让 id 与内容脱节。
 */
function buildPayload(): CharacterWritePayload {
  const payload: CharacterWritePayload = {
    pinyin: form.pinyin.trim(),
    radical: form.radical.trim(),
    structure: form.structure,
    glyph: form.glyph.trim() || null,
    meaning: form.meaning.trim(),
    words: splitList(form.words),
    sentences: splitList(form.sentences),
    tags: splitList(form.tags),
    status: form.status,
  };
  if (!isEditing.value) payload.char = form.char.trim();
  if (form.tone !== undefined) payload.tone = form.tone;
  if (form.stroke_count !== undefined) payload.stroke_count = form.stroke_count;
  if (form.grade !== undefined) payload.grade = form.grade;
  return payload;
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await adminApi.updateCharacter(editingId.value, buildPayload());
      ElMessage.success('已保存');
    } else {
      await adminApi.createCharacter(buildPayload());
      ElMessage.success('已创建');
    }
    dialogVisible.value = false;
    await load();
    await loadGradeCounts();
  } catch (err) {
    reportError(err, '保存失败');
  } finally {
    submitting.value = false;
  }
}

// ---------------------------------------------------------------------------
// 下架（软删）
// ---------------------------------------------------------------------------
async function offline(row: AdminCharacter): Promise<void> {
  try {
    await adminApi.offlineCharacter(row._id);
    ElMessage.success(`已下架「${row.char ?? row._id}」`);
    await load();
    await loadGradeCounts();
  } catch (err) {
    reportError(err, '下架失败');
  }
}

// ---------------------------------------------------------------------------
// 真删（物理删除，不可恢复）
// ---------------------------------------------------------------------------
/**
 * 字是最容易被引用的内容（关卡、单元、短文都靠 `character_ids` 指过来），
 * 所以删除前让后端先查一遍引用；命中 40903 时把明细念给使用者听，
 * 由他决定放弃还是强制删除。**不做静默级联删除** ——
 * 那会连关卡一起抹掉，而关卡又挂着孩子的学习进度。
 */
async function remove(row: AdminCharacter): Promise<void> {
  const name = row.char ?? row._id;
  try {
    await ElMessageBox.confirm(
      `将物理删除「${name}」，从数据库中移除且不可恢复。若只是想让它不再下发给客户端，请改用「下架」。`,
      '确认删除？',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    );
  } catch {
    return; // 用户取消
  }
  await removeConfirmed(row, name, false);
}

async function removeConfirmed(row: AdminCharacter, name: string, force: boolean): Promise<void> {
  try {
    await adminApi.deleteCharacter(row._id, { force });
    ElMessage.success(`已删除「${name}」`);
    await load();
    await loadGradeCounts();
  } catch (err) {
    if (!force && err instanceof ApiError && err.code === CONTENT_IN_USE) {
      const detail = (err.errors ?? []).map((item) => item.reason).join('；');
      try {
        await ElMessageBox.confirm(
          `「${name}」仍被引用（${detail || '有关卡或单元在用'}）。删掉之后这些地方会指向不存在的字，孩子的关卡可能点不进去。仍然删除？`,
          '该内容仍在使用中',
          { type: 'warning', confirmButtonText: '仍然删除', cancelButtonText: '放弃' },
        );
      } catch {
        return;
      }
      await removeConfirmed(row, name, true);
      return;
    }
    reportError(err, '删除失败');
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>字库</h2>
      <div class="header-actions">
        <el-button :loading="importing" @click="triggerImport">导入 JSON</el-button>
        <el-button @click="downloadTemplate">下载模板</el-button>
        <el-button @click="exportJson">导出 JSON</el-button>
        <el-button type="primary" @click="openCreate">新建汉字</el-button>
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
      运行时真源是<b>服务端数据库</b>；<span class="mono">content/characters/*.json</span> 是
      可版本管理的内容形态，需要回写仓库时请「导出 JSON」（05-1 §1.1）。
      <br />
      导入按 <span class="mono">_id</span> 幂等 upsert，可放心重跑；导出的文件可直接再次导入或进 git。
      <b>导入的内容不会再被发布清掉</b>（库里有数据时以库为准，不覆盖、不删除）。
    </p>

    <div class="grade-tabs">
      <button
        v-for="tab in gradeTabs"
        :key="String(tab.value)"
        type="button"
        class="grade-tab"
        :class="{ 'grade-tab--active': activeGrade === tab.value }"
        @click="selectGrade(tab.value)"
      >
        {{ tab.label }}
        <span class="grade-tab__count">{{ gradeCount(tab.value) }}</span>
      </button>
    </div>

    <div class="filter-bar">
      <el-input v-model="query.keyword" placeholder="搜索汉字 / 释义" clearable style="width: 220px" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px">
        <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe size="small">
      <el-table-column label="汉字" width="72" align="center">
        <template #default="{ row }"><span class="glyph">{{ row.char }}</span></template>
      </el-table-column>
      <el-table-column label="ID" width="110">
        <template #default="{ row }"><span class="mono">{{ row._id }}</span></template>
      </el-table-column>
      <el-table-column label="拼音" width="130">
        <template #default="{ row }">{{ row.pinyin || '—' }}<span v-if="row.tone !== undefined" class="dim">（{{ row.tone }} 声）</span></template>
      </el-table-column>
      <el-table-column label="部首" width="70"><template #default="{ row }">{{ row.radical || '—' }}</template></el-table-column>
      <el-table-column label="笔画" width="70"><template #default="{ row }">{{ row.stroke_count ?? '—' }}</template></el-table-column>
      <el-table-column label="结构" width="90"><template #default="{ row }">{{ row.structure || '—' }}</template></el-table-column>
      <el-table-column label="年级" width="80"><template #default="{ row }">{{ gradeText(row.grade) }}</template></el-table-column>
      <el-table-column label="释义" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.meaning || '—' }}</template>
      </el-table-column>
      <el-table-column label="组词" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">{{ joinList(row.words) || '—' }}</template>
      </el-table-column>
      <el-table-column label="字源图" width="90" align="center">
        <template #default="{ row }">
          <span v-if="row.glyph" class="glyph-emoji" :title="row.glyph">{{ row.glyph }}</span>
          <span v-else class="text-dim">—</span>
        </template>
      </el-table-column>
      <el-table-column label="素材" width="140">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="row.audio_ref ? 'success' : 'info'">音</el-tag>
          <el-tag size="small" effect="plain" :type="row.image_ref ? 'success' : 'info'">图</el-tag>
          <el-tag size="small" effect="plain" :type="row.glyph ? 'success' : 'info'">源</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="版本" width="70" align="center"><template #default="{ row }">{{ row.version ?? 1 }}</template></el-table-column>
      <el-table-column label="更新时间" width="180">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm
            title="下架后该字不再下发到客户端（状态置为 offline，不物理删除）。确认下架？"
            confirm-button-text="下架"
            cancel-button-text="取消"
            @confirm="offline(row)"
          >
            <template #reference>
              <el-button link type="warning" :disabled="row.status === 'offline'">下架</el-button>
            </template>
          </el-popconfirm>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
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
    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑汉字' : '新建汉字'" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-divider content-position="left">基础</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="汉字" prop="char">
              <el-input v-model="form.char" maxlength="1" :disabled="isEditing" placeholder="例如：水" />
              <span v-if="isEditing" class="form-tip">ID 与汉字绑定，不可修改</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="拼音">
              <el-input v-model="form.pinyin" placeholder="例如：shuǐ" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="声调">
              <el-input-number v-model="form.tone" :min="0" :max="4" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="年级">
              <el-input-number v-model="form.grade" :min="0" :max="maxGrade" />
              <span class="form-tip">0 = 学龄前；留空 = 未分级（客户端不下发）</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">字形</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="部首"><el-input v-model="form.radical" maxlength="2" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="笔画数"><el-input-number v-model="form.stroke_count" :min="1" :max="64" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="结构">
              <el-select v-model="form.structure" clearable placeholder="选择结构">
                <el-option v-for="item in STRUCTURE_OPTIONS" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">字源</el-divider>
        <el-form-item label="字源图">
          <div class="glyph-editor">
            <el-input
              v-model="form.glyph"
              placeholder="emoji（💧）、图片链接（https://…）或素材 id（as_…）"
              maxlength="200"
              style="width: 420px"
            />
            <!-- 预览：三种形态在后台就要看得见，否则运营填错了要等客户端才发现 -->
            <div class="glyph-editor__preview">
              <GlyphPreview :glyph="form.glyph" />
            </div>
          </div>
          <span class="form-tip">
            「看图选字」的题干主图。必须是<b>字义联想</b>（水 → 流水、太阳），不是随意装饰图。
            可填 emoji、图片链接，或在「素材」里上传后填素材 id。
            留空时该题型退化为按释义提示出题。
          </span>
        </el-form-item>

        <el-divider content-position="left">释义</el-divider>
        <el-form-item label="释义">
          <el-input v-model="form.meaning" type="textarea" :rows="2" maxlength="40" show-word-limit placeholder="不超过 40 字" />
        </el-form-item>
        <el-form-item label="组词">
          <el-input v-model="form.words" placeholder="用「、」分隔，例如：水果、喝水" />
          <span class="form-tip">每个词都应包含本字</span>
        </el-form-item>
        <el-form-item label="例句">
          <el-input v-model="form.sentences" type="textarea" :rows="2" placeholder="用「、」分隔" />
        </el-form-item>

        <el-divider content-position="left">分类与流程</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="标签"><el-input v-model="form.tags" placeholder="用「、」分隔" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status">
                <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.glyph-editor {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.glyph-editor__preview {
  padding-top: 2px;
}

.glyph {
  font-size: 18px;
  font-weight: 600;
}

.dim {
  color: #a8abb2;
  font-size: 12px;
}

.text-dim {
  color: #c0c4cc;
}

.glyph-emoji {
  font-size: 20px;
  line-height: 1;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

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
</style>
