import { defineConfig } from 'vitepress'

// 仓库地址：**主仓库在 Gitee**，GitHub 为镜像。
// 主仓库：https://gitee.com/perry-space/study-club
// 镜像仓库名与主仓库一致（study-club），故 .github/workflows/docs.yml 的 DOCS_BASE 保持 /study-club/。
const REPO = 'https://gitee.com/perry-space/study-club'
const REPO_MIRROR = 'https://github.com/PerrySpace/study-club'
const DEMO = 'https://study.perryspace.club'
const SITE = 'https://perryspace.github.io/study-club/'

export default defineConfig({
  title: '学习俱乐部',
  titleTemplate: ':title — 学习俱乐部',
  description:
    '跟着课本学汉字 —— 面向小学 1–6 年级的课内识字与古诗文启蒙应用，免费开放、开源、可自托管。',

  // 部署子路径：GitHub Pages 项目站点为 /<repo>/，本地与根路径部署保持 '/'。
  base: process.env.DOCS_BASE ?? '/',
  cleanUrls: true,

  // 固定浅色主题：VitePress 无 'force-light'，false = 不启用暗色、隐藏主题切换。
  appearance: false,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#f4b942' }],
    // 社交分享卡片：链接被转发到微信 / 微博 / X 等平台时用于生成摘要。
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: '学习俱乐部 — 跟着课本学汉字' }],
    [
      'meta',
      {
        property: 'og:description',
        content:
          '面向小学 1–6 年级的课内识字与古诗文启蒙应用，免费开放、开源、可自托管。',
      },
    ],
    ['meta', { property: 'og:url', content: SITE }],
    ['meta', { name: 'twitter:card', content: 'summary' }],
  ],

  themeConfig: {
    logo: '/logo.svg',
    // GitHub 图标指向镜像仓库；主仓库（Gitee）见导航项。
    socialLinks: [{ icon: 'github', link: REPO_MIRROR }],

    locales: {
      root: {
        label: '中文',
        lang: 'zh-CN',
        themeConfig: {
          nav: [
            { text: '首页', link: '/' },
            { text: '文档', link: '/docs/what' },
            { text: '贡献', link: '/docs/contributing' },
            { text: 'Demo', link: DEMO },
            { text: 'Gitee', link: REPO },
          ],
          sidebar: {
            '/docs/': [
              {
                text: '介绍',
                items: [
                  { text: '学习俱乐部是什么', link: '/docs/what' },
                  { text: '快速开始', link: '/docs/quick-start' },
                ],
              },
              {
                text: '架构',
                items: [
                  { text: '总体架构', link: '/docs/architecture' },
                  { text: '存储与后端策略', link: '/docs/storage' },
                  { text: '邀请码身份与准入', link: '/docs/identity' },
                  { text: '多端适配', link: '/docs/responsive' },
                ],
              },
              {
                text: '数据与接口',
                items: [
                  { text: '数据设计', link: '/docs/data' },
                  { text: 'API 接口', link: '/docs/api' },
                ],
              },
              {
                text: '内容与部署',
                items: [
                  { text: '内容体系与创作', link: '/docs/content' },
                  { text: '自托管部署', link: '/docs/deploy' },
                ],
              },
              {
                text: '项目',
                items: [
                  { text: '路线图', link: '/docs/roadmap' },
                  { text: '贡献指南', link: '/docs/contributing' },
                  { text: '常见问题', link: '/docs/faq' },
                ],
              },
            ],
          },
        },
      },

      en: {
        label: 'English',
        lang: 'en-US',
        link: '/en/',
        themeConfig: {
          nav: [
            { text: 'Home', link: '/en/' },
            { text: 'Docs', link: '/en/docs/what' },
            { text: 'Demo', link: DEMO },
            { text: 'Gitee', link: REPO },
          ],
          sidebar: {
            '/en/docs/': [
              {
                text: 'Introduction',
                items: [{ text: 'What is it', link: '/en/docs/what' }],
              },
              {
                text: 'Getting Started',
                items: [{ text: 'Quick Start', link: '/en/docs/quick-start' }],
              },
              {
                text: 'Architecture',
                items: [{ text: 'Overview', link: '/en/docs/architecture' }],
              },
            ],
          },
        },
      },
    },
  },
})
