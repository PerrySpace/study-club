<script setup lang="ts">
/**
 * LoginView —— 账号（用户名 / 手机号）+ 密码登入。
 *
 * 统一账号入口，`identifier` 可填**用户名或手机号**；邀请码是注册页的字段（见 RegisterView）。
 * 没有「先不注册，直接使用」的出口 —— 身份一律由服务端签发。
 *
 * 「记住账号与密码」：勾选后把 identifier / passcode 存本机 localStorage 并回填。
 * 会话本身本来就会持久化（下次打开直接进学习页），这个选项只影响**登出之后**
 * 或换到登入页时要不要重新输一遍。密码明文只落在本机、不上传 —— 详见
 * platform/storage.ts 的 readLoginMemory 注释（含取舍说明）。
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { BizError, useAuthStore } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import { readLoginMemory, writeLoginMemory } from '@/platform';
import { usePlatform } from '@/composables/usePlatform';
import { useToast } from '@/composables/useToast';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { api } = usePlatform();
const toast = useToast();

const identifier = ref('');
const passcode = ref('');
const submitting = ref(false);
/** 记住账号与密码：默认开（家庭设备，省得每次重输）。 */
const remember = ref(true);

onMounted(() => {
  const saved = readLoginMemory();
  if (!saved) return;
  identifier.value = saved.identifier;
  passcode.value = saved.passcode;
  remember.value = true;
});

const canSubmit = computed(
  () => !submitting.value && identifier.value.trim().length > 0 && passcode.value.length > 0,
);

/** 注册入口可能因能力开关未注册；此时不渲染「去注册」，避免跳到不存在的路由。 */
const canRegister = computed(() => router.hasRoute('register'));

async function submit(): Promise<void> {
  if (!api) {
    toast.error('服务端未配置，无法登入');
    return;
  }
  submitting.value = true;
  try {
    await auth.login(identifier.value.trim(), passcode.value);
    // 成功才写记忆：输错了不该把错密码记下来
    writeLoginMemory(
      remember.value ? { identifier: identifier.value.trim(), passcode: passcode.value } : null,
    );
    toast.success('登入成功');
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '';
    await router.replace(redirect || { name: 'home' });
  } catch (err) {
    if (err instanceof BizError) {
      // 统一错误信息，不区分「账号不存在 / 密码错误」（防枚举，见 02-5 §四）。
      toast.error(err.message || '账号或密码不正确');
    } else {
      toast.error('登入失败，请检查网络后重试');
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="page form-page">
    <BaseCard title="登入" subtitle="使用注册时设置的用户名或手机号">
      <div class="stack">
        <label class="field">
          <span class="field__label">账号</span>
          <input
            v-model="identifier"
            class="field__input tap"
            type="text"
            name="username"
            autocomplete="username"
            autocapitalize="none"
            spellcheck="false"
            placeholder="用户名或手机号"
          />
        </label>

        <label class="field">
          <span class="field__label">密码</span>
          <input
            v-model="passcode"
            class="field__input tap"
            type="password"
            name="password"
            autocomplete="current-password"
            @keyup.enter="canSubmit && submit()"
          />
        </label>

        <!--
          「记住」用原生 checkbox：iOS / 安卓都有内建尺寸与无障碍语义，
          比自绘一个方块样式省事，也不会把触控目标做小。
        -->
        <label class="remember">
          <input v-model="remember" class="remember__box" type="checkbox" />
          <span class="remember__text">
            记住账号与密码
            <span class="remember__note">只存在本机浏览器，不上传；公共设备请勿勾选</span>
          </span>
        </label>

        <p class="notice text-sm">
          忘记密码只能靠注册时抄写的<strong>恢复码</strong>重置，我们无法帮你找回密码。
        </p>
      </div>

      <template #footer>
        <div class="stack--sm">
          <BaseButton size="lg" block :disabled="!canSubmit" :loading="submitting" @click="submit">
            登入
          </BaseButton>
          <BaseButton
            v-if="canRegister"
            variant="ghost"
            block
            @click="router.push({ name: 'register' })"
          >
            还没有账号？去注册
          </BaseButton>
        </div>
      </template>
    </BaseCard>
  </section>
</template>

<style scoped>
.page {
  padding-block: var(--space-lg);
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

.notice {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--color-warn) 14%, var(--color-surface));
  color: var(--color-text);
}

.remember {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  /* 整行可点：勾选框本身的触控目标太小，孩子/老人点不准 */
  min-height: var(--tap-min);
  padding-block: var(--space-xs);
  cursor: pointer;
}

.remember__box {
  /* 显式放大勾选框：默认 13px 在手机上基本点不到 */
  inline-size: 22px;
  block-size: 22px;
  margin: 0;
  flex: none;
  accent-color: var(--color-info);
}

.remember__text {
  display: flex;
  flex-direction: column;
  font-size: var(--font-body);
  line-height: 1.4;
}

.remember__note {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}
</style>
