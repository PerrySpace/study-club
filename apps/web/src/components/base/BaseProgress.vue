<script setup lang="ts">
/** BaseProgress —— 进度条（0–1）。 */
import { computed } from 'vue';

import { percent } from '@/utils/format';

const props = withDefaults(
  defineProps<{
    value: number;
    label?: string;
    showText?: boolean;
    tone?: 'primary' | 'success';
  }>(),
  { label: '', showText: true, tone: 'primary' },
);

const ratio = computed(() => Math.min(1, Math.max(0, props.value)));
</script>

<template>
  <div class="progress">
    <div v-if="label || showText" class="progress__meta">
      <span class="progress__label">{{ label }}</span>
      <span v-if="showText" class="progress__text">{{ percent(ratio) }}</span>
    </div>
    <div
      class="progress__track"
      role="progressbar"
      :aria-valuenow="Math.round(ratio * 100)"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="label || '进度'"
    >
      <div class="progress__bar" :class="`progress__bar--${tone}`" :style="{ width: `${ratio * 100}%` }" />
    </div>
  </div>
</template>

<style scoped>
.progress {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.progress__meta {
  display: flex;
  justify-content: space-between;
  gap: var(--space-sm);
  font-size: var(--font-sm);
  color: var(--color-text-muted);
}

.progress__track {
  height: 12px;
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  overflow: hidden;
}

.progress__bar {
  height: 100%;
  border-radius: var(--radius-pill);
  transition: width 240ms ease-out;
}

.progress__bar--primary {
  background: var(--color-primary-strong);
}

.progress__bar--success {
  background: var(--color-success);
}
</style>
