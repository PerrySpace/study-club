import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

/**
 * apps/admin 构建配置。
 *
 * 与 apps/web 的差异（有意为之）：
 *  1. **不带 PWA** —— 后台是内部工具，不需要离线能力与 Service Worker。
 *  2. **不读 content/** —— 内容由后端接口提供，无需把仓库根加入 fs.allow。
 *  3. **默认端口 5174**（web dev 用 5173），避免两者同时起时冲突。
 *  4. `base: '/'` —— 由 deploy/admin/nginx.conf 独立端口托管，不与主站共享域名前缀。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // host: true —— 与 web 一致：允许通过局域网 IP 访问（方便在别的机器上开后台）。
    host: true,
    port: 5174,
    strictPort: true,
  },
  preview: {
    host: true,
    port: 4174,
    strictPort: true,
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.1.0'),
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    // Element Plus 全量引入，包体较大；只对后台生效，不影响主站体积。
    chunkSizeWarningLimit: 1200,
  },
});
