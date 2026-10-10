/**
 * 后台入口（05-1 §九「形态 ②」）。
 *
 * 装配顺序：Element Plus → Pinia → Router → mount。
 * 后台是单人工具，不做 PWA、不做离线缓存、不做移动端适配。
 */

import * as ElementPlusIconsVue from '@element-plus/icons-vue';
import ElementPlus from 'element-plus';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import { createPinia } from 'pinia';
import { createApp, type Component } from 'vue';

import App from './App.vue';
import router from './router';

import 'element-plus/dist/index.css';
import '@/styles/index.css';

const app = createApp(App);

for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component as Component);
}

app.use(createPinia());
app.use(router);
app.use(ElementPlus, { locale: zhCn });

app.mount('#app');
