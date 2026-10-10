<script setup lang="ts">
/**
 * TabBar —— 手机端底部导航（4–5 项）。
 * 底部安全区：padding-bottom: env(safe-area-inset-bottom)（由 .app-shell__nav + 本文件共同处理）。
 *
 * ⚠️ 条目观感复用 `.navlink`（见 styles/components.css），与 SideNav 同一套：
 * 未选中灰、当前蓝底、胶囊圆角、热区 56px。本文件只处理底栏自身的排布。
 */
import { RouterLink, useRoute } from 'vue-router';

import { TAB_BAR_ITEMS } from '@/utils/nav';

const route = useRoute();

const items = TAB_BAR_ITEMS;

function isActive(path: string): boolean {
  return path === '/' ? route.path === '/' : route.path.startsWith(path);
}
</script>

<template>
  <nav class="tabbar" aria-label="主导航">
    <ul class="tabbar__list">
      <li v-for="item in items" :key="item.name" class="tabbar__item">
        <RouterLink
          class="tabbar__link navlink clickable"
          :class="{ 'navlink--active': isActive(item.path) }"
          :to="item.path"
        >
          <svg class="navlink__icon" aria-hidden="true">
            <use :href="`/icons.svg#${item.icon}`" />
          </svg>
          <span class="tabbar__label">{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.tabbar {
  position: sticky;
  bottom: 0;
  z-index: var(--z-nav);
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  padding-bottom: var(--safe-bottom);
}

.tabbar__list {
  display: flex;
  align-items: stretch;
}

.tabbar__item {
  flex: 1 1 0;
  min-width: 0;
}

.tabbar__link {
  /* 底栏排布：图标在上、文字在下 */
  flex-direction: column;
  gap: 2px;
  padding: var(--space-xs) 2px;
  font-size: var(--font-xs);
}

.tabbar__label {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
