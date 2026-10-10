/**
 * 平台实现：语音（朗读 + 跟读识别）。
 *
 * 方案：**只用浏览器原生免费能力**，不引入任何付费 SDK、不向任何第三方发请求。
 *   - 朗读：`speechSynthesis`（Chrome / Edge / Safari / 国产 Chromium 内核均可用）
 *   - 跟读：`SpeechRecognition`（Chrome / Edge 需 `webkit` 前缀；**Firefox 不支持**）
 *
 * 隐私：麦克风录音只在设备端由浏览器转写，`SpeechAdapter` 不持有也不外传音频；
 * 说明文案里必须把这一点告诉家长（设置页已有隐私说明）。
 *
 * 为什么不在这里做「发音打分」：
 *   原生 ASR 只给最终文本（中文还常常不给 confidence），拿「字符串像不像」
 *   冒充分数会让一个把「妈」读成「马」的孩子得到 95 分。真正的音素级评测
 *   属于付费云端能力（`enableCloudAssessment`），没接就不能给分。
 *
 * 为什么在这里挑音色（而不是让 `speak` 直接用系统默认）：
 *   各家系统的默认中文音色差别很大，部分设备默认就是「老式朗读机」音色 ——
 *   机械、平、声调几乎听不出来，这正是「声音太难听」的主要来源。
 *   同一台设备往往还装了 2–3 个可选中文音色（童声、女声、神经网络音色），
 *   启蒙场景值得让用户挑一次。挑选规则见 `VOICE_NAME_PREFERENCE`，
 *   它是**可解释的数据**而不是玄学：挑不中就退回第一个本地音色。
 *
 * ⚠️ 所有浏览器 API 都收敛在本文件：视图层只通过 `useSpeech()` 使用，
 * 不允许在组件里直接出现 `speechSynthesis` / `SpeechRecognition`（06-1 §2.9.2）。
 */

import type { ListenResult, SpeakOptions, SpeechAdapter, SpeechVoice } from '@study-club/core';

// ---------------------------------------------------------------------------
// Web Speech API 的最小结构类型
// 之所以自己写：`SpeechRecognition` 在 lib.dom 里尚未标准化（多数 TS 版本没有），
// 而 `any` 会让后面所有用法都失去检查。
// ---------------------------------------------------------------------------

interface SpeechRecognitionAlternativeLike {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionResultLike {
  readonly length: number;
  readonly isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  readonly length: number;
  [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionErrorEventLike {
  error: string;
  message?: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechWindow {
  SpeechRecognition?: SpeechRecognitionCtor;
  webkitSpeechRecognition?: SpeechRecognitionCtor;
}

/** 跟读识别的默认超时：到点还没出结果就当没读到，避免按钮一直转圈。 */
const DEFAULT_LISTEN_TIMEOUT_MS = 6000;

/** 音色列表变化事件的封装名（部分内核只有带前缀的那个）。 */
const VOICES_CHANGED_EVENTS = ['voiceschanged', 'webkitvoiceschanged'] as const;

/** 判定一个音色是否适合中文朗读。 */
function isChineseVoice(voice: SpeechSynthesisVoice, lang: string): boolean {
  const voiceLang = (voice.lang ?? '').toLowerCase();
  // zh / zh-CN / zh-Hans-CN / cmn-Hans-CN 都算中文；cmn 是部分内核用的语言码
  return (
    voiceLang === lang.toLowerCase() ||
    voiceLang.startsWith('zh') ||
    voiceLang.startsWith('cmn')
  );
}

function toSpeechVoice(voice: SpeechSynthesisVoice): SpeechVoice {
  return {
    voiceURI: voice.voiceURI,
    name: voice.name,
    lang: voice.lang,
    localService: voice.localService,
  };
}

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as SpeechWindow;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** 平台是否支持朗读。 */
export function canSpeechSynthesis(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.speechSynthesis !== 'undefined' &&
    typeof window.SpeechSynthesisUtterance === 'function'
  );
}

/** 平台是否支持语音识别。 */
export function canSpeechRecognition(): boolean {
  return getRecognitionCtor() !== null;
}

/**
 * 空实现：平台无语音能力时注入。
 * 存在的意义是让 `platform.speech` 恒存在，调用方只需判断 `canSpeak/canListen`，
 * 不必写 `platform.speech?.xxx` 这类到处 `?.` 的防御代码。
 */
export function createNullSpeechAdapter(): SpeechAdapter {
  return {
    canSpeak: false,
    canListen: false,
    speak: () => Promise.resolve(false),
    listVoices: () => [],
    stopSpeaking: () => undefined,
    isSpeaking: () => false,
    listen: () => Promise.reject(new Error('SPEECH_UNSUPPORTED')),
    stopListening: () => undefined,
    dispose: () => undefined,
  };
}

/**
 * 平台当前可用的音色（已过滤为中文，按「本地优先」排序）。
 *
 * 排序理由：本地音色（`localService`）在无网时仍能朗读，而启蒙场景
 * 经常发生在地铁、车上、信号不好的地方 —— 联网音色一旦不可用就完全不出声。
 * 同组内保持平台顺序（那通常是其推荐序）。
 */
export function listChineseVoices(lang = 'zh-CN'): SpeechVoice[] {
  if (!canSpeechSynthesis()) return [];
  const raw = window.speechSynthesis.getVoices() ?? [];
  return raw
    .filter((voice) => isChineseVoice(voice, lang))
    .map(toSpeechVoice)
    .sort((a, b) => Number(b.localService) - Number(a.localService));
}

/**
 * 在候选音色里挑一个「最可能适合教孩子」的。
 *
 * 为什么不直接用 `getVoices()[0]`：各家系统的第一个音色往往是**最机械的那个**
 * （老式 eSpeak / 早期 TTS 引擎），这正是「声音太难听」的常见来源。
 * 这里用一组可解释的偏好规则去挑，规则写在 `VOICE_NAME_PREFERENCE` 里，
 * 挑不中就退回第一个本地音色 —— 规则是数据不是玄学，便于按反馈调整。
 */
const VOICE_NAME_PREFERENCE: readonly string[] = [
  // 神经网络 / 增强音色：多数系统会用这些词标注音质档次
  'neural',
  'enhanced',
  'premium',
  'natural',
  'siri',
  // 常见的中文童声/女声命名
  'tingting',
  'ting-ting',
  'meijia',
  'sinji',
  'huihui',
  'yaoyao',
  'xiaoxiao',
  'google 普通话',
  '普通话',
];

export function pickChildFriendlyVoice(voices: SpeechVoice[]): SpeechVoice | null {
  if (!voices.length) return null;
  const lower = voices.map((v) => ({ v, key: v.name.toLowerCase() }));
  for (const preferred of VOICE_NAME_PREFERENCE) {
    const hit = lower.find((item) => item.key.includes(preferred));
    if (hit) return hit.v;
  }
  return voices[0] ?? null;
}

export function createSpeechAdapter(): SpeechAdapter {
  const canSpeak = canSpeechSynthesis();
  const canListen = canSpeechRecognition();

  if (!canSpeak && !canListen) return createNullSpeechAdapter();

  const synth = canSpeak ? window.speechSynthesis : null;
  const RecognitionCtor = getRecognitionCtor();

  /** 当前正在进行的识别实例；同一时刻只允许一个，否则两条流会互相抢麦克风。 */
  let activeRecognition: SpeechRecognitionLike | null = null;
  /**
   * 本次会话已选定的音色。
   *
   * 缓存下来而不是每次朗读都重算：`getVoices()` 在部分内核上开销不小，
   * 而音色在一次会话里不会变。
   */
  let cachedVoiceURI: string | null = null;

  function listVoices(lang?: string): SpeechVoice[] {
    return listChineseVoices(lang ?? 'zh-CN');
  }

  function stopSpeaking(): void {
    if (!synth) return;
    try {
      synth.cancel();
    } catch {
      // 某些内核在无正在播放内容时 cancel 会抛，属于噪音，忽略。
    }
  }

  /**
   * 解析本次朗读实际使用的音色。
   *
   * 顺序：显式指定 → 会话缓存 → 启发式优选 → 平台默认。
   * 指定与缓存的 URI 都要校验**当前仍可用** —— 用户换设备、浏览器升级后
   * 旧的 URI 会失效，此时静默回落而不是不出声。
   */
  function resolveVoice(requested?: string): SpeechSynthesisVoice | null {
    const available = synth?.getVoices() ?? [];
    if (!available.length) return null;

    if (requested) {
      const hit = available.find((v) => v.voiceURI === requested);
      if (hit) return hit;
    }
    if (cachedVoiceURI) {
      const hit = available.find((v) => v.voiceURI === cachedVoiceURI);
      if (hit) return hit;
      cachedVoiceURI = null;
    }
    const preferred = pickChildFriendlyVoice(listChineseVoices('zh-CN'));
    if (preferred) {
      cachedVoiceURI = preferred.voiceURI;
      return available.find((v) => v.voiceURI === preferred.voiceURI) ?? null;
    }
    return null;
  }

  function speak(text: string, options: SpeakOptions = {}): Promise<boolean> {
    if (!synth) return Promise.resolve(false);
    const content = text.trim();
    if (!content) return Promise.resolve(false);

    return new Promise<boolean>((resolve) => {
      // 默认打断：连着点两个字时，不打断会排队，孩子要先听完上一句。
      if (options.interrupt !== false) stopSpeaking();

      let settled = false;
      const settle = (played: boolean): void => {
        if (settled) return;
        settled = true;
        resolve(played);
      };

      const utterance = new SpeechSynthesisUtterance(content);
      utterance.lang = options.lang ?? 'zh-CN';
      utterance.rate = options.rate ?? 0.85;
      // 音调略微上抬（1.05）：默认 1.0 在部分内核上偏低偏闷，
      // 孩子听「水」和「谁」的差别靠声调，偏低会让声调对比变弱。
      utterance.pitch = options.pitch ?? 1.05;
      utterance.volume = options.volume ?? 1;

      const voice = resolveVoice(options.voiceURI);
      if (voice) {
        utterance.voice = voice;
        // ⚠️ 必须同时对齐 lang：部分内核在显式给了 voice 之后，
        // 若 lang 与音色语言不一致会用**错误语言的发音规则**去读它，
        // 表现为「声音选对了但念得像外语」。
        utterance.lang = voice.lang || utterance.lang;
      }

      utterance.onend = () => settle(true);
      // `interrupted` / `canceled` 也是 onerror 之一：用户主动打断不该算失败，
      // 但这里无法区分「平台不支持」和「被 cancel」，统一按「已结束」处理。
      utterance.onerror = () => settle(true);

      try {
        synth.speak(utterance);
      } catch {
        settle(false);
      }
    });
  }

  function stopListening(): void {
    const rec = activeRecognition;
    activeRecognition = null;
    if (!rec) return;
    try {
      rec.abort();
    } catch {
      // 同上，忽略 abort 的噪音异常。
    }
  }

  function listen(options: { lang?: string; timeoutMs?: number } = {}): Promise<ListenResult> {
    return new Promise<ListenResult>((resolve, reject) => {
      if (!RecognitionCtor) {
        reject(new Error('SPEECH_UNSUPPORTED'));
        return;
      }

      // 上一次还没结束就再点一次：先收掉旧的，避免两个识别实例抢麦克风。
      stopListening();

      const recognition = new RecognitionCtor();
      activeRecognition = recognition;
      recognition.lang = options.lang ?? 'zh-CN';
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      let settled = false;
      const timer = window.setTimeout(() => {
        finish(() => reject(new Error('SPEECH_TIMEOUT')));
        stopListening();
      }, options.timeoutMs ?? DEFAULT_LISTEN_TIMEOUT_MS);

      function finish(action: () => void): void {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (activeRecognition === recognition) activeRecognition = null;
        action();
      }

      recognition.onresult = (event) => {
        const list = event.results;
        const last = list.length > 0 ? list[list.length - 1] : undefined;
        const alternative = last && last.length > 0 ? last[0] : undefined;
        const transcript = (alternative?.transcript ?? '').replace(/\s+/g, '');
        // 中文识别普遍返回 confidence 0 —— 0 意味着「没给」，不是「很低」。
        const raw = alternative?.confidence;
        const confidence = typeof raw === 'number' && raw > 0 ? raw : null;

        if (!transcript) {
          finish(() => reject(new Error('SPEECH_EMPTY')));
          return;
        }
        finish(() => resolve({ transcript, confidence }));
      };

      recognition.onerror = (event) => {
        const reason = (event.error || 'error').toUpperCase();
        finish(() => reject(new Error(`SPEECH_${reason}`)));
      };

      // onend 在「没识别到任何结果」时是唯一的收尾信号。
      recognition.onend = () => finish(() => reject(new Error('SPEECH_NO_RESULT')));

      try {
        recognition.start();
      } catch (err) {
        finish(() =>
          reject(err instanceof Error ? err : new Error('SPEECH_START_FAILED')),
        );
      }
    });
  }

  return {
    canSpeak,
    canListen,
    speak,
    listVoices,
    stopSpeaking,
    isSpeaking: () => (synth ? synth.speaking : false),
    listen,
    stopListening,
    dispose: () => {
      stopSpeaking();
      stopListening();
      cachedVoiceURI = null;
    },
  };
}

/**
 * 订阅「音色列表就绪」事件。
 *
 * ⚠️ 必须靠事件而不是「页面加载完就取」：Chrome / Edge / Safari 的
 * `getVoices()` 在 `DOMContentLoaded` 前后行为不一致 —— 多数内核此时
 * 返回**空数组**，要等 `voiceschanged` 事件才填上。
 * 只在 onMounted 里同步取一次，表现为「音色列表永远是空的」，
 * 于是设置页的音色选择器不会出现，用户也就无从「换个音色」。
 */
export function onVoicesChanged(handler: () => void): () => void {
  if (!canSpeechSynthesis()) return () => undefined;
  const target = window.speechSynthesis as unknown as {
    addEventListener?: (type: string, cb: () => void) => void;
    removeEventListener?: (type: string, cb: () => void) => void;
  };
  // 优先用 addEventListener（带 webkit 前缀的那个事件名只存在于老内核）
  const bound: string[] = [];
  for (const event of VOICES_CHANGED_EVENTS) {
    if (typeof target.addEventListener !== 'function') break;
    target.addEventListener(event, handler);
    bound.push(event);
  }
  return () => {
    if (typeof target.removeEventListener !== 'function') return;
    for (const event of bound) target.removeEventListener(event, handler);
  };
}
