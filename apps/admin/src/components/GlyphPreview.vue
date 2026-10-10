<script setup lang="ts">
/**
 * GlyphPreview —— 后台字源图预览（只读，不依赖客户端运行时）。
 *
 * ⛔ 为什么后台**必须**有预览：
 * 字源图有三种形态（emoji / 图片链接 / 素材 id），填错了在后台看不出来，
 * 要等运营发布、孩子做题时才发现「看图选字」的题干没图 —— 那时候已经
 * 影响真实学习了。预览把「填对没有」的成本从发布后挪到填表时。
 *
 * 只读外部图片：外链可能指向任何站点，后台不该主动加载。
 * 判定「外链」而不真发请求，因此不产生网络与隐私风险。
 */
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    glyph: string | null | undefined;
    size?: number;
  }>(),
  { size: 44 },
);

type Kind = 'empty' | 'asset' | 'image' | 'emoji';

const parsed = computed<{ kind: Kind; src?: string; text: string }>(() => {
  const value = (props.glyph ?? '').trim();
  if (!value) return { kind: 'empty', text: '' };
  // 站内素材 id：素材端点是公开的，图片可直接加载
  if (value.startsWith('as_')) return { kind: 'asset', src: `/api/v1/assets/${value}`, text: value };
  // 外链：只标出来，不主动加载
  if (/^https?:\/\//i.test(value)) return { kind: 'image', src: value, text: value };
  return { kind: 'emoji', text: value };
});

/** 外链与素材 id 的语义提示 —— 让运营知道自己填的是哪种。 */
const hint = computed(() => {
  switch (parsed.value.kind) {
    case 'asset':
      return '站内素材';
    case 'image':
      return '外链图片（客户端才会加载）';
    case 'emoji':
      return '文字 / emoji';
    default:
      return '';
  }
});
</script>

<template>
  <div class="glyph-preview">
    <div
      class="glyph-preview__box"
      :class="`glyph-preview__box--${parsed.kind}`"
      :style="{ width: `${size}px`, height: `${size}px` }"
    >
      <!-- 只有站内素材才真加载：外链不该由后台主动请求 -->
      <img
        v-if="parsed.kind === 'asset' && parsed.src"
        class="glyph-preview__img"
        :src="parsed.src"
        :alt="parsed.text"
      />
      <span
        v-else-if="parsed.kind === 'image'"
        class="glyph-preview__link"
        title="外链图片：后台不加载，发布后客户端才会请求"
        >链接</span
      >
      <span
        v-else-if="parsed.kind === 'emoji'"
        class="glyph-preview__text"
        :style="{ fontSize: `${Math.round(size * 0.72)}px` }"
        >{{ parsed.text }}</span
      >
      <span v-else class="glyph-preview__none">无</span>
    </div>
    <span v-if="hint" class="glyph-preview__hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.glyph-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.glyph-preview__box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}

.glyph-preview__img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.glyph-preview__text {
  line-height: 1;
}

/* 外链只做标识，不加载：外链可能指向任意站点 */
.glyph-preview__link {
  color: #909399;
  font-size: 12px;
}

.glyph-preview__none {
  color: #c0c4cc;
  font-size: 12px;
}

.glyph-preview__hint {
  color: #909399;
  font-size: 11px;
  white-space: nowrap;
}
</style>