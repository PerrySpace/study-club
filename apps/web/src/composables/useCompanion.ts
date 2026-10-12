/**
 * useCompanion —— 「学习伙伴」的当前设定（头像 + 名字）。
 *
 * 为什么单开一个 composable：伙伴出现在识字 / 古诗 / 故事**三个关卡页**、
 * 引导气泡、表扬词、跟读按钮里，共 10 处左右。若每处各自去 child store 取
 * `avatar_key`，必然出现「有的地方跟着孩子的选择、有的地方还是兔子」——
 * 而「各处不一致」正是 2026-10-11 用户报的「关卡提示头像没跟着我选的走」的形态。
 *
 * 取值顺序：当前孩子 → 账号（还没建档案时的兜底）→ 默认兔子。
 * 注意 `child.avatar_key` 在服务端创建档案时就已经落成「账号上次的选择或兔子」
 * （见 core `useChildStore.resolveAvatarKey`），所以正常情况下第一档就命中。
 */

import { computed, type ComputedRef } from 'vue';

import {
  avatarImagePath,
  avatarLabel,
  DEFAULT_AVATAR,
  useAuthStore,
  useChildStore,
} from '@study-club/core';

export interface Companion {
  /** 头像 key（如 `panda`） */
  avatarKey: ComputedRef<string>;
  /** 伙伴称呼（如「熊猫」），用于文案与气泡署名 */
  name: ComputedRef<string>;
  /** 头像图片路径 */
  imagePath: ComputedRef<string>;
}

export function useCompanion(): Companion {
  const childStore = useChildStore();
  const authStore = useAuthStore();

  const avatarKey = computed(
    () => childStore.current?.avatar_key || authStore.account?.avatar_key || DEFAULT_AVATAR,
  );

  return {
    avatarKey,
    name: computed(() => avatarLabel(avatarKey.value)),
    imagePath: computed(() => avatarImagePath(avatarKey.value)),
  };
}
