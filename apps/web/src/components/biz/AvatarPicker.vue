<script setup lang="ts">
/**
 * AvatarPicker —— 学习伙伴头像选择。
 *
 * 规则（与 core 的 DEFAULT_AVATAR 一致）：**没选过就是兔子**；选过则沿用。
 * 动物头像用本地 SVG（`public/avatars/<key>.svg`），不依赖网络也不依赖后端。
 *
 * 关于「用户上传自己的图片」：core 的 `avatar_key` 已支持 `asset:<asset_id>` 形态、
 * 常量 `AVATAR_ASSET_PREFIX` / `customAvatarAssetId()` 也已就位，
 * 但用户侧上传接口尚未开放（现有素材上传接口属管理端，需 admin 权限），
 * 因此这里暂不渲染上传入口 —— 留一个死按钮比没有按钮更糟。
 */
import { AVATAR, avatarImagePath, avatarLabel } from '@study-club/core';

const props = withDefaults(defineProps<{ modelValue: string; size?: number }>(), { size: 56 });
const emit = defineEmits<{ 'update:modelValue': [string] }>();

const animals = Object.values(AVATAR);

const avatarSrc = avatarImagePath;

function pick(key: string): void {
  if (key !== props.modelValue) emit('update:modelValue', key);
}
</script>

<template>
  <div class="avatar-picker" :style="{ '--avatar-size': `${props.size}px` }">
    <button
      v-for="key in animals"
      :key="key"
      type="button"
      class="avatar-picker__item tap"
      :class="{ 'is-active': modelValue === key }"
      :aria-pressed="modelValue === key"
      :aria-label="`选择头像 ${avatarLabel(key)}`"
      @click="pick(key)"
    >
      <img :src="avatarSrc(key)" :alt="avatarLabel(key)" draggable="false" />
    </button>
  </div>
</template>

<style scoped>
.avatar-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--avatar-size), 1fr));
  gap: var(--space-sm);
}

.avatar-picker__item {
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  padding: var(--space-2xs);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.avatar-picker__item img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.avatar-picker__item.is-active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 22%, transparent);
}

.avatar-picker__item:active {
  transform: scale(0.94);
}
</style>
