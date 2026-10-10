<script setup lang="ts">
/**
 * BaseEmpty —— 空态（可带操作插槽）。
 *
 * ⚠️ `icon` 是 emoji 占位插画，因此**必须**满足视觉规范 3.2 的两条：
 *   ① 包在**固定尺寸的圆形容器**里（否则各平台字号/行高不同，视觉尺寸会飘）；
 *   ② 旁边必有**文字标题**（emoji 绝不能是唯一信息来源）。
 * 这里的 `title` 恒有文案，容器固定 96px 圆形 —— 两条都落在组件内部，
 * 调用方换 emoji 也不会破坏一致性。
 */
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    icon?: string;
  }>(),
  { title: '暂无内容', description: '', icon: '🐰' },
);
</script>

<template>
  <div class="empty">
    <span class="empty__badge" aria-hidden="true">
      <span class="empty__icon">{{ icon }}</span>
    </span>
    <p class="empty__title">{{ title }}</p>
    <p v-if="description" class="empty__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-2xl) var(--space-md);
  text-align: center;
}

/* 固定尺寸的圆形容器：emoji 占位插画的视觉尺寸才稳定（规范 3.2） */
.empty__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--color-surface-alt);
}

.empty__icon {
  font-size: 44px;
  line-height: 1;
}

.empty__title {
  font-size: var(--font-lg);
  font-weight: 600;
}

.empty__desc {
  color: var(--color-text-muted);
  max-width: 32ch;
}

.empty__action {
  margin-top: var(--space-sm);
}
</style>
