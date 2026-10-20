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

// ---------------------------------------------------------------------------
// 麦克风电平（「声音模式」）
//
// 为什么要它：Chrome 自带的语音识别要把音频送到**境外**服务器，国内网络经常
// 直接 `network` 失败 —— 表现就是「对着麦克风读，界面毫无反应」，家长只会
// 认为功能坏了。这里用 `getUserMedia` + `AnalyserNode` 做一个本地音量检测：
// 拿不到文字时，至少能如实回答「有没有听到你说话」。
//
// ⛔ 它**不是**语音识别：只能判断「有人说话」，不能判断读得对不对。
//    界面上必须把这一点说清楚，绝不能拿它冒充满分。
// ---------------------------------------------------------------------------

/** 判定「真的有人说话」的音量门限（归一化 0–1）。 */
const SPEECH_PEAK_THRESHOLD = 0.16;

/** 至少要有这么多帧超过门限（约 200ms）才算「读了一句」，排除咳嗽/碰麦。 */
const SPEECH_MIN_FRAMES = 12;

/** 采集期间的电平回调与统计。 */
interface MicMonitor {
  /** 本次采集到的最大音量 0–1 */
  peak(): number;
  /** 是否检测到「持续的人声」 */
  voiced(): boolean;
  stop(): void;
}

type AudioContextCtor = new () => AudioContext;

function getAudioContextCtor(): AudioContextCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    AudioContext?: AudioContextCtor;
    webkitAudioContext?: AudioContextCtor;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

/**
 * 打开麦克风并开始采样电平。拿不到麦克风（无权限 / 无设备）时返回 `null`，
 * **不抛错** —— 权限问题交给识别引擎去报准确错误码，避免同一个问题两种说法。
 */
async function startMicMonitor(onLevel?: (level: number) => void): Promise<MicMonitor | null> {
  const media = typeof navigator !== 'undefined' ? navigator.mediaDevices : undefined;
  const Ctor = getAudioContextCtor();
  if (!media?.getUserMedia || !Ctor) return null;

  let stream: MediaStream;
  try {
    stream = await media.getUserMedia({ audio: true });
  } catch {
    return null;
  }

  let ctx: AudioContext;
  try {
    ctx = new Ctor();
  } catch {
    for (const track of stream.getTracks()) track.stop();
    return null;
  }

  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.6;
  source.connect(analyser);
  const buffer = new Uint8Array(analyser.fftSize);

  let peak = 0;
  let voicedFrames = 0;
  let raf = 0;
  let stopped = false;

  const tick = (): void => {
    if (stopped) return;
    analyser.getByteTimeDomainData(buffer);
    let sum = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const v = (buffer[i]! - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / buffer.length);
    // 乘一个经验系数，把「正常说话」拉到 0.3–0.6 的可读区间
    const level = Math.min(1, rms * 6);
    if (level > peak) peak = level;
    if (level >= SPEECH_PEAK_THRESHOLD) voicedFrames += 1;
    onLevel?.(level);
    raf = window.requestAnimationFrame(tick);
  };
  raf = window.requestAnimationFrame(tick);

  return {
    peak: () => peak,
    voiced: () => voicedFrames >= SPEECH_MIN_FRAMES,
    stop: () => {
      stopped = true;
      if (raf) window.cancelAnimationFrame(raf);
      try {
        source.disconnect();
      } catch {
        /* 忽略 */
      }
      try {
        void ctx.close();
      } catch {
        /* 忽略 */
      }
      for (const track of stream.getTracks()) {
        try {
          track.stop();
        } catch {
          /* 忽略 */
        }
      }
      onLevel?.(0);
    },
  };
}

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

/** 平台能否采集麦克风（决定「只听声音」这条路走不走得通）。 */
export function canMicrophoneCapture(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
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
    canHearSound: false,
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
 * 平台当前可用的音色（已过滤为中文，优先本地音色）。
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
  // 有麦克风就能「听到声音」，与识别引擎是否可用是两件事
  const canHearSound = canMicrophoneCapture();

  if (!canSpeak && !canListen && !canHearSound) return createNullSpeechAdapter();

  const synth = canSpeak ? window.speechSynthesis : null;
  const RecognitionCtor = getRecognitionCtor();

  /** 当前正在进行的识别实例；同一时刻只允许一个，否则两条流会互相抢麦克风。 */
  let activeRecognition: SpeechRecognitionLike | null = null;

  /** 当前开着的麦克风电平采样（只用于「有没有听到声音」）。 */
  let activeMonitor: MicMonitor | null = null;

  /**
   * 同一页面会话内已确认识别引擎不可用的原因（如 `NETWORK`）。
   *
   * 记住它，是为了**不要每次都让同一个孩子等一遍失败**：
   * 第一次失败会如实报错，之后直接走「只测声音」模式。
   * 刷新页面即重置 —— 换了网络环境（比如挂上可用的网络）应该再给识别一次机会。
   */
  let asrBrokenReason: string | null = null;
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
   *
   * ⛔ 只对**中文**朗读做优选：缓存的是中文音色，拿它读英文会把
   *    「Good job」念成「古德 久布」。非中文一律交给引擎按 `lang` 挑。
   */
  function resolveVoice(requested: string | undefined, lang: string): SpeechSynthesisVoice | null {
    if (!lang.toLowerCase().startsWith('zh')) return null;
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

      const voice = resolveVoice(options.voiceURI, utterance.lang);
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

  function stopMonitor(): void {
    const monitor = activeMonitor;
    activeMonitor = null;
    monitor?.stop();
  }

  function stopListening(): void {
    const rec = activeRecognition;
    activeRecognition = null;
    if (rec) {
      try {
        rec.abort();
      } catch {
        // 同上，忽略 abort 的噪音异常。
      }
    }
    stopMonitor();
  }

  /**
   * 「声音模式」：只用麦克风电平判断「有没有在读」。
   *
   * 用于识别引擎连不上（典型是国内网络访问不了 Chrome 的识别服务）时。
   * resolve 的 `soundOnly` 明确告诉界面「没拿到文字」，不得据此判「读对了」。
   */
  function listenBySound(options: {
    timeoutMs?: number;
    onLevel?: (level: number) => void;
  } = {}): Promise<ListenResult> {
    const duration = options.timeoutMs ?? DEFAULT_LISTEN_TIMEOUT_MS;
    return startMicMonitor(options.onLevel).then((monitor) => {
      if (!monitor) return Promise.reject(new Error('SPEECH_UNSUPPORTED'));
      activeMonitor = monitor;
      return new Promise<ListenResult>((resolve, reject) => {
        const started = Date.now();
        let timer = 0;
        let settled = false;

        const finish = (action: () => void): void => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timer);
          if (activeMonitor === monitor) activeMonitor = null;
          monitor.stop();
          action();
        };

        const tick = (): void => {
          if (settled) return;
          if (monitor.voiced()) {
            finish(() =>
              resolve({
                transcript: '',
                confidence: null,
                soundOnly: true,
                peak: monitor.peak(),
              }),
            );
            return;
          }
          if (Date.now() - started >= duration) {
            finish(() => reject(new Error('SPEECH_NO_SPEECH')));
            return;
          }
          timer = window.setTimeout(tick, 100);
        };
        tick();
      });
    });
  }

  /** 识别服务明确坏掉的错误码前缀：调用方据此切成「只听声音」。 */
  const ASR_DOWN = 'SPEECH_ASR_DOWN';

  /** 走浏览器的语音识别，拿回文字。失败时按错误码 reject。 */
  function runRecognition(options: {
    lang?: string;
    timeoutMs?: number;
    onLevel?: (level: number) => void;
  }): Promise<ListenResult> {
    const Ctor = RecognitionCtor;
    if (!Ctor) return Promise.reject(new Error('SPEECH_UNSUPPORTED'));

    return new Promise<ListenResult>((resolve, reject) => {
      // 上一次还没结束就再点一次：先收掉旧的，避免两个识别实例抢麦克风。
      stopListening();

      const recognition = new Ctor();
      activeRecognition = recognition;
      recognition.lang = options.lang ?? 'zh-CN';
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      let settled = false;
      let timer = 0;
      /** 本次是否因为「识别服务连不上」而失败（决定要不要同一次按压里切成声音模式）。 */
      let broken = false;

      function finish(action: () => void): void {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (activeRecognition === recognition) activeRecognition = null;
        stopMonitor();
        action();
      }

      /**
       * 失败时的统一收尾：只要麦克风确实听到了人声，就退化为「声音模式」
       * 的结果，而不是告诉孩子「没读到」—— 后者会让一个读得很好的孩子
       * 反复重来，而真正的原因是他连不上识别服务。
       */
      function settleFailure(code: string): void {
        const monitor = activeMonitor;
        const heard = monitor?.voiced() ?? false;
        const peak = monitor?.peak() ?? 0;
        finish(() =>
          heard
            ? resolve({ transcript: '', confidence: null, soundOnly: true, peak })
            : reject(new Error(broken ? `${ASR_DOWN}:${code}` : code)),
        );
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
          settleFailure('SPEECH_EMPTY');
          return;
        }
        finish(() => resolve({ transcript, confidence }));
      };

      recognition.onerror = (event) => {
        const reason = (event.error || 'error').toUpperCase();
        // 网络 / 服务不可用是**设备层面**的坏：记住它，别每次都让孩子先等一遍失败。
        if (reason === 'NETWORK' || reason === 'SERVICE_NOT_ALLOWED' || reason === 'LANGUAGE_NOT_SUPPORTED') {
          asrBrokenReason = reason;
          broken = true;
        }
        settleFailure(`SPEECH_${reason}`);
      };

      // onend 在「没识别到任何结果」时是唯一的收尾信号。
      recognition.onend = () => settleFailure('SPEECH_NO_RESULT');

      try {
        recognition.start();
      } catch (err) {
        finish(() =>
          reject(err instanceof Error ? err : new Error('SPEECH_START_FAILED')),
        );
        return;
      }

      // 电平采样晚 250ms 才开：先让识别引擎拿到麦克风，
      // 避免两个消费者抢设备（iOS 上会直接把识别掐掉）。
      // 它只是「让孩子看见麦克风在工作」，拿不到也不影响识别。
      window.setTimeout(() => {
        if (settled || activeRecognition !== recognition) return;
        void startMicMonitor(options.onLevel).then((monitor) => {
          if (!monitor) return;
          if (settled || activeRecognition !== recognition) {
            monitor.stop();
            return;
          }
          activeMonitor = monitor;
        });
      }, 250);

      timer = window.setTimeout(
        () => settleFailure('SPEECH_TIMEOUT'),
        options.timeoutMs ?? DEFAULT_LISTEN_TIMEOUT_MS,
      );
    });
  }

  /**
   * 跟读总入口。
   *
   * 三层结构（按顺序退化，孩子只需要按一次）：
   *   ① 语音识别拿到文字 → 正常判「读到没有」；
   *   ② 识别服务连不上（国内网络访问不了 Chrome 的识别服务）→ **同一次按压里**
   *      直接切成「只听声音」，不再让孩子重按；
   *   ③ 设备压根没有识别能力 → reject `SPEECH_UNSUPPORTED`，组件退化为「我听过了」。
   */
  async function listen(options: {
    lang?: string;
    timeoutMs?: number;
    onLevel?: (level: number) => void;
  } = {}): Promise<ListenResult> {
    // 没有识别引擎（Firefox / 部分 WebView）：只要麦克风能采集，就走「只听声音」
    if (!RecognitionCtor) {
      if (canHearSound) return listenBySound(options);
      throw new Error('SPEECH_UNSUPPORTED');
    }
    // 同一页面会话内已确认识别服务不可用 → 直接走声音模式
    if (asrBrokenReason) return listenBySound(options);

    try {
      return await runRecognition(options);
    } catch (err) {
      const code = err instanceof Error ? err.message : '';
      if (!code.startsWith(ASR_DOWN)) throw err;
      // 识别服务连不上：这次按压还没结束，接着听声音（孩子不用重按）
      return listenBySound({ ...options, timeoutMs: 5000 });
    }
  }

  return {
    canSpeak,
    canListen,
    canHearSound,
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
