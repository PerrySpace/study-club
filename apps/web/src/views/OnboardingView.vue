<script setup lang="ts">
/**
 * OnboardingView —— 登录后的第二步：建第一个孩子档案。
 *
 * ⚠️ 与旧版的差异：旧版这一页是「身份模式选择」（先不注册 / 邀请码注册），
 * 并承诺「先不注册永远可用」。存储口径改为「彻底服务端、必须先登录」后这条承诺已废止 ——
 * 能走到这一页的人一定已经登录了，所以这一页只剩一件事：建档案、选头像。
 *
 * 也不再有「稍后再说」：没有档案就没有可学习的主体，放行回首页只会立刻被守卫弹回来，
 * 反而绕成一个看起来像 bug 的死循环。需要的出口是「退出登录」。
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import { DEFAULT_AVATAR, useAuthStore, useChildStore } from '@study-club/core';
import { gradeOptions as gradeOptionsFromConfig } from '@/utils/format';

import AvatarPicker from '@/components/biz/AvatarPicker.vue';
import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import { useToast } from '@/composables/useToast';

const router = useRouter();
const auth = useAuthStore();
const childStore = useChildStore();
const toast = useToast();

const nickname = ref('');
const grade = ref(1);
// 头像默认沿用账号上次的选择，没选过才是兔子（与 core 的 resolveAvatarKey 同一口径）
const avatar = ref<string>(auth.account?.avatar_key || DEFAULT_AVATAR);
const submitting = ref(false);

// 年级下拉取自服务端下发的年级表（后台可任意增删），而不是写死的常量。
const gradeOptions = computed(() => gradeOptionsFromConfig());

async function createProfile(): Promise<void> {
  if (!nickname.value.trim()) {
    toast.warn('请先给孩子取个昵称');
    return;
  }
  submitting.value = true;
  try {
    await childStore.create({
      nickname: nickname.value.trim(),
      grade: grade.value,
      avatarKey: avatar.value,
    });
    toast.success('档案已创建，开始学习吧！');
    await router.replace({ name: 'home' });
  } catch (err) {
    toast.error(err instanceof Error ? err.message : '创建档案失败，请稍后重试');
  } finally {
    submitting.value = false;
  }
}

async function logout(): Promise<void> {
  await auth.logout();
  await router.replace({ name: 'login' });
}
</script>

<template>
  <section class="onboarding form-page form-page--wide">
    <header class="onboarding__hero">
      <p class="onboarding__logo" aria-hidden="true">🐰</p>
      <h1 class="onboarding__title">欢迎来到学习俱乐部</h1>
      <p class="onboarding__subtitle">小学识字 + 古诗文，进度保存到你的账号，换设备也能接着学。</p>
    </header>

    <BaseCard title="建立第一个孩子档案" subtitle="昵称、年级与头像仅用于推荐内容与界面展示">
      <div class="stack">
        <label class="field">
          <span class="field__label">孩子昵称</span>
          <input
            v-model="nickname"
            class="field__input tap"
            type="text"
            maxlength="12"
            placeholder="例如：小兔子"
            autocomplete="off"
          />
        </label>

        <label class="field">
          <span class="field__label">年级</span>
          <select v-model.number="grade" class="field__input tap">
            <option v-for="opt in gradeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>

        <div class="field">
          <span class="field__label">选个学习伙伴</span>
          <AvatarPicker v-model="avatar" :size="60" />
        </div>
      </div>

      <template #footer>
        <div class="stack--sm">
          <BaseButton size="lg" block :loading="submitting" @click="createProfile">
            创建并开始
          </BaseButton>
          <BaseButton variant="ghost" block @click="logout">换一个账号登录</BaseButton>
        </div>
      </template>
    </BaseCard>
  </section>
</template>

<style scoped>
.onboarding {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  padding-block: var(--space-lg);
}

.onboarding__hero {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.onboarding__logo {
  font-size: 56px;
}

.onboarding__title {
  font-size: var(--font-2xl);
  font-weight: 700;
}

.onboarding__subtitle {
  color: var(--color-text-muted);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.field__label {
  font-size: var(--font-sm);
  color: var(--color-text-muted);
}

.field__input {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
</style>
