import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

/**
 * apps/web 构建配置。
 *
 * 关键点：
 *  1. 内容由服务端提供（经 `/content/*` 接口）；`content/**` 位于仓库根，
 *     仅用于种子导入与本地开发，故把 fs.allow 放宽到仓库根。
 *  2. PWA：`registerType: 'autoUpdate'`，预缓存应用外壳与字体；
 *     **不缓存任何 API 响应**（数据以服务端为准，避免陈旧内容）。
 *  3. 三档断点由 packages/tokens 的 CSS 变量与 TS 常量提供，此处不写魔法数字。
 */
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      includeAssets: ['favicon.svg', 'icons.svg', 'robots.txt'],
      manifest: {
        name: '学习俱乐部',
        short_name: '学习俱乐部',
        description: '小学 1–6 年级课内识字 + 古诗文启蒙。',
        lang: 'zh-CN',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any',
        theme_color: '#ffd76b',
        background_color: '#f5fff8',
        icons: [
          { src: 'pwa-192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'any' },
          { src: 'pwa-512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any' },
          { src: 'pwa-512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'maskable' },
        ],
      },
      workbox: {
        // 预缓存：构建产物 + 内容 JSON（字库/古诗）+ 字体。
        //
        // ⚠️ 刻意**不包含 `html`**：`index.html` 一旦进预缓存，就只能在「SW 版本更新」时
        //    才会刷新。而 SW 更新要连过两道关——浏览器对同一 registration 的自动更新检查
        //    有 24h 节流，对外 CDN 又可能给 `/sw.js` 带上缓存头。任何一道延迟，
        //    用户就会被旧 SW 用旧 `index.html` 应答（进而引用旧 hash 的 JS），
        //    表现为「服务端明明发了新版，页面还是旧的」。
        //    改为交给下方「导航请求」那条规则**网络优先**获取：在线必取最新。
        globPatterns: ['**/*.{js,css,svg,json,woff,woff2,ttf,png,webp}'],
        //
        // ⚠️ 必须**显式置空**：vite-plugin-pwa 的默认 workbox 配置里
        //    `navigateFallback` 就是 `'index.html'`（见 vite-plugin-pwa dist 的
        //    `defaultWorkbox`），**删掉这一行它会被自动补回来**。而它会生成
        //    `registerRoute(new NavigationRoute(createHandlerBoundToURL('index.html')))`：
        //      ① 那是 **cache-first**，会把导航请求抢先答掉；
        //      ② 模板里它注册在 `runtimeCaching` **之前**
        //         （见 workbox-build/build/templates/sw-template.js），
        //         于是下面的 NetworkFirst 永远轮不到；
        //      ③ 既然 `index.html` 已不进预缓存，它还会在运行期因
        //         「index.html 未预缓存」抛错，等于把整个 SW 搞坏。
        //    要「在线永远取最新 HTML」就必须置空（`Object.assign` 合并，undefined 可覆盖默认值）。
        navigateFallback: undefined,
        runtimeCaching: [
          {
            // 导航请求（HTML 文档）→ **网络优先**。
            //
            // `request.mode === 'navigate'` 精确命中「地址栏打开 / 刷新 / 新标签页」这类
            // 文档请求，天然排除同源 API（cors）与静态资源（no-cors），
            // 也不会误伤跨域上报请求 —— 比用 RegExp 硬凑路径白名单更可靠、不用随路由维护。
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'study-club-html',
              // 弱网下最多等 3s 即回落缓存，避免白屏
              networkTimeoutSeconds: 3,
              // 离线兜底：缓存最近成功导航过的文档。
              // 应用 start_url 为 '/'，主屏启动恒走该路径，因此离线冷启动始终可用。
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
          {
            // 构建产物资源（带内容哈希）→ 缓存优先，可长缓存；
            // 新 HTML 引用的是新 hash 的文件名，天然不会命中旧缓存。
            // API 响应一律不进缓存（由宿主 nginx 反代，SW 不介入）。
            urlPattern: /\/assets\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'study-club-assets',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // host: true —— 必须监听 0.0.0.0，否则手机 / iPad 无法通过局域网 IP 访问
    // dev server（Vite 默认只绑 127.0.0.1，同一 WiFi 下的设备会连不上）。
    host: true,
    port: 5173,
    strictPort: true,
    // 内容包在仓库根（content/**），必须把仓库根加入允许列表。
    fs: { allow: [fileURLToPath(new URL('../../', import.meta.url))] },
  },
  preview: {
    // 本地验证构建产物时同样开放局域网访问（模拟 nginx 容器行为）。
    host: true,
    port: 4173,
    strictPort: true,
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.1.0'),
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
});
