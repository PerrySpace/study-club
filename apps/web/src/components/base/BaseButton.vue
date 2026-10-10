<script setup lang="ts">
/**
 * BaseButton —— 基础按钮。
 * 触控热区：默认 ≥ --tap-min(56px)，primary 尺寸 ≥ --tap-primary(64px)（06-1 §2.9.3）。
 * 相邻热区间距由容器 gap ≥ 12px 保证。
 */
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    size?: 'md' | 'lg';
    block?: boolean;
    disabled?: boolean;
    loading?: boolean;
    type?: 'button' | 'submit';
  }>(),
  {
    variant: 'primary',
    size: 'md',
    block: false,
    disabled: false,
    loading: false,
    type: 'button',
  },
);

const emit = defineEmits<{ (e: 'click', ev: MouseEvent): void }>();

function onClick(ev: MouseEvent): void {
  emit('click', ev);
}
</script>

<template>
  <button
    class="btn tap clickable"
    :class="[
      `btn--${variant}`,
      `btn--${size}`,
      { 'btn--block': block, 'btn--loading': loading },
    ]"
    :type="type"
    :disabled="disabled || loading"
    @click="onClick"
  >
    <span v-if="loading" class="btn__spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-pill);
  font-size: var(--font-body);
  font-weight: 600;
  line-height: 1.4;
  transition:
    transform 90ms ease-out,
    filter 90ms ease-out;
}

.btn--md {
  min-height: var(--tap-min);
}

.btn--lg {
  min-height: var(--tap-primary);
  font-size: var(--font-lg);
}

.btn--block {
  display: flex;
  width: 100%;
}

.btn--primary {
  background: var(--color-primary);
  color: var(--color-text);
}

.btn--secondary {
  background: var(--color-surface-alt);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn--ghost {
  background: transparent;
  color: var(--color-text-muted);
}

.btn--danger {
  background: var(--color-danger);
  color: var(--color-text-invert);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn:active:not(:disabled) {
  transform: scale(0.98);
}

.btn__spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: btn-spin 0.7s linear infinite;
}

@keyframes btn-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
