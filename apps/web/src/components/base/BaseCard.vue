<script setup lang="ts">
/** BaseCard —— 基础卡片（纯展示，无业务）。 */
withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    hoverable?: boolean;
    padding?: boolean;
  }>(),
  { title: '', subtitle: '', hoverable: false, padding: true },
);
</script>

<template>
  <section class="card" :class="{ 'card-hoverable': hoverable, 'card--flush': !padding }">
    <header v-if="title || $slots.header" class="card__header">
      <slot name="header">
        <h2 class="card__title">{{ title }}</h2>
        <p v-if="subtitle" class="card__subtitle">{{ subtitle }}</p>
      </slot>
    </header>
    <div class="card__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="card__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition:
    transform 120ms ease-out,
    box-shadow 120ms ease-out;
}

.card__header {
  padding: var(--space-md) var(--space-md) 0;
}

.card__title {
  font-size: var(--font-lg);
  font-weight: 600;
}

.card__subtitle {
  margin-top: var(--space-xs);
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.card__body {
  padding: var(--space-md);
}

.card--flush .card__body {
  padding: 0;
}

.card__footer {
  padding: 0 var(--space-md) var(--space-md);
}
</style>
