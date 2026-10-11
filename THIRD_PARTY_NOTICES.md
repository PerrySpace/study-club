# 第三方声明

本仓库的**代码**以 [MIT](./LICENSE) 授权，**内容与文档**以 **CC BY-SA 4.0** 授权。

学习俱乐部（study-club）构建于众多开源项目之上。**下列第三方依赖与素材各自遵循其原始许可**（均非本项目所授权的 MIT / CC BY-SA 4.0）。本文件仅用于署名与合规说明，不改变各依赖自身的许可条款。

## 前端依赖（npm）

| 依赖 | 版本线 | 许可 | 说明 |
| --- | --- | --- | --- |
| [vue](https://github.com/vuejs/core) | 3 | MIT | 前端框架 |
| [vue-router](https://github.com/vuejs/router) | 4 | MIT | 路由 |
| [pinia](https://github.com/vuejs/pinia) | 2 | MIT | 状态管理 |
| [vite](https://github.com/vitejs/vite) | 5 | MIT | 构建与开发服务器 |
| [vite-plugin-pwa](https://github.com/vite-pwa/vite-plugin-pwa) | — | MIT | PWA 构建插件 |
| [workbox-window](https://github.com/GoogleChrome/workbox) | — | MIT | Service Worker 运行时 |
| [typescript](https://github.com/microsoft/TypeScript) | 5 | Apache-2.0 | 类型系统 |
| [@vitejs/plugin-vue](https://github.com/vitejs/vite-plugin-vue) | — | MIT | Vite 的 Vue 支持 |
| [vue-tsc](https://github.com/vuejs/language-tools) | — | MIT | Vue 类型检查 |
| [element-plus](https://github.com/element-plus/element-plus) | — | MIT | 管理后台 UI 组件库 |
| [@element-plus/icons-vue](https://github.com/element-plus/element-plus-icons) | — | MIT | Element Plus 图标集 |

> 若上表中某项许可与实际情况不符，**以该依赖自身 `LICENSE` 为准**。

## 后端依赖（Python）

| 依赖 | 版本线 | 许可 | 说明 |
| --- | --- | --- | --- |
| [fastapi](https://github.com/tiangolo/fastapi) | — | MIT | Web 框架 |
| [uvicorn](https://github.com/encode/uvicorn) | — | BSD-3-Clause | ASGI 服务器 |
| [motor](https://github.com/mongodb/motor) / [pymongo](https://github.com/mongodb/mongo-python-driver) | — | Apache-2.0 | 异步 / 同步 MongoDB 驱动 |
| [pydantic](https://github.com/pydantic/pydantic) | — | MIT | 数据校验与模型 |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | — | MIT | 配置管理 |
| [argon2-cffi](https://github.com/hynek/argon2-cffi) | — | MIT | Argon2id 口令哈希 |
| [pyjwt](https://github.com/jpadilla/pyjwt) | — | MIT | JWT 会话令牌 |
| [cryptography](https://github.com/pyca/cryptography) | — | Apache-2.0 OR BSD-3-Clause | Ed25519 邀请码验签等 |
| [python-multipart](https://github.com/Kludex/python-multipart) | — | Apache-2.0 | 后台素材上传（multipart/form-data） |

> 若上表中某项许可与实际情况不符，**以该依赖自身 `LICENSE` 为准**。

## 内容与素材来源

本项目的内容数据采用**内容即仓库**方式维护（详见 [`README.md`](./README.md) 与 [`CONTRIBUTING.md`](./CONTRIBUTING.md)）。每一份内容数据文件的**来源与许可**均登记于 **[`content/sources.json`](./content/sources.json)**，包括自编内容与第三方数据源（及其仓库地址、许可、用途）。

> ⛔ **未在 `content/sources.json` 中登记来源的素材不得入库。** 新增任何第三方素材（数据、配图、音频、字体等）前，必须先完成来源登记。

如需了解内容版权红线的完整判定标准，见 [`docs/01-产品规划/04-免费开放与开源策略.md`](./docs/01-产品规划/04-免费开放与开源策略.md)。
