# 快速开始

> 本文是面向用户与贡献者的导读，完整说明见仓库 [README · 快速开始](https://gitee.com/perry-space/study-club#快速开始本地测试)（Gitee）。

本地起全栈（内容 + 后端 + 前端）只需四条命令。首次运行按顺序执行：

```bash
cp .env.example .env          # 首次：生成环境变量（含端口与开关）
scripts/dev/bootstrap.sh      # 建目录、生成密钥、准备图标等（可选，一步到位）
scripts/dev/up-all.sh         # 按 db → api → web 顺序起全栈（各自独立编排）
scripts/seed/seed.sh          # 首次运行：导入内容与初始化数据（按表/功能拆分）
```

> 四个服务**各自独立编排**（`deploy/mongo`、`deploy/api`、`deploy/web`、`deploy/admin` 四份 compose），
> 均使用 `network_mode: host` —— 容器直接占用宿主端口，**不做端口映射**。
> `scripts/dev/up-all.sh` 只是按依赖顺序依次调用它们，不改变「可单独构建」的设计。

## 前置要求

| 依赖 | 版本 |
| --- | --- |
| Node.js | ≥ 20 |
| pnpm | 9.12.0 |
| Python | 3.12 |
| Docker | Docker + Docker Compose |

## 访问地址

| 用途 | 地址 | 端口来源 |
| --- | --- | --- |
| **学生端 / 家长端（主要入口）** | `http://localhost:8080/` | `WEB_PORT` |
| 局域网设备（手机 / iPad 同 WiFi） | `http://<宿主局域网 IP>:8080/` | `WEB_PORT` |
| 管理后台（单管理员，内部工具） | `http://localhost:8081/` | `ADMIN_PORT` |
| 后端 API | `http://localhost:8000/api/v1` | `API_PORT` |
| 接口文档（Swagger） | `http://localhost:8000/docs` | `API_PORT` |
| 健康检查 | `http://localhost:8000/api/v1/health` | `API_PORT` |
| MongoDB | `mongodb://localhost:27017/study_club` | `MONGO_PORT` |

## 管理后台（可选，内部工具）

管理后台**不在 `up-all.sh` 的默认链路里**，建议按需启动。使用前须先在 `.env` 配置管理员密码：

```bash
scripts/api/hash-password.sh  # 交互式生成 Argon2id 密码哈希 → 填入 .env
scripts/api/restart.sh        # 让 api 读到新哈希
scripts/admin/up.sh           # 起后台 → http://localhost:8081/
```

> ⚠️ **哈希那一行的单引号不能去掉**：Argon2 哈希含大量 `$`，Docker Compose 的 dotenv
> 解析未加引号的值时会把 `$m`、`$xxxx` 当变量引用替换成空串，导致
> 「密码明明对，却一直返回 `40301 管理员密码不正确`」。
>
> ⚠️ 管理后台是**单人使用的内部工具**，**不要暴露到公网**；不用时 `scripts/admin/down.sh` 关掉即可。

## 常用运维脚本

```
scripts/
├── lib/common.sh      # 公共函数（日志 / 路径 / 环境加载）
├── db/                # start stop reset backup restore shell logs init-indexes
├── api/               # build up down logs restart hash-password gen-invite-keys issue-invites
├── web/               # dev build up down logs
├── admin/             # dev build up down logs（管理后台，建议按需启动）
├── seed/              # seed.sh + data/*.json（每张表/每个功能一个文件）
├── content/           # 内容构建、Schema 校验、清单生成
└── dev/               # up-all / down-all / status / bootstrap
```

- 一键停全栈：`scripts/dev/down-all.sh`
- 查看状态：`scripts/dev/status.sh`
- 只跑前端 dev server（不起容器）：`scripts/web/dev.sh` → `http://<局域网 IP>:5173/`

## 局域网设备测试

手机 / iPad 与电脑连同一 WiFi 后访问 `http://<宿主局域网 IP>:8080/`。

查本机局域网 IP：

```bash
ipconfig getifaddr en0        # macOS Wi-Fi；有线为 en1 或 bridge0
```

> ⚠️ 手机连不上时按顺序检查：① 是否同一 WiFi；② 容器是否 `network_mode: host`
> （host 网络下服务监听 `0.0.0.0`，无需额外绑定）；③ 系统防火墙是否放行。

## 下一步

- 系统怎么搭 → [总体架构](./architecture.md)
- 数据存哪、后端做什么 → [存储与后端策略](./storage.md)
- 注册登入怎么做 → [邀请码身份与准入](./identity.md)
