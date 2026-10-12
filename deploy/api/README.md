# deploy/api —— api 服务编排

单服务独立编排（只含 `api` 一个 service），`network_mode: host`，通过 env_file 读取仓库根 `.env`。
配套脚本在 `scripts/api/`。

## 前置

1. 仓库根复制出 `.env`（容器内应用变量来源）：
   ```bash
   cp .env.example .env
   ```
2. 本目录复制出 `.env`（compose 变量插值，如端口）：
   ```bash
   cp deploy/api/.env.example deploy/api/.env
   ```
3. 有一个可用的 MongoDB（本地或容器）。本仓库的 MongoDB 编排在 `deploy/mongo/`，用 `scripts/db/start.sh` 启动。

## 启动后访问地址

| 用途 | 地址 |
| --- | --- |
| 健康检查 | `http://localhost:8000/api/v1/health` |
| 接口文档（Swagger） | `http://localhost:8000/docs` |
| 接口基址 | `http://localhost:8000/api/v1` |
| 局域网设备（手机 / iPad） | `http://<宿主局域网 IP>:8000/api/v1` |

> 容器使用 `network_mode: host`，直接监听宿主端口，**不做端口映射**。
> 前端要连它时，把根 `.env` 的 `VITE_API_BASE_URL` 设为上面地址并**重新构建 web 镜像**
> （接口地址是构建期注入）。跨设备调试时不要写 `localhost`，要写宿主局域网 IP。

## 启动 / 停止 / 日志

```bash
scripts/api/build.sh      # 构建镜像（上下文=仓库根）
scripts/api/up.sh         # 启动（后台）
scripts/api/logs.sh       # 跟踪日志
scripts/api/restart.sh    # 重建容器使 .env 变更生效
scripts/api/down.sh       # 停止并移除
```

也可直接用 compose：

```bash
docker compose -f deploy/api/docker-compose.yml up -d
```

## 连接串怎么改

- **host 网络（默认）**：容器与宿主共享网络栈，MongoDB 用 `localhost:27017`：
  ```
  MONGODB_URI=mongodb://localhost:27017/study_club
  ```
- **Docker Desktop for macOS/Windows 若未启用 host 网络**：宿主与容器不在同一网络栈，
  改用 `host.docker.internal`：
  ```
  MONGODB_URI=mongodb://host.docker.internal:27017/study_club
  ```
  同时把 compose 的 `network_mode: host` 换成端口映射（host 网络在 Docker Desktop 上行为受限）：
  ```yaml
  ports:
    - "${API_PORT:-8000}:8000"
  ```
- **独立部署 MongoDB 容器**：把 `MONGODB_URI` 指向该容器可达的地址（同网络时用服务名）。

## 端口

端口完全由 `API_PORT` 控制：compose 的 `${API_PORT}` 插值 + 容器 command 均读取该变量。

## 密钥

- `JWT_SECRET`：部署时必须替换（`openssl rand -hex 32`）。
- `ADMIN_PASSWORD_HASH`：用 `scripts/api/hash-password.sh` 生成。
- `INVITE_SIGNING_PRIVATE_KEY` / `INVITE_SIGNING_PUBLIC_KEY`：用 `scripts/api/gen-invite-keys.sh` 生成。
- 端到端加密**没有服务端密钥**：密钥由用户密码在客户端派生，服务端只存密文（见 02-5 §4.5）。

## 初始化数据

```bash
scripts/seed/seed.sh                      # 导入全部种子与内容包（集合为空时全量灌入）
scripts/seed/seed.sh --only characters    # 只导入某张表
scripts/seed/seed.sh --force              # 强制以仓库为准（覆盖同名 + 清理库内多余）
```

⭐ **内容优先级：初始化时用仓库，库里有数据就用库里的。**
内容型集合为空时（首次部署）用仓库 `content/` 全量灌入；已有数据时**只补缺 ——
不覆盖同名、不删除库内多余项**。因此后台「导入 JSON」进来的内容不会再被发布清掉。
唯一例外是 `--force` / `--drop`（显式声明以仓库为准）。详见 `scripts/seed/README.md`。

内容接口 `GET /api/v1/content/*` 在导入内容包后才有数据。
