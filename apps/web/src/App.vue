<script setup lang="ts">
/**
 * App —— 承载三档外壳。外壳形态由路由 meta 决定（关卡/古诗/引导页用沉浸式外壳）。
 *
 * `oneScreen` 与 `plain` 是两件事，别合并：
 *   plain      → 有没有侧/底导航（视觉外壳）
 *   oneScreen  → 内容区是否锁在视口内、整页不滚动（布局契约，见 styles/learn-screen.css）
 */
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';

import BaseModal from '@/components/base/BaseModal.vue';
import AppShell from '@/components/layout/AppShell.vue';

const route = useRoute();
const plain = computed(() => route.meta.plain === true);
const oneScreen = computed(() => route.meta.oneScreen === true);
</script>

<template>
  <AppShell :plain="plain" :one-screen="oneScreen">
    <RouterView v-slot="{ Component }">
      <component :is="Component" />
    </RouterView>
  </AppShell>
  <BaseModal />
</template>
