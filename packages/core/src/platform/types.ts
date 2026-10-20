/**
 * 平台能力接口 —— **只定义，不实现**。
 *
 * core 必须零平台依赖（不出现 window / document / localStorage / indexedDB / axios），
 * 平台实现由各外壳在 `apps/<外壳>/src/platform/` 内提供，通过依赖注入交给 core（见 06-1 §2.9.1/2.9.2）。
 */

import type { ClientCapabilities } from '../types/api';

/** 轻量偏好存储（localStorage）。⚠️ 仅允许存**会话 Token 一个键**，禁止放任何业务数据。 */
export interface PreferenceAdapter {
  get(key: string): string | null;
  set(key: string, value: string): void;
  remove(key: string): void;
}

/** HTTP 客户端（axios / fetch / uni.request 由外壳实现）。 */
export interface HttpAdapter {
  request<T>(config: {
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    url: string;
    params?: Record<string, unknown>;
    data?: unknown;
    headers?: Record<string, string>;
    timeoutMs?: number;
  }): Promise<T>;
}

/** 静态资源缓存（Cache Storage）。 */
export interface AssetCacheAdapter {
  match(url: string): Promise<Response | null>;
  put(url: string, response: Response): Promise<void>;
}

export interface ClockAdapter {
  now(): Date;
}

export interface LoggerAdapter {
  debug(msg: string, meta?: unknown): void;
  info(msg: string, meta?: unknown): void;
  warn(msg: string, meta?: unknown): void;
  error(msg: string, meta?: unknown): void;
}

/**
 * 朗读（TTS）参数。
 *
 * 启蒙场景默认**放慢语速**（`rate` 0.85）：成人语速下 6 岁孩子听不清声调，
 * 「听音选字」类题型会退化成瞎猜。语速是业务参数，不是平台参数，
 * 所以由调用方（学科包/视图）决定，平台只负责如实执行。
 */
export interface SpeakOptions {
  /** BCP-47 语言标签，默认 `zh-CN` */
  lang?: string;
  /** 语速 0.1–10，默认 0.85（启蒙放慢） */
  rate?: number;
  /** 音调 0–2，默认 1 */
  pitch?: number;
  /** 音量 0–1，默认 1 */
  volume?: number;
  /**
   * 是否打断正在播放的内容，默认 `true`。
   * 连续点两个字时若为 false 会**排队**播放，孩子先听完上一句才听到这一句，
   * 体感上像是「卡了」。
   */
  interrupt?: boolean;
  /**
   * 指定的音色 `voiceURI`。
   *
   * ⛔ 传一个当前平台**没有**的音色 URI 不会报错 —— 引擎会静默回落到默认音色。
   * 因此这个字段是「尽力而为」的请求，不是保证；需要确认可用音色请先调
   * `listVoices()`。留空表示由平台挑默认。
   *
   * 为什么需要它：各家系统的默认中文音色差别很大 —— 部分设备默认音色是
   * 「老式朗读机」音色，机械且平，启蒙听感很差；同台设备往往还装了 2–3 个
   * 可选的中文音色（童声、男声、神经网络音色）。让用户在设置里挑一次，
   * 比我们在代码里赌一个默认值可靠得多。
   */
  voiceURI?: string;
}

/** 可选朗读音色（由平台运行时枚举，不写死任何具体音色名）。 */
export interface SpeechVoice {
  /** `voiceURI`，朗读时回传 */
  voiceURI: string;
  /** 展示名，如「Tingting」 */
  name: string;
  /** 语言标签，如 `zh-CN` */
  lang: string;
  /** 平台是否标注为本地音色（离线可用）。本地音色在无网时仍能读。 */
  localService: boolean;
}

/** 跟读识别结果。 */
export interface ListenResult {
  /** 识别到的文本（已去掉空白） */
  transcript: string;
  /**
   * 引擎置信度 0–1；多数引擎（含 Chrome 的中文识别）**不给**这个值，
   * 拿不到时一律为 `null`。⚠️ 不要用别的量（长度、相似度）去填这个字段，
   * 填充值与「引擎真的给了」在类型上无法区分，界面会显示一个假分数。
   */
  confidence: number | null;
  /**
   * 只检测到了「有人说话」，**没有拿到文本**。
   *
   * 什么时候会出现：设备有麦克风、也真的听到了声音，但识别引擎不可用
   * （典型是 Chrome 自带的识别要连境外服务器，网络到不了）。
   * 此时不能判「读对了没有」，只能确认「你确实读了」——
   * 界面必须把这一点写在脸上，⛔ 不得当成识别成功。
   */
  soundOnly?: boolean;
  /** 本次采集到的最大音量 0–1（仅供界面做「麦克风在工作」的提示）。 */
  peak?: number;
}

/**
 * 语音适配器 —— **只定义，不实现**（平台实现见各外壳 `src/platform/speech.ts`）。
 *
 * 本轮方案（已与产品确认）：**只用浏览器原生免费能力**
 *   - 朗读：`speechSynthesis` + `SpeechSynthesisUtterance`
 *   - 跟读：`SpeechRecognition` / `webkitSpeechRecognition`
 * 不接任何付费 SDK、不发任何音频到服务端 —— 孩子的录音不出设备。
 *
 * 两条硬纪律：
 *   ① `canSpeak` / `canListen` **如实上报**。不支持就 false，由业务组件走降级
 *      （跟读退化为「我听过了」按钮），**不得伪造「读对了」**。
 *   ② 跟读判定只回答「有没有读到目标字词」，**不做发音打分**。
 *      音素级打分需要云端付费评测（`enableCloudAssessment` 开关），
 *      没接该能力时用字符串相似度冒充分数，本质是在骗孩子。
 */
export interface SpeechAdapter {
  /** 是否支持朗读（TTS） */
  readonly canSpeak: boolean;
  /** 是否支持跟读识别（ASR） */
  readonly canListen: boolean;
  /**
   * 能否至少「听到声音」（麦克风可采集）。
   *
   * 与 `canListen` 分开：识别引擎可能没有（Firefox / 部分 WebView），
   * 也可能是坏的（国内网络到不了 Chrome 的识别服务），但麦克风本身是好的。
   * 此时只能确认「有人在读」，**不能**判断读得对不对 ——
   * 界面必须把这条差别说出来（`ListenResult.soundOnly`）。
   */
  readonly canHearSound: boolean;
  /** 朗读一段文本；resolve `true` 表示播放结束，`false` 表示平台不支持（调用方走降级） */
  speak(text: string, options?: SpeakOptions): Promise<boolean>;
  /**
   * 列出**当前设备可用**的朗读音色。
   *
   * ⚠️ 必须在 `voiceschanged` 事件之后再调：多数内核在页面刚加载时
   * 返回空数组，音色是异步装载的。所以本方法返回的是**响应式读取**，
   * 实现方需要保证在事件触发后调用方能拿到最新值。
   */
  listVoices(lang?: string): SpeechVoice[];
  /** 停止当前朗读 */
  stopSpeaking(): void;
  /** 当前是否正在朗读 */
  isSpeaking(): boolean;
  /**
   * 开始一次跟读识别，resolve 出最终识别文本。
   * 不支持 / 无权限 / 无结果 / 超时一律 **reject**，由调用方降级（不要吞掉后当成功）。
   */
  listen(options?: {
    lang?: string;
    timeoutMs?: number;
    /** 实时音量回调（0–1）：界面用它画「麦克风正在听」的电平条。 */
    onLevel?: (level: number) => void;
  }): Promise<ListenResult>;
  /** 中止识别（用户中途放弃） */
  stopListening(): void;
  /** 释放资源（组件卸载、页面离开时调用） */
  dispose(): void;
}

export interface PlatformContext {
  /**
   * 平台上下文只暴露 `preference`（凭据与 UI 偏好），不暴露业务数据存储。
   * 学习数据已全部服务端化，浏览器不再持有业务数据；
   * 外壳只暴露 `preference`，且它**只承载会话 Token**。
   */
  preference: PreferenceAdapter;
  http: HttpAdapter;
  clock: ClockAdapter;
  logger: LoggerAdapter;
  /**
   * 语音能力（朗读 + 跟读）。
   * 浏览器原生实现在 `apps/web/src/platform/speech.ts`；
   * 小程序等外壳若不实现，必须注入一个 `canSpeak/canListen` 均为 false 的空实现 ——
   * 让 `platform.speech` 恒存在，调用方只判断能力、不判断「有没有这个对象」。
   */
  speech: SpeechAdapter;
  capabilities: ClientCapabilities;
  /** 客户端标识（注入请求头用） */
  client: {
    client: string;
    platform: string;
    deviceForm: string;
    version: string;
    /**
     * 本机设备标识（持久化的随机 id，非用户信息）。
     *
     * 用途单一但关键：登录时随 `body.client.client_id` 上报，服务端据此把
     * 「同一账号的不同设备」存成**各自独立**的会话记录。
     * 缺了它，服务端只能按客户端形态指纹认设备，同形态的两台设备会互相覆盖
     * Refresh Token —— 表现是「一台登录，另一台被踢下线」。
     */
    clientId: string;
  };
}
