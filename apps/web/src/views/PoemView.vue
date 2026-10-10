<script setup lang="ts">
/**
 * PoemView —— 古诗学习（S-07）：逐句注音 + 白话 + 填字练习 + 关卡完成闭环。
 * 练习题的判定与复习记录复用 core 的 learning store（命中字库的字才写入 SRS）。
 *
 * 本轮加入朗读与跟读（启蒙人群不识字，古诗尤其需要「先听见」）：
 *   - 整首朗读：古诗要整体读才有韵律，逐句放慢会毁掉节奏；
 *   - 逐句朗读 / 跟读：定位到某一联再练；
 *   - 朗读走浏览器原生 TTS，设备不支持时按钮整块不渲染（不留哑按钮）。
 *
 * 本轮补上**闭环**：以前做完填字练习就停住了 —— 没有「这一关完成了」的
 * 记录，也没有「下一首」的出口，地图上的古诗关因此永远不解锁。
 * 现在完成方式与识字关不同（不是答题正确率，而是「念完 + 练了」），
 * 所以星星由本页按表现显式给出，阈值仍遵循 `starsForAccuracy` 的口径。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute, useRouter } from 'vue-router';

import { useChildStore, useContentStore, useLearningStore } from '@study-club/core';
import type { Lesson, Poem } from '@study-club/core';
import { generatePoemFillQuestion, readingPlanForSentence } from '@study-club/subject-hanzi';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import GuideBubble from '@/components/biz/GuideBubble.vue';
import LevelResult from '@/components/biz/LevelResult.vue';
import PoemLine from '@/components/biz/PoemLine.vue';
import ReadAlongButton from '@/components/biz/ReadAlongButton.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import { useToast } from '@/composables/useToast';
import { pickPraise } from '@/utils/feedback';
import { lessonByContentId, nextLesson, routeForLesson, trackOf } from '@/utils/levels';

const route = useRoute();
const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();
const toast = useToast();

const { current } = storeToRefs(childStore);

const poemRef = ref<Poem | null>(null);
const selected = ref<string | null>(null);
const revealed = ref(false);
const isCorrect = ref(false);
/** 答对时的表扬语（每次从词库随机抽，不再固定「答对啦」） */
const praiseText = ref('');
const questionStartedAt = ref(0);

/** 本次填字练习错了几次 —— 决定星星，也决定「要不要再练一次」。 */
const wrongTries = ref(0);
const finished = ref(false);
const stars = ref(0);
const newBadges = ref<string[]>([]);

const poemId = computed(() => String(route.params.poemId ?? ''));

/**
 * 古诗线的全部关卡。
 *
 * 用来算「下一首」：孩子念完一首后最自然的动作是接着念下一首，
 * 而不是回到首页再找一遍。
 */
const trackLessons = computed<Lesson[]>(() =>
  current.value
    ? content.lessonsOfTrack(current.value.grade, 'poem').filter((l) => trackOf(l) === 'poem')
    : [],
);

const lessonId = computed(() => {
  const fromQuery = route.query.lesson;
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery;
  return lessonByContentId(trackLessons.value, poemId.value)?._id ?? '';
});

const next = computed<Lesson | null>(() =>
  lessonId.value ? nextLesson(trackLessons.value, lessonId.value) : null,
);

const question = computed(() => {
  const poem = poemRef.value;
  if (!poem || !poem.key_characters.length || !poem.lines.length) return null;
  const line = poem.lines.find((l) => poem.key_characters.some((k) => l.text.includes(k)));
  const keyChar = poem.key_characters.find((k) => line?.text.includes(k) ?? false);
  if (!line || !keyChar) return null;

  const pool = Array.from(
    new Set([...poem.key_characters, ...poem.full_text.split('')].filter((c) => c !== keyChar)),
  );
  return generatePoemFillQuestion({
    poemId: poem._id,
    lineText: line.text,
    keyChar,
    pool,
  });
});

function reload(): void {
  poemRef.value = content.bundle.poems.find((p) => p._id === poemId.value) ?? null;
  selected.value = null;
  revealed.value = false;
  wrongTries.value = 0;
  finished.value = false;
  stars.value = 0;
  newBadges.value = [];
  questionStartedAt.value = Date.now();
}

onMounted(reload);
watch(() => route.params.poemId, reload);

async function choose(option: string): Promise<void> {
  const q = question.value;
  if (!q || revealed.value) return;
  const child = current.value;

  selected.value = option;
  revealed.value = true;
  isCorrect.value = option === q.answer;
  praiseText.value = isCorrect.value ? pickPraise() : '';
  if (!isCorrect.value) wrongTries.value += 1;

  // 命中学字库时才写入复习状态/错题本，避免污染识字 SRS。
  const matched = content.charByText.get(q.char);
  if (child && matched) {
    await learning.submitAnswer({
      childId: child._id,
      question: { ...q, character_id: matched._id },
      answer: option,
      isCorrect: isCorrect.value,
      responseMs: Date.now() - questionStartedAt.value,
    });
  } else if (!matched) {
    toast.show('这个字暂不在字库中，仅在本页练习，不计入复习计划', 'info', 3000);
  }
}

function retry(): void {
  selected.value = null;
  revealed.value = false;
  isCorrect.value = false;
  finished.value = false;
  questionStartedAt.value = Date.now();
}

/**
 * 星星：一次答对 3 颗；错一次后答对 2 颗；只念完没练（或一直没答对）1 颗。
 *
 * ⛔ 不因为「没做练习」判 0 星 —— 把一首诗念下来已经是完成，
 *    判 0 星等于告诉孩子「你刚才那段不算」。
 */
function earnedStars(): number {
  if (!isCorrect.value) return 1;
  if (wrongTries.value === 0) return 3;
  return 2;
}

/**
 * 完成这一关（写 `lesson_complete` 流水）。
 *
 * `lessonId` 可能为空（直接输 /poem/xxx 进来）：此时**仍然记录完成**，
 * 只是不带关卡归属。不记会让孩子「学完了但地图没解锁」，
 * 那比多一条无归属的流水难解释得多。
 */
async function finish(): Promise<void> {
  const child = current.value;
  const poem = poemRef.value;
  if (!child || !poem) return;

  stars.value = earnedStars();

  // 关卡流水记「本诗练到的字」：重点字里命中字库的那些
  const characterIds = poem.key_characters
    .map((ch) => content.charByText.get(ch)?._id)
    .filter((id): id is string => Boolean(id));

  try {
    const res = await learning.completeLesson({
      childId: child._id,
      lessonId: lessonId.value || null,
      characterIds,
      score: isCorrect.value ? 1 : 0,
      total: 1,
      stars: stars.value,
    });
    const titles = (res.newly_earned_badges ?? [])
      .map((code) => content.bundle.badges.find((b) => b.code === code)?.title ?? code)
      .filter(Boolean);
    if (titles.length) newBadges.value = titles;
  } catch {
    toast.warn('完成记录没有保存成功，但这一首已经学完啦');
  }
  finished.value = true;
}

function goNext(): void {
  if (next.value) void router.replace(routeForLesson(next.value));
  else void router.replace({ name: 'map', query: { track: 'poem' } });
}

function goBackToMap(): void {
  void router.replace({ name: 'map', query: { track: 'poem' } });
}
</script>

<template>
  <!-- 一屏三段式骨架，与识字 / 故事关同一份（见 styles/learn-screen.css） -->
  <section class="learn-page">
    <div v-if="!poemRef" class="learn-page__body learn-page__body--center">
      <BaseEmpty
        title="找不到这首诗"
        description="可能内容包尚未包含该古诗。"
        icon="📜"
      >
        <BaseButton @click="goBackToMap">回到地图</BaseButton>
      </BaseEmpty>
    </div>

    <!-- 结果 —— 与识字 / 故事关共用同一张结果卡，闭环一致 -->
    <div v-else-if="finished" class="learn-page__body learn-page__body--center">
      <GuideBubble
        :text="stars >= 2 ? '背得真棒！我们再来一首。' : '念完啦！多念几遍就更熟了。'"
        :mood="stars >= 2 ? 'happy' : 'idle'"
      />
      <LevelResult
        :stars="stars"
        title="这一首学完啦"
        :subtitle="poemRef.title"
        :stats="[
          { label: '诗句', value: poemRef.lines.length },
          { label: '重点字', value: poemRef.key_characters.length },
        ]"
        :badges="newBadges"
        note="诗里的重点字已进入复习计划，下次打开首页就能练。"
        :has-next="Boolean(next)"
        next-label="下一首"
        :show-retry="false"
        :done-text="'古诗都学完啦，回地图看看别的方向。'"
        @next="goNext"
        @retry="retry"
        @back="goBackToMap"
      />
    </div>

    <template v-else>
      <header class="learn-page__head">
        <div class="poem-head">
          <h2 class="title-lg">{{ poemRef.title }}</h2>
          <p class="text-muted">{{ poemRef.dynasty }} · {{ poemRef.author }}</p>
          <div class="row row--wrap">
            <span class="pill">{{ poemRef.source }}</span>
            <!-- 整首朗读：古诗的韵律只在整篇连读里存在 -->
            <SpeakButton
              :text="poemRef.full_text"
              :rate="readingPlanForSentence(poemRef.full_text).rate"
              label="朗读整首"
              variant="primary"
            />
          </div>
        </div>
      </header>

      <div class="learn-page__body">
        <GuideBubble
          text="先跟着小兔听一遍，再一句一句跟着读，最后试试填字练习吧！"
          :auto-speak="false"
        />

        <div class="poem-layout">
          <BaseCard>
            <ul class="poem-body">
              <PoemLine
                v-for="(line, index) in poemRef.lines"
                :key="`${line.text}-${index}`"
                :text="line.text"
                :pinyin="line.pinyin"
                :meaning="line.meaning"
                :highlight="poemRef.key_characters"
              >
                <template #actions>
                  <SpeakButton
                    :text="line.text"
                    :rate="readingPlanForSentence(line.text).rate"
                    label="读这句"
                    size="sm"
                    variant="ghost"
                  />
                  <ReadAlongButton
                    :text="line.text"
                    label="跟读这句"
                    size="sm"
                  />
                </template>
              </PoemLine>
            </ul>
          </BaseCard>

          <div class="stack">
            <!--
              手机上的顺序（靠 CSS `order` 调，DOM 顺序不变）：
              填字练习 → 诗意与背景。
              「读完 → 练一练」是这一步的主链路，而诗意是读的部分，
              在窄屏上不该把练习挤到第二屏。
            -->
            <BaseCard class="poem-card--fill" v-if="question" title="填字练习" subtitle="补全下面这句诗">
              <p class="fill-prompt">{{ question.prompt }}</p>
              <ul class="fill-options">
                <li v-for="option in question.options" :key="option.id">
                  <button
                    type="button"
                    class="fill-option tap clickable"
                    :class="{
                      'fill-option--ok': revealed && option.char === question.answer,
                      'fill-option--no':
                        revealed && option.char === selected && option.char !== question.answer,
                    }"
                    :disabled="revealed"
                    @click="choose(option.char)"
                  >
                    {{ option.char }}
                  </button>
                </li>
              </ul>

              <div v-if="revealed" class="fill-feedback">
                <p v-if="isCorrect" class="feedback feedback--ok">{{ praiseText }}</p>
                <p v-else class="feedback feedback--no">正确答案是「{{ question.answer }}」</p>
                <BaseButton v-if="!isCorrect" variant="secondary" @click="retry">再做一次</BaseButton>
                <BaseButton v-else size="lg" block @click="finish">学完这一首</BaseButton>
              </div>
            </BaseCard>

            <BaseCard title="诗意与背景">
              <p class="text-muted selectable">{{ poemRef.appreciation }}</p>
              <p v-if="poemRef.background" class="text-sm text-muted selectable">
                {{ poemRef.background }}
              </p>
              <template #footer>
                <SpeakButton
                  :text="poemRef.appreciation"
                  :rate="0.95"
                  label="听听诗的意思"
                  variant="ghost"
                  size="sm"
                />
              </template>
            </BaseCard>
          </div>
        </div>
      </div>

      <!-- 主出口：没做填字练习也能完成这一关（念完就算数） -->
      <footer class="learn-page__foot">
        <BaseButton size="lg" block @click="finish">我念完啦</BaseButton>
        <p class="text-sm text-muted text-center">
          跟着念完就能点亮星星；做完填字练习可以再多一颗。
        </p>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.poem-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
  align-items: flex-start;
}

/*
 * 手机上的卡序：填字练习排在诗意之前。
 * 用 `order` 调而不是改 DOM 顺序 —— 大屏（双栏）时右边的顺序仍是
 * 「先读懂诗意，再动手练」，那是有地方铺开时的合理顺序。
 */
@media (max-width: 767px) {
  .poem-card--fill {
    order: -1;
  }
}

.poem-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.fill-prompt {
  font-size: var(--font-lg);
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.fill-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-sm);
}

.fill-option {
  width: 100%;
  min-height: var(--tap-min);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  border: 2px solid transparent;
  font-size: var(--font-lg);
  font-weight: 600;
}

.fill-option--ok {
  border-color: var(--color-success);
}

.fill-option--no {
  border-color: var(--color-danger);
}

.fill-feedback {
  margin-top: var(--space-sm);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-sm);
}

.feedback--ok {
  color: var(--color-success);
}

.feedback--no {
  color: var(--color-danger);
}
</style>
