import { createRouter, createWebHistory } from 'vue-router';

import AdminLayout from '@/layouts/AdminLayout.vue';
import { useSessionStore } from '@/stores/session';

declare module 'vue-router' {
  interface RouteMeta {
    /** 免登录访问（仅登录页） */
    public?: boolean;
    /** 顶栏与菜单显示的标题 */
    title?: string;
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '管理员登录' },
    },
    {
      path: '/',
      component: AdminLayout,
      children: [
        { path: '', redirect: '/overview' },
        {
          path: 'overview',
          name: 'overview',
          component: () => import('@/views/OverviewView.vue'),
          meta: { title: '概览' },
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UsersView.vue'),
          meta: { title: '用户' },
        },
        {
          path: 'invites',
          name: 'invites',
          component: () => import('@/views/InvitesView.vue'),
          meta: { title: '邀请码' },
        },
        {
          path: 'characters',
          name: 'characters',
          component: () => import('@/views/CharactersView.vue'),
          meta: { title: '字库' },
        },
        {
          path: 'poems',
          name: 'poems',
          component: () => import('@/views/PoemsView.vue'),
          meta: { title: '古诗' },
        },
        {
          path: 'stories',
          name: 'stories',
          component: () => import('@/views/StoriesView.vue'),
          meta: { title: '识字短文' },
        },
        {
          path: 'config',
          name: 'config',
          component: () => import('@/views/ConfigView.vue'),
          meta: { title: '站点配置' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/overview' },
  ],
});

router.beforeEach((to) => {
  const session = useSessionStore();
  if (!to.meta.public && !session.isAuthenticated) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } };
  }
  if (to.meta.public && session.isAuthenticated) {
    return { name: 'overview' };
  }
  return true;
});

export default router;
