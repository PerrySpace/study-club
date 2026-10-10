<script setup lang="ts">
/**
 * PoemsView —— 古诗维护（走通用 ContentManager）。
 *
 * 字段与后端 `content_registry` 里 poems 的 `field_docs` 逐条对应，
 * 「下载模板」拿到的说明与这里展示的一致。
 */
import ContentManager from '@/components/ContentManager.vue';
import { GRADE_TABS, LEVEL_OPTIONS, type ColumnDef, type FieldDef } from '@/components/content-fields';

const fields: FieldDef[] = [
  { name: 'title', label: '诗题', kind: 'text', required: true, maxlength: 24, hint: 'ID 由诗题派生，改诗题等于换一条记录' },
  { name: 'dynasty', label: '朝代', kind: 'text', maxlength: 8, placeholder: '唐 / 宋' },
  { name: 'author', label: '作者', kind: 'text', maxlength: 16 },
  {
    name: 'lines',
    label: '诗句',
    kind: 'poem-lines',
    required: true,
    hint: '每行一句；填字游戏与逐句朗读都靠它。拼音可留空，但建议补齐',
  },
  { name: 'full_text', label: '全文', kind: 'textarea', rows: 2, derived: true },
  { name: 'appreciation', label: '译文赏析', kind: 'textarea', rows: 2, maxlength: 300, hint: '儿童可读的口语化版本，不要写成文学评论' },
  { name: 'background', label: '创作背景', kind: 'textarea', rows: 2, maxlength: 300 },
  { name: 'key_characters', label: '重点字', kind: 'list', hint: '与字库相同的汉字字面，用于诗内生字标注' },
  { name: 'grade', label: '年级', kind: 'number', hint: '1–6；0 为学龄前' },
  { name: 'level', label: '难度', kind: 'select', options: LEVEL_OPTIONS },
  { name: 'difficulty', label: '难度分', kind: 'number', hint: '1–5，用于排序' },
  {
    name: 'theme_tags',
    label: '主题标签',
    kind: 'list',
    hint: '写景 / 咏物 / 思乡 / 友情 / 励志',
  },
  {
    name: 'source',
    label: '出处',
    kind: 'select',
    options: [
      { value: 'classic', label: '经典必背' },
      { value: 'extension', label: '拓展' },
    ],
    hint: '可溯源要求见 01-4 第五章',
  },
  { name: 'audio_ref', label: '音频', kind: 'audio', hint: '留空时客户端用浏览器 TTS 逐句朗读' },
];

const columns: ColumnDef[] = [
  { prop: 'title', label: '诗题', width: 130 },
  { prop: 'dynasty', label: '朝代', width: 70, align: 'center' },
  { prop: 'author', label: '作者', width: 100, align: 'center' },
  { prop: 'grade', label: '年级', width: 90, align: 'center', formatter: 'grade' },
  { prop: 'lines', label: '句数', width: 70, align: 'center', formatter: 'count' },
  { prop: 'full_text', label: '全文', minWidth: 220 },
  { prop: 'audio_ref', label: '音频', width: 80, align: 'center' },
  { prop: 'status', label: '状态', width: 90, align: 'center', formatter: 'status' },
  { prop: 'updated_at', label: '更新时间', width: 170, formatter: 'time' },
];
</script>

<template>
  <ContentManager
    collection="poems"
    title="古诗"
    label="古诗"
    :fields="fields"
    :columns="columns"
    :grade-tabs="GRADE_TABS"
    hint="古诗是「诵读」类内容，务必逐句填拼音与释义 —— 客户端的逐句朗读与家长导读都依赖它们。"
  />
</template>
