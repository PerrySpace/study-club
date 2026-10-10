/**
 * 导航项 —— TabBar（手机）与 SideNav（iPad / 桌面）共用同一份数据，
 * 保证「一份 DOM 结构、两种排布」不出现两套入口。
 *
 * 掩藏能力（账号/支付/小程序/App）在此**没有入口**：不是隐藏，而是不存在。
 */

import type { NavItem } from '@/types';

/**
 * 导航项清单。
 *
 * ⛔ 「读一读」已**整体下线**：导航项、/reading 路由、ReadingView、i-reading 图标
 * 与结果页的跳转按钮都已删除。阅读承接由地图的「故事」线承担（一关一个故事），
 * 阅读因此成为闯关链路里的一环，而不再是一条需要单独入口的支路。
 */
export const NAV_ITEMS: NavItem[] = [
  { name: 'home', path: '/', label: '今日', icon: 'i-home', inTabBar: true },
  { name: 'map', path: '/map', label: '学习地图', icon: 'i-map', inTabBar: true },
  { name: 'review', path: '/review', label: '复习', icon: 'i-review', inTabBar: true },
  {
    name: 'wrong',
    path: '/wrong',
    label: '错题本',
    icon: 'i-wrong',
    // 移出手机底栏（仍保留在 iPad/桌面侧栏）：
    // 底栏最多 5 项，错题本另有两个入口（首页卡片、关卡结果页），不会找不到。
    inTabBar: false,
  },
  { name: 'report', path: '/report', label: '家长报告', icon: 'i-report', inTabBar: true },
  { name: 'settings', path: '/settings', label: '设置', icon: 'i-settings', inTabBar: true },
];

/** 手机底部 TabBar 项（限 5 项以内，02-2 §3.2）。 */
export const TAB_BAR_ITEMS: NavItem[] = NAV_ITEMS.filter((i) => i.inTabBar).slice(0, 5);
