<script setup lang="ts">
/**
 * GlyphFigure —— 字源图（图 / emoji 二态渲染）。
 *
 * ⛔ **图片加载失败必须显示占位，而不是空白。**
 * 「看图选字」的题干主图就是它 —— 图一挂，整道题变成「选一个看不见的字」，
 * 孩子只能瞎猜。这是外链图片的固有风险（素材中心的上传图同理），
 * 所以这里用 `@error` 兜住：占位块上写清「图没加载出来」，
 * 并保留 `alt`，让家长知道是内容问题而不是题目坏了。
 *
 * 用它而不是各写一遍：`glyph` 有三种形态（外链 / 素材 id / emoji），
 * 两个渲染点各自 if-else 一定会漏 —— 历史上就是这么漏的。
 */
import { computed, ref, watch } from 'vue';

import { resolveGlyph } from '@/utils/glyph';

const props = withDefaults(
  defineProps<{
    /** `character.glyph` 原始值 */
    glyph: string | null | undefined;
    /** 图片尺寸（px），emoji 用 `fontSize` 缩放 */
    size?: number;
    /** 图片加载失败时的提示文案 */
    alt?: string;
    /** 说明文字（图注），有值时显示在下方 */
    caption?: string | null;
    /** 下方图注的说明（字理解释） */
    note?: string | null;
  }>(),
  {
    size: 64,
    alt: '字源图',
    caption: null,
    note: null,
  },
);

const resolved = computed(() => resolveGlyph(props.glyph));
const failed = ref(false);

// 换字时重置失败态：否则上一张图的失败会连带把下一张也显示成占位。
watch(
  () => props.glyph,
  () => {
    failed.value = false;
  },
);
</script>

<template>
  <figure v-if="resolved" class="glyph-figure">
    <!-- 图片 -->
    <img
      v-if="resolved.kind === 'image' && !failed"
      class="glyph-figure__image"
      :src="resolved.src"
      :alt="alt"
      :style="{ width: `${size}px`, height: `${size}px` }"
      loading="lazy"
      @error="failed = true"
    />
    <!-- 占位：图挂了要说清楚，不能留白 -->
    <span
      v-else-if="resolved.kind === 'image'"
      class="glyph-figure__broken"
      :style="{ width: `${size}px`, height: `${size}px` }"
      role="img"
      :aria-label="`${alt}（未加载）`"
    >
      图未加载
    </span>
    <!-- emoji -->
    <span
      v-else
      class="glyph-figure__emoji"
      :style="{ fontSize: `${Math.round(size * 0.8)}px` }"
      aria-hidden="true"
      >{{ resolved.text }}</span
    >

    <figcaption v-if="caption || note" class="glyph-figure__caption">
      {{ caption || note }}
    </figcaption>
  </figure>
</template>

<style scoped>
.glyph-figure {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2xs);
  margin: 0;
}

.glyph-figure__image {
  object-fit: contain;
  border-radius: var(--radius-md);
}

.glyph-figure__emoji {
  line-height: 1;
}

/*
 * 占位用虚线框 + 浅灰底：一眼看出「这里本该有图」，
 * 而不是以为题目本身就没有图。
 */
.glyph-figure__broken {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}

.glyph-figure__caption {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  text-align: center;
  line-height: 1.6;
}
</style>