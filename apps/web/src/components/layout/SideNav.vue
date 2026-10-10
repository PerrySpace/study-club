<script setup lang="ts">
/**
 * SideNav —— iPad（窄边栏，图标+小字）/ 桌面（完整侧边栏，图标+文字）左侧导航。
 * 由 tokens/responsive.css 的 --nav-width-rail / --nav-width-full 控制宽度。
 *
 * ⚠️ 条目观感**不在这里定义**：SideNav 与 TabBar 共用 `styles/components.css`
 * 里的 `.navlink`（胶囊圆角 / 未选中灰 / 当前蓝底 / 热区 56px）。
 * 本文件只负责**排布**（竖排图标+文字、窄栏居中），
 * 两处样式各写一份必然会长歪，这是上一次风格分裂的直接原因。
 */
import { RouterLink, useRoute } from 'vue-router';

import { NAV_ITEMS } from '@/utils/nav';

const route = useRoute();

const items = NAV_ITEMS;

function isActive(path: string): boolean {
  return path === '/' ? route.path === '/' : route.path.startsWith(path);
}
</script>

<template>
  <nav class="sidenav" aria-label="主导航">
    <ul class="sidenav__list">
      <li v-for="item in items" :key="item.name" class="sidenav__item">
        <RouterLink
          class="sidenav__link navlink clickable"
          :class="{ 'navlink--active': isActive(item.path) }"
          :to="item.path"
        >
          <svg class="navlink__icon" aria-hidden="true">
            <use :href="`/icons.svg#${item.icon}`" />
          </svg>
          <span class="sidenav__label">{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.sidenav {
  position: sticky;
  top: 0;
  align-self: start;
  height: 100dvh;
  z-index: var(--z-nav);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  padding: var(--space-md) var(--space-sm);
  overflow-y: auto;
}

.sidenav__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.sidenav__link {
  /* 排布：图标在前、文字在后（桌面）；观感统一由 .navlink 负责 */
  justify-content: flex-start;
  font-size: var(--font-md);
}

.sidenav__label {
  display: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* iPad 窄栏：图标居中 + 小字 */
@media (min-width: 768px) and (max-width: 1279px) {
  .sidenav__link {
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    font-size: var(--font-xs);
  }
  .sidenav__label {
    display: block;
  }
}

/* 桌面：完整侧边栏 */
@media (min-width: 1280px) {
  .sidenav__label {
    display: block;
  }
  .sidenav {
    padding-inline: var(--space-md);
  }
}
</style>
