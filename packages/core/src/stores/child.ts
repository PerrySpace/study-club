/**
 * child store —— 儿童档案（**服务端唯一真源**）。
 *
 * 要点：
 *   - `_id` 由服务端生成，客户端不自己造 `c_xxx` 假 id（自造 id 会导致
 *     后续所有请求 40301，且看起来像权限问题，极难排查）。
 *   - 统计（累计学习/掌握/连续天数）由服务端维护，客户端不 `bumpStats` 自行累加。
 *   - 头像：**默认兔子**；若账号曾选过动物（或上传过图片），新建档案时沿用账号的选择。
 *
 * 唯一仍留在本机的只有「当前选中哪个孩子」这个 UI 偏好 —— 它不属于业务数据，
 * 且换设备时重选一次即可，没必要为它多加一个服务端字段。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { DEFAULT_AVATAR } from '../constants';
import type { Child } from '../types/identity';
import { useAuthStore } from './auth';
import { useCore } from './context';

const CURRENT_CHILD_KEY = 'sc.currentChild';

export const useChildStore = defineStore('child', () => {
  const children = ref<Child[]>([]);
  const currentId = ref<string | null>(null);
  const loaded = ref(false);
  const loading = ref(false);

  const current = computed<Child | null>(
    () => children.value.find((c) => c._id === currentId.value) ?? null,
  );

  /**
   * 新建档案时的头像取值顺序：调用方指定 → 账号上次的选择 → 默认兔子。
   * 这就是「默认兔子头像，若用户上次选过则沿用」的落点。
   */
  function resolveAvatarKey(explicit?: string): string {
    if (explicit) return explicit;
    const accountKey = useAuthStore().account?.avatar_key;
    return accountKey || DEFAULT_AVATAR;
  }

  async function load(): Promise<void> {
    loading.value = true;
    try {
      children.value = await useCore().repositories.progress.listChildren();
      const saved = useCore().platform.preference.get(CURRENT_CHILD_KEY);
      currentId.value =
        (saved && children.value.some((c) => c._id === saved) ? saved : null) ??
        children.value.find((c) => c.status !== 'archived')?._id ??
        null;
      loaded.value = true;
    } finally {
      loading.value = false;
    }
  }

  function setCurrent(id: string): void {
    currentId.value = id;
    useCore().platform.preference.set(CURRENT_CHILD_KEY, id);
  }

  async function create(input: {
    nickname: string;
    grade: number;
    avatarKey?: string;
    birthYear?: number | null;
  }): Promise<Child> {
    const child = await useCore().repositories.progress.createChild({
      nickname: input.nickname.trim().slice(0, 12) || '小朋友',
      grade: input.grade,
      avatar_key: resolveAvatarKey(input.avatarKey),
      ...(input.birthYear !== undefined ? { birth_year: input.birthYear } : {}),
    });
    children.value = [...children.value, child];
    setCurrent(child._id);
    return child;
  }

  /**
   * 局部更新。服务端返回完整文档，直接用它替换本地副本，
   * 避免本地猜测字段（例如服务端顺带更新的 `updated_at` / `stats`）与真源不一致。
   */
  async function update(id: string, patch: Partial<Child>): Promise<Child | null> {
    const next = await useCore().repositories.progress.updateChild(id, patch);
    children.value = children.value.map((c) => (c._id === id ? next : c));
    return next;
  }

  /** 软删除（服务端置 archived）；本地同步移除视图。 */
  async function remove(id: string): Promise<void> {
    await useCore().repositories.progress.deleteChild(id);
    children.value = children.value.filter((c) => c._id !== id);
    if (currentId.value === id) {
      const fallback = children.value[0]?._id ?? null;
      currentId.value = fallback;
      if (fallback) useCore().platform.preference.set(CURRENT_CHILD_KEY, fallback);
      else useCore().platform.preference.remove(CURRENT_CHILD_KEY);
    }
  }

  /** 单独重拉一个档案（学习完刷新统计用，避免整体列表请求）。 */
  async function refreshOne(id: string): Promise<Child | null> {
    const fresh = await useCore().repositories.progress.getChild(id);
    if (!fresh) return null;
    children.value = children.value.map((c) => (c._id === id ? fresh : c));
    return fresh;
  }

  return { children, currentId, current, loaded, loading, load, setCurrent, create, update, remove, refreshOne };
});
