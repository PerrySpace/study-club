<script setup lang="ts">
/** BaseModal —— 通用确认弹窗（状态在 ui store，非业务 store）。 */
import BaseButton from '@/components/base/BaseButton.vue';
import { useUiStore } from '@/stores/ui';

const ui = useUiStore();
</script>

<template>
  <Transition name="modal">
    <div
      v-if="ui.modal.open"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="ui.modal.title"
    >
      <div class="modal__backdrop" @click="ui.closeModal()" />
      <div class="modal__panel">
        <h2 class="modal__title">{{ ui.modal.title }}</h2>
        <p class="modal__message selectable">{{ ui.modal.message }}</p>
        <div class="modal__actions">
          <BaseButton variant="secondary" @click="ui.closeModal()">知道了</BaseButton>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: grid;
  place-items: center;
  padding: var(--space-md);
}

.modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(44, 44, 42, 0.42);
}

.modal__panel {
  position: relative;
  width: min(100%, 420px);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.modal__title {
  font-size: var(--font-lg);
  font-weight: 700;
}

.modal__message {
  color: var(--color-text-muted);
  white-space: pre-wrap;
}

.modal__actions {
  display: flex;
  justify-content: flex-end;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 160ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
