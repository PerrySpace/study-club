<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';

import { API_BASE_URL } from '@/api/client';
import { useSessionStore } from '@/stores/session';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const title = computed(() => (route.meta.title as string | undefined) ?? '内容后台');

/** 构建期常量需显式绑到 setup 作用域，模板里才能直接引用。 */
const appVersion = __APP_VERSION__;

// 图标名取自 @element-plus/icons-vue 全量注册（main.ts 里 `app.component` 逐个注册），
// 因此必须用该包确实存在的导出名 —— 写错会在渲染时静默变成一片空白。
const menu = [
  { index: '/overview', label: '概览', icon: 'DataBoard' },
  { index: '/users', label: '用户', icon: 'User' },
  { index: '/invites', label: '邀请码', icon: 'Ticket' },
  { index: '/characters', label: '字库', icon: 'Collection' },
  { index: '/readings', label: '识字短文', icon: 'Document' },
  { index: '/poems', label: '古诗', icon: 'Notebook' },
  { index: '/config', label: '站点配置', icon: 'Setting' },
];

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确认退出管理后台？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    });
  } catch {
    return;
  }
  session.logout();
  await router.replace({ name: 'login' });
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside class="admin-aside" :width="'var(--admin-aside-width)'">
      <div class="brand">
        <span class="brand-dot" />
        <div>
          <strong>study-club</strong>
          <small>内容后台 · 单管理员</small>
        </div>
      </div>

      <el-menu :default-active="route.path" router class="admin-menu">
        <el-menu-item v-for="item in menu" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>

      <div class="aside-foot">
        <div class="mono">{{ API_BASE_URL }}</div>
        <div class="mono">v{{ appVersion }}</div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="admin-header">
        <span class="header-title">{{ title }}</span>
        <div class="header-actions">
          <el-tag size="small" type="warning" effect="plain">管理员</el-tag>
          <el-button text type="primary" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-shell {
  height: 100%;
}

.admin-aside {
  display: flex;
  flex-direction: column;
  background: #1f2d3d;
  color: #e6e8eb;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid rgb(255 255 255 / 8%);
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #67c23a;
  flex: none;
}

.brand strong {
  display: block;
  font-size: 14px;
}

.brand small {
  display: block;
  color: #9aa5b1;
  font-size: 11px;
}

.admin-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #c0c8d1;
  --el-menu-hover-bg-color: rgb(255 255 255 / 8%);
  --el-menu-active-color: #ffd76b;
}

.aside-foot {
  padding: 12px 16px;
  border-top: 1px solid rgb(255 255 255 / 8%);
  color: #6b7785;
  font-size: 11px;
  line-height: 1.8;
  word-break: break-all;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-main {
  padding: 20px;
  overflow: auto;
}
</style>
