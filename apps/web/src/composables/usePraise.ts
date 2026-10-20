/**
 * usePraise —— 「全部闯关完成」的语音鼓励。
 *
 * 为什么单独一个 composable：这是**跨三条线共用**的一次性大节点（识字 / 古诗 /
 * 短文都可能在最后一关触发），而且它要同时做三件事 —— 抽一句庆祝语、
 * 用中文念出来、再补一句英文 `Good job!`。写进任何一个视图都会变成
 * 复制三份，改一处漏两处。
 *
 * ⛔ 英文必须单独用 `lang: 'en-US'` 播：中文音色读 "Good job" 会念成
 *    「古德 久布」，孩子听不懂，也就起不到鼓励作用。
 * ⛔ 没有朗读能力时**静默不播**，但调用方仍要把文案显示出来 ——
 *    声音是加分项，不是唯一反馈。
 */

import { ref } from 'vue';

import { pickCheer } from '@/utils/feedback';

import { useCompanion } from './useCompanion';
import { useSpeech } from './useSpeech';

/** 英文那半句：短、常见、孩子在学校/动画里听过。 */
const ENGLISH_CHEER = 'Good job!';

export function usePraise() {
  const { canSpeak, speak } = useSpeech();
  const companion = useCompanion();

  /** 本次抽到的庆祝语（界面同步显示，家长也能看到说了什么）。 */
  const cheerText = ref('');
  /** 是否正在播庆祝语（给界面做「再说一遍」这类状态用）。 */
  const cheering = ref(false);

  async function cheer(): Promise<void> {
    cheerText.value = pickCheer(companion.name.value);
    if (!canSpeak) return;
    if (cheering.value) return;
    cheering.value = true;
    try {
      await speak(cheerText.value, { rate: 0.85 });
      await speak(ENGLISH_CHEER, { rate: 0.8, lang: 'en-US' });
    } catch {
      // 语音失败不该影响结果页：文案已经在上面了。
    } finally {
      cheering.value = false;
    }
  }

  return { cheerText, cheering, cheer, canSpeak };
}
