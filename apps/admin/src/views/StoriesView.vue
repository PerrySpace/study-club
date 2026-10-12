<script setup lang="ts">
/**
 * StoriesView —— 故事 / 儿歌维护（走通用 ContentManager）。
 *
 * 为什么单开一页：`stories` 早就在后端与内容包里（seed 会导入），
 * 却一直没有后台入口 —— 运营导入完故事后**无处查看、无处纠错**，
 * 只能靠重新导入整包。这里补齐，字段与后端 `content_registry` 的
 * stories spec（`required_on_create=(title, text)`、可筛选 `grade/level`）对齐。
 *
 * 与识字短文的区别：故事的长短与生字量都不受控，用 `highlight_characters`
 * 标出「读的时候要高亮的字」，而不是像短文那样卡覆盖率。
 */
import ContentManager from '@/components/ContentManager.vue';
import { LEVEL_OPTIONS, type ColumnDef, type FieldDef } from '@/components/content-fields';

const fields: FieldDef[] = [
  { name: 'title', label: '标题', kind: 'text', required: true, maxlength: 24, hint: 'ID 由标题派生，改标题等于换一条记录' },
  {
    name: 'type',
    label: '类型',
    kind: 'select',
    required: true,
    options: [
      { value: 'story', label: '故事' },
      { value: 'rhyme', label: '儿歌' },
    ],
  },
  {
    name: 'text',
    label: '正文',
    kind: 'textarea',
    rows: 4,
    required: true,
    hint: '用换行分行；客户端按行逐句朗读，一行不要太长',
  },
  {
    name: 'highlight_characters',
    label: '高亮字',
    kind: 'list',
    hint: '读的时候要高亮的汉字字面（通常填本关要认的字）',
  },
  { name: 'grade', label: '年级', kind: 'number', hint: '0 = 学龄前；缺省 = 未分级（客户端不下发）。可选年级见「站点配置」' },
  { name: 'level', label: '难度', kind: 'select', options: LEVEL_OPTIONS },
  { name: 'audio_ref', label: '音频', kind: 'audio', hint: '留空时按行用 TTS 朗读' },
  {
    name: 'unlock_after_lesson_ids',
    label: '前置关卡',
    kind: 'list',
    hint: '需先完成的关卡 id；留空表示不限',
  },
  { name: 'word_count', label: '字数', kind: 'number', derived: true, hint: '导入时自动统计' },
];

const columns: ColumnDef[] = [
  { prop: 'title', label: '标题', width: 140 },
  { prop: 'type', label: '类型', width: 80, align: 'center' },
  { prop: 'grade', label: '年级', width: 90, align: 'center', formatter: 'grade' },
  { prop: 'word_count', label: '字数', width: 70, align: 'center' },
  { prop: 'highlight_characters', label: '高亮字', width: 80, align: 'center', formatter: 'count' },
  { prop: 'text', label: '正文', minWidth: 240 },
  { prop: 'status', label: '状态', width: 90, align: 'center', formatter: 'status' },
  { prop: 'updated_at', label: '更新时间', width: 170, formatter: 'time' },
];
</script>

<template>
  <ContentManager
    collection="stories"
    title="故事 / 儿歌"
    label="故事"
    :fields="fields"
    :columns="columns"
    hint="故事与儿歌按年级下发（客户端取「孩子年级及以下」）。正文字数不受限，但一行别太长 —— 客户端按行朗读与高亮。"
  />
</template>
