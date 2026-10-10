# deploy/web —— Web PWA 静态托管

单服务独立编排（只含 `web`），与 `api` / `mongo` 的编排互不牵连。

## 目录

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | `web` service：`context: ../..`、`dockerfile: apps/web/Dockerfile`、`network_mode: host`、端口 `WEB_PORT`（默认 8080） |
| `nginx.conf` | SPA history fallback、gzip、静态资源长效缓存、`index.html` 不缓存、安全响应头（HSTS 注释） |

## 构建与启动

在**仓库根**执行：

```bash
# 1) 复制环境变量模板（绝不要提交真实 .env）
cp .env.example .env

# 2) 构建镜像
docker compose -f deploy/web/docker-compose.yml build

# 3) 启动（默认监听 8080）
docker compose -f deploy/web/docker-compose.yml up -d

# 4) 查看日志 / 停止
docker compose -f deploy/web/docker-compose.yml logs -f
docker compose -f deploy/web/docker-compose.yml down
```

等价的脚本入口：

```bash
scripts/web/build.sh   # 构建镜像
scripts/web/up.sh      # 启动
scripts/web/down.sh    # 停止并移除容器
scripts/web/logs.sh    # 跟随日志
scripts/web/dev.sh     # 本机 dev server（不走 Docker）
```

## 启动后访问地址

| 用途 | 地址 |
| --- | --- |
| 本机浏览器 | `http://localhost:8080/` |
| 手机 / iPad（同一 WiFi） | `http://<宿主局域网 IP>:8080/` |
| 本机 IP 查询 | `ipconfig getifaddr en0` |
| 全部服务地址一览 | `scripts/dev/status.sh` |

> 容器使用 `network_mode: host`，nginx 直接监听宿主 `WEB_PORT`，**不做端口映射**，
> 也不监听 80（避免与宿主机既有服务冲突）。

## 如何修改 API 地址

接口地址是**构建期**注入（Vite 静态求值，用于死代码消除），因此必须**重新构建**镜像：

```bash
# 方式一：改根 .env 后重建
VITE_API_BASE_URL=https://api.example.com/api/v1
docker compose -f deploy/web/docker-compose.yml build --no-cache
docker compose -f deploy/web/docker-compose.yml up -d

# 方式二：命令行临时覆盖
VITE_API_BASE_URL=https://api.example.com/api/v1 \
  docker compose -f deploy/web/docker-compose.yml up -d --build
```

关键变量（完整清单见根 `.env.example`）：

| 变量 | 说明 |
| --- | --- |
| `VITE_API_BASE_URL` | 云端后台接口地址；**留空则前端只走随包内容**（离线完整可用） |
| `VITE_CDN_BASE` | 远端静态内容根地址（可选） |
| `VITE_ENABLE_CONTENT_API` | 是否启用后端内容接口（默认 `false`） |
| `VITE_ENABLE_REMOTE_CONTENT` | 是否启用远端静态内容覆盖（默认 `false`） |
| `VITE_ENABLE_INVITE_AUTH` | 是否启用邀请码身份（默认 `true`） |
| `WEB_PORT` | nginx 监听端口（容器 host 网络，默认 `8080`） |

## 变更端口

```bash
WEB_PORT=8090 docker compose -f deploy/web/docker-compose.yml up -d --build
```

`nginx.conf` 中的 `${WEB_PORT}` 由容器启动时的 envsubst 渲染（`NGINX_ENVSUBST_FILTER` 只替换这一个变量，避免误伤 nginx 自带变量）。

## 安全响应头与 HTTPS

已下发：`X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options`、`Permissions-Policy`。

**HSTS 默认注释**：仅在已经配置好 HTTPS（外层 TLS 终止）后才应开启，否则用户会被锁在 HTTPS 上而打不开站点。开启方式见 `nginx.conf` 中对应注释行。

## 缓存策略

| 资源 | 策略 |
| --- | --- |
| `/assets/*`（带内容哈希） | `expires 1y` |
| 字体 / 图片 | `expires 30d` |
| `index.html` / `sw.js` / `manifest.webmanifest` | 不缓存（保证发版立即生效） |
| `/content/*` | `expires 5m`（若由本容器托管远端静态内容） |

> ⚠️ 配置里刻意**不用 `add_header Cache-Control`**：nginx 的 `add_header` 只在本层没有
> `add_header` 时才继承上层。一旦在 `location` 里写它，服务端级的安全响应头
> （`X-Frame-Options` 等）会**整层失效**——而 HTML 文档恰恰最需要它们。
> 因此缓存一律用 `expires` 表达。

## 注意

- 容器使用 `network_mode: host`，**不能同时使用 `ports` 端口映射**（Docker 限制）。
- Docker Desktop（macOS/Windows）上 host 网络行为与 Linux 不同；本机开发建议直接用 `scripts/web/dev.sh`。
