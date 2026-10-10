# syntax=docker/dockerfile:1
# ============================================================================
# apps/web —— Web PWA 多阶段构建
#
# 关键点：pnpm workspace 构建必须把仓库根的 package.json / pnpm-workspace.yaml
# 以及被 apps/web 依赖的 packages/** 与随包内容 content/** 一并 COPY 进构建上下文，
# 否则 `workspace:*` 依赖与 `../../../../content/*.json` 都解析不到。
# ============================================================================

# ---------- 构建阶段 ----------
FROM node:22-alpine AS build

WORKDIR /repo

# corepack 提供与根 package.json 声明的 packageManager 一致的 pnpm
RUN corepack enable

# ① workspace 描述文件（先 COPY 以复用依赖层缓存）
COPY package.json pnpm-workspace.yaml ./

# ② workspace 内被 web 依赖的包与内容（内容随包构建）
COPY packages ./packages
COPY content ./content
COPY apps/web ./apps/web

# ③ 安装依赖（无 lockfile 时允许解析；有 lockfile 时可用 --frozen-lockfile）
RUN pnpm install --frozen-lockfile=false

# ④ 构建期能力开关与接口地址（Vite 静态求值，用于死代码消除）
ARG VITE_API_BASE_URL=""
ARG VITE_CDN_BASE=""
ARG VITE_ENABLE_INVITE_AUTH="true"
ARG VITE_ENABLE_INVITE_REQUIRED="true"
ARG VITE_ENABLE_INVITE_OFFLINE_VERIFY="true"
ARG VITE_ENABLE_CLOUD_PROFILE="false"
ARG VITE_ENABLE_E2E_ENCRYPTION="true"
ARG VITE_ENABLE_CONTENT_API="false"
ARG VITE_ENABLE_REMOTE_CONTENT="false"
ARG VITE_ENABLE_STATS="false"
ARG VITE_ENABLE_CLOUD_ASSESSMENT="false"
ARG VITE_ENABLE_ACCOUNT_AUTH="false"
ARG VITE_ENABLE_PAYMENT="false"
ARG VITE_ENABLE_MINIPROGRAM="false"
ARG VITE_ENABLE_NATIVE_APP="false"
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_CDN_BASE=${VITE_CDN_BASE} \
    VITE_ENABLE_INVITE_AUTH=${VITE_ENABLE_INVITE_AUTH} \
    VITE_ENABLE_INVITE_REQUIRED=${VITE_ENABLE_INVITE_REQUIRED} \
    VITE_ENABLE_INVITE_OFFLINE_VERIFY=${VITE_ENABLE_INVITE_OFFLINE_VERIFY} \
    VITE_ENABLE_CLOUD_PROFILE=${VITE_ENABLE_CLOUD_PROFILE} \
    VITE_ENABLE_E2E_ENCRYPTION=${VITE_ENABLE_E2E_ENCRYPTION} \
    VITE_ENABLE_CONTENT_API=${VITE_ENABLE_CONTENT_API} \
    VITE_ENABLE_REMOTE_CONTENT=${VITE_ENABLE_REMOTE_CONTENT} \
    VITE_ENABLE_STATS=${VITE_ENABLE_STATS} \
    VITE_ENABLE_CLOUD_ASSESSMENT=${VITE_ENABLE_CLOUD_ASSESSMENT} \
    VITE_ENABLE_ACCOUNT_AUTH=${VITE_ENABLE_ACCOUNT_AUTH} \
    VITE_ENABLE_PAYMENT=${VITE_ENABLE_PAYMENT} \
    VITE_ENABLE_MINIPROGRAM=${VITE_ENABLE_MINIPROGRAM} \
    VITE_ENABLE_NATIVE_APP=${VITE_ENABLE_NATIVE_APP}

# ⑤ 类型检查 + 构建（build 脚本内含 vue-tsc --noEmit）
RUN pnpm --filter @study-club/web build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine AS runtime

# 监听端口由 WEB_PORT 注入；NGINX_ENVSUBST_FILTER 限制只替换这一个变量，
# 避免 envsubst 把 nginx 自带的 $uri / $host 等变量一并清空。
ENV WEB_PORT=8080
ENV NGINX_ENVSUBST_FILTER="^WEB_PORT$"

# nginx 配置以模板形式提供（容器启动时由官方 entrypoint 渲染到 conf.d）
COPY deploy/web/nginx.conf /etc/nginx/templates/default.conf.template

# 构建产物（Vite 默认输出 apps/web/dist）
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
