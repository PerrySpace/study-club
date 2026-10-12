<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { ApiError, FEATURE_DISABLED, NetworkError, API_BASE_URL } from '@/api/client';
import { useSessionStore } from '@/stores/session';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const password = ref('');
const loading = ref(false);
const errorMessage = ref('');

/** 后端未配置管理员密码时的排查提示（对应 FEATURE_DISABLED）。 */
const notConfigured =
  '后端未配置管理员密码：请在仓库根 .env 里设置 ADMIN_PASSWORD_HASH（用 scripts/api/hash-password.sh 生成），然后重启 api 容器。';

async function handleSubmit(): Promise<void> {
  errorMessage.value = '';
  const value = password.value.trim();
  if (!value) {
    errorMessage.value = '请输入管理员密码';
    return;
  }

  loading.value = true;
  try {
    await session.login(value);
    ElMessage.success('登录成功');
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/overview';
    await router.replace(redirect);
  } catch (err) {
    if (err instanceof ApiError) {
      errorMessage.value = err.code === FEATURE_DISABLED ? notConfigured : err.message;
    } else if (err instanceof NetworkError) {
      errorMessage.value = `${err.message}（当前接口地址：${API_BASE_URL}）`;
    } else {
      errorMessage.value = err instanceof Error ? err.message : '登录失败';
    }
  } finally {
    loading.value = false;
    password.value = '';
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <div class="login-head">
        <!-- 白卡上 logo 圆角外的透明区域露出卡片本身，视觉上就是一个纯图形 -->
        <img class="login-logo" src="/logo-mark.png" alt="study-club" />
        <h1>study-club</h1>
        <p>内容后台 · 单管理员</p>
      </div>

      <el-form @submit.prevent="handleSubmit">
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            size="large"
            placeholder="请输入管理员密码"
            show-password
            autofocus
            :disabled="loading"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-alert
          v-if="errorMessage"
          class="login-alert"
          type="error"
          :closable="false"
          show-icon
          :title="errorMessage"
        />

        <el-button
          class="login-submit"
          type="primary"
          size="large"
          :loading="loading"
          native-type="submit"
        >
          登录
        </el-button>
      </el-form>

      <p class="login-foot mono">{{ API_BASE_URL }}</p>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: linear-gradient(160deg, #1f2d3d 0%, #2c3e50 55%, #3a4a5c 100%);
}

.login-card {
  width: 380px;
  padding: 8px 4px;
  border: none;
  border-radius: 10px;
}

.login-head {
  margin-bottom: 20px;
  text-align: center;
}

.login-head h1 {
  margin: 0;
  font-size: 20px;
  letter-spacing: 0.5px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin-bottom: 12px;
}

.login-head p {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}

.login-alert {
  margin-bottom: 16px;
}

.login-submit {
  width: 100%;
}

.login-foot {
  margin: 18px 0 0;
  color: #c0c4cc;
  text-align: center;
  word-break: break-all;
}
</style>
