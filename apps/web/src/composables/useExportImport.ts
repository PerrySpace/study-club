/**
 * 导出学习数据（**只有导出，没有导入**）。
 *
 * ⚠️ 与旧版的分野：旧版的「导出/导入」是「无账号 + 只存本机」模式下的**唯一数据保险**，
 * 换设备必须手动导文件。数据真源搬到服务端后这个保险已经由服务端承担 ——
 * 换设备重新登录就能看到全部进度，再让家长导文件是多余的一步。
 *
 * 导出**保留**：它对应的不再是「备份」，而是「用户的退出自由」（P0 合规要求）——
 * 随时能把数据带走，而不是被产品锁住。因此文件里带 `schema_version`，可长期留存。
 */

import { ref } from 'vue';

import { useCore } from '@study-club/core';

import { downloadJson } from '@/platform';

import { useToast } from './useToast';

export function useExportImport() {
  const toast = useToast();
  const exporting = ref(false);

  async function exportChild(childId: string): Promise<void> {
    if (exporting.value) return;
    exporting.value = true;
    try {
      const bundle = await useCore().repositories.progress.exportAll(childId);
      const stamp = new Date().toISOString().slice(0, 10);
      // 文件名保持 ASCII：中文文件名在部分系统/下载器上会乱码或被截断
      downloadJson(`study-club-export-${stamp}.json`, bundle);
      toast.success('已导出全部学习数据');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '导出失败，请稍后重试');
    } finally {
      exporting.value = false;
    }
  }

  return { exportChild, exporting };
}
