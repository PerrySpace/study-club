<script setup lang="ts">
/**
 * ReadingsView —— 识字短文维护（走通用 ContentManager）。
 *
 * 短文是「阅读承接」的内容：只用孩子**已经学过**的字编的读本。
 * 客户端只推覆盖率 ≥75% 的短文，所以运营最该盯的两个数是
 * `character_ids / character_chars` 与配图 —— 前者是能不能推，后者是孩子读不读得下去。
 */
import ContentManager from '@/components/ContentManager.vue';
import { GRADE_TABS, LEVEL_OPTIONS, type ColumnDef, type FieldDef } from '@/components/content-fields';

const fields: FieldDef[] = [
  { name: 'title', label: '标题', kind: 'text', required: true, maxlength: 24 },
  {
    name: 'type',
    label: '类型',
    kind: 'select',
    required: true,
    options: [
      { value: 'sentence', label: '单句起步' },
      { value: 'passage', label: '多句短文' },
    ],
    hint: '单句用于刚起步的孩子；多句短文用于阅读承接',
  },
  {
    name: 'image_ref',
    label: '配图',
    kind: 'image',
    hint: '强烈建议填：没有配图的短文孩子读不下去。优先选字义联想图，而不是装饰图',
  },
  {
    name: 'sentences',
    label: '句子',
    kind: 'reading-sentences',
    required: true,
    hint: '逐句朗读与逐字高亮都靠它；拼音可留空但建议补齐',
  },
  { name: 'text', label: '正文', kind: 'textarea', rows: 2, derived: true },
  { name: 'full_pinyin', label: '全文拼音', kind: 'text', derived: true },
  { name: 'character_ids', label: '已学字 id', kind: 'list', derived: true, hint: '导入时按正文与字库自动匹配' },
  { name: 'character_chars', label: '全部字面', kind: 'list', derived: true, hint: '导入时按正文逐字提取' },
  { name: 'new_character_chars', label: '生字', kind: 'list', derived: true, hint: '文中出现但尚未入字库的字' },
  { name: 'word_count', label: '字数', kind: 'number', derived: true },
  { name: 'grade', label: '年级', kind: 'number', hint: '1–6；0 为学龄前' },
  { name: 'level', label: '难度', kind: 'select', options: LEVEL_OPTIONS },
  { name: 'difficulty', label: '难度分', kind: 'number', hint: '1–5' },
  { name: 'order', label: '排序', kind: 'number', hint: '同级内排序，小的靠前' },
  { name: 'theme', label: '主题', kind: 'text', maxlength: 12, placeholder: '自然 / 校园 / 家庭' },
  { name: 'tips', label: '家长导读', kind: 'textarea', rows: 2, maxlength: 200, hint: '怎么带读、可以问什么问题' },
  { name: 'audio_ref', label: '整篇音频', kind: 'audio', hint: '留空时按句用 TTS 朗读' },
];

const columns: ColumnDef[] = [
  { prop: 'title', label: '标题', width: 140 },
  { prop: 'image_ref', label: '配图', width: 90, align: 'center', formatter: 'image' },
  { prop: 'type', label: '类型', width: 90, align: 'center' },
  { prop: 'grade', label: '年级', width: 90, align: 'center', formatter: 'grade' },
  { prop: 'sentences', label: '句数', width: 70, align: 'center', formatter: 'count' },
  { prop: 'word_count', label: '字数', width: 70, align: 'center' },
  { prop: 'character_ids', label: '已学字', width: 80, align: 'center', formatter: 'count' },
  { prop: 'character_chars', label: '全字面', width: 80, align: 'center', formatter: 'count' },
  { prop: 'text', label: '正文', minWidth: 200 },
  { prop: 'status', label: '状态', width: 90, align: 'center', formatter: 'status' },
  { prop: 'updated_at', label: '更新时间', width: 170, formatter: 'time' },
];
</script>

<template>
  <ContentManager
    collection="readings"
    title="识字短文"
    label="短文"
    :fields="fields"
    :columns="columns"
    :grade-tabs="GRADE_TABS"
    hint="短文只用孩子已学过的字。客户端只推覆盖率 ≥75% 的短文 —— 「已学字」少于「全字面」七成，这篇就等于天书，孩子只会挫败。"
  />
</template>
