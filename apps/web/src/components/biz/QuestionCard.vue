<script setup lang="ts">
/**
 * QuestionCard —— 题目卡片（业务组件）。
 *
 * 选项排布随形态变化：手机纵向堆叠大按钮 / iPad 2×2 / 桌面横排（02-2 §3.2）。
 * 判定由父级完成（本地即时判定），本组件只做展示与选择广播。
 *
 * ⚠️ 本轮加入语音互动（启蒙人群的关键改动）：
 *   1. **题面可朗读**。孩子不识字，只把题面写在屏幕上等于没出题。
 *      「读什么」由学科包 `speechTextForQuestion` 决定（关键是别把答案读出来）。
 *   2. **听音题（audio-choice）有播放按钮**，而不是「靠家长念」。
 *   3. **跟读题（speak）没有选项**，走麦克风；设备不支持识别时降级为「我听过了」，
 *      并如实告诉用户「这台设备听不到声音」，不假装评测过了。
 *   4. **提示（hint）可折叠**：字源 / 组词 / 拼音按需展开，
 *      先让孩子自己想，想不出来再给梯子 —— 直接摊开等于送答案。
 *   5. **看图选字真的有图了**：`image-choice` 题型把字源图（象形 emoji）作为题干主图，
 *      而不是只留一句「哪个字是『流动的水』？」让孩子凭空想象。
 *      图与朗读语速都受后台玩法开关控制（在这里读 store，避免每个调用方都要记得传参）。
 *
 * ⚠️ **文案必须与实际交互一致**：跟读按钮的交互是**长按**（见 ReadAlongButton），
 * 所以这里的按钮文案与提示都写「按住」而不是「点一下」。
 * 提示与行为不符时，孩子按提示操作却什么都没发生 —— 启蒙产品里这种
 * 「界面看起来没问题、功能却是坏的」最难排查。
 */
import { computed, ref, watch } from 'vue';

import { QUESTION_TYPE, useSiteConfigStore } from '@study-club/core';
import type { Question, QuestionOption } from '@study-club/core';
import { readingMatches, speechTextForQuestion } from '@study-club/subject-hanzi';

import GlyphFigure from '@/components/biz/GlyphFigure.vue';
import ReadAlongButton from '@/components/biz/ReadAlongButton.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import { useSpeech } from '@/composables/useSpeech';

const props = withDefaults(
  defineProps<{
    question: Question;
    /** 已作答后禁用 */
    disabled?: boolean;
    /** 已选中的选项（存选项文本，与 `Question.answer` 同一口径） */
    selected?: string | null;
    /** 是否已揭晓正确答案（展示对错着色） */
    revealed?: boolean;
    /** 是否在题目变化时自动朗读题面（默认开；启蒙场景强烈建议保持开启） */
    autoSpeak?: boolean;
    /** 是否显示「给点提示」 */
    showHint?: boolean;
  }>(),
  {
    disabled: false,
    selected: null,
    revealed: false,
    autoSpeak: true,
    showHint: true,
  },
);

const emit = defineEmits<{
  (e: 'select', option: string): void;
  (e: 'speak', payload: { matched: boolean; transcript: string; degraded: boolean }): void;
}>();

const siteConfig = useSiteConfigStore();

const optionCount = computed(() => props.question.options.length);

/** 拼音题的选项是拼音，需要与汉字区分渲染（拼音不宜用大字号宋体）。 */
const isPinyin = computed(() => props.question.question_type === QUESTION_TYPE.pinyinMatch);

/** 跟读题：没有选项，靠麦克风作答。 */
const isSpeak = computed(() => props.question.question_type === QUESTION_TYPE.speak);

/** 听音题：需要播放读音。 */
const isAudio = computed(() => props.question.question_type === QUESTION_TYPE.audioChoice);

/** 看图选字：题干主图就是字源图。 */
const isImageChoice = computed(() => props.question.question_type === QUESTION_TYPE.imageChoice);

/** 该题的朗读文本；为 null 表示这题不该朗读。 */
const speechText = computed(() => speechTextForQuestion(props.question));

/**
 * 朗读语速：玩法配置的 `speak_rate` 是整体档位（默认 0.8），
 * 各处的基速按比例缩放并夹在可听区间 —— 单字比词句更慢这个相对关系要保住。
 */
const rateScale = computed(() => siteConfig.gameplay.speak_rate / 0.8);
function rate(base: number): number {
  return Math.min(1.2, Math.max(0.4, Number((base * rateScale.value).toFixed(2))));
}

/**
 * 题干主图（看图选字）。
 *
 * 只在 `image-choice` 且开关打开时展示：其他题型的题干给图会把注意力从字上带走；
 * 而「给意思选字」本身不带图，硬塞一张图等于变成另一种题型。
 */
const stemGlyph = computed(() =>
  siteConfig.gameplay.show_pictograph && isImageChoice.value ? props.question.glyph ?? null : null,
);

/** 「给点提示」是否展开。默认收起：直接摊开等于送答案。 */
const hintOpen = ref(false);

const hintWords = computed(() => (props.question.words ?? []).slice(0, 4));
/**
 * 拼音提示。
 * ⚠️ 拼音题的**答案就是拼音**，此时必须藏起来 —— 提示变答案是最典型的一种
 * 「界面看起来没问题、题目却废了」的缺陷。
 */
const hintPinyin = computed(() =>
  props.question.question_type === QUESTION_TYPE.pinyinMatch ? null : props.question.pinyin ?? null,
);
/**
 * 字源提示。
 * ⚠️ 同理：看图选字题**已经把字源图放在题干上了**，再列一遍是纯重复。
 */
const hintPictograph = computed(() => (isImageChoice.value ? null : props.question.pictograph ?? null));
const hasHint = computed(
  () => Boolean(hintPictograph.value) || Boolean(hintPinyin.value) || hintWords.value.length > 0,
);

function optionState(option: QuestionOption): 'correct' | 'wrong' | 'idle' {
  if (!props.revealed) return 'idle';
  if (option.char === props.question.answer) return 'correct';
  if (option.char === props.selected) return 'wrong';
  return 'idle';
}

function onSelect(option: QuestionOption): void {
  if (props.disabled) return;
  // 对外仍广播选项文本：判分与提交都以文本为准，选项顺序变化不影响任何记录
  emit('select', option.char);
}

// 换题即收起提示：上一题的提示留在屏幕上会干扰下一题。
watch(
  () => props.question.id,
  () => {
    hintOpen.value = false;
  },
);

const { speak } = useSpeech();

/**
 * 题目变化时自动把题面读出来。
 *
 * ⚠️ 可能被浏览器的「自动播放策略」拦掉（首次交互前不允许发声）。
 * 因此**只把朗读当锦上添花**：朗读失败不影响作答，按钮始终在，孩子可以自己点。
 * 绝不能把「有没有听到」当成流程分支条件。
 */
watch(
  () => [props.question.id, props.autoSpeak] as const,
  ([, auto]) => {
    if (!auto || !speechText.value) return;
    void speak(speechText.value, { rate: rate(isAudio.value ? 0.7 : 0.9) });
  },
  { immediate: true },
);
</script>

<template>
  <section class="question learning-surface">
    <!-- 题面：可朗读 -->
    <div class="question__stem">
      <p class="question__prompt">{{ question.stem || question.prompt }}</p>
      <SpeakButton
        v-if="speechText"
        :text="speechText"
        :label="isAudio ? '听读音' : '读题目'"
        :rate="rate(isAudio ? 0.7 : 0.9)"
        size="sm"
      />
    </div>

    <!-- 看图选字：把字源图作为题干主图（否则「看图选字」其实没有图） -->
    <figure v-if="stemGlyph" class="question__picture">
      <GlyphFigure
        :glyph="stemGlyph"
        :size="104"
        :alt="`${question.char} 的字源图`"
        caption="看这张图，选出对应的字"
      />
    </figure>

    <!-- 听音题：把「播放」做成主操作 -->
    <div v-if="isAudio && !revealed" class="question__audio">
      <SpeakButton
        :text="question.char"
        label="点击播放读音"
        :rate="rate(0.7)"
        variant="primary"
        size="lg"
        block
      />
      <p class="text-sm text-muted text-center">听清楚了吗？从下面选出你听到的字</p>
    </div>

    <!-- 跟读题：麦克风作答 -->
    <div v-if="isSpeak" class="question__speak">
      <p class="question__speak-char">{{ question.char }}</p>
      <p v-if="question.pinyin" class="question__speak-pinyin">{{ question.pinyin }}</p>
      <ReadAlongButton
        :text="question.char"
        label="按住读一遍"
        size="lg"
        block
        :disabled="disabled"
        :matcher="readingMatches"
        @result="emit('speak', $event)"
      />
      <p class="text-sm text-muted text-center">按住别松手，圆圈转满就会听你读</p>
    </div>

    <!-- 选项 -->
    <ul
      v-if="optionCount"
      class="question__options"
      :class="`question__options--${optionCount > 4 ? 'many' : 'few'}`"
    >
      <li v-for="option in question.options" :key="option.id" class="question__option-item">
        <button
          type="button"
          class="question__option tap tap--primary clickable"
          :class="[
            `question__option--${optionState(option)}`,
            {
              'question__option--chosen': selected === option.char,
              'question__option--textual': isPinyin && !option.image_url,
            },
          ]"
          :disabled="disabled"
          @click="onSelect(option)"
        >
          <img v-if="option.image_url" class="question__option-image" :src="option.image_url" alt="" draggable="false" />
          <span class="question__option-text">{{ option.char }}</span>
        </button>
      </li>
    </ul>

    <!-- 提示：按需展开 -->
    <div v-if="showHint && hasHint && !revealed" class="question__hint-box">
      <button
        type="button"
        class="question__hint-toggle clickable"
        :aria-expanded="hintOpen"
        @click="hintOpen = !hintOpen"
      >
        💡 {{ hintOpen ? '收起提示' : '给点提示' }}
      </button>

      <div v-if="hintOpen" class="question__hint-content">
        <p v-if="hintPictograph" class="question__hint-item">
          <span class="question__hint-label">字源</span>{{ hintPictograph }}
        </p>
        <p v-if="question.words?.length" class="question__hint-item">
          <span class="question__hint-label">组词</span>{{ hintWords.join(' · ') }}
        </p>
        <p v-if="hintPinyin" class="question__hint-item">
          <span class="question__hint-label">拼音</span>{{ hintPinyin }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.question {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.question__stem {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
}

.question__prompt {
  font-size: var(--font-xl);
  font-weight: 600;
  text-align: center;
}

.question__audio {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

/* ---- 题干主图（看图选字） ---- */
.question__picture {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2xs);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--color-surface-alt);
}

.question__picture-emoji {
  font-size: clamp(64px, 18vw, 104px);
  line-height: 1;
}

.question__picture-caption {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.question__speak {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--color-surface-alt);
  border: 1px dashed var(--color-border);
}

.question__speak-char {
  /* 跟读目标字：要够大够醒目，但不能用字卡的 --font-card-glyph（最小 120px），
     否则题干会被挤到屏幕外、孩子找不到「点哪里开始读」。
     矮屏再压一档（下方高度媒体查询），横屏手机上只按 vw 算会给出 96px，
     把麦克风按钮顶出屏幕 —— 而那才是这一步唯一的操作。 */
  font-size: clamp(56px, 14vw, 96px);
  font-weight: 500;
  line-height: 1.1;
}

@media (max-height: 700px) {
  .question__speak-char {
    font-size: clamp(44px, 12vw, 72px);
  }
}

.question__speak-pinyin {
  color: var(--color-info);
  letter-spacing: 0.08em;
}

.question__options {
  display: grid;
  gap: var(--space-md);
  grid-template-columns: 1fr;
}

@media (min-width: 768px) {
  .question__options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1280px) {
  .question__options--few,
  .question__options--many {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

/*
 * 矮屏（横屏手机 / 小屏手机）上把 4 个选项从「纵向堆叠」切成 2×2。
 *
 * 为什么：纵向 4 行 × (96 + 16) ≈ 448px，加题干、进度、反馈后超过 667px，
 * 选项会被挤到屏幕外 —— 答题时「选项不可见」等于这一题没法答。
 * 2×2 后高度减半，每格仍是约 160×84 的大方块（远高于 56px 热区下限），
 * 识字选项的辨识度不受影响。
 * ⛔ 只在矮屏生效：屏幕够高时保持规范里的「纵向大按钮」形态（02-2 §3.2）。
 */
@media (max-width: 767px) and (max-height: 760px) {
  .question {
    gap: var(--space-sm);
  }

  .question__options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-sm);
  }

  .question__option {
    min-height: 84px;
    padding: var(--space-sm);
  }

  .question__option--textual {
    font-size: var(--font-md);
  }

  /* 题干仍然要 ≥18px（儿童端正文下限），只收掉「大标题」的那一号 */
  .question__prompt {
    font-size: var(--font-lg);
  }

  .question__picture,
  .question__speak {
    padding: var(--space-sm);
  }
}

.question__option-item {
  display: flex;
}

.question__option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: 2px solid var(--color-border);
  font-size: var(--font-xl);
  font-weight: 600;
  /*
   * 选项是这一屏**唯一的操作区**，所以它的热区要比一般按钮更大。
   * min-height 96px 保证：单字选项在 iPad 2×2 布局下也是接近正方形的大块，
   * 而不是一条扁扁的横条 —— 6 岁孩子手部精细动作尚未发育好，
   * 扁平按钮点不准会直接放弃作答。
   */
  min-height: 96px;
}

.question__option-image {
  width: 100%;
  max-height: 88px;
  object-fit: contain;
  border-radius: var(--radius-sm);
}

/* 拼音选项用无衬线、略小一号：拼音不是汉字，用汉字字号会显得很挤 */
.question__option--textual {
  font-size: var(--font-lg);
  font-weight: 500;
  font-family: ui-sans-serif, system-ui, sans-serif;
  letter-spacing: 0.02em;
}

.question__option--correct {
  border-color: var(--color-success);
  background: color-mix(in srgb, var(--color-success) 16%, var(--color-surface));
}

.question__option--wrong {
  border-color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 16%, var(--color-surface));
}

.question__option:disabled {
  cursor: default;
}

@media (hover: hover) {
  .question__option:not(:disabled):hover {
    border-color: var(--color-primary-strong);
  }
}

.question__hint-box {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.question__hint-toggle {
  align-self: flex-start;
  padding: var(--space-2xs) var(--space-md);
  min-height: 40px;
  border-radius: var(--radius-pill);
  border: 1px dashed var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.question__hint-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  font-size: var(--font-sm);
}

.question__hint-item {
  display: flex;
  gap: var(--space-sm);
}

.question__hint-label {
  flex: none;
  width: 32px;
  color: var(--color-text-muted);
}
</style>
