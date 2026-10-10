<script setup lang="ts">
/**
 * AppShell —— 三档外壳（一份 DOM，靠 packages/tokens 的 .app-shell 栅格切换）：
 *   手机：顶部栏 + 内容 + 底部 TabBar
 *   iPad：左侧窄边栏 + 顶部栏 + 内容（双栏）
 *   桌面：左侧完整侧边栏 + 顶部栏 + 内容（三栏，内容区受 --content-max 约束）
 *
 * `oneScreen`：内容区锁在视口内、**整页不滚动**（学习页专用，见 styles/learn-screen.css）。
 * 普通页面保持「整页生长 + 整页滚动」的文档流 —— 报告页、设置页本来就该能往下翻。
 *
 * 平台差异（浏览器 API）只出现在 useBreakpoint → platform/breakpoint.ts。
 */
import { ref } from 'vue';

import BaseToast from '@/components/base/BaseToast.vue';
import { useBreakpoint } from '@/composables/useBreakpoint';

import SideNav from './SideNav.vue';
import TabBar from './TabBar.vue';
import TopBar from './TopBar.vue';

const props = withDefaults(defineProps<{ plain?: boolean; oneScreen?: boolean }>(), {
  plain: false,
  oneScreen: false,
});

const rootEl = ref<HTMLElement | null>(null);
const { useBottomNav } = useBreakpoint({ target: rootEl });
</script>

<template>
  <div
    ref="rootEl"
    class="app-shell"
    :class="{ 'app-shell--plain': props.plain, 'app-shell--one': props.oneScreen }"
  >
    <TopBar class="app-shell__topbar" />

    <TabBar v-if="!props.plain && useBottomNav" class="app-shell__nav" />
    <SideNav v-else-if="!props.plain" class="app-shell__nav" />

    <main class="app-shell__main">
      <slot />
    </main>

    <BaseToast />
  </div>
</template>
