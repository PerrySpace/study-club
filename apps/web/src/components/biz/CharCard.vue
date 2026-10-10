<script setup lang="ts">
/**
 * CharCard —— 字卡（业务组件）。
 * 三档差异化（02-2 §4.3）：手机满屏单字；iPad+ 与拼音/释义/组词/部首笔画同屏。
 *
 * 本轮加入**字源图**（`character.glyph`）：启蒙阶段靠"图"记字形，
 * 但为 500 个字配插图是巨大的素材工作量，而象形 emoji 天生就是那张图
 * （水 → 💧、山 → ⛰️），零上传、零版权风险。是否展示由后台玩法开关
 * （`gameplay.show_pictograph`）统一控制 —— 在这里读开关而不是让每个调用方传参，
 * 否则总有一处忘了传，表现就不一致。
 */
import { computed } from 'vue';

import { useSiteConfigStore } from '@study-club/core';
import type { Character } from '@study-club/core';

const props = withDefaults(
  defineProps<{
    character: Character;
    /** 是否展示释义/组词等细节（手机端可折叠） */
    detailed?: boolean;
    /** 展示拼音 */
    showPinyin?: boolean;
    /**
     * 「看一看」模式：**只留字形相关**（拼音 + 字 + 字源图）。
     *
     * 为什么需要：默认形态把拼音、字、图、部首、笔画、结构、释义、组词、例句
     * 9 块信息从上到下堆在一张卡里，手机上要滚两三屏。而「看一看」这一步的目标
     * 只是**记住字形**，其余信息在 LessonView 的右栏（与「听一听」观感一致地并排）。
     *
     * 不是删掉信息，而是换位置 —— 右栏那边一字没少。
     */
    studyCompact?: boolean;
  }>(),
  { detailed: true, showPinyin: true, studyCompact: false },
);

import GlyphFigure from '@/components/biz/GlyphFigure.vue';

const siteConfig = useSiteConfigStore();

const words = computed(() => props.character.words.slice(0, 4));
const sentences = computed(() => props.character.sentences.slice(0, 2));
/** 只在这两样都有的时候才占版面：开关开着，且这个字确实配了字形图。 */
const glyph = computed(() =>
  siteConfig.gameplay.show_pictograph && props.character.glyph ? props.character.glyph : null,
);
</script>

<template>
  <article class="char-card">
    <p v-if="showPinyin && character.pinyin" class="char-card__pinyin">{{ character.pinyin }}</p>
    <p class="char-card__glyph learning-surface" :aria-label="`汉字 ${character.char}`">
      {{ character.char }}
    </p>

    <figure v-if="glyph" class="char-card__pictograph">
      <GlyphFigure :glyph="glyph" :size="34" :alt="`${character.char} 的字源图`" />
    </figure>

    <!-- 紧凑模式下，部首/笔画/结构/释义/组词/例句都由右栏承载，这里只留字形 -->
    <dl v-if="detailed && !studyCompact" class="char-card__meta">
      <div class="char-card__meta-item">
        <dt>部首</dt>
        <dd>{{ character.radical }}</dd>
      </div>
      <div class="char-card__meta-item">
        <dt>笔画</dt>
        <dd>{{ character.stroke_count }}</dd>
      </div>
      <div class="char-card__meta-item">
        <dt>结构</dt>
        <dd>{{ character.structure }}</dd>
      </div>
    </dl>

    <p v-if="detailed && !studyCompact" class="char-card__meaning selectable">{{ character.meaning }}</p>

    <div v-if="detailed && !studyCompact && words.length" class="char-card__words">
      <span v-for="word in words" :key="word" class="char-card__word">{{ word }}</span>
    </div>

    <ul v-if="detailed && !studyCompact && sentences.length" class="char-card__sentences selectable">
      <li v-for="sentence in sentences" :key="sentence">{{ sentence }}</li>
    </ul>

    <slot />
  </article>
</template>

<style scoped>
.char-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  text-align: center;
}

.char-card__pinyin {
  font-size: var(--font-xl);
  color: var(--color-info);
  letter-spacing: 0.08em;
}

.char-card__glyph {
  font-size: var(--font-card-glyph);
  line-height: 1.05;
  font-weight: 500;
}

.char-card__meta {
  display: flex;
  gap: var(--space-md);
  justify-content: center;
  flex-wrap: wrap;
}

/* ---- 字源图：象形 emoji + 一句字理 ---- */
.char-card__pictograph {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
}

.char-card__pictograph-emoji {
  font-size: 34px;
  line-height: 1;
}

.char-card__pictograph-text {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  text-align: left;
}

.char-card__meta-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: var(--font-sm);
}

.char-card__meta-item dt {
  color: var(--color-text-muted);
}

.char-card__meta-item dd {
  margin: 0;
  font-weight: 600;
  font-size: var(--font-md);
}

.char-card__meaning {
  font-size: var(--font-body);
}

.char-card__words {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  justify-content: center;
}

.char-card__word {
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  font-size: var(--font-body);
}

.char-card__sentences {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}
</style>
