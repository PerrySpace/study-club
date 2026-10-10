/**
 * 偏好存储适配器（localStorage）—— 本文件是 apps/web 中**唯一**允许出现
 * `localStorage` 的地方（见 06-1 §2.8.2、§2.9.1）。
 *
 * ⚠️ 重要变更：IndexedDB 适配器（`IndexedDbStorageAdapter`）已**整体删除**。
 * 学习数据与内容全部改为服务端存储，浏览器不再持有任何业务数据。
 * 现在 localStorage 只允许承载四类键，且仅此四类：
 *   ① 会话 Token（`sc.session`）；
 *   ② 少量纯 UI 偏好（`sc.currentChild` 之类），丢了最多是重选一次，不含任何学习记录；
 *   ③ 设备标识（`sc.deviceId`）—— 见 `ensureDeviceId()`，用来把同一账号的
 *      不同设备分开成独立会话（不然家里两台设备会互相顶下线）；
 *   ④ 登录记忆（`sc.loginMemory`）—— 见 `readLoginMemory()`，「记住账号与口令」
 *      勾选后才写，**只在本机**，不含任何儿童数据。
 * 任何「以本地为主存储」的新键都属于违规。
 *
 * 为什么不干脆把 Token 也挪到别处：Token 必须是同步可读的
 * （路由守卫在首个 tick 就要判断登录态），而 IndexedDB / Cache Storage 都是异步的，
 * 用它们会导致「进页面闪一下登录页再跳回来」。所以 Token 留在 localStorage，
 * 这是刻意保留的唯一例外 —— 而且它只是凭据，不含任何儿童数据。
 */

import type { PreferenceAdapter } from '@study-club/core';

// ---------------------------------------------------------------------------
// 通用读写（隐私模式 / 存储被禁用时静默降级，绝不阻断登录流程）
// ---------------------------------------------------------------------------
function readRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 写入失败（配额 / 隐私模式）：不抛错
  }
}

function removeRaw(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // 同上
  }
}

export function createPreferenceAdapter(): PreferenceAdapter {
  return {
    get: readRaw,
    set: writeRaw,
    remove: removeRaw,
  };
}

// ---------------------------------------------------------------------------
// 设备标识（sc.deviceId）
// ---------------------------------------------------------------------------
export const DEVICE_ID_KEY = 'sc.deviceId';

/**
 * 生成一个随机 id。
 *
 * ⚠️ `crypto.randomUUID()` **只在安全上下文（HTTPS / localhost）可用** ——
 * 局域网 http://192.168.x.x:8090 直连时它是 undefined，所以必须有降级链。
 * `crypto.getRandomValues` 在非安全上下文里仍可用，`Math.random` 只是最后的兜底：
 * 这个 id 只用来区分设备、不承担任何安全职责，随机性不足的后果仅仅是「极小概率撞号」。
 */
function createRandomId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  if (c?.getRandomValues) {
    const bytes = new Uint8Array(16);
    c.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  }
  return `dev-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** 进程内缓存：设备 id 在一次会话里不会变，没必要每次请求都读一遍 localStorage。 */
let cachedDeviceId: string | null = null;

/**
 * 取本机设备标识；没有就生成一个并持久化。
 *
 * 为什么需要它（这是一条真实缺陷的修复）：服务端给每个登录会话建一条 `devices`
 * 记录，定位设备靠的是 `client_id`。前端此前**从不发** client_id，服务端只好退化成
 * 「按客户端形态指纹」认设备 —— 于是「平板 + 手机」两台都是 web/desktop 形态的设备
 * 会算成同一台，后登录的一方会**覆盖**先登录一方的 Refresh Token，
 * 表现就是「家里 iPad 一登，妈妈手机就被踢下线」。带上稳定的设备 id 后，
 * 每台设备各持一份 Refresh Token，可以同时在线、各自登出互不影响。
 */
export function ensureDeviceId(): string {
  if (cachedDeviceId) return cachedDeviceId;
  const existing = readRaw(DEVICE_ID_KEY);
  if (existing) {
    cachedDeviceId = existing;
    return existing;
  }
  const created = createRandomId();
  writeRaw(DEVICE_ID_KEY, created);
  cachedDeviceId = created;
  return created;
}

// ---------------------------------------------------------------------------
// 登录记忆（sc.loginMemory）
// ---------------------------------------------------------------------------
export const LOGIN_MEMORY_KEY = 'sc.loginMemory';

/** 登入页「记住账号与口令」存下来的内容。 */
export interface RememberedLogin {
  identifier: string;
  passcode: string;
}

/**
 * 读登录记忆。
 *
 * ⚠️ **明文口令存本机**是刻意的取舍，不是疏忽：产品定位是「家长自托管的家庭应用」，
 * 与这里已经存着的会话 Token（能让任何拿到它的人直接以该账号发请求）相比，
 * 口令的额外暴露面并不更大；换来的是孩子/老人不必每次输一长串口令。
 * 代码上做了三件事把风险压到最低：
 *   ① **默认不写**，要用户在登入页勾选「记住」才写；
 *   ② 只写 localStorage，不上传、不参与任何同步；
 *   ③ 取消勾选或登出时立即删除。
 * 公共设备上不要勾选 —— 这一点在登入页有明确提示。
 */
export function readLoginMemory(): RememberedLogin | null {
  const raw = readRaw(LOGIN_MEMORY_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<RememberedLogin> | null;
    if (!parsed || typeof parsed.identifier !== 'string') return null;
    return { identifier: parsed.identifier, passcode: parsed.passcode ?? '' };
  } catch {
    // 坏数据等同于没记住，顺手清掉，避免每次进来都解析失败
    removeRaw(LOGIN_MEMORY_KEY);
    return null;
  }
}

/** 写入 / 清除登录记忆（`null` 表示清除）。 */
export function writeLoginMemory(value: RememberedLogin | null): void {
  if (!value) {
    removeRaw(LOGIN_MEMORY_KEY);
    return;
  }
  writeRaw(LOGIN_MEMORY_KEY, JSON.stringify(value));
}

