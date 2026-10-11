<script setup lang="ts">
/**
 * WrongBookView —— 错题本与重练（S-06）。
 * 答错即入本；答对则标记为已解决（由 learning store 维护，数据持久化在服务端）。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import { useChildStore, useContentStore, useLearningStore } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import StatTile from '@/components/biz/StatTile.vue';
import { formatDate } from '@/utils/format';

const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();

const { current } = storeToRefs(childStore);
const showResolved = ref(false);

const pending = computed(() => learning.wrongQuestions.filter((w) => !w.resolved));
const resolved = computed(() => learning.wrongQuestions.filter((w) => w.resolved));

const rows = computed(() => {
  const source = showResolved.value ? resolved.value : pending.value;
  return [...source]
    .sort((a, b) => b.wrong_count - a.wrong_count)
    .map((w) => ({
      ...w,
      pinyin: content.charByText.get(w.char)?.pinyin ?? '',
      meaning: content.charByText.get(w.char)?.meaning ?? '',
    }));
});

async function load(): Promise<void> {
  if (!current.value) return;
  await learning.loadChildData(current.value._id);
}

onMounted(load);
watch(() => current.value?._id, load);

function retry(): void {
  void router.push({ name: 'lesson', params: { lessonId: 'wrong' } });
}
</script>

<template>
  <section class="stack--lg stack">
    <BaseEmpty v-if="!current" title="还没有孩子档案" description="建立档案后才能记录错题。">
      <BaseButton @click="router.push({ name: 'settings' })">去创建档案</BaseButton>
    </BaseEmpty>

    <template v-else>
      <BaseCard title="错题概览" subtitle="错题优先进入每日任务，答对后自动移出">
        <div class="grid grid--2">
          <StatTile label="待解决" :value="pending.length" :tone="pending.length ? 'danger' : 'success'" />
          <StatTile label="已解决" :value="resolved.length" tone="success" />
        </div>
        <template #footer>
          <BaseButton size="lg" block :disabled="pending.length === 0" @click="retry">
            {{ pending.length === 0 ? '暂无待解决错题 🎉' : `重练错题（${pending.length} 个）` }}
          </BaseButton>
        </template>
      </BaseCard>

      <BaseCard :title="showResolved ? '已解决的错题' : '待解决的错题'">
        <template #header>
          <div class="row row--between">
            <h2 class="section-title">{{ showResolved ? '已解决的错题' : '待解决的错题' }}</h2>
            <BaseButton variant="ghost" @click="showResolved = !showResolved">
              {{ showResolved ? '看未解决' : '看已解决' }}
            </BaseButton>
          </div>
        </template>

        <BaseEmpty v-if="!rows.length" title="这里空空如也" description="继续保持！" icon="🌟" />

        <ul v-else class="wrong-list">
          <li v-for="row in rows" :key="row._id" class="wrong-item">
            <span class="wrong-item__char">{{ row.char }}</span>
            <span class="wrong-item__main">
              <span class="wrong-item__pinyin">{{ row.pinyin }}</span>
              <span class="text-sm text-muted">{{ row.meaning }}</span>
            </span>
            <SpeakButton :text="row.char" :rate="0.7" label="听" size="sm" variant="ghost" />
            <span class="wrong-item__meta text-sm text-muted">
              错 {{ row.wrong_count }} 次 · {{ formatDate(row.last_wrong_at) }}
            </span>
          </li>
        </ul>
      </BaseCard>
    </template>
  </section>
</template>

<style scoped>
.wrong-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.wrong-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.wrong-item__char {
  font-size: var(--font-xl);
  font-weight: 600;
}

.wrong-item__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.wrong-item__pinyin {
  color: var(--color-info);
}

.wrong-item__meta {
  margin-left: auto;
  text-align: right;
}
</style>
