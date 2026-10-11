# 学习俱乐部 · 文档站

基于 [VitePress](https://vitepress.dev/) 构建，是面向访客的**精简版**文档站。
面向开发者的完整设计文档在仓库根目录的 [`docs/`](../docs/)。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `index.md` / `en/index.md` | 中文 / 英文首页 |
| `docs/` / `en/docs/` | 中文 / 英文文档页 |
| `.vitepress/config.mts` | 站点配置（导航、侧边栏、`base`） |
| `public/` | 静态资源（`logo.svg`、`robots.txt`） |

## 本地开发

```bash
npm install
npm run dev      # http://localhost:5173，改动 .md 保存后即时生效
```

## 构建与预览

```bash
npm run build    # 产物在 .vitepress/dist/
npm run preview
```

## 部署

推送到 `master` 且改动包含 `website/**` 时，`.github/workflows/docs.yml`
会自动构建并部署到 GitHub Pages：

<https://perryspace.github.io/study-club/>

线上构建通过环境变量 `DOCS_BASE=/study-club/` 指定子路径 —— GitHub Pages
项目站点部署在 `/<repo>/` 下，本地与根路径部署则保持 `/`。

## 两个必须知道的坑

**1. 平台原生二进制依赖必须放 `optionalDependencies`**

`@esbuild/win32-x64` 与 `@rollup/rollup-win32-x64-msvc` 带有 `"os": ["win32"]` 约束。
放进 `dependencies` 会让 Linux CI 直接以 `EBADPLATFORM` 失败；
只有放进 `optionalDependencies`，npm 才会在平台不匹配时静默跳过。

**2. CI 必须丢弃 `package-lock.json` 再安装**

`package-lock.json` 在 Windows 上生成时，rollup / esbuild 的 **Linux** 原生包
不会被正确安装（npm 已知问题 npm/cli#4828），导致 CI 构建时报
`Cannot find module @rollup/rollup-linux-x64-gnu`。

因此 workflow 在安装前会先 `rm -f package-lock.json` 按 `package.json` 重新解析。
**请勿移除这一步。**
