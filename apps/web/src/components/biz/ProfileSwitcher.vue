<script setup lang="ts">
/**
 * ProfileSwitcher —— 多档案快切（I-03 / S-15 / X-04）。
 * iPad+ 断点下提升到顶栏一级；手机端收进设置页（由父级控制是否渲染）。
 * 所有数据读写走 core 的 child store → 仓储层。
 */
import { computed } from 'vue';
import { storeToRefs } from 'pinia';

import { useChildStore } from '@study-club/core';

import { useToast } from '@/composables/useToast';

const childStore = useChildStore();
const { children, current } = storeToRefs(childStore);
const toast = useToast();

const currentId = computed({
  get: () => childStore.currentId ?? '',
  set: (id: string) => {
    childStore.setCurrent(id);
    toast.show('已切换学习档案');
  },
});
</script>

<template>
  <div v-if="children.length" class="switcher">
    <label class="visually-hidden" for="profile-switcher">切换学习档案</label>
    <select id="profile-switcher" v-model="currentId" class="switcher__select tap clickable">
      <option v-for="child in children" :key="child._id" :value="child._id">
        {{ child.nickname }}
      </option>
    </select>
    <span class="switcher__badge" aria-hidden="true">{{ current?.nickname?.slice(0, 1) ?? '🙂' }}</span>
  </div>
</template>

<style scoped>
.switcher {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.switcher__select {
  padding: var(--space-xs) var(--space-lg) var(--space-xs) var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  font-size: var(--font-sm);
  appearance: none;
}

.switcher__badge {
  position: absolute;
  right: 6px;
  pointer-events: none;
  font-size: var(--font-md);
}
</style>
