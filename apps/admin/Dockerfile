# syntax=docker/dockerfile:1
# ============================================================================
# apps/admin —— 单管理员内容后台（桌面）多阶段构建
#
# 与 apps/web/Dockerfile 的差异：
#   - 后台**不依赖** packages/** 与 content/**（内容走接口），构建上下文更小
#   - **不带 PWA**，产物是纯静态 SPA，由独立 nginx 容器在 ADMIN_PORT 上托管
#   - 只有一个构建期变量：VITE_API_BASE_URL
# ============================================================================

# ---------- 构建阶段 ----------
FROM node:22-alpine AS build

WORKDIR /repo

# corepack 提供与根 package.json 声明的 packageManager 一致的 pnpm
RUN corepack enable

# workspace 描述文件先 COPY，以复用依赖层缓存。
# pnpm-workspace.yaml 里列出的 packages/* 与 apps/web 在本上下文中不存在，
# pnpm 会直接跳过未匹配的 glob，只把 apps/admin 作为 workspace 成员。
COPY package.json pnpm-workspace.yaml ./
COPY apps/admin ./apps/admin

RUN pnpm install --frozen-lockfile=false

# 构建期注入后端地址（Vite 静态替换，运行时不可改）
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# 类型检查 + 构建（build 脚本内含 vue-tsc --noEmit）
RUN pnpm --filter @study-club/admin build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine AS runtime

# 监听端口由 ADMIN_PORT 注入；NGINX_ENVSUBST_FILTER 限制只替换这一个变量，
# 避免 envsubst 把 nginx 自带的 $uri / $host 等变量一并清空。
ENV ADMIN_PORT=8081
ENV NGINX_ENVSUBST_FILTER="^ADMIN_PORT$"

COPY deploy/admin/nginx.conf /etc/nginx/templates/default.conf.template

# 构建产物（Vite 默认输出 apps/admin/dist）
COPY --from=build /repo/apps/admin/dist /usr/share/nginx/html

EXPOSE 8081

CMD ["nginx", "-g", "daemon off;"]
