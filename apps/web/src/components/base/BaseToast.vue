<script setup lang="ts">
/** BaseToast —— 全局轻提示（顶部居中，避开顶部安全区）。 */
import { useUiStore } from '@/stores/ui';

const ui = useUiStore();
</script>

<template>
  <div class="toast-layer" aria-live="polite" aria-atomic="true">
    <TransitionGroup name="toast">
      <button
        v-for="toast in ui.toasts"
        :key="toast.id"
        type="button"
        class="toast"
        :class="`toast--${toast.level}`"
        @click="ui.dismissToast(toast.id)"
      >
        {{ toast.message }}
      </button>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-layer {
  position: fixed;
  top: calc(var(--safe-top) + var(--space-md));
  left: 50%;
  transform: translateX(-50%);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  align-items: center;
  pointer-events: none;
  width: min(100% - 2 * var(--space-md), 480px);
}

.toast {
  pointer-events: auto;
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-text);
  color: var(--color-text-invert);
  box-shadow: var(--shadow-md);
  font-size: var(--font-md);
  text-align: left;
}

.toast--success {
  background: var(--color-success);
}

.toast--warn {
  background: var(--color-warn);
}

.toast--error {
  background: var(--color-danger);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
