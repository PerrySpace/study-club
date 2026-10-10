<script setup lang="ts">
/** PoemLine —— 古诗单句（逐句注音 + 白话）。 */
withDefaults(
  defineProps<{
    text: string;
    pinyin: string;
    meaning: string;
    showMeaning?: boolean;
    /** 高亮字（如本句的关键字） */
    highlight?: string[];
  }>(),
  { showMeaning: true, highlight: () => [] },
);
</script>

<template>
  <li class="poem-line">
    <p class="poem-line__pinyin">{{ pinyin }}</p>
    <p class="poem-line__text learning-surface">
      <span
        v-for="(ch, i) in text.split('')"
        :key="`${ch}-${i}`"
        :class="{ 'poem-line__char--hl': highlight.includes(ch) }"
        class="poem-line__char"
        >{{ ch }}</span
      >
    </p>
    <p v-if="showMeaning" class="poem-line__meaning selectable">{{ meaning }}</p>
    <!-- 逐句的朗读 / 跟读按钮由父级注入：本组件只是版式，不决定交互 -->
    <div v-if="$slots.actions" class="poem-line__actions">
      <slot name="actions" />
    </div>
  </li>
</template>

<style scoped>
.poem-line {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding-block: var(--space-sm);
}

.poem-line__pinyin {
  color: var(--color-info);
  font-size: var(--font-sm);
  letter-spacing: 0.06em;
}

.poem-line__text {
  font-size: var(--font-xl);
  font-weight: 500;
  letter-spacing: 0.12em;
}

.poem-line__char--hl {
  color: var(--color-danger);
  font-weight: 700;
}

.poem-line__meaning {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.poem-line__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}
</style>
