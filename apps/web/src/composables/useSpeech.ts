/**
 * useSpeech —— 视图层使用语音能力的**唯一入口**。
 *
 * 职责边界：
 *   - 把 `PlatformContext.speech` 包成带响应式状态的形式（`playing` / `listening`），
 *     让按钮能直接绑「朗读中 / 识别中」；
 *   - 组件卸载时**自动停播、自动松麦克风** —— 忘了停会留下「离开页面麦克风还亮着」
 *     这种家长一定会发现的问题；
 *   - 管理**音色选择**（`voices` / `voiceURI` / `setVoice`）：音色是异步就绪的，
 *     必须靠 `voiceschanged` 事件刷新，不能只在挂载时取一次；
 *   - **不**做「读对了没有」的判定（那是学科包 `readingMatches` 的事），
 *     也不做任何降级文案（那是组件的事：降级长什么样取决于场景）。
 *
 * 用法：
 *   const { canSpeak, canListen, speak, listen } = useSpeech();
 */

import { getCurrentInstance, onUnmounted, ref } from 'vue';

import type { ListenResult, SpeakOptions, SpeechVoice } from '@study-club/core';

import { onVoicesChanged } from '@/platform/speech';

import { usePlatform } from './usePlatform';

/** 音色选择的持久化 key —— 与「无 Key 也要能用」的纪律无关，纯本地偏好。 */
const VOICE_PREF_KEY = 'sc.speech.voice';

/** 试听文本：选三个声调差别大的字，听感上最容易分辨音色好坏。 */
const VOICE_PREVIEW_TEXT = '山，水，火';

function readStoredVoice(): string {
  try {
    return localStorage.getItem(VOICE_PREF_KEY) ?? '';
  } catch {
    return '';
  }
}

function writeStoredVoice(voiceURI: string): void {
  try {
    if (voiceURI) localStorage.setItem(VOICE_PREF_KEY, voiceURI);
    else localStorage.removeItem(VOICE_PREF_KEY);
  } catch {
    /* 隐私模式下写入失败：本次会话仍生效，只是下次不记得 */
  }
}

export function useSpeech() {
  const { speech } = usePlatform();

  const playing = ref(false);
  const listening = ref(false);
  /** 识别期间实时音量（0–1）。界面用它画电平条，证明「麦克风真的在听」。 */
  const level = ref(0);
  /** 当前设备可用的中文音色（`voiceschanged` 后会刷新）。 */
  const voices = ref<SpeechVoice[]>([]);
  /** 选中的音色 `voiceURI`；空串表示「自动挑选」。 */
  const voiceURI = ref<string>(readStoredVoice());

  /**
   * 实际生效的音色。
   *
   * 存的是一个 `ref` 而不是每次现算：`speak` 是 async 的，
   * 现算的话「点击时看到的音色」和「真正播出来的音色」可能不是同一个
   * （音色列表在这期间刷新过），排查起来非常费劲。
   */
  const activeVoice = ref<SpeechVoice | null>(null);
  /** 本次会话是否已自动试听过（避免每次音色事件都抢着出声）。 */
  const hasAutoSpoken = ref(false);

  function refreshVoices(): void {
    if (!speech.canSpeak) return;
    const list = speech.listVoices('zh-CN');
    voices.value = list;
    // 选中的音色在设备上已不存在（换设备 / 浏览器升级）时静默回落到自动挑选，
    // 不保留一个永远不会被命中的 URI。
    if (voiceURI.value && !list.some((v) => v.voiceURI === voiceURI.value)) {
      voiceURI.value = '';
      writeStoredVoice('');
    }
    activeVoice.value =
      list.find((v) => v.voiceURI === voiceURI.value) ?? list[0] ?? null;
  }

  function setVoice(uri: string): void {
    voiceURI.value = uri;
    writeStoredVoice(uri);
    activeVoice.value = voices.value.find((v) => v.voiceURI === uri) ?? voices.value[0] ?? null;
  }

  /**
   * 朗读一段文本。`await` 会等到播放结束（或被打断）。
   * 返回 `false` 表示平台不支持 —— 调用方据此走降级，**不要**当成「已经读过了」。
   */
  async function speak(text: string, options?: SpeakOptions): Promise<boolean> {
    if (!speech.canSpeak) return false;
    playing.value = true;
    const lang = options?.lang ?? 'zh-CN';
    // 中文才注入「挑好的中文音色」；英文等其它语言交给引擎按 lang 选，
    // 否则中文音色会把 "Good job" 念成「古德 久布」。
    const withChineseVoice = lang.toLowerCase().startsWith('zh');
    try {
      return await speech.speak(text, {
        ...options,
        lang,
        voiceURI: withChineseVoice
          ? options?.voiceURI ?? (voiceURI.value || undefined)
          : options?.voiceURI,
      });
    } finally {
      playing.value = false;
    }
  }

  function stopSpeaking(): void {
    speech.stopSpeaking();
    playing.value = false;
  }

  /** 开始一次跟读识别；失败会抛错，调用方负责降级与提示。 */
  async function listen(options?: {
    timeoutMs?: number;
    onLevel?: (value: number) => void;
  }): Promise<ListenResult> {
    listening.value = true;
    level.value = 0;
    try {
      return await speech.listen({
        lang: 'zh-CN',
        ...options,
        onLevel: (value) => {
          level.value = value;
          options?.onLevel?.(value);
        },
      });
    } finally {
      listening.value = false;
      level.value = 0;
    }
  }

  function stopListening(): void {
    speech.stopListening();
    listening.value = false;
    level.value = 0;
  }

  // 音色是异步就绪的：只在挂载时同步取一次的话，拿到的是空数组
  // （多数内核在 DOMContentLoaded 前后都不填音色），于是「可选音色」永远不出现。
  // 这里订阅 `voiceschanged`，并在组件卸载时解绑 —— 漏解绑会在多次进出设置页后
  // 累积监听器。
  let stopVoicesWatch: (() => void) | null = null;
  if (speech.canSpeak) {
    // 首次取一次：部分内核在加载时已经就绪，不发事件
    refreshVoices();
    stopVoicesWatch = onVoicesChanged(() => {
      refreshVoices();
      if (getCurrentInstance() && voices.value.length && !hasAutoSpoken.value) {
        // 音色到位后自动试听一次：让用户直接听见「换音色之后什么感觉」，
        // 而不是面对一列读不出差别的名字。
        hasAutoSpoken.value = true;
        void speak(VOICE_PREVIEW_TEXT, { rate: 0.9 });
      }
    });
  }

  // 只在组件内注册生命周期钩子：在 store / 工具函数里调用 useSpeech() 时
  // 没有当前实例，此时强行 onUnmounted 会抛警告。
  if (getCurrentInstance()) {
    onUnmounted(() => {
      speech.stopSpeaking();
      speech.stopListening();
      stopVoicesWatch?.();
      stopVoicesWatch = null;
    });
  }

  return {
    canSpeak: speech.canSpeak,
    canListen: speech.canListen,
    canHearSound: speech.canHearSound,
    playing,
    listening,
    level,
    voices,
    voiceURI,
    activeVoice,
    refreshVoices,
    setVoice,
    speak,
    stopSpeaking,
    listen,
    stopListening,
  };
}
