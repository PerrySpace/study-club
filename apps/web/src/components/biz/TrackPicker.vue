<script setup lang="ts">
/**
 * TrackPicker —— 学习地图首屏：三选一（识字 / 识字短文 / 古诗）。
 *
 * ## 为什么是「三块」而不是一条混合时间线
 * 孩子（尤其是不识字的孩子）没法判断「该学识字还是该读短文」——
 * 把三类内容混在一条线上，等于让他自己决策。分块之后每个块的**语义一目了然**：
 * 「我想认字」「我想读一小段」「我要学古诗」，认得字的大孩子则直接看块上的关卡数。
 *
 * 每块显示：插画 + 名称 + 「还剩几关」。⛔ 不显示「还剩几个字」——
 * 家长关心的是「还有多少关能玩」，字数是实现细节。
 *
 * 选好之后才进链路图：**先选方向，再看路**，避免一进地图就是一屏节点。
 */
import { computed } from 'vue';

const props = defineProps<{
  /** 三条线各自的关卡进度 */
  stats: Record<string, { total: number; done: number }>;
}>();

const emit = defineEmits<{
  (e: 'pick', track: 'literacy' | 'poem' | 'story'): void;
}>();

/**
 * 三块元数据。
 *
 * 顺序按「启蒙优先级」排：先识字（主线），再古诗（诵读），最后识字短文（阅读延伸）。
 * emoji 作为插画：与项目「象形 emoji 零素材成本」的既有决策一致，
 * 且**没有版权风险**；要更精细的插画时把 `art` 换成图片 URL 即可。
 */
const BLOCKS = [
  {
    key: 'literacy' as const,
    title: '识字',
    subtitle: '一个字一个字认',
    art: '📖',
    tint: '#dff0c8',
  },
  {
    key: 'poem' as const,
    title: '古诗',
    subtitle: '跟着念一念',
    art: '🏮',
    tint: '#fde8d0',
  },
  {
    key: 'story' as const,
    // 展示名是「识字短文」，但 track key / 集合名仍是 story / stories ——
    // 改 key 要动数据与接口，而这两条线的语义本就同源（认完字就读得下来的短文本）。
    title: '识字短文',
    subtitle: '读一小段话',
    art: '📄',
    tint: '#e0eefb',
  },
];

const cards = computed(() =>
  BLOCKS.map((b) => {
    const s = props.stats[b.key] ?? { total: 0, done: 0 };
    const remain = Math.max(0, s.total - s.done);
    return {
      ...b,
      total: s.total,
      done: s.done,
      remain,
      // 全空时禁用而不是隐藏：用户会以为功能坏了。
      // 提示写明「还没内容」，让运营知道该去导入。
      empty: s.total === 0,
    };
  }),
);
</script>

<template>
  <ul class="track-picker" role="list">
    <li v-for="c in cards" :key="c.key" class="track-picker__item">
      <button
        type="button"
        class="track-picker__card tap clickable"
        :class="{ 'track-picker__card--empty': c.empty }"
        :style="{ '--tint': c.tint }"
        :disabled="c.empty"
        :aria-label="
          c.empty ? `${c.title}：内容还没有准备好` : `${c.title}：${c.subtitle}，还剩 ${c.remain} 关`
        "
        @click="emit('pick', c.key)"
      >
        <span class="track-picker__art" aria-hidden="true">{{ c.art }}</span>
        <span class="track-picker__body">
          <span class="track-picker__title">{{ c.title }}</span>
          <span class="track-picker__sub">{{ c.subtitle }}</span>
          <span v-if="c.empty" class="track-picker__meta">内容还在准备中</span>
          <span v-else class="track-picker__meta">
            <template v-if="c.done >= c.total">全部 {{ c.total }} 关已学完</template>
            <template v-else>还剩 {{ c.remain }} 关 · 共 {{ c.total }} 关</template>
          </span>
        </span>
        <span v-if="!c.empty" class="track-picker__go" aria-hidden="true">›</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.track-picker {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-md);
  margin: 0;
  padding: 0;
  list-style: none;
}

.track-picker__item {
  display: flex;
}

/**
 * 卡片是一整块可点的区域。
 *
 * ⛔ 不用「图标 + 文字两行左对齐」的传统列表：孩子扫一眼要靠文字识别，
 *    而大插画 + 大标题让他**不看字就知道这块是什么**。
 */
.track-picker__card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  width: 100%;
  min-height: 108px;
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  /* 每块一个底色：与后面链路图的绿/蓝/暖色调呼应 */
  background: var(--tint, var(--color-surface-alt));
  border: 1px solid var(--color-border);
  text-align: left;
  transition: transform 120ms ease-out;
}

.track-picker__card:not(:disabled):active {
  transform: scale(0.98);
}

.track-picker__card--empty {
  opacity: 0.6;
  cursor: not-allowed;
}

.track-picker__art {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.72);
  font-size: 34px;
  line-height: 1;
}

.track-picker__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.track-picker__title {
  font-size: var(--font-xl);
  font-weight: 700;
  color: var(--color-text);
}

.track-picker__sub {
  font-size: var(--font-sm);
  color: var(--color-text-muted);
}

.track-picker__meta {
  margin-top: 2px;
  font-size: var(--font-xs);
  color: var(--color-text-muted);
}

/* 右侧箭头：暗示「点进去还有一层」，减少点下去的犹豫 */
.track-picker__go {
  flex: none;
  font-size: 26px;
  line-height: 1;
  color: var(--color-text-muted);
}
</style>
