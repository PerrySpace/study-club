<script setup lang="ts">
/**
 * RegisterView —— 账号注册（用户名 / 手机号二选一 + 自设密码）。
 *
 * ⚠️ 恢复码**仅显示一次**，必须强制抄写确认（01-3 I-13）。
 * 邀请码退为**可选**字段，是否必填由能力开关 `enableInviteRequired` 决定。
 *
 * 实现说明（core 适配）：`authStore.register()` 会把恢复码一并返回，
 * 但本页需要在拿到账号态之后**先展示恢复码、再允许继续**，
 * 因此这里直接用 `ApiClient.register()` 取回完整结果，
 * 再通过 `auth.adoptSession()` 把账号与会话一次性回填到 core store。
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import { BizError, DEFAULT_AVATAR, useAuthStore, useChildStore, useSiteConfigStore } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import { copyText } from '@/platform';
import { usePlatform } from '@/composables/usePlatform';
import { useToast } from '@/composables/useToast';

const router = useRouter();
const auth = useAuthStore();
const childStore = useChildStore();
const siteConfig = useSiteConfigStore();
const { api } = usePlatform();
const toast = useToast();

const username = ref('');
const phone = ref('');
const inviteCode = ref('');
const passcode = ref('');
const passcode2 = ref('');
const displayName = ref('');
const submitting = ref(false);

const recoveryCode = ref<string | null>(null);
const copied = ref(false);
const confirmed = ref(false);

/** 邀请码是否必填：以服务端站点配置为准（后台可热改），未加载时回落构建期开关。 */
const inviteRequired = computed(() => siteConfig.inviteRequired);
/** 服务端可关闭注册（运营开关），此时前端直接给出说明而不是让人白填一遍。 */
const registrationOpen = computed(() => siteConfig.registrationOpen);

/** 与后端 auth_controller 的校验规则保持一致（前端只做即时提示，最终以后端为准）。 */
const USERNAME_RE = /^[A-Za-z][A-Za-z0-9_]{3,19}$/;
const PHONE_RE = /^1[3-9]\d{9}$/;

const usernameError = computed(() => {
  const v = username.value.trim();
  if (!v) return '';
  return USERNAME_RE.test(v) ? '' : '4–20 位，字母开头，仅含字母/数字/下划线';
});
const phoneError = computed(() => {
  const v = phone.value.trim();
  if (!v) return '';
  return PHONE_RE.test(v) ? '' : '请输入有效的 11 位手机号';
});

const hasIdentifier = computed(() => {
  const u = username.value.trim();
  const p = phone.value.trim();
  return (!!u && !usernameError.value) || (!!p && !phoneError.value);
});

const canSubmit = computed(
  () =>
    !submitting.value &&
    hasIdentifier.value &&
    displayName.value.trim().length > 0 &&
    passcode.value.length >= 6 &&
    passcode.value === passcode2.value &&
    (!inviteRequired.value || inviteCode.value.trim().length > 0),
);

async function submit(): Promise<void> {
  if (!hasIdentifier.value) {
    toast.warn('用户名与手机号请至少填写一个');
    return;
  }
  if (usernameError.value || phoneError.value) {
    toast.warn('用户名或手机号格式不正确');
    return;
  }
  if (passcode.value !== passcode2.value) {
    toast.warn('两次输入的密码不一致');
    return;
  }
  if (!api) {
    toast.error('云端后台未配置，请先联系管理员完成部署');
    return;
  }
  submitting.value = true;
  try {
    const res = await api.register({
      username: username.value.trim() || null,
      phone: phone.value.trim() || null,
      invite_code: inviteCode.value.trim() || null,
      passcode: passcode.value,
      display_name: displayName.value.trim(),
      // 注册阶段先给默认头像；具体伙伴在引导页/设置页里挑。
      avatar_key: DEFAULT_AVATAR,
    });

    // 一次性回填会话与账号：Token 挂载、持久化、store 更新都在这里完成。
    auth.adoptSession({ account: res.account, tokens: res.tokens });

    recoveryCode.value = res.recovery_code;
    if (!res.recovery_code) {
      finish();
    }
  } catch (err) {
    if (err instanceof BizError) {
      // 字段级错误优先展示（如「用户名已被占用」）
      const first = err.fieldErrors?.[0]?.reason;
      toast.error(first || err.message);
    } else {
      toast.error('注册失败，请稍后重试');
    }
  } finally {
    submitting.value = false;
  }
}

async function copyRecovery(): Promise<void> {
  if (!recoveryCode.value) return;
  if (await copyText(recoveryCode.value)) {
    copied.value = true;
    toast.success('已复制到剪贴板');
  } else {
    toast.warn('复制失败，请手动抄写');
  }
}

function finish(): void {
  // 还没有档案就去引导页建第一个；守卫也会做同样的判断，这里只是避免多一次跳转闪烁。
  if (childStore.children.length) void router.replace({ name: 'home' });
  else void router.replace({ name: 'onboarding' });
}
</script>

<template>
  <section class="page form-page">
    <BaseCard v-if="!api" title="服务端未配置" subtitle="注册与登录都需要服务端支持">
      <p class="text-muted">
        当前构建未配置 <code>VITE_API_BASE_URL</code>，因此无法注册或登入。
        学习数据全部保存在服务端，请先联系管理员完成部署配置。
      </p>
      <template #footer>
        <BaseButton block @click="router.replace({ name: 'login' })">返回登入</BaseButton>
      </template>
    </BaseCard>

    <BaseCard v-else-if="!registrationOpen" title="注册暂未开放" subtitle="管理员已关闭新账号注册">
      <p class="text-muted">
        当前暂不开放注册。已有账号仍可正常登入；如需账号，请联系管理员。
      </p>
      <template #footer>
        <BaseButton block @click="router.replace({ name: 'login' })">返回登入</BaseButton>
      </template>
    </BaseCard>

    <template v-else-if="!recoveryCode">
      <BaseCard title="注册账号" subtitle="用户名或手机号 + 自设密码，二选一即可">
        <div class="stack">
          <label class="field">
            <span class="field__label">
              用户名
              <em class="field__optional">（与手机号至少填一个）</em>
            </span>
            <input
              v-model="username"
              class="field__input tap"
              type="text"
              inputmode="text"
              autocomplete="username"
              placeholder="4–20 位，字母开头"
            />
            <span v-if="usernameError" class="field__error">{{ usernameError }}</span>
          </label>

          <label class="field">
            <span class="field__label">手机号</span>
            <input
              v-model="phone"
              class="field__input tap"
              type="tel"
              inputmode="numeric"
              maxlength="11"
              autocomplete="tel"
              placeholder="选填，用于登录"
            />
            <span v-if="phoneError" class="field__error">{{ phoneError }}</span>
          </label>

          <label class="field">
            <span class="field__label">
              邀请码
              <em v-if="!inviteRequired" class="field__optional">（可选）</em>
            </span>
            <input
              v-model="inviteCode"
              class="field__input tap"
              type="text"
              inputmode="text"
              autocomplete="off"
              placeholder="请输入邀请码"
            />
          </label>

          <label class="field">
            <span class="field__label">昵称<span class="field__optional">（用于在设备上区分账号）</span></span>
            <input
              v-model="displayName"
              class="field__input tap"
              type="text"
              maxlength="12"
              autocomplete="off"
              placeholder="例如：小兔子家"
            />
          </label>

          <label class="field">
            <span class="field__label">设置密码（至少 6 位）</span>
            <input
              v-model="passcode"
              class="field__input tap"
              type="password"
              autocomplete="new-password"
              placeholder="忘记密码只能靠恢复码"
            />
          </label>

          <label class="field">
            <span class="field__label">再次输入密码</span>
            <input
              v-model="passcode2"
              class="field__input tap"
              type="password"
              autocomplete="new-password"
            />
          </label>
        </div>

        <template #footer>
          <BaseButton size="lg" block :disabled="!canSubmit" :loading="submitting" @click="submit">
            注册
          </BaseButton>
        </template>
      </BaseCard>
    </template>

    <BaseCard v-else title="请抄写你的恢复码" subtitle="仅显示这一次，关闭后无法再次查看">
      <div class="stack">
        <p class="recovery learning-surface">{{ recoveryCode }}</p>
        <BaseButton variant="secondary" block @click="copyRecovery">
          {{ copied ? '已复制' : '复制恢复码' }}
        </BaseButton>

        <label class="confirm tap">
          <input v-model="confirmed" type="checkbox" class="confirm__box" />
          <span>我已把恢复码抄写在安全的地方</span>
        </label>

        <p class="text-sm text-muted">
          忘记密码时，只能凭这串恢复码重置。它不会上传到任何服务器，我们也无法帮你找回。
        </p>
      </div>

      <template #footer>
        <BaseButton size="lg" block :disabled="!confirmed" @click="finish">我已抄好，继续</BaseButton>
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

.field__optional {
  font-style: normal;
  font-size: var(--font-xs);
}

.field__error {
  font-size: var(--font-xs);
  color: var(--color-danger, #e5484d);
}

.field__input {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.recovery {
  padding: var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  border: 1px dashed var(--color-border);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: var(--font-lg);
  letter-spacing: 0.14em;
  text-align: center;
  word-break: break-all;
}

.confirm {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.confirm__box {
  width: 24px;
  height: 24px;
}
</style>
