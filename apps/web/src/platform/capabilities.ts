/**
 * 平台实现：运行时能力探测。
 *
 * 一次性探测，产出 `ClientCapabilities` 注入 core（见 02-2 §7.3）。
 * **每个能力缺失都必须有降级路径**，本文件只负责如实上报，不做降级决策。
 *
 * ⚠️ 变更（本轮）：新增 `speech_synthesis` / `speech_recognition` ——
 * 客户端玩法的语音互动走**浏览器原生免费能力**，因此必须先把「这台设备能不能用」
 * 探测清楚，再决定「朗读按钮渲不渲染」「跟读走真识别还是走『我听过了』」。
 * 早先只有 `record`（getUserMedia）一项，它回答不了「有没有 TTS」。
 */

import type { ClientCapabilities } from '@study-club/core';

import { canSpeechRecognition, canSpeechSynthesis } from './speech';

function hasGetUserMedia(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function'
  );
}

function canRealtimeAudio(): boolean {
  if (typeof window === 'undefined') return false;
  const w = window as unknown as {
    AudioContext?: unknown;
    webkitAudioContext?: unknown;
    AudioWorkletNode?: unknown;
  };
  const Ctor = w.AudioContext ?? w.webkitAudioContext;
  return typeof Ctor === 'function' && typeof w.AudioWorkletNode === 'function';
}

function canHandwriting(): boolean {
  if (typeof window === 'undefined') return false;
  // Pointer Events + 触控/笔设备（不做 iPad 型号判定，见 02-2 §3.1）。
  const hasPointer = 'PointerEvent' in window;
  const hasCoarse = window.matchMedia?.('(pointer: coarse)').matches ?? false;
  return hasPointer && hasCoarse;
}

function canOffline(): boolean {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator;
}

function canPush(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    typeof window.Notification !== 'undefined'
  );
}

export function detectCapabilities(): ClientCapabilities {
  return {
    record: hasGetUserMedia(),
    // 本地 ASR 小模型（20–60MB）在本版本不加载，如实报 false。
    // 「跟读」走浏览器原生 SpeechRecognition，与本地模型是两码事，见下一行。
    local_asr: false,
    realtime_audio: canRealtimeAudio(),
    handwriting: canHandwriting(),
    offline: canOffline(),
    push: canPush(),
    speech_synthesis: canSpeechSynthesis(),
    speech_recognition: canSpeechRecognition(),
  };
}
