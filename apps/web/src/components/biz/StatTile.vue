<script setup lang="ts">
/** StatTile —— 统计小卡（报告页与首页复用）。 */
withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    hint?: string;
    tone?: 'default' | 'primary' | 'success' | 'danger';
  }>(),
  { hint: '', tone: 'default' },
);
</script>

<template>
  <div class="tile" :class="`tile--${tone}`">
    <p class="tile__value">{{ value }}</p>
    <p class="tile__label">{{ label }}</p>
    <p v-if="hint" class="tile__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.tile--primary {
  background: color-mix(in srgb, var(--color-primary) 30%, var(--color-surface));
}

.tile--success {
  background: color-mix(in srgb, var(--color-success) 16%, var(--color-surface));
}

.tile--danger {
  background: color-mix(in srgb, var(--color-danger) 16%, var(--color-surface));
}

.tile__value {
  font-size: var(--font-xl);
  font-weight: 700;
}

.tile__label {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.tile__hint {
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}
</style>
