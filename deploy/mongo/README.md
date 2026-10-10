# deploy/mongo · MongoDB

单服务独立编排，**只用 `docker-compose.yml` 一个文件启动数据库**，与 api / web 互不耦合。

## 启动

```bash
# 推荐：用统一入口脚本（会自动加载仓库根 .env 并做健康检查）
scripts/db/start.sh

# 或直接
cd deploy/mongo && docker compose -p study-club-mongo --env-file ../../.env up -d
```

## 网络模式：为什么是 host

本项目的约定是 **「服务之间用 host 网络互连」**：容器不组成自定义 bridge 网络，而是直接使用宿主网络栈。

| 好处 | 说明 |
| --- | --- |
| 连接串统一 | MongoDB 就是 `mongodb://localhost:27017/study_club`，api 容器与宿主上的工具用同一个地址 |
| 少一层 NAT | 排查连接问题不需要猜容器 IP |
| 与「一人可维护」目标一致 | 不引入 docker 自定义网络、服务发现这些额外概念 |

因此：

- MongoDB 监听宿主 `27017`；
- `deploy/api` 与 `deploy/web` 的容器都是 `network_mode: host`，用 `localhost` 直连；
- **host 网络下不能写 `ports:`**（compose 会直接报错），端口由容器内部的监听参数决定。

## ⚠️ Docker Desktop（macOS / Windows）注意事项

`network_mode: host` 在 Docker Desktop 上需要 **Docker Desktop 4.34+ 且手动开启**（Settings → Resources → Network → Enable host networking）。
若未开启，容器内的 `localhost` 指向容器自身而非宿主，api 会连不上数据库。

两种解决办法：

1. **启用 host networking**（推荐，与 Linux 服务器行为一致）；
2. **改用 bridge 模式**：把仓库根 `.env` 里的连接串改成
   `MONGODB_URI=mongodb://host.docker.internal:27017/study_club`，
   并让 api 的 compose 去掉 `network_mode: host`、改加
   `extra_hosts: ["host.docker.internal:host-gateway"]`。

> 生产部署目标是 Linux 服务器，host 网络在 Linux 上是原生行为，无此问题。

## 数据与备份

| 项 | 值 |
| --- | --- |
| 数据卷 | `study-club-mongo-data` |
| 配置卷 | `study-club-mongo-config` |
| 备份脚本 | `scripts/db/backup.sh`（导出到 `backups/`，不入库） |
| 重置脚本 | `scripts/db/reset.sh`（**会删除数据卷，需二次确认**） |

## 鉴权

本地开发默认**不启用鉴权**（`MONGO_INITDB_ROOT_USERNAME` / `PASSWORD` 留空）。
对外暴露或上服务器时**必须**填写，并同步修改 `MONGODB_URI`：

```
MONGODB_URI=mongodb://<user>:<password>@localhost:27017/study_club?authSource=admin
```

## 索引从哪来

集合与索引**不在本目录维护**——由后端启动时按 `docs/03-数据设计/02-数据字典.md` 幂等创建（`apps/api/app/db/mongo.py`），
这样数据字典是唯一事实来源，避免两处漂移。本目录的 `init/01-init.js` 只做数据库层面的基础初始化。
