<script setup lang="ts">
/**
 * GuideBubble —— 学习伙伴的引导气泡（业务组件）。
 *
 * 存在的理由：启蒙人群**看不懂界面上的字**。纯文字的操作说明（「先看字卡，再进入闯关」）
 * 对他们等于不存在。伙伴用口语把下一步说出来，是「互动和引导」最省成本的一环。
 *
 * 设计要点：
 *   - 文案要**短、口语、第二人称**（「我们一起读读这个字吧」），不要书面语；
 *   - 默认**不自动朗读**：浏览器对「页面加载即发声」的策略不一致，
 *     有的内核会静默丢弃（表现为「有时有声音有时没有」，比一直没声音更难排查）。
 *     由父组件在用户第一次点击之后再打开 `autoSpeak`；
 *   - 头像用**孩子自己选的那只**（`child.avatar_key` → `AVATAR_LABELS`）。
 *
 * ⛔ 曾经的写法是「伙伴用 emoji」：一来省资源，二来各端一致。但那样伙伴就**永远是一只兔子**，
 *    孩子在设置页选了熊猫、企鹅，关卡里的伙伴照样是 🐰 —— 用户侧只能读成「我选的没生效」。
 *    情绪（开心 / 加油 / 思考）**不再顶掉头像**，改成头像右下角的角标。
 */
import { computed, ref, watch } from 'vue';

import { avatarImagePath, avatarLabel, AVATAR_LABELS, DEFAULT_AVATAR } from '@study-club/core';

import { useCompanion } from '@/composables/useCompanion';
import { useSpeech } from '@/composables/useSpeech';

const props = withDefaults(
  defineProps<{
    /** 引导语（口语、简短） */
    text: string;
    /** 伙伴名字；缺省跟随头像（选了熊猫就叫「熊猫」） */
    name?: string;
    mood?: 'idle' | 'happy' | 'cheer' | 'think';
    /** 是否在文案变化时自动朗读（建议在用户首次交互后再打开） */
    autoSpeak?: boolean;
    /** 是否提供「再听一遍」按钮 */
    showSpeak?: boolean;
    /** 头像 key 覆盖；缺省取当前孩子的选择 */
    avatarKey?: string;
  }>(),
  {
    mood: 'idle',
    autoSpeak: false,
    showSpeak: true,
  },
);

const companion = useCompanion();

/** 传入的 key 只认已登记的动物；其余（含 `asset:` 自定义图）一律回落到孩子的选择。 */
const avatarKey = computed(() => {
  const explicit = props.avatarKey;
  if (explicit && (explicit as keyof typeof AVATAR_LABELS) in AVATAR_LABELS) return explicit;
  return companion.avatarKey.value || DEFAULT_AVATAR;
});

const displayName = computed(() => props.name?.trim() || avatarLabel(avatarKey.value));
const imagePath = computed(() => avatarImagePath(avatarKey.value));

/** 情绪角标：只有非 idle 才露头，避免遮住头像本身。 */
const MOOD_BADGE: Record<'happy' | 'cheer' | 'think', string> = {
  happy: '🎉',
  cheer: '💪',
  think: '🤔',
};
const moodBadge = computed(() => (props.mood === 'idle' ? '' : MOOD_BADGE[props.mood]));

const { canSpeak, speak } = useSpeech();

const speaking = ref(false);

async function say(): Promise<void> {
  if (!canSpeak || !props.text.trim()) return;
  speaking.value = true;
  try {
    // 引导语用接近正常语速：放慢会让整句话失去语气，听起来像机器报数。
    await speak(props.text, { rate: 0.95 });
  } finally {
    speaking.value = false;
  }
}

watch(
  () => [props.text, props.autoSpeak] as const,
  ([, auto]) => {
    if (auto) void say();
  },
);

defineExpose({ say });
</script>

<template>
  <div class="guide" :class="`guide--${mood}`">
    <span class="guide__face" aria-hidden="true">
      <img class="guide__face-img" :src="imagePath" alt="" draggable="false" />
      <span v-if="moodBadge" class="guide__mood">{{ moodBadge }}</span>
    </span>
    <div class="guide__bubble">
      <p class="guide__name">{{ displayName }}</p>
      <p class="guide__text">{{ text }}</p>
      <button
        v-if="showSpeak && canSpeak"
        type="button"
        class="guide__speak clickable"
        :class="{ 'guide__speak--on': speaking }"
        :aria-label="`听${displayName}再说一遍`"
        @click="say"
      >
        {{ speaking ? '🔈 正在说…' : '🔊 再说一遍' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.guide {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
}

.guide__face {
  position: relative;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-surface-alt);
  border: 2px solid var(--color-border);
}

/* 头像本身自带圆角，不用给父级 overflow:hidden —— 否则右下角的情绪角标会被裁掉 */
.guide__face-img {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

.guide__mood {
  position: absolute;
  right: -4px;
  bottom: -4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  font-size: 12px;
  line-height: 1;
}

.guide--happy .guide__face {
  border-color: var(--color-success);
}

.guide--cheer .guide__face {
  border-color: var(--color-primary-strong);
  animation: guide-bounce 1.2s ease-in-out infinite;
}

.guide__bubble {
  position: relative;
  flex: 1;
  min-width: 0;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
}

/* 气泡小尖角，指向伙伴 */
.guide__bubble::before {
  content: '';
  position: absolute;
  left: -7px;
  top: 16px;
  width: 12px;
  height: 12px;
  background: var(--color-surface-alt);
  border-left: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  transform: rotate(45deg);
}

.guide__name {
  font-size: var(--font-xs);
  color: var(--color-text-muted);
}

.guide__text {
  font-size: var(--font-body);
  line-height: 1.5;
}

.guide__speak {
  margin-top: var(--space-2xs);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-pill);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  font-size: var(--font-xs);
  color: var(--color-text-muted);
}

.guide__speak--on {
  color: var(--color-info);
  border-color: var(--color-info);
}

@keyframes guide-bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
</style>
