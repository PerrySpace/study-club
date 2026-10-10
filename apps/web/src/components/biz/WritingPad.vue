<script setup lang="ts">
/**
 * WritingPad —— 米字格手写板（业务组件）。
 *
 * 三件事，按「学完字就该写」这个顺序：
 *   1. **米字格**：田字格 + 虚线十字，标出「字的中心与中线」。启蒙写字必须给这个 ——
 *      没有中线参照，孩子写出来的字整体偏斜，且自己看不出来。
 *   2. **描红**：底层用浅色大字当描红底稿，上面盖一层手写笔迹。
 *      描红是识字产品里最有效的巩固手段之一（写一遍比看三遍有用）。
 *   3. **手写**：canvas 采集笔迹，支持触摸（iPad + Apple Pencil）与鼠标。
 *
 * ⚠️ **笔顺动画需要素材**：真正的笔顺要 `character.stroke_order_ref` 指向的
 * 笔顺 JSON（`hanzi-writer` 那类 SVG path 数据），本仓库目前**没有入库**。
 * 因此这里的设计是：
 *   - 传了 `strokes`（有素材）→ 播放真实笔顺动画；
 *   - 没传 → 底部给出**明确提示**「笔顺素材未入库」，并降级为「按笔顺数逐笔描红」，
 *     **不假装有笔顺**。给孩子一个假的笔顺演示比不给更糟。
 *
 * 判定纪律：本组件**不判断写得对不对** —— 笔画顺序、间架结构的判定需要
 * 图形相似度算法，属于「像不像」的能力，那要单独的评测服务。
 * 这里只做「让孩子写」，写得像不像交给老师/家长看。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

/** 一笔的路径数据（归一化到 0–1 的坐标系，与素材格式一致）。 */
interface Stroke {
  /** SVG path 的 d 属性，坐标系 0–1024（hanzi-writer 约定） */
  path: string;
}

const props = withDefaults(
  defineProps<{
    /** 要写的汉字 */
    char: string;
    /** 笔画数，用于降级时的「写 N 笔」提示 */
    strokeCount?: number;
    /**
     * 笔顺数据（已解析的路径数组）。
     * **为空时不显示笔顺动画**，并如实说明「素材未入库」——不做假的演示。
     */
    strokes?: Stroke[];
    /** 格子边长（px） */
    size?: number;
    /** 是否显示描红底稿 */
    showTrace?: boolean;
  }>(),
  {
    strokeCount: 0,
    strokes: () => [],
    size: 300,
    showTrace: true,
  },
);

const emit = defineEmits<{
  /** 有笔迹变化（用于「写过了」判定与落库时机） */
  (e: 'change', payload: { strokesDrawn: number; hasInk: boolean }): void;
  /** 一笔画完 */
  (e: 'stroke-end'): void;
}>();

const canvasRef = ref<HTMLCanvasElement>();
const hasInk = ref(false);
const strokeCountDrawn = ref(0);
const drawing = ref(false);
const lastPoint = ref<{ x: number; y: number } | null>(null);
/** 笔顺动画播放到第几笔；-1 = 未播放 */
const demoStroke = ref(-1);

const hasStrokes = computed(() => props.strokes.length > 0);

// ---------------------------------------------------------------------------
// canvas 尺寸与缩放
// ---------------------------------------------------------------------------
let ctx: CanvasRenderingContext2D | null = null;
let dpr = 1;

function setupCanvas(): void {
  const canvas = canvasRef.value;
  if (!canvas) return;
  dpr = window.devicePixelRatio || 1;
  canvas.width = props.size * dpr;
  canvas.height = props.size * dpr;
  ctx = canvas.getContext('2d');
  ctx?.scale(dpr, dpr);
  clearInk();
}

/** 只清手写层，不动描红（描红是 DOM 里的元素，不在 canvas 上）。 */
function clearInk(): void {
  if (ctx) {
    ctx.clearRect(0, 0, props.size, props.size);
  }
  hasInk.value = false;
  strokeCountDrawn.value = 0;
  demoStroke.value = -1;
  emit('change', { strokesDrawn: 0, hasInk: false });
}

function clear(): void {
  clearInk();
}

// ---------------------------------------------------------------------------
// 笔迹绘制
// ---------------------------------------------------------------------------
function pointFrom(event: PointerEvent): { x: number; y: number } {
  const canvas = canvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * props.size,
    y: ((event.clientY - rect.top) / rect.height) * props.size,
  };
}

function onPointerDown(event: PointerEvent): void {
  if (!ctx) return;
  // 只响应主指针 / 触摸，避免 stylus 与 touch 同时触发时画两次
  if (event.pointerType === 'mouse' && event.button !== 0) return;
  event.preventDefault();
  // 捕获指针：手指（或笔）滑出格子边界时事件仍然回到 canvas。
  // 不捕获的话 `pointerleave` 会把一笔在半路截断 —— 孩子看到的是「笔画写着写着断了」，
  // 而真正的原因是手指越过了一像素的边界。失败（老内核）不影响主流程。
  try {
    (event.currentTarget as HTMLCanvasElement).setPointerCapture(event.pointerId);
  } catch {
    /* 不支持指针捕获的浏览器：退回原来的 leave 结束逻辑 */
  }
  drawing.value = true;
  const p = pointFrom(event);
  lastPoint.value = p;
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  // 点一下也要留下一个点：点错了位置也算写过一笔
  ctx.lineTo(p.x + 0.1, p.y + 0.1);
  ctx.strokeStyle = 'rgba(45, 55, 72, 0.85)';
  ctx.lineWidth = Math.max(10, props.size * 0.045);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
}

function onPointerMove(event: PointerEvent): void {
  if (!drawing.value || !ctx) return;
  event.preventDefault();
  const p = pointFrom(event);
  const last = lastPoint.value;
  if (!last) return;
  ctx.lineTo(p.x, p.y);
  ctx.stroke();
  lastPoint.value = p;
  if (!hasInk.value) {
    hasInk.value = true;
  }
}

function onPointerUp(): void {
  if (!drawing.value) return;
  drawing.value = false;
  lastPoint.value = null;
  if (hasInk.value) {
    strokeCountDrawn.value += 1;
    emit('stroke-end');
    emit('change', { strokesDrawn: strokeCountDrawn.value, hasInk: hasInk.value });
  }
}

// ---------------------------------------------------------------------------
// 笔顺演示
// ---------------------------------------------------------------------------
/**
 * 播放笔顺动画。
 *
 * ⚠️ 用 `@keyframes` 描边 SVG path 来实现，而不是逐点画：素材给的是 path，
 * 描边动画正好对应「一笔一笔写出来」，且不需要自己算路径长度。
 * 动画结束后停止，不循环 —— 循环播放会让孩子以为要一直看着。
 */
const demoPlaying = ref(false);
let demoTimer: number | null = null;

function playDemo(): void {
  if (!hasStrokes.value) return;
  stopDemo();
  demoPlaying.value = true;
  demoStroke.value = -1;
  const total = props.strokes.length;
  let index = 0;
  const step = (): void => {
    index += 1;
    demoStroke.value = index - 1;
    if (index < total) {
      demoTimer = window.setTimeout(step, 700);
    } else {
      demoPlaying.value = false;
      demoTimer = null;
    }
  };
  demoTimer = window.setTimeout(step, 350);
}

function stopDemo(): void {
  if (demoTimer !== null) {
    window.clearTimeout(demoTimer);
    demoTimer = null;
  }
  demoPlaying.value = false;
  demoStroke.value = -1;
}

onMounted(() => {
  setupCanvas();
});

onBeforeUnmount(() => {
  stopDemo();
});

watch(() => props.char, () => clear());
watch(() => props.size, () => setupCanvas());

defineExpose({ clear, playDemo, stopDemo });
</script>

<template>
  <div class="writing-pad">
    <div class="writing-pad__stage" :style="{ width: `${size}px`, height: `${size}px` }">
      <!-- 米字格：田字格实线 + 对角虚线 + 中心十字 -->
      <svg
        class="writing-pad__grid"
        :viewBox="`0 0 ${size} ${size}`"
        :width="size"
        :height="size"
        aria-hidden="true"
      >
        <rect
          x="1"
          y="1"
          :width="size - 2"
          :height="size - 2"
          fill="none"
          stroke="#e0a0a0"
          stroke-width="1.5"
          rx="4"
        />
        <!-- 中心十字：写竖、撇、捺时的中线参照 -->
        <line
          :x1="size / 2"
          y1="2"
          :x2="size / 2"
          :y2="size - 2"
          stroke="#e8b4b4"
          stroke-width="1"
          stroke-dasharray="5 5"
        />
        <line
          x1="2"
          :y1="size / 2"
          :x2="size - 2"
          :y2="size / 2"
          stroke="#e8b4b4"
          stroke-width="1"
          stroke-dasharray="5 5"
        />
        <!-- 对角线 -->
        <line
          x1="2"
          y1="2"
          :x2="size - 2"
          :y2="size - 2"
          stroke="#f0c8c8"
          stroke-width="1"
          stroke-dasharray="4 7"
        />
        <!-- 反向对角线：起点在右上、终点在左下 -->
        <line
          :x1="size - 2"
          y1="2"
          x2="2"
          :y2="size - 2"
          stroke="#f0c8c8"
          stroke-width="1"
          stroke-dasharray="4 7"
        />
      </svg>

      <!-- 描红底稿：浅色大字 -->
      <span
        v-if="showTrace"
        class="writing-pad__trace"
        :style="{ fontSize: `${size * 0.76}px`, lineHeight: `${size}px` }"
        aria-hidden="true"
      >
        {{ char }}
      </span>

      <!-- 笔顺演示层：素材路径逐笔描出 -->
      <svg
        v-if="hasStrokes"
        class="writing-pad__demo"
        :viewBox="`0 0 ${size} ${size}`"
        :width="size"
        :height="size"
        aria-hidden="true"
      >
        <g :transform="`scale(${size / 1024})`">
          <path
            v-for="(stroke, i) in strokes"
            :key="i"
            :d="stroke.path"
            fill="none"
            stroke="#4a5b8c"
            stroke-width="42"
            stroke-linecap="round"
            stroke-linejoin="round"
            :class="{
              'writing-pad__stroke--on': i <= demoStroke,
              'writing-pad__stroke--active': i === demoStroke && demoPlaying,
            }"
          />
        </g>
      </svg>

      <!-- 手写层 -->
      <canvas
        ref="canvasRef"
        class="writing-pad__canvas"
        :style="{ width: `${size}px`, height: `${size}px` }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @pointerleave="onPointerUp"
      />
    </div>

    <div class="writing-pad__actions">
      <button type="button" class="writing-pad__btn tap clickable" @click="clear">
        重写
      </button>
      <button
        v-if="hasStrokes"
        type="button"
        class="writing-pad__btn writing-pad__btn--primary tap clickable"
        @click="demoPlaying ? stopDemo() : playDemo()"
      >
        {{ demoPlaying ? '停一下' : '看笔顺' }}
      </button>
    </div>

    <p class="writing-pad__tip">
      <template v-if="hasStrokes">
        照着浅色的字描一遍，写完点「重写」可以再写。
      </template>
      <template v-else-if="strokeCount > 0">
        这个字有 <b>{{ strokeCount }}</b> 笔，照着浅色的字描一遍吧。
        <span class="writing-pad__tip-note">（笔顺动画素材还没入库，先按描红练）</span>
      </template>
      <template v-else>
        照着浅色的字描一遍。
      </template>
    </p>
  </div>
</template>

<style scoped>
.writing-pad {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
}

.writing-pad__stage {
  position: relative;
  border-radius: var(--radius-md);
  background: #fffdf7;
  overflow: hidden;
  touch-action: none;
}

.writing-pad__grid,
.writing-pad__demo,
.writing-pad__canvas,
.writing-pad__trace {
  position: absolute;
  inset: 0;
}

.writing-pad__canvas {
  z-index: 3;
  cursor: crosshair;
}

/* 描红：浅到能看清又不至于干扰 */
.writing-pad__trace {
  z-index: 1;
  color: #e3d9c8;
  text-align: center;
  font-weight: 400;
  user-select: none;
  pointer-events: none;
}

.writing-pad__demo {
  z-index: 2;
  pointer-events: none;
}

/* 笔顺：未演示到的那几笔不显示，演示到的是实色，当前笔有轻微放大提示 */
.writing-pad__stroke--on {
  opacity: 1;
}

.writing-pad__stroke--active {
  animation: stroke-blink 700ms ease-in-out infinite;
}

.writing-pad__actions {
  display: flex;
  gap: var(--space-sm);
}

.writing-pad__btn {
  min-height: var(--tap-min);
  padding: 0 var(--space-md);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  font-size: var(--font-body);
  font-weight: 600;
}

.writing-pad__btn--primary {
  background: var(--color-info);
  border-color: var(--color-info);
  color: var(--color-text-invert);
}

.writing-pad__tip {
  max-width: 280px;
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  line-height: 1.6;
  text-align: center;
}

.writing-pad__tip-note {
  color: var(--color-text-tertiary, #b6b9c0);
  font-size: var(--font-xs);
}

@keyframes stroke-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}
</style>
