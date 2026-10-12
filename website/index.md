---
layout: home

hero:
  name: 学习俱乐部
  text: 跟着课本学汉字
  tagline: 面向小学 1–6 年级的课内识字 + 古诗文启蒙应用；免费开放、开源、可自托管。
  image:
    src: /logo.svg
    alt: 学习俱乐部
  actions:
    - theme: brand
      text: 开始使用
      link: /docs/quick-start
    - theme: alt
      text: 界面导览
      link: /docs/tour
    - theme: alt
      text: 在线 Demo
      link: https://study.perryspace.club
    - theme: alt
      text: Gitee
      link: https://gitee.com/perry-space/study-club

features:
  - title: 一个账号，多个孩子
    details: 每个孩子一份独立档案与进度，随时切换、可归档；学情、复习、错题互不干扰，不必为孩子单独注册。
  - title: 三档响应式
    details: 手机（<768px）· iPad（768–1279px）· 桌面（≥1280px），一套 Web + PWA 代码覆盖三端，靠响应式区分。
  - title: 服务端权威
    details: 学习数据、儿童档案、进度与内容全部以服务端 MongoDB 为唯一真源，同账号跨设备一致。
  - title: 内容即仓库
    details: 内容以 content/**/*.json 维护并附带 JSON Schema，导入数据库后经接口下发 —— 改内容不必发版。
  - title: 邀请码身份
    details: 邀请码 + 自设密码完成注册登入，不需要手机号、不需要微信，也不需要企业主体。
  - title: 可自托管
    details: Docker Compose 分服务独立编排（mongo / api / web / admin），nginx 同源反代，单机即可维护。
  - title: 免费开放
    details: 无付费墙、无会员、无广告、无内购；代码 MIT，内容与文档 CC BY-SA 4.0。
---

## 孩子端一览

学 → 练 → 测 → 闯关，一条线走完；每个环节都有即时反馈。

<div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;margin:12px 0 4px;">
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-home.png" alt="今日任务" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">今日任务：新学 / 复习 / 重练</figcaption>
  </figure>
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-map.png" alt="学习地图" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">学习地图：识字 · 古诗 · 识字短文</figcaption>
  </figure>
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-card-learn.png" alt="字卡学习" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">字卡四步：看 · 听 · 读 · 写</figcaption>
  </figure>
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-card-write.png" alt="田字格描红" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">田字格描红，跟着笔顺写</figcaption>
  </figure>
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-quiz.png" alt="游戏化答题" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">游戏化答题（看图选字）</figcaption>
  </figure>
  <figure style="margin:0;width:190px;text-align:center;">
    <img src="/screenshots/web-lesson-done.png" alt="关卡完成" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">星级结算与多条出口</figcaption>
  </figure>
</div>

## 一个账号，多个孩子

家里不止一个娃？**一个账号可以放多个孩子的独立档案**：各自年级、头像、进度、复习与错题互不干扰，随时切换；不用了可以归档，不打扰当前学习的孩子。新建档案只需昵称 + 年级 + 头像。

<div style="display:flex;justify-content:center;margin:12px 0 4px;">
  <figure style="margin:0;width:240px;text-align:center;">
    <img src="/screenshots/web-children.png" alt="孩子档案：切换与归档" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">孩子档案：切换 · 归档 · 新建</figcaption>
  </figure>
</div>

## 管理后台

单管理员后台覆盖内容全生命周期：字库 / 古诗 / 识字短文 / 单元 / 关卡 / 徽章的增删改查与批量导入，站点配置（注册开关、年级体系）即时生效。

<div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;margin:12px 0 4px;">
  <figure style="margin:0;flex:1 1 460px;max-width:760px;text-align:center;">
    <img src="/screenshots/admin-overview.png" alt="管理端概览" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">概览：内容规模 · 邀请码 · 字库完成度 · 素材填充率</figcaption>
  </figure>
  <figure style="margin:0;flex:1 1 460px;max-width:760px;text-align:center;">
    <img src="/screenshots/admin-characters.png" alt="字库管理" loading="lazy" style="width:100%;border-radius:12px;border:1px solid var(--vp-c-divider);box-shadow:0 2px 12px rgba(0,0,0,.06);" />
    <figcaption style="font-size:13px;color:var(--vp-c-text-2);margin-top:6px;">字库：按年级筛选 · 批量导入导出 · 在线编辑</figcaption>
  </figure>
</div>

想看完整的走查（含注册、闯关地图、站点配置等全部 15 张截图）→ **[界面导览](/docs/tour)**。
