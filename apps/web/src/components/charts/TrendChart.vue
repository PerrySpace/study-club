<script setup lang="ts">
/**
 * TrendChart —— 近 7 天学习趋势。
 * **不引第三方图表库**：内联 SVG 手写折线（首屏 JS 预算 <150KB，见 06-1 §八）。
 */
import { computed } from 'vue';

import type { LearningOverview } from '@study-club/core';

const props = defineProps<{ points: LearningOverview['trend'] }>();

const WIDTH = 320;
const HEIGHT = 140;
const PAD = { top: 16, right: 12, bottom: 28, left: 28 };

const plot = computed(() => ({
  w: WIDTH - PAD.left - PAD.right,
  h: HEIGHT - PAD.top - PAD.bottom,
}));

const maxValue = computed(() => {
  const values = props.points.map((p) => p.learned);
  return Math.max(1, ...values);
});

function x(index: number): number {
  const count = Math.max(1, props.points.length - 1);
  return PAD.left + (plot.value.w * index) / count;
}

function y(value: number): number {
  return PAD.top + plot.value.h * (1 - value / maxValue.value);
}

const linePath = computed(() =>
  props.points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.learned)}`).join(' '),
);

const areaPath = computed(() => {
  if (!props.points.length) return '';
  const startX = x(0);
  const endX = x(props.points.length - 1);
  const baseY = PAD.top + plot.value.h;
  return `${linePath.value} L${endX},${baseY} L${startX},${baseY} Z`;
});

const labels = computed(() =>
  props.points.map((p) => ({
    x: x(props.points.indexOf(p)),
    text: p.date.slice(5).replace('-', '/'),
  })),
);
</script>

<template>
  <figure class="chart">
    <svg
      class="chart__svg"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      aria-label="近 7 天每日接触字数趋势"
    >
      <line
        :x1="PAD.left"
        :y1="PAD.top + plot.h"
        :x2="WIDTH - PAD.right"
        :y2="PAD.top + plot.h"
        stroke="var(--color-border)"
        stroke-width="1"
      />
      <path :d="areaPath" fill="var(--color-primary)" opacity="0.25" />
      <path :d="linePath" fill="none" stroke="var(--color-primary-strong)" stroke-width="2.5" />
      <circle
        v-for="(p, i) in points"
        :key="p.date"
        :cx="x(i)"
        :cy="y(p.learned)"
        r="3.5"
        fill="var(--color-surface)"
        stroke="var(--color-primary-strong)"
        stroke-width="2"
      />
      <text
        v-for="label in labels"
        :key="label.text"
        :x="label.x"
        :y="HEIGHT - 8"
        text-anchor="middle"
        font-size="10"
        fill="var(--color-text-muted)"
      >
        {{ label.text }}
      </text>
    </svg>
    <figcaption class="chart__caption text-sm text-muted">
      每日接触字数（最多 {{ maxValue }} 字）
    </figcaption>
  </figure>
</template>

<style scoped>
.chart {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.chart__svg {
  width: 100%;
  height: auto;
}

.chart__caption {
  text-align: center;
}
</style>
