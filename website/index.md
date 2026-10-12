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
      text: 在线 Demo
      link: https://study.perryspace.club
    - theme: alt
      text: Gitee
      link: https://gitee.com/perry-space/study-club

features:
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
