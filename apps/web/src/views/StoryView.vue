<script setup lang="ts">
/**
 * StoryView —— 故事关（S-07 阅读承接，挂在地图「故事」线上）。
 *
 * ## 为什么要有这一页
 * 地图的故事线本来就存在（关卡由内容包自动生成），但点进去后跳的是**识字闯关页**，
 * 而故事关的 `character_ids` 里装的是故事 id 而不是字 id —— 于是必然落到
 * 「这里暂时没有可练的字」的空状态。**线上有关卡，点了却进不去**，流程到这里就断了。
 *
 * 故事关的完成方式与识字关不同：它不是「答对几题」，而是**读没读下来**。
 * 因此星星按「跟读通过的句数」给，读完本身至少给 1 颗（读完了就该有奖励，
 * 而不是因为没有跟读就判 0 星 —— 那会让孩子觉得「读了也白读」）。
 *
 * 一个字三色（认识 / 字库待学 / 字库外）沿用短文页的口径：家长要能一眼看出
 * 「这篇孩子能不能自己读」。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute, useRouter } from 'vue-router';

import { useChildStore, useContentStore, useLearningStore, useSiteConfigStore } from '@study-club/core';
import type { Lesson, Story } from '@study-club/core';
import { readingMatches, readingPlanForSentence } from '@study-club/subject-hanzi';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import BaseProgress from '@/components/base/BaseProgress.vue';
import GuideBubble from '@/components/biz/GuideBubble.vue';
import LevelResult from '@/components/biz/LevelResult.vue';
import ReadAlongButton from '@/components/biz/ReadAlongButton.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import { useCompanion } from '@/composables/useCompanion';
import { useToast } from '@/composables/useToast';
import {
  entryLessonOfTrack,
  lessonByContentId,
  nextLesson,
  routeForLesson,
  type Track,
  trackOf,
} from '@/utils/levels';

const route = useRoute();
const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();
const siteConfig = useSiteConfigStore();
const toast = useToast();
const companion = useCompanion();

const { current } = storeToRefs(childStore);

const storyId = computed(() => String(route.params.storyId ?? ''));
const story = computed<Story | null>(
  () => content.bundle.stories.find((s) => s._id === storyId.value) ?? null,
);

/** 故事线（本年级）的全部关卡 —— 用来定位「我是第几关」与「下一关」。 */
const trackLessons = computed<Lesson[]>(() =>
  current.value
    ? content
        .lessonsOfTrack(current.value.grade, 'story')
        .filter((l) => trackOf(l) === 'story')
    : [],
);

/**
 * 当前关卡 id。
 *
 * 优先用 query 里带的（地图跳转时一定带）；直接输 URL 进来时按故事 id 反查。
 */
const lessonId = computed(() => {
  const fromQuery = route.query.lesson;
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery;
  return lessonByContentId(trackLessons.value, storyId.value)?._id ?? '';
});

const next = computed<Lesson | null>(() =>
  lessonId.value ? nextLesson(trackLessons.value, lessonId.value) : null,
);

/** 正文按行拆句（内容包用 \n 分行）。 */
const lines = computed(() =>
  (story.value?.text ?? '')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean),
);

/** 已学字集合（有复习状态即算学过）。 */
const knownChars = computed(() => {
  const set = new Set<string>();
  for (const state of learning.reviewStates) {
    const char = content.characterMap.get(state.character_id);
    if (char) set.add(char.char);
  }
  return set;
});

/** 跟读通过的句数（按行号记，同一句重复跟读不重复计数）。 */
const readOk = ref<Set<number>>(new Set());
/** 是否已进入结果页。 */
const finished = ref(false);
const stars = ref(0);
const newBadges = ref<string[]>([]);

/** 完成度：跟读通过句数 / 总句数。 */
const readProgress = computed(() =>
  lines.value.length ? readOk.value.size / lines.value.length : 0,
);

/** 朗读语速：句子基速按后台整体档位缩放。 */
function sentenceRate(): number {
  const base = readingPlanForSentence('').rate;
  const scaled = base * (siteConfig.gameplay.speak_rate / 0.8);
  return Math.min(1.2, Math.max(0.4, Number(scaled.toFixed(2))));
}

function charState(ch: string): 'known' | 'pending' | 'extra' {
  if (knownChars.value.has(ch)) return 'known';
  return content.charByText.has(ch) ? 'pending' : 'extra';
}

/** 只对汉字着色：标点、数字没有「认不认识」这回事。 */
function isCjk(ch: string): boolean {
  return /[\u3400-\u4dbf\u4e00-\u9fff]/.test(ch);
}

function onReadResult(index: number, payload: { matched: boolean }): void {
  if (!payload.matched) return;
  const nextSet = new Set(readOk.value);
  nextSet.add(index);
  readOk.value = nextSet;
}

/**
 * 完成这一关。
 *
 * 星星口径：全部跟读通过 3 颗；过半 2 颗；读完了至少 1 颗。
 * ⛔ 不跟读也给 1 颗 —— 读完整篇已经是完成，判 0 星会让孩子觉得白读了。
 */
async function finish(): Promise<void> {
  const child = current.value;
  if (!child || !story.value) return;

  const accuracy = readProgress.value;
  const earned = accuracy >= 0.9 ? 3 : accuracy >= 0.5 ? 2 : 1;
  stars.value = earned;

  // 关卡流水记「本故事练到的字」：高亮字里命中字库的那些
  const characterIds = story.value.highlight_characters
    .map((ch) => content.charByText.get(ch)?._id)
    .filter((id): id is string => Boolean(id));

  try {
    const res = await learning.completeLesson({
      childId: child._id,
      lessonId: lessonId.value || null,
      characterIds,
      score: readOk.value.size,
      total: lines.value.length || 1,
      stars: earned,
    });
    const titles = (res.newly_earned_badges ?? [])
      .map((code) => content.bundle.badges.find((b) => b.code === code)?.title ?? code)
      .filter(Boolean);
    if (titles.length) newBadges.value = titles;
  } catch {
    toast.warn('完成记录没有保存成功，但你已经读完啦');
  }
  finished.value = true;
}

function goNext(): void {
  if (next.value) void router.replace(routeForLesson(next.value));
  else void router.replace({ name: 'map', query: { track: 'story' } });
}

function goBackToMap(): void {
  void router.replace({ name: 'map', query: { track: 'story' } });
}

/** 换条线闯关 —— 去那条线的第一关（见 `entryLessonOfTrack` 的取舍说明）。 */
function goTrack(key: string): void {
  const child = current.value;
  const track = key as Track;
  const target = child
    ? entryLessonOfTrack(content.lessonsOfTrack(child.grade, track), track)
    : null;
  if (!target) {
    toast.show('这条线暂时还没有关卡，先回地图看看吧');
    goBackToMap();
    return;
  }
  void router.replace(routeForLesson(target));
}

function retry(): void {
  readOk.value = new Set();
  finished.value = false;
  stars.value = 0;
}

async function load(): Promise<void> {
  const child = current.value;
  if (!child) return;
  if (!learning.reviewStates.length) {
    try {
      await learning.loadChildData(child._id);
    } catch {
      toast.warn('已学字记录加载失败，故事里的字会按「还没学过」展示');
    }
  }
}

function resetAndLoad(): void {
  // ⛔ 切到另一个故事时组件会被复用（同路由名只换参数），
  //    不清掉上一关的星星与跟读记录，新故事会一开场就显示上一关的结算页。
  readOk.value = new Set();
  finished.value = false;
  stars.value = 0;
  newBadges.value = [];
  void load();
}

onMounted(load);
watch(() => [current.value?._id, storyId.value] as const, resetAndLoad);
</script>

<template>
  <!-- 一屏三段式骨架，与识字 / 古诗关同一份（见 styles/learn-screen.css） -->
  <section class="learn-page">
    <div v-if="!story" class="learn-page__body learn-page__body--center">
      <BaseEmpty
        title="找不到这个故事"
        description="内容包可能已更新，或这个故事已被下架。"
        icon="📖"
      >
        <BaseButton @click="goBackToMap">回到地图</BaseButton>
      </BaseEmpty>
    </div>

    <!-- 结果：与识字/古诗共用同一张结果卡，闭环一致 -->
    <div v-else-if="finished" class="learn-page__body learn-page__body--center">
      <GuideBubble
        :text="stars >= 2 ? '读得真棒！我们接着读下一个。' : '读完啦！多读几遍会更熟。'"
        :mood="stars >= 2 ? 'happy' : 'idle'"
      />
      <LevelResult
        :stars="stars"
        title="这个故事读完啦"
        :subtitle="`跟读通过 ${readOk.size} / ${lines.length} 句`"
        :stats="[
          { label: '句子', value: lines.length },
          { label: '跟读通过', value: readOk.size },
        ]"
        :badges="newBadges"
        note="故事里的字已进入复习计划，下次打开首页就能练。"
        :has-next="Boolean(next)"
        next-label="下一个故事"
        :show-retry="false"
        :done-text="'故事都读完啦，回地图看看别的方向。'"
        :track-links="[
          { key: 'literacy', label: '去识字闯关' },
          { key: 'poem', label: '去古诗闯关' },
        ]"
        @next="goNext"
        @retry="retry"
        @back="goBackToMap"
        @track="goTrack"
      />
    </div>

    <template v-else>
      <header class="learn-page__head">
        <div class="story-head">
          <h2 class="title-lg">{{ story.title }}</h2>
          <p class="text-muted text-sm">共 {{ lines.length }} 句 · {{ story.word_count }} 字</p>
          <div class="row row--wrap">
            <SpeakButton
              :text="story.text"
              :rate="sentenceRate()"
              label="听整个故事"
              variant="primary"
            />
          </div>
        </div>
      </header>

      <div class="learn-page__body">
        <GuideBubble
          text="先听一遍，再一句一句跟着读。读完点下面的「我读完啦」。"
          :auto-speak="false"
        />

        <!--
          句子的列表在内容区内部滚动：故事有十几句，一屏放不完是正常的；
          但「听 / 跟读」是逐句操作，滚到哪句就练哪句，所以列表自己滚不影响操作。
        -->
        <BaseCard title="一句一句读">
          <BaseProgress
            :value="readProgress"
            :label="`跟读通过 ${readOk.size} / ${lines.length} 句`"
          />
          <ol class="lines">
            <li v-for="(line, index) in lines" :key="`${line}-${index}`" class="line">
              <p class="line__text learning-surface">
                <span
                  v-for="(ch, i) in line.split('')"
                  :key="`${ch}-${i}`"
                  class="line__char"
                  :class="isCjk(ch) ? `line__char--${charState(ch)}` : undefined"
                  >{{ ch }}</span
                >
              </p>
              <div class="line__actions">
                <SpeakButton
                  :text="line"
                  :rate="sentenceRate()"
                  label="听这一句"
                  size="sm"
                  variant="ghost"
                />
                <ReadAlongButton
                  :text="line"
                  :matcher="readingMatches"
                  :companion-name="companion.name.value"
                  label="我来读这句"
                  size="sm"
                  @result="onReadResult(index, $event)"
                />
                <span v-if="readOk.has(index)" class="line__ok" aria-label="这句读过了">✓</span>
              </div>
            </li>
          </ol>
        </BaseCard>
      </div>

      <footer class="learn-page__foot">
        <BaseButton size="lg" block @click="finish">我读完啦</BaseButton>
        <p class="text-sm text-muted text-center">
          每个字有三种颜色：<span class="line__char--known">学过</span> ·
          <span class="line__char--pending">还没学</span> ·
          <span class="line__char--extra">字库外（家长带读）</span>
        </p>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.story-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
  align-items: flex-start;
}

.lines {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  margin: var(--space-sm) 0 0;
  padding: 0;
  list-style: none;
}

.line {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
  padding-bottom: var(--space-sm);
  border-bottom: 1px dashed var(--color-border);
}

.line:last-child {
  border-bottom: none;
}

.line__text {
  font-size: var(--font-xl);
  font-weight: 500;
  letter-spacing: 0.1em;
  line-height: 1.6;
}

.line__char--known {
  color: var(--color-text);
}

.line__char--pending {
  color: var(--color-text-muted);
}

.line__char--extra {
  color: var(--color-danger);
  text-decoration: underline dotted;
  text-underline-offset: 4px;
}

.line__actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.line__ok {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--color-success) 20%, var(--color-surface));
  color: var(--color-success);
  font-weight: 700;
}
</style>
