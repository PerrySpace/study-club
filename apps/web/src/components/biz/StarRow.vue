<script setup lang="ts">
/**
 * StarRow —— 关卡星星（0–3 颗）。结果页、地图节点、古诗/故事页共用。
 *
 * ## 为什么自绘而不是用 ★ / emoji
 * ★（U+2605）在部分安卓与 Windows 字体里会被替换成彩色字形或宽度不一致的符号，
 * 而 emoji ⭐ 更是三端三个样。**星星是「我做得怎么样」的唯一反馈**，
 * 它的形状与颜色必须处处一致（规范 3.1：正式图形自绘）。
 *
 * ## 颜色语义
 * - 点亮：`--color-primary-strong`（金）—— 奖励语义，与「主色黄 = 可行动」同源但更饱和；
 * - 未点亮：`--color-border`（中性灰）—— ⛔ 未得到的星星**不能**用彩色描边，
 *   否则「灰的那颗」会被读成「另一种状态」，而不是「还没得到」（规范 2.2）。
 */
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    /** 点亮的颗数（0–3） */
    stars?: number;
    /** 总颗数（默认 3） */
    total?: number;
    /** 单颗边长（px） */
    size?: number;
    /** 是否做逐颗点亮的入场动画（prefers-reduced-motion 时由调用方关闭） */
    animated?: boolean;
    /** 给读屏的说明；缺省自动生成 */
    label?: string;
  }>(),
  { stars: 0, total: 3, size: 20, animated: true, label: '' },
);

/** 五角星路径（24 视窗，圆角收尖，避免儿童界面出现锐角 —— 规范 1.2）。 */
const STAR_PATH =
  'M12 3.2l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17.3l-5.4 2.8 1-6.1L3.2 9.7l6.1-.9z';

const filled = computed(() => Math.max(0, Math.min(props.total, Math.round(props.stars))));

const ariaLabel = computed(
  () => props.label || `获得 ${filled.value} 颗星，共 ${props.total} 颗`,
);
</script>

<template>
  <span class="star-row" role="img" :aria-label="ariaLabel">
    <svg
      v-for="i in total"
      :key="i"
      class="star-row__item"
      :class="{ 'star-row__item--on': i <= filled }"
      :style="{
        width: `${size}px`,
        height: `${size}px`,
        animationDelay: animated ? `${(i - 1) * 140}ms` : '0ms',
      }"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path :d="STAR_PATH" stroke-linejoin="round" stroke-linecap="round" />
    </svg>
  </span>
</template>

<style scoped>
.star-row {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  line-height: 0;
}

.star-row__item {
  flex: none;
  /* 未点亮：中性灰（没得到的部分），不用彩色描边 */
  fill: var(--color-border);
  stroke: var(--color-border);
  stroke-width: 1.4;
}

.star-row__item--on {
  fill: var(--color-primary-strong);
  stroke: var(--color-primary-strong);
  animation: star-pop 420ms ease-out backwards;
}

@keyframes star-pop {
  from {
    opacity: 0;
    transform: scale(0.4) rotate(-22deg);
  }
  to {
    opacity: 1;
    transform: scale(1) rotate(0);
  }
}

/* 关掉动效时直接呈现最终状态（规范 5.2） */
@media (prefers-reduced-motion: reduce) {
  .star-row__item--on {
    animation: none;
  }
}
</style>
