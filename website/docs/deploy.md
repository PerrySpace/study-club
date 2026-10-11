# 自托管部署

> 本文是面向用户与贡献者的导读，完整设计见 [06-2 发布与更新流程](https://gitee.com/perry-space/study-club/blob/master/docs/06-工程规范/02-发布与更新流程.md) 与 `deploy/*/README.md`（Gitee）。

部署单元就是 `deploy/` 下的 Docker Compose，由 `scripts/` 里的脚本驱动 —— 本机、内网服务器、云主机是**同一套动作**，且**不绑定任何 CI/CD 服务**。最低 1C1G 即可起步。

## 一、四份 compose 的分工

四个服务**各自独立编排**，统一 `network_mode: host`（容器直接占用宿主端口，**不做端口映射**）：

| 服务 | Compose | 默认端口 | 对外 |
| --- | --- | --- | --- |
| web（nginx：静态前端 + `/api/` 反代） | `deploy/web` | `WEB_PORT`（8080） | ✅ **唯一对外入口** |
| api（FastAPI / uvicorn） | `deploy/api` | `API_PORT`（8000） | ⛔ 只应由 web / admin 的 nginx 反代访问 |
| admin（nginx：单管理员内容后台） | `deploy/admin` | `ADMIN_PORT`（8081） | ⛔ 内部工具，**勿暴露公网** |
| mongo（MongoDB 7） | `deploy/mongo` | `MONGO_PORT`（27017） | ⛔ 只绑 `127.0.0.1`（默认无鉴权） |

> 端口全部由 `.env` 控制，改一处即可整体切换。

## 二、同源反代（为什么接口必须同源）

前端是静态站，接口在另一个进程上。如果让浏览器**直连后端**，会撞上两堵墙：**混合内容**（HTTPS 页面调用 http 接口会被浏览器直接拦掉）与 **CORS 白名单**（每加一个入口就要改配置并重启 api）。

因此：`VITE_API_BASE_URL=/api/v1`（**相对路径**）+ web / admin 容器的 nginx `location ^~ /api/ → proxy_pass http://127.0.0.1:8000`。同源之后两堵墙一起消失，**同一份构建产物在 IP、域名、localhost 下都能用**。

> ⚠️ 两个细节：① 必须写 `^~`，否则正则 location 会把 `/api/v1/assets/xxx.svg` 抢走并在静态目录 404；② 该 location 里**不要写 `add_header`**，一条就会让 server 级安全响应头整层失效。

## 三、初始化

```bash
git clone <你的仓库地址> && cd study-club
cp .env.example .env            # 生成环境变量（端口 / 开关 / 密钥占位）
scripts/dev/bootstrap.sh        # 建目录、生成密钥、准备图标等（一步到位）
scripts/dev/up-all.sh           # db → api → web 依次起，并做健康检查
scripts/seed/seed.sh            # 导入初始化数据（按表/功能拆分）
scripts/dev/status.sh           # 查看容器状态与全部访问地址
```

**必需的环境变量**（`.env` 从 `.env.example` 复制，**密钥必须替换**）：

| 变量 | 说明 |
| --- | --- |
| `JWT_SECRET` | 部署时必须替换（`openssl rand -hex 32`） |
| `ADMIN_PASSWORD_HASH` | 用 `scripts/api/hash-password.sh` 生成 |
| `INVITE_SIGNING_PRIVATE_KEY` / `..._PUBLIC_KEY` | 用 `scripts/api/gen-invite-keys.sh` 生成 |
| `MONGODB_URI` | host 网络下为 `mongodb://localhost:27017/study_club` |

> ⚠️ `ADMIN_PASSWORD_HASH` 必须用**单引号**包住（Argon2 哈希含大量 `$`，不加引号会被 Compose 的 dotenv 插值改坏，症状是「口令明明对却一直 `40301`」）。

## 四、改配置怎么生效

`.env` 是真源，**不在仓库里**（只提交 `.env.example`）。按「改了什么」选动作：

| 改动 | 动作 | 为什么 |
| --- | --- | --- |
| `apps/web/**` | `scripts/web/up.sh` | 重建 web 镜像 |
| `apps/api/**` / `apps/admin/**` | `scripts/api/up.sh` / `scripts/admin/up.sh` | 重建镜像并重启容器 |
| `content/**`（字库 / 古诗 / 单元 / 关卡） | `scripts/seed/seed.sh` | 内容真源是 MongoDB，`content/` 是导入种子，幂等 upsert |
| `.env` 的 `VITE_*`（构建期开关） | `scripts/web/up.sh` | 只改 `.env` 不重建**不生效** |
| `.env` 的其它键（`JWT_SECRET` / 端口 / `CORS_ORIGINS`） | 重启对应服务 | 运行期变量，重启即生效 |
| 站点运行配置（后台 `/admin/config`） | 后台直接改 | 写 DB 并刷新进程缓存，**不需要重启** |

> ⚠️ `JWT_SECRET` 一变，所有人立刻被登出——这是预期行为，不是 bug。

## 五、备份与恢复

MongoDB 数据在命名卷 `study-club-mongo-data` / `study-club-mongo-config`，上传的素材在 `study-club-assets`；**`down` 不删卷**。

```bash
scripts/db/backup.sh                     # 导出到 backups/（.gitignore 已忽略）
scripts/db/restore.sh backups/<文件>      # 需要时回灌
```

## 六、回滚注意事项

部署是**原地覆盖**，回滚 = 把代码退回上一版再发一次：

| 回滚对象 | 动作 |
| --- | --- |
| 代码（api / web / admin） | `git revert <坏提交>`（或退回上一个 tag）→ 重跑更新流程 |
| 内容（`content/**`） | revert 内容 JSON → `scripts/seed/seed.sh`（幂等 upsert 会把字段改回去） |
| 配置 | 改回 `.env` → 重启对应服务 |

> ⚠️ **数据不会跟着回滚**：MongoDB 数据在命名卷里，`down` 不删卷；破坏性的数据结构变更**没有自动回滚路径**，动手前先 `scripts/db/backup.sh`。

## 七、部署红线

1. **密钥不进仓库**：仓库里只有 `.env.example`。
2. **管理后台不对公网开放**：只监听 `ADMIN_PORT`（默认 8081），需要时临时起、用完 `scripts/admin/down.sh`。
3. **发布永远针对一个确定的提交**：`git pull` 后先确认是要发的那一版。
4. **发布必跑验证**：`curl -s http://127.0.0.1:8080/api/v1/health` 必须返回 JSON 信封（若返回 HTML，说明 `/api/` 反代没生效，而状态码可能仍是 200）。
5. **数据库默认无鉴权**：mongo 必须绑 `127.0.0.1`，**不要**把 27017 暴露到公网。

## 继续阅读

- 本地跑起来 → [快速开始](/docs/quick-start)
- 总体架构 → [总体架构](/docs/architecture)
- 数据存哪 → [数据设计](/docs/data)
