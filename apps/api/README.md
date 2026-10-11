# apps/api —— study-club 云端后台

Python 3.12 + FastAPI + MongoDB（motor 异步）。职责按 [docs/README.md](../../docs/README.md) 约束为**轻职责**：
内容读取、邀请码校验、匿名统计、可选端到端加密同步、反馈收集、单管理员内容与邀请码管理。

> **后端是增强，不是必需依赖**：前端不连后端时功能必须完整。因此所有接口都要能降级（内容落静态包、身份落本地、统计静默丢弃）。

## 一、接口概览

统一前缀 `/api/v1`（由 `API_PREFIX` 控制）；响应信封 `{code, message, data|errors, request_id}`，成功 `code=0`。

| 分组 | 方法 + 路径 | 说明 |
| --- | --- | --- |
| 健康 | `GET /health` | 含 `content_version` |
| 内容 | `GET /content/manifest` | 内容包清单 |
| 内容 | `GET /content/characters` `…/by-char/{char}` `…/batch` `…/{id}` `…/{id}/similar` | 汉字 |
| 内容 | `GET /content/poems` `…/by-char/{char}` `…/{id}` `…/{id}/quiz` | 古诗 |
| 内容 | `GET /content/units` `…/{id}` · `GET /content/lessons` `…/{id}` `…/{id}/questions` · `GET /content/stories` `…/{id}` · `GET /content/badges` `…/{code}` | 单元/关卡/故事/徽章 |
| 认证 | `POST /auth/invite/verify` `…/register` `…/login` · `POST /auth/recovery/reset` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `DELETE /auth/account` | 邀请码 + 自设口令 |
| 档案 | `GET/POST /children` · `GET/PATCH/DELETE /children/{id}` · `GET /children/{id}/stats` | 儿童档案 |
| 学习 | `GET /learning/daily-task` · `POST /learning/answer` `…/answer/batch` `…/lesson/complete` · `GET /learning/review/due` `…/wrong-questions` `…/progress` · `POST /learning/wrong-questions/{id}/resolve` | 承接前端上报 |
| 报告 | `GET /reports/child/{id}/overview` `…/trend` `…/mastery` `…/weak-chars` `…/weekly` | 服务端聚合；无数据时返回 `compute_locally` |
| 统计 | `POST /stats/events` | 匿名聚合计数，**禁止个人标识** |
| 反馈 | `POST /feedbacks` | 允许匿名 |
| 同步 | `GET /sync/manifest` · `POST /sync/push` · `GET /sync/pull` · `GET /sync/salt` | 端到端加密，服务端只存密文 |
| 后台 | `POST /admin/login` · `POST/GET /admin/invites` · `POST /admin/invites/{id}/revoke` · `GET/POST /admin/characters` `PATCH/DELETE /admin/characters/{id}` | 单管理员，无 RBAC |

### ⛔ 掩藏（不注册任何路由，调不到）

手机号/短信 OTP、微信授权登录、账号绑定、支付与订阅、推送与设备（以上**需企业主体**）；多角色 RBAC（`/admin/roles`、`/admin/users`，属**本期不做**，与企业主体无关）。
契约与类型保留，代码不启用——见 `tests/test_routes.py` 的断言。

## 二、本地运行（不装 Docker 也能跑）

```bash
cd apps/api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 需要 MongoDB：默认 localhost:27017；仅健康检查/内容接口也应在导入内容后使用
cp ../../.env.example ../../.env    # 按需修改 MONGODB_URI / JWT_SECRET

uvicorn app.main:app --reload --port 8000
# 文档：http://localhost:8000/docs
```

### 环境变量（见根 `.env.example`）

| 变量 | 说明 |
| --- | --- |
| `APP_ENV` | `development` / `production` |
| `MONGODB_URI` / `MONGODB_DB` | MongoDB 连接与库名 |
| `API_HOST` / `API_PORT` / `API_PREFIX` | 监听与接口前缀 |
| `JWT_SECRET` | 会话签名密钥，**部署必须替换** |
| `ACCESS_TOKEN_TTL_MIN` / `REFRESH_TOKEN_TTL_DAYS` | 会话时长 |
| `INVITE_SIGNING_PRIVATE_KEY` / `INVITE_SIGNING_PUBLIC_KEY` | Ed25519 邀请码签发/验签 |
| `ADMIN_PASSWORD_HASH` | 单管理员口令哈希（Argon2id） |
| `CORS_ORIGINS` | 允许来源，逗号分隔 |

> 端到端加密**没有服务端密钥**：密钥由用户口令在客户端派生，服务端只存密文。若有人要加「数据加密密钥」变量，说明方案被改坏了。

## 三、Docker 运行

```bash
scripts/api/build.sh
scripts/api/up.sh
scripts/api/logs.sh
```

编排见 `deploy/api/`（`network_mode: host`；macOS Docker Desktop 未启用 host 网络时改用 `host.docker.internal`）。

## 四、导入内容与种子数据

内容即仓库：`content/*.json` 通过种子导入器进 MongoDB，供 `/content/*` 使用。

```bash
scripts/seed/seed.sh                      # 全量导入（幂等）
scripts/seed/seed.sh --only characters    # 只导入某张表
scripts/seed/seed.sh --drop               # 导入前清空目标集合
```

种子文件在 `scripts/seed/data/`，每个文件一个集合/功能；详见 `scripts/seed/README.md`。

## 五、安全要点

- 口令：**Argon2id**（含盐），明文不落日志、不入库。
- 邀请码：只存 **SHA-256 哈希**；12 位 Crockford Base32（60 bit 熵）；失败信息统一（防枚举）。
- 会话：短期 Access（JWT）+ 可吊销的 Refresh（只存哈希）；失败 5 次锁定 15 分钟；按 `client_id` + IP 限流。
- 恢复码：注册时一次性返回明文，服务端只存哈希。
- 统计：`stats_events` 禁止 `account_id`/`child_id`/`client_id`（模型层强制）。

## 六、目录结构（06-1 §3.1）

```
app/
├── main.py            # 装配：挂载 /api/v1、CORS、异常、启动建索引
├── core/              # 配置 / db 连接 / 响应 / 异常 / 安全 / 依赖 / 客户端头
├── models/            # Pydantic 请求/响应模型（按域拆分）
├── routers/           # 只做参数解析与调用 service
├── services/          # 业务逻辑 + 纯函数（SRS、徽章、邀请码）
├── db/                # 集合名、连接、索引初始化
└── seed/              # 内容与种子导入器
tests/                 # pytest：响应、错误码、邀请码、口令哈希、限流、SRS、隐私红线、路由
```

## 七、测试

```bash
cd apps/api && pip install -r requirements-dev.txt
python -m pytest -q          # 或 python -m pytest apps/api/tests -q（仓库根）
python -m compileall app     # 语法检查
```

测试不依赖 MongoDB（覆盖纯逻辑、模型校验与路由注册）。
