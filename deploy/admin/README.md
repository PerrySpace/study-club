# deploy/admin —— 管理后台静态托管

单服务独立编排（只含 `admin`），与 `web` / `api` / `mongo` 的编排互不牵连。

> ⚠️ **这是内部工具，不是「系统的管理端」**（`docs/05-管理后台/01-内容管理与用户管理体系.md` §1.3）。
> 单人使用、不做 RBAC。**不要暴露到公网**：建议用完就 `scripts/admin/down.sh` 关掉。

## 目录

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | `admin` service：`context: ../..`、`dockerfile: apps/admin/Dockerfile`、`network_mode: host`、端口 `ADMIN_PORT`（默认 8081） |
| `nginx.conf` | SPA history fallback、gzip、静态资源长效缓存、`index.html` 不缓存、`X-Robots-Tag: noindex`、`X-Frame-Options: DENY` |

## 前置条件：必须先配置管理员口令

后台的登录接口在 `ADMIN_PASSWORD_HASH` 为空时直接返回 `FEATURE_DISABLED`（`40302`），
**整个后台不可用**。所以第一次用之前：

```bash
# 1) 生成 Argon2id 口令哈希（交互式输入，不回显）
scripts/api/hash-password.sh

# 2) 把脚本输出的那一行（⚠️ 含单引号）整行替换进仓库根 .env 的 ADMIN_PASSWORD_HASH

# 3) 让 api 读到新变量
scripts/api/restart.sh
```

> ⚠️ **必须带单引号**。Argon2 哈希形如 `$argon2id$v=19$m=65536,t=3,p=2$<salt>$<digest>`，
> 含大量 `$`；Docker Compose 用 dotenv 解析 `.env` / `env_file`，**不加引号会把 `$m`、`$xxxx`
> 当成变量引用替换成空串**，哈希被悄悄改坏。症状是「口令明明对，却一直返回
> `40301 管理员口令不正确`」。dotenv 对单引号值不做插值，所以写成
> `ADMIN_PASSWORD_HASH='$argon2id$v=19$m=65536,t=3,p=2$...$...'`。

## 构建与启动

在**仓库根**执行：

```bash
cp .env.example .env            # 首次

docker compose -f deploy/admin/docker-compose.yml build
docker compose -f deploy/admin/docker-compose.yml up -d
docker compose -f deploy/admin/docker-compose.yml logs -f
docker compose -f deploy/admin/docker-compose.yml down
```

等价的脚本入口：

```bash
scripts/admin/build.sh   # 构建镜像
scripts/admin/up.sh      # 启动
scripts/admin/down.sh    # 停止并移除容器
scripts/admin/logs.sh    # 跟随日志
scripts/admin/dev.sh     # 本机 dev server（不走 Docker，默认 5174）
```

## 启动后访问地址

| 用途 | 地址 |
| --- | --- |
| 本机浏览器 | `http://localhost:8081/` |
| 局域网 | `http://<宿主局域网 IP>:8081/` |
| 全部服务地址一览 | `scripts/dev/status.sh` |

> 容器使用 `network_mode: host`，nginx 直接监听宿主 `ADMIN_PORT`，**不做端口映射**，
> 也不监听 80（避免与宿主机既有服务冲突）。

## 如何修改 API 地址

`VITE_API_BASE_URL` 是**构建期**注入的，改了必须重建镜像：

```bash
VITE_API_BASE_URL=https://api.example.com/api/v1 \
  docker compose -f deploy/admin/docker-compose.yml up -d --build
```

留空时前端会**按当前访问主机的 8000 端口自动推断**接口地址
（例如用 `http://192.168.1.10:8081/` 打开，就连 `http://192.168.1.10:8000/api/v1`），
这样局域网内换机器访问无需重新构建。

| 变量 | 说明 |
| --- | --- |
| `VITE_API_BASE_URL` | 后端接口地址；留空则按同主机 8000 端口推断 |
| `ADMIN_PORT` | nginx 监听端口（容器 host 网络，默认 `8081`） |
| `ADMIN_PASSWORD_HASH` | **后端**变量，不是构建参数；留空则登录接口不可用 |
| `CORS_ORIGINS` | **后端**变量；需包含后台的访问来源（如 `http://localhost:8081`） |

## 缓存策略

| 资源 | 策略 |
| --- | --- |
| `/assets/*`（带内容哈希） | `expires 1y` |
| `index.html` | `expires -1`（不缓存，发版立即生效） |
| 其余 | 继承默认 |

> 配置里刻意**不用 `add_header Cache-Control`**：nginx 的 `add_header` 只在本层没有
> `add_header` 时才继承上层，一旦在 `location` 里写它，服务端级的安全响应头会整层失效。

## 注意

- 容器使用 `network_mode: host`，**不能同时使用 `ports` 端口映射**（Docker 限制）。
- 后台**不参与 `scripts/dev/up-all.sh` 的默认链路**（它是内部工具，建议按需启动）。
- 后台只做「内容的在线 CRUD 与邀请码管理」；内容的主路径仍是
  `content/**` 仓库 JSON + PR 评审（`05-1 §1.2`）。
