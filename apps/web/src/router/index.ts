/**
 * 路由表 —— **由能力开关生成**（四道防线之①：关闭的能力「路由不注册」）。
 *
 * 本文件不写任何浏览器 API；能力开关从 core 的 CoreContext 读取。
 */

import {
  createRouter,
  createWebHistory,
} from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';

import { useCore } from '@study-club/core';
import type { FeatureFlags } from '@study-club/core';

import { installGuards } from './guards';

declare module 'vue-router' {
  interface RouteMeta {
    /** 文档标题后缀 */
    title?: string;
    /** 沉浸式外壳（隐藏底部/侧边导航：关卡、古诗、引导、注册页） */
    plain?: boolean;
    /**
     * 学习页「一屏」模式：内容区锁在视口内、整页不滚动（见 styles/learn-screen.css）。
     *
     * 只给**学习中**的页面（识字闯关 / 古诗 / 故事）：这几页的核心操作
     * （下一步 / 下一题 / 我念完啦）必须常驻屏幕内，不能被内容顶出去。
     * ⛔ 别给列表页（首页 / 地图 / 报告 / 设置）加 —— 它们本来就该能往下翻。
     */
    oneScreen?: boolean;
    /** 该路由对应的能力开关；关闭时**不注册**（含四道防线之①） */
    feature?: keyof FeatureFlags;
    /**
     * 是否需要登录。默认 `true`；只有登录/注册/引导页与 404 显式设为 `false`。
     * 存储口径已改为「彻底服务端、必须先登录」，所以默认值刻意选 `true` ——
     * 漏标注的后果是「多要一次登录」（可接受），而不是「漏出一整个未登录页面」（不可接受）。
     */
    requiresAuth?: boolean;
    /** 是否需要有孩子档案。默认 `true`；引导页需为 `false`，否则会绕成死循环。 */
    requiresChild?: boolean;
  }
}

/**
 * 全量路由定义（含被开关关闭者，注册时过滤）。
 *
 * ⚠️ `requiresAuth: false` 是白名单语义，只给三类页面：
 *   ① 登录/注册（不然没法登录）；② 引导页（登录后还没建档案时要去的地方，仍需登录）；
 *   ③ 404（路径写错时不该被弹去登录页，那样会掩盖真正的问题）。
 */
const ALL_ROUTES: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '今日学习' },
  },
  {
    path: '/map',
    name: 'map',
    component: () => import('@/views/MapView.vue'),
    meta: { title: '学习地图' },
  },
  {
    /**
     * ⛔ 已废弃：关卡不再挂在「单元」下（改为按 `track` 分线自动生成），
     * 这个路径只是**兼容旧深链**保留的 —— 外部可能已经分享过
     * `/map/u-g1-01` 这样的链接，直接删会 404。
     * MapView 会忽略 `unitId` 并落到首屏三选一。
     * 确认没有外部链接后再删。
     */
    path: '/map/:unitId',
    name: 'unit',
    component: () => import('@/views/MapView.vue'),
    meta: { title: '单元关卡' },
  },
  {
    path: '/lesson/:lessonId',
    name: 'lesson',
    component: () => import('@/views/LessonView.vue'),
    meta: { title: '字卡闯关', plain: true, oneScreen: true },
  },
  {
    path: '/poem/:poemId',
    name: 'poem',
    component: () => import('@/views/PoemView.vue'),
    meta: { title: '古诗学习', plain: true, oneScreen: true },
  },
  {
    /**
     * 故事关（地图「故事」线的落地页）。
     *
     * ⛔ 不能复用 `/lesson/:id`：故事关的 `character_ids` 装的是故事 id，
     * 进识字闯关页必然落到空状态。参数用故事 id 便于分享与刷新，
     * 关卡 id 由 query 的 `lesson` 携带（用于记完成流水）。
     */
    path: '/story/:storyId',
    name: 'story',
    component: () => import('@/views/StoryView.vue'),
    meta: { title: '故事阅读', plain: true, oneScreen: true },
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/views/ReviewView.vue'),
    meta: { title: '到期复习' },
  },
  {
    path: '/wrong',
    name: 'wrong',
    component: () => import('@/views/WrongBookView.vue'),
    meta: { title: '错题本' },
  },
  {
    path: '/report',
    name: 'report',
    component: () => import('@/views/ReportView.vue'),
    meta: { title: '家长报告' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置' },
  },
  {
    path: '/onboarding',
    name: 'onboarding',
    component: () => import('@/views/OnboardingView.vue'),
    // 已登录但还没建档案时来建档案：仍需登录，但不要求已有档案
    meta: { title: '欢迎', plain: true, requiresChild: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: {
      title: '邀请码注册',
      plain: true,
      feature: 'enableInviteAuth',
      requiresAuth: false,
      requiresChild: false,
    },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    // 登录页**不受能力开关控制**：既然「必须先登录」是硬前提，
    // 关掉登录入口等于把所有人挡在门外，那不是「掩藏能力」而是「产品不可用」。
    // 需要临时停止拉新时，关的是 `enableInviteAuth`（只影响注册路由）。
    meta: { title: '登入', plain: true, requiresAuth: false, requiresChild: false },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在', requiresAuth: false, requiresChild: false },
  },
];

/** 按能力开关过滤路由：关闭的能力其路由**不注册**（不是隐藏入口）。 */
export function buildRoutes(flags: FeatureFlags): RouteRecordRaw[] {
  return ALL_ROUTES.filter((route) => {
    const feature = route.meta?.feature;
    return feature ? flags[feature] : true;
  });
}

export function createAppRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: buildRoutes(useCore().flags),
    scrollBehavior: () => ({ top: 0 }),
  });
  installGuards(router);
  return router;
}
