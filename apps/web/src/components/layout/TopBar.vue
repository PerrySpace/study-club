<script setup lang="ts">
/**
 * TopBar —— 顶部栏（三档共用）。
 *  - 手机：仅返回 + 标题（主要操作在下 1/3，02-2 §六）
 *  - iPad+：额外把「多档案快切」提升到一级（X-04，家庭共用场景）
 *  - 顶部安全区（刘海/灵动岛）由 padding-top: env(safe-area-inset-top) 处理
 */
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import ProfileSwitcher from '@/components/biz/ProfileSwitcher.vue';
import { useBreakpoint } from '@/composables/useBreakpoint';

const route = useRoute();
const router = useRouter();
const { isPhone } = useBreakpoint();

const title = computed(() => route.meta.title ?? '学习俱乐部');
const showBack = computed(() => route.name !== 'home' && route.name !== 'onboarding');
const showSwitcher = computed(() => !isPhone.value && route.name !== 'onboarding');

function goBack(): void {
  if (window.history.length > 1) router.back();
  else router.push({ name: 'home' });
}
</script>

<template>
  <header class="topbar">
    <div class="topbar__inner">
      <button
        v-if="showBack"
        type="button"
        class="topbar__back tap clickable"
        aria-label="返回"
        @click="goBack"
      >
        <svg class="topbar__icon" aria-hidden="true"><use href="/icons.svg#i-back" /></svg>
      </button>
      <h1 v-else class="topbar__brand">
        <span class="topbar__brand-mark" aria-hidden="true">🐰</span>
        <span class="topbar__brand-text">学习俱乐部</span>
      </h1>

      <p v-if="showBack" class="topbar__title">{{ title }}</p>

      <div class="topbar__actions">
        <ProfileSwitcher v-if="showSwitcher" />
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: var(--z-topbar);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding-top: var(--safe-top);
}

.topbar__inner {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-height: var(--topbar-height);
  max-width: var(--content-max);
  margin-inline: auto;
  padding-inline: var(--space-md);
}

.topbar__back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  min-height: 44px;
  border-radius: var(--radius-pill);
}

.topbar__icon {
  width: 24px;
  height: 24px;
  color: var(--color-text);
}

.topbar__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-lg);
  font-weight: 700;
}

.topbar__brand-mark {
  font-size: var(--font-xl);
}

.topbar__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-lg);
  font-weight: 600;
}

.topbar__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

@media (max-width: 767px) {
  .topbar__brand-text {
    font-size: var(--font-md);
  }
}
</style>
