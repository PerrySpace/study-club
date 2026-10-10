<script setup lang="ts">
/**
 * ContentFieldEditor —— 按字段类型渲染对应的输入控件。
 *
 * 存在的意义是让「新增一类内容」只需要写字段定义，不必再写一遍表单：
 * 所有控件的**取值形状**与内容包 JSON 严格一致（数组就是数组、对象就是对象），
 * 保存时不做隐式转换 —— 隐式转换是内容对不上的主要来源。
 */
import { computed, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { adminApi, type AdminAsset } from '@/api/admin';
import { reportError } from '@/utils/error';
import type { FieldDef } from './content-fields';

const props = defineProps<{
  field: FieldDef;
}>();

const model = defineModel<unknown>();

const emit = defineEmits<{
  (e: 'pick-asset', assetId: string | null): void;
}>();

// ---------------------------------------------------------------------------
// 素材选择（图片 / 音频 / 笔顺数据共用）
// ---------------------------------------------------------------------------
const assets = ref<AdminAsset[]>([]);
const assetsLoading = ref(false);
const assetsLoaded = ref(false);
/** 期望的素材类型：image 字段只让挑 image，避免把音频绑成配图。 */
const wantedType = computed<'image' | 'audio' | 'stroke'>(() => {
  if (props.field.kind === 'audio') return 'audio';
  if (props.field.kind === 'stroke') return 'stroke';
  return 'image';
});

async function loadAssets(): Promise<void> {
  if (assetsLoaded.value) return;
  assetsLoading.value = true;
  try {
    const data = await adminApi.listAssets({ type: wantedType.value, page_size: 100 });
    assets.value = data.items;
    assetsLoaded.value = true;
  } catch (err) {
    reportError(err, '加载素材失败');
  } finally {
    assetsLoading.value = false;
  }
}

const currentAssetId = computed(() => (typeof model.value === 'string' ? model.value : ''));

const currentPreview = computed(() => {
  const id = currentAssetId.value;
  if (!id.startsWith('as_')) return null;
  return `/api/v1/assets/${id}`;
});

function chooseAsset(asset: AdminAsset | null): void {
  const id = asset?._id ?? null;
  model.value = id ?? '';
  emit('pick-asset', id);
  if (asset) ElMessage.success(`已选择素材：${asset.original_name}`);
}

// ---------------------------------------------------------------------------
// 数组类字段（tags / list）
// ---------------------------------------------------------------------------
const listText = ref('');

function currentList(): string[] {
  return Array.isArray(model.value) ? (model.value as string[]).map(String) : [];
}

function commitList(next: string[]): void {
  model.value = next;
}

function addListItem(): void {
  const parts = listText.value
    .split(/[、,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!parts.length) return;
  commitList([...currentList(), ...parts]);
  listText.value = '';
}

function removeListItem(index: number): void {
  commitList(currentList().filter((_, i) => i !== index));
}

// ---------------------------------------------------------------------------
// 诗句 / 句子类字段
// ---------------------------------------------------------------------------
interface LineItem {
  text: string;
  pinyin: string;
  meaning: string;
}

function currentLines(): LineItem[] {
  if (!Array.isArray(model.value)) return [];
  return (model.value as Record<string, unknown>[]).map((row) => ({
    text: String(row?.text ?? ''),
    pinyin: String(row?.pinyin ?? ''),
    meaning: String(row?.meaning ?? ''),
  }));
}

function commitLines(next: LineItem[]): void {
  // 丢掉整行空白：留着空行会让客户端逐句朗读时读出空句
  model.value = next.filter((l) => l.text.trim());
}

function addLine(): void {
  commitLines([...currentLines(), { text: '', pinyin: '', meaning: '' }]);
}

function removeLine(index: number): void {
  commitLines(currentLines().filter((_, i) => i !== index));
}

/** 按正文统计字数 —— 覆盖率门槛（≥75%）是运营最该盯的指标，编辑时要能立刻看到。 */
function countChars(): void {
  const text = currentLines()
    .map((l) => l.text.trim())
    .filter(Boolean)
    .join('');
  const unique = new Set(text.replace(/[^一-鿿]/g, '')).size;
  ElMessage.success(`正文 ${text.length} 字，去重汉字 ${unique} 个`);
}

async function uploadAndSelect(file: File): Promise<void> {
  try {
    const asset = await adminApi.uploadAsset(file, { type: 'image' });
    ElMessage.success(`已上传：${asset.original_name}`);
  } catch (err) {
    reportError(err, '上传素材失败');
  }
}

/** 派生字段的展示文案（如「3 个字」），避免让运营看到一堆 JSON。 */
function formatDerived(value: unknown): string {
  if (value === null || value === undefined || value === '') return '（导入时自动生成）';
  if (Array.isArray(value)) return value.length ? value.join('、') : '（空）';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/*
 * 文本 / 数字的读写走**计算属性 + setter**，而不是在模板里写 `v-model="model as string"`。
 *
 * 原因有二：
 *   ① `model` 是 `defineModel<unknown>()`，它的类型是 `unknown`，
 *      元素组件的 v-model 需要具体类型，直接断言在模板编译期过不去；
 *   ② 属性名收敛到一处，父组件换成别的存储方式时只改这三行。
 * setter 里的 `?? ''` / `?? 0` 是**归一化**：空值统一成「空串 / 0」，
 * 免得 `Number(undefined)` 变 NaN 写进库。
 */
const textValue = computed<string>({
  get: () => (typeof model.value === 'string' ? model.value : model.value == null ? '' : String(model.value)),
  set: (v: string) => {
    model.value = v;
  },
});

const numberValue = computed<number>({
  get: () => {
    const n = Number(model.value);
    return Number.isFinite(n) ? n : 0;
  },
  set: (v: number | undefined) => {
    model.value = v ?? 0;
  },
});
</script>

<template>
  <!-- 派生字段：只读，说明为什么不能改 -->
  <el-input v-if="field.derived" :model-value="formatDerived(model)" disabled />

  <!-- 素材类：图片 / 音频 / 笔顺 -->
  <div v-else-if="['image', 'audio', 'stroke'].includes(field.kind)" class="asset-field">
    <div class="asset-field__row">
      <el-select
        :model-value="currentAssetId"
        filterable
        clearable
        placeholder="从素材库选择"
        style="width: 320px"
        :loading="assetsLoading"
        @visible-change="(v: boolean) => v && loadAssets()"
        @change="(v: string) => chooseAsset(assets.find((a) => a._id === v) ?? null)"
      >
        <el-option
          v-for="a in assets"
          :key="a._id"
          :label="`${a.original_name}（${a.storage_key}）`"
          :value="a._id"
        />
      </el-select>
      <el-upload
        :show-file-list="false"
        :auto-upload="false"
        accept="image/*"
        @change="async (f: any) => await uploadAndSelect(f)"
      >
        <el-button :loading="assetsLoading">上传图片</el-button>
      </el-upload>
      <el-button v-if="currentAssetId" link type="danger" @click="chooseAsset(null)">清除</el-button>
    </div>
    <div v-if="currentPreview" class="asset-field__preview">
      <img :src="currentPreview" alt="素材预览" />
    </div>
    <el-input
      :model-value="currentAssetId"
      placeholder="或直接填写素材 id（as_ 开头）"
      size="small"
      style="width: 320px"
      @update:model-value="(v: string) => (model = v)"
    />
  </div>

  <!-- 诗句 / 句子 -->
  <div v-else-if="['poem-lines', 'reading-sentences'].includes(field.kind)" class="lines-field">
    <div v-for="(line, index) in currentLines()" :key="index" class="lines-field__row">
      <span class="lines-field__no">{{ index + 1 }}</span>
      <el-input v-model="line.text" placeholder="正文（必填）" style="flex: 2" />
      <el-input v-model="line.pinyin" placeholder="拼音" style="flex: 2" />
      <el-input v-model="line.meaning" placeholder="释义" style="flex: 2" />
      <el-button link type="danger" @click="removeLine(index)">删</el-button>
    </div>
    <div class="lines-field__actions">
      <el-button size="small" @click="addLine">加一行</el-button>
      <el-button size="small" text type="primary" @click="countChars">
        统计字数
      </el-button>
    </div>
    <p class="form-tip">
      拼音与释义可留空（客户端会退化为只读正文），但**逐句朗读与家长导读**依赖它们，建议补齐。
    </p>
  </div>

  <!-- 数组（组词 / 标签 / 近义词） -->
  <div v-else-if="field.kind === 'list' || field.kind === 'tags'" class="list-field">
    <div class="list-field__tags">
      <el-tag
        v-for="(item, index) in currentList()"
        :key="`${item}-${index}`"
        closable
        @close="removeListItem(index)"
      >
        {{ item }}
      </el-tag>
      <span v-if="!currentList().length" class="text-dim">暂无</span>
    </div>
    <div class="list-field__add">
      <el-input
        v-model="listText"
        placeholder="用「、」或空格分隔后回车"
        size="small"
        style="width: 320px"
        @keyup.enter="addListItem"
      />
      <el-button size="small" @click="addListItem">添加</el-button>
    </div>
  </div>

  <!-- 下拉 -->
  <el-select v-else-if="field.kind === 'select'" v-model="model" clearable style="width: 240px">
    <el-option
      v-for="opt in field.options ?? []"
      :key="opt.value"
      :label="opt.label"
      :value="opt.value"
    />
  </el-select>

  <!-- 数字 -->
  <el-input-number
    v-else-if="field.kind === 'number'"
    v-model="numberValue"
    :min="0"
    :max="99"
  />

  <!-- 多行文本 -->
  <el-input
    v-else-if="field.kind === 'textarea'"
    v-model="textValue"
    type="textarea"
    :rows="field.rows ?? 3"
    :maxlength="field.maxlength"
    show-word-limit
    :placeholder="field.placeholder"
    style="width: 100%"
  />

  <!-- 单行文本 -->
  <el-input
    v-else
    v-model="textValue"
    :maxlength="field.maxlength"
    :placeholder="field.placeholder"
    clearable
    style="width: 100%"
  />
</template>

<style scoped>
.asset-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.asset-field__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.asset-field__preview img {
  max-width: 160px;
  max-height: 100px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  object-fit: contain;
}

.lines-field__row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.lines-field__no {
  width: 20px;
  color: #a8abb2;
  font-size: 12px;
  text-align: right;
}

.lines-field__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-field__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 24px;
  margin-bottom: 6px;
}

.list-field__add {
  display: flex;
  align-items: center;
  gap: 6px;
}

.text-dim {
  color: #c0c4cc;
  font-size: 12px;
}

.form-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
