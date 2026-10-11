<script setup lang="ts">
/**
 * LevelResult —— 关卡结果卡（识字 / 古诗 / 故事三条线共用）。
 *
 * ## 为什么抽出来
 * 若三个关卡页各写一套结果区，闭环就会各不相同：有的有星星与「回首页」，
 * 有的做完就停住（没有完成、没有下一步）。抽成一处之后，
 * 「完成一关后能做什么」只有一份答案：
 *
 *   **看星星 → 再练一次 / 下一关（没有下一关时是「回地图」）**
 *
 * ## 为什么「下一关」是主按钮
 * 孩子完成一关的那一刻是**继续意愿最强**的时刻。把主行动给「回首页」等于
 * 在最想继续的时候打断他；而「下一关」让闯关链路自己往下走，地图上的解锁
 * 状态则由完成流水自动跟上 —— 这就是流程的闭环。
 */
import { computed } from 'vue';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import StarRow from '@/components/biz/StarRow.vue';

const props = withDefaults(
  defineProps<{
    /** 本关星星（0–3） */
    stars: number;
    /** 标题，默认「本关完成」 */
    title?: string;
    /** 副标题（如「答对 8 / 10」） */
    subtitle?: string;
    /** 结果数字块 */
    stats?: Array<{ label: string; value: string | number }>;
    /** 新解锁的徽章 */
    badges?: string[];
    /** 底部说明（家长向） */
    note?: string;
    /** 是否有下一关 */
    hasNext?: boolean;
    /** 下一关按钮文案（故事/古诗可换成「下一首」「下一个故事」） */
    nextLabel?: string;
    /** 是否显示「再练一次」 */
    showRetry?: boolean;
    /** 全部完成时的结语（覆盖默认文案） */
    doneText?: string;
  }>(),
  {
    title: '本关完成',
    subtitle: '',
    stats: () => [],
    badges: () => [],
    note: '',
    hasNext: false,
    nextLabel: '下一关',
    showRetry: true,
    doneText: '',
  },
);

const emit = defineEmits<{
  (e: 'next'): void;
  (e: 'retry'): void;
  (e: 'back'): void;
}>();

const ending = computed(() => props.doneText || '这一条线全部学完啦，回地图看看别的方向。');
</script>

<template>
  <BaseCard :title="title" :subtitle="subtitle">
    <div class="result">
      <!-- 星星是「我做得怎么样」的唯一反馈：放在结果区最上方、最大 -->
      <StarRow :stars="stars" :size="44" class="result__stars" />
      <p class="result__stars-text text-sm text-muted">
        {{ stars > 0 ? `点亮 ${stars} 颗星` : '这次没有点亮星星，再试一次就会亮起来' }}
      </p>

      <div v-if="stats.length" class="grid grid--2">
        <div v-for="s in stats" :key="s.label" class="result__tile">
          <p class="result__value">{{ s.value }}</p>
          <p class="text-muted text-sm">{{ s.label }}</p>
        </div>
      </div>

      <div v-if="badges.length" class="result__badges">
        <p class="result__badges-title">新解锁徽章</p>
        <ul class="result__badges-list">
          <li v-for="badge in badges" :key="badge" class="result__badge">{{ badge }}</li>
        </ul>
      </div>

      <p v-if="note" class="text-sm text-muted result__note">{{ note }}</p>
      <p v-if="!hasNext" class="text-sm text-muted result__note">{{ ending }}</p>
    </div>

    <template #footer>
      <div class="row row--wrap">
        <BaseButton v-if="showRetry" variant="secondary" @click="emit('retry')">再练一次</BaseButton>
        <BaseButton v-if="hasNext" size="lg" @click="emit('next')">{{ nextLabel }}</BaseButton>
        <BaseButton v-else size="lg" @click="emit('back')">回地图</BaseButton>
      </div>
    </template>
  </BaseCard>
</template>

<style scoped>
.result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
}

.result__stars {
  margin-block: var(--space-2xs);
}

.result__stars-text {
  margin: 0;
}

.result__tile {
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  text-align: center;
}

.result__value {
  font-size: var(--font-xl);
  font-weight: 700;
}

.result__badges {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--color-primary) 28%, var(--color-surface));
}

.result__badges-title {
  font-size: var(--font-sm);
  font-weight: 600;
}

.result__badges-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-top: var(--space-2xs);
  padding: 0;
  list-style: none;
}

.result__badge {
  padding: 2px var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  font-size: var(--font-sm);
}

.result__note {
  margin: 0;
  text-align: center;
}
</style>
