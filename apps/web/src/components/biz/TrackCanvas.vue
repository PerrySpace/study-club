<script setup lang="ts">
/**
 * TrackCanvas —— Canvas 绘制的闯关赛道（业务组件）。
 *
 * ## 为什么用 Canvas 而不是 SVG
 * 参考的竞品界面（洪恩「闯关达人」）是**手绘感**的：蜿蜒的赛道穿过草地，
 * 路边有树、花、云，节点是带高光的立体圆盘。这类场景有几十个装饰元素，
 * 且要随容器尺寸重排 —— 用 SVG 会产生上百个 DOM 节点，低端机上滚动直接掉帧；
 * Canvas 一个节点搞定，且 `requestAnimationFrame` 可做入场动画。
 *
 * ## 交互与可访问性（不牺牲）
 * Canvas 对屏幕阅读器是黑盒，所以：
 *   - 画布本身 `aria-hidden`；
 *   - ⭐ **每个关卡都是一个真实的 `<button>`**，绝对定位叠在画布之上。
 *     这样点得到、Tab 能遍历、读屏能念出关卡名与状态 —— 图形只是装饰，
 *     交互与语义都在 DOM 里。
 *
 * ## 确定性
 * 装饰（树、花、云）的位置由关卡 id 派生的伪随机数决定，**同一个 id 永远
 * 长在同一个位置**。若用 `Math.random()`，每次进页面装饰都会跳位，孩子会
 * 觉得「地图在动」。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { Lesson } from '@study-club/core';

import StarRow from '@/components/biz/StarRow.vue';

const props = defineProps<{
  lessons: Lesson[];
  completed: ReadonlySet<string>;
  /**
   * 已完成关卡的星星数（0–3）；缺失时按 0 处理。
   *
   * 与 `completed` 分开传：`completed` 只回答「做过没有」（解锁判定用），
   * 星星回答「做得怎么样」（显示用）—— 两者不是一回事，
   * 把星星塞进 Set 里就只能在「全空」和「全亮」之间二选一。
   */
  stars?: ReadonlyMap<string, number>;
  /** 判定某关是否解锁（逻辑在父层，这里只负责画与派发） */
  isUnlocked: (lesson: Lesson, index: number) => boolean;
  /** 关卡名（override 过的那种），缺省用 title */
  labelOf?: (lesson: Lesson, index: number) => string;
}>();

const emit = defineEmits<{
  (e: 'select', lesson: Lesson): void;
}>();

interface Node {
  lesson: Lesson;
  index: number;
  done: boolean;
  locked: boolean;
  current: boolean;
  label: string;
  /** 归一化坐标（0–1），渲染时乘以实际宽高 */
  x: number;
  y: number;
}

const wrapRef = ref<HTMLDivElement>();
const canvasRef = ref<HTMLCanvasElement>();
/** 节点绝对定位的像素坐标，供覆盖层的 button 使用。 */
const pixelNodes = ref<
  Array<Node & { px: number; py: number; size: number; stars: number }>
>([]);
/** 入场动画进度 0→1；关掉 prefers-reduced-motion 时直接置 1。 */
const progress = ref(0);

let raf = 0;
let observer: ResizeObserver | null = null;
let reduceMotion = false;

/**
 * 赛道横向摆幅。
 *
 * 参考图是明显的「之」字：节点左右交替且幅度接近半屏。摆幅给到 0.30（±30%）
 * 是权衡过的：再大节点会撞到边缘装饰，再小就退化成一条直线、失去「在走」的感觉。
 */
const SWAY_X = 0.3;
const NODE_SIZE = 58;

const nodes = computed<Node[]>(() => {
  const n = props.lessons.length;
  return props.lessons.map((lesson, index) => {
    const done = props.completed.has(lesson._id);
    // ⛔ 已完成 ⇒ 一定可点。父层的 `isUnlocked` 已经这样判；这里再兜一次，
    //    是因为「绿色对勾按不动」的根因就在这条链路上（父层传什么，这里画什么），
    //    而它只在「跳过前面的关直接做了后面」时出现，很难靠手点复现。
    const locked = !done && !props.isUnlocked(lesson, index);
    return {
      lesson,
      index,
      done,
      locked,
      current: !done && !locked,
      label: props.labelOf?.(lesson, index) || lesson.tag_label || lesson.title,
      // 纵向：首节点留出顶部空间（避开状态栏），末节点留出底部（避开开始按钮）
      y: n <= 1 ? 0.5 : 0.08 + (index / (n - 1)) * 0.84,
      // 横向之字：偶数偏右、奇数偏左，逐关交替
      x: n <= 1 ? 0.5 : 0.5 + (index % 2 === 0 ? SWAY_X : -SWAY_X) * (0.6 + 0.4 * ((index / 3) % 1)),
    };
  });
});

/**
 * 读取 CSS 变量作为画笔颜色。
 *
 * ⛔ **为什么不能硬编码色值**：场景色已上收为令牌
 * （`docs/06-工程规范/04-视觉风格规范.md` 规则 4.1）。硬编码意味着改主题要翻组件代码，
 * 而 Canvas 的绘制代码又不走 CSS 作用域样式 —— 这是最容易分裂的地方。
 *
 * 每次绘制时读取（而不是模块加载时缓存）：主题切换、页面首帧尚未完成
 * 样式加载时，缓存下来的会是空字符串。
 */
function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  return v.trim() || fallback;
}

/** 一次取齐本组件用到的场景色，避免每帧反复读样式。 */
interface Palette {
  sky: string;
  grass: string;
  path: string;
  pathEdge: string;
  trailDone: string;
  nodeDone: string;
  nodeDoneEdge: string;
  nodeCurrent: string;
  nodeCurrentEdge: string;
  nodeLocked: string;
  tree: string;
  flowerA: string;
  flowerB: string;
  cloud: string;
  petalCore: string;
  trunk: string;
  leafAlt: string;
  nodeIdle: string;
  nodeIdleEdge: string;
  nodeShadow: string;
  nodeGloss: string;
  white: string;
}

function readPalette(): Palette {
  return {
    sky: cssVar('--color-scene-sky', '#dff0c8'),
    grass: cssVar('--color-scene-grass', '#bcdc9c'),
    path: cssVar('--color-scene-path', '#f2f7e4'),
    pathEdge: cssVar('--color-scene-path-edge', '#96be6e'),
    trailDone: cssVar('--color-scene-trail-done', '#7ed6a3'),
    nodeDone: cssVar('--color-scene-node-done', '#4ec98a'),
    nodeDoneEdge: cssVar('--color-scene-node-done-edge', '#2f9e69'),
    nodeCurrent: cssVar('--color-scene-node-current', '#7ec8ff'),
    nodeCurrentEdge: cssVar('--color-scene-node-current-edge', '#3a86ff'),
    nodeLocked: cssVar('--color-scene-node-locked', '#b9c4ad'),
    tree: cssVar('--color-scene-tree', '#4f9e4a'),
    flowerA: cssVar('--color-scene-flower-a', '#f2a93b'),
    flowerB: cssVar('--color-scene-flower-b', '#ef6f6c'),
    cloud: cssVar('--color-scene-cloud', 'rgba(255,255,255,0.75)'),
    petalCore: '#fff3c4',
    trunk: '#8a6a44',
    leafAlt: '#3f8a3c',
    nodeIdle: '#ffffff',
    nodeIdleEdge: '#c8d6bc',
    nodeShadow: 'rgba(60, 90, 40, 0.22)',
    nodeGloss: 'rgba(255,255,255,0.55)',
    white: '#ffffff',
  };
}

/** 由字符串派生的确定性伪随机（同一 seed 永远同一结果）。 */
function seeded(seed: string): () => number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- 绘制

function draw(): void {
  const canvas = canvasRef.value;
  const wrap = wrapRef.value;
  if (!canvas || !wrap) return;

  const dpr = window.devicePixelRatio || 1;
  const w = wrap.clientWidth;
  // 每关给 130px 高度：赛道蜿蜒需要纵向空间，太密会看不清前后关系
  const h = Math.max(420, nodes.value.length * 130);
  if (w <= 0) return;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const p = readPalette();
  drawGround(ctx, w, h, p);
  const pts = nodes.value.map((n) => ({ x: n.x * w, y: n.y * h }));

  // 赛道：走过的实心、没走的虚线（用 progress 让它「生长」）
  drawTrail(ctx, pts, p);

  // 装饰画在赛道之下，避免压住节点
  drawDecorations(ctx, w, h, p);

  drawNodes(ctx, pts, p);

  // 记录像素坐标给覆盖层 button
  pixelNodes.value = nodes.value.map((n, i) => ({
    ...n,
    px: pts[i].x,
    py: pts[i].y,
    size: NODE_SIZE,
    stars: props.stars?.get(n.lesson._id) ?? 0,
  }));
}

/** 草地底色：上浅下深的渐层，模拟参考图的「站在草地上」。 */
function drawGround(ctx: CanvasRenderingContext2D, w: number, h: number, p: Palette): void {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, p.sky);
  g.addColorStop(1, p.grass);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

/** 赛道主体。节点坐标已由 draw() 算好，这里只负责画。 */
function drawTrail(
  ctx: CanvasRenderingContext2D,
  pts: Array<{ x: number; y: number }>,
  p: Palette,
): void {
  if (pts.length < 2) return;

  // 用二次贝塞尔把节点串成蜿蜒的路：控制点在两点中点的**水平**方向偏出，
  // 于是每一段都是弧线而不是折线 —— 这是与参考图观感最接近的做法。
  const path = new Path2D();
  path.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i += 1) {
    const prev = pts[i - 1];
    const cur = pts[i];
    const midY = (prev.y + cur.y) / 2;
    const bend = (cur.x - prev.x) * 0.35;
    path.bezierCurveTo(prev.x + bend, midY, cur.x - bend, midY, cur.x, cur.y);
  }

  // 路基（深色描边）：先画粗的暗色，再叠浅色的路面
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = p.pathEdge;
  ctx.lineWidth = 34;
  ctx.stroke(path);

  ctx.strokeStyle = p.path;
  ctx.lineWidth = 26;
  ctx.stroke(path);

  // 路面上的虚线中心线：还没走到的部分才画（走过的用实心暖色覆盖）
  const doneCount = nodes.value.filter((n) => n.done).length;
  // 画到「已完成关卡」之后：未完成段用虚线，已完成段用暖色实线
  if (doneCount > 0 && doneCount < pts.length) {
    const done = new Path2D();
    done.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i <= doneCount; i += 1) {
      const prev = pts[i - 1];
      const cur = pts[i];
      const midY = (prev.y + cur.y) / 2;
      const bend = (cur.x - prev.x) * 0.35;
      done.bezierCurveTo(prev.x + bend, midY, cur.x - bend, midY, cur.x, cur.y);
    }
    ctx.strokeStyle = p.trailDone;
    ctx.lineWidth = 8;
    ctx.setLineDash([]);
    ctx.stroke(done);
  }
}

/** 路边装饰：树、花、云。由关卡 id 派生的伪随机决定位置，刷新不跳位。 */
function drawDecorations(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  p: Palette,
): void {
  const rnd = seeded('decor:' + props.lessons.map((l) => l._id).join('|'));
  const margin = 26;

  for (let i = 0; i < 16; i += 1) {
    const x = margin + rnd() * (w - margin * 2);
    const y = 30 + rnd() * (h - 60);
    const kind = rnd();
    if (kind < 0.4) drawFlower(ctx, x, y, rnd, p);
    else if (kind < 0.7) drawTree(ctx, x, y, rnd, p);
    else drawCloud(ctx, x, y, rnd, p);
  }
}

function drawTree(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  rnd: () => number,
  p: Palette,
): void {
  const s = 0.6 + rnd() * 0.4;
  ctx.fillStyle = p.trunk;
  ctx.fillRect(x - 2 * s, y, 4 * s, 12 * s);
  ctx.fillStyle = rnd() > 0.5 ? p.tree : p.leafAlt;
  ctx.beginPath();
  ctx.arc(x, y, 11 * s, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x - 7 * s, y + 4 * s, 8 * s, 0, Math.PI * 2);
  ctx.arc(x + 7 * s, y + 4 * s, 8 * s, 0, Math.PI * 2);
  ctx.fill();
}

function drawFlower(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  rnd: () => number,
  p: Palette,
): void {
  const s = 0.5 + rnd() * 0.4;
  ctx.fillStyle = rnd() > 0.5 ? p.flowerA : p.flowerB;
  for (let i = 0; i < 5; i += 1) {
    const a = (i / 5) * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(x + Math.cos(a) * 4 * s, y + Math.sin(a) * 4 * s, 3 * s, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = p.petalCore;
  ctx.beginPath();
  ctx.arc(x, y, 2.2 * s, 0, Math.PI * 2);
  ctx.fill();
}

function drawCloud(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  rnd: () => number,
  p: Palette,
): void {
  const s = 0.5 + rnd() * 0.5;
  ctx.fillStyle = p.cloud;
  ctx.beginPath();
  ctx.arc(x, y, 10 * s, 0, Math.PI * 2);
  ctx.arc(x + 10 * s, y + 2 * s, 8 * s, 0, Math.PI * 2);
  ctx.arc(x - 10 * s, y + 2 * s, 7 * s, 0, Math.PI * 2);
  ctx.fill();
}

/** 关卡节点：立体圆盘（外圈 + 高光 + 底部阴影）。 */
function drawNodes(
  ctx: CanvasRenderingContext2D,
  pts: Array<{ x: number; y: number }>,
  pal: Palette,
): void {
  nodes.value.forEach((n, i) => {
    const p = pts[i];
    if (!p) return;
    const r = NODE_SIZE / 2;
    const appear = Math.min(1, Math.max(0, progress.value * nodes.value.length - i));
    if (appear <= 0) return;

    ctx.save();
    ctx.globalAlpha = appear;
    ctx.translate(p.x, p.y);

    // 底部投影：给节点「浮起来」的感觉
    ctx.fillStyle = pal.nodeShadow;
    ctx.beginPath();
    ctx.ellipse(0, r * 0.92, r * 0.92, r * 0.3, 0, 0, Math.PI * 2);
    ctx.fill();

    if (n.locked) {
      // ⛔ 未解锁一律灰（规则 2.2）。这里曾经用主色黄，等于教孩子
      // 「黄色 = 可以点」，点了没反应就毁掉了这个映射。
      ctx.fillStyle = pal.nodeLocked;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.85)';
      ctx.lineWidth = 4;
      ctx.stroke();
    } else {
      const fill = n.done ? pal.nodeDone : n.current ? pal.nodeCurrent : pal.nodeIdle;
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      // 外圈：已完成偏暖、当前偏蓝，形成「进度感」
      ctx.strokeStyle = n.done
        ? pal.nodeDoneEdge
        : n.current
          ? pal.nodeCurrentEdge
          : pal.nodeIdleEdge;
      ctx.lineWidth = 4;
      ctx.stroke();
      // 顶部高光
      ctx.fillStyle = pal.nodeGloss;
      ctx.beginPath();
      ctx.ellipse(0, -r * 0.34, r * 0.62, r * 0.34, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // 序号 / 对勾 / 锁
    // 序号 / 对勾 / 锁。
    // ⚠️ 三个状态的字色**分别验过对比度**（WCAG 大字需 ≥3:1）：
    //    已完成 #14512f on #4ec98a → 4.47
    //    进行中 #16548f on #7ec8ff → 4.30
    //    未解锁 #4e5946 on #b9c4ad → 4.07
    //    ⛔ 别为了让字「好看」调浅 —— 原来的白字/蓝字只有 1.8~1.9:1，
    //    低于阈值，在户外强光下完全看不清关卡编号。
    ctx.fillStyle = n.locked ? '#4e5946' : n.done ? '#14512f' : '#16548f';
    ctx.font = `600 ${Math.round(r * 0.8)}px system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    // ⛔ 未解锁**不画 emoji 🔒**：emoji 在各平台渲染差异大（规范 3.1），
    //    而且它不会跟随 ctx.fillStyle —— 各系统用自己的配色，深浅不可控。
    //    改画矢量锁形，颜色由 fillStyle 唯一决定。
    if (n.locked) {
      const s = r * 0.2;
      ctx.lineWidth = Math.max(2, r * 0.11);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.rect(-s, -s * 0.15, s * 2, s * 1.7);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(0, -s * 0.15, s * 0.75, Math.PI, 0);
      ctx.stroke();
    } else {
      ctx.fillText(n.done ? '✓' : String(n.index + 1), 0, 1);
    }
    ctx.restore();
  });
}

// ---------------------------------------------------------------- 生命周期

function animate(): void {
  if (reduceMotion) {
    progress.value = 1;
    draw();
    return;
  }
  const start = performance.now();
  const tick = (now: number): void => {
    const t = Math.min(1, (now - start) / 600);
    progress.value = t;
    draw();
    if (t < 1) raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
}

onMounted(() => {
  reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  observer = new ResizeObserver(() => draw());
  if (wrapRef.value) observer.observe(wrapRef.value);
  animate();
});

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf);
  observer?.disconnect();
});

watch(
  () => [props.lessons.length, props.completed.size, props.lessons.map((l) => l._id).join('|')],
  () => {
    progress.value = reduceMotion ? 1 : 0;
    animate();
  },
);
</script>

<template>
  <div ref="wrapRef" class="track-canvas">
    <!-- ⭐ 画布只是装饰，交互与语义都在下面这层真实的 button 上 -->
    <canvas ref="canvasRef" class="track-canvas__layer" aria-hidden="true" />

    <ul class="track-canvas__hits" role="list">
      <li
        v-for="n in pixelNodes"
        :key="n.lesson._id"
        class="track-canvas__hit"
        :style="{
          left: `${n.px - n.size / 2}px`,
          top: `${n.py - n.size / 2}px`,
          width: `${n.size}px`,
          height: `${n.size}px`,
        }"
      >
        <button
          type="button"
          class="track-canvas__btn tap clickable"
          :class="{
            'track-canvas__btn--locked': n.locked,
            'track-canvas__btn--current': n.current,
            'track-canvas__btn--done': n.done,
          }"
          :disabled="n.locked"
          :aria-label="`第 ${n.index + 1} 关 ${n.label}${n.done ? `（已完成，${n.stars} 颗星）` : n.locked ? '（未解锁）' : ''}`"
          @click="emit('select', n.lesson)"
        >
          <span class="sr-only">{{ n.label }}</span>
        </button>

        <!-- 关卡标签 + 已获得的星星（DOM 层：点得到、读屏念得出） -->
        <span class="track-canvas__tag" aria-hidden="true">
          <span class="track-canvas__name">{{ n.label }}</span>
          <StarRow v-if="n.done" :stars="n.stars" :size="13" class="track-canvas__stars" />
        </span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.track-canvas {
  position: relative;
  width: 100%;
  border-radius: var(--radius-lg);
  overflow: hidden;
  /* 底部渐隐，暗示「下面还有」，鼓励往下滑 */
  mask-image: linear-gradient(to bottom, #000 0, #000 88%, transparent 100%);
}

.track-canvas__layer {
  display: block;
  width: 100%;
}

.track-canvas__hits {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.track-canvas__hit {
  position: absolute;
}

/**
 * 透明的点击热区。
 *
 * 画布上的圆盘只是图像，**热区必须有一个真实的 button**：
 * 否则键盘 Tab 不到、读屏念不出、也无从获得焦点态。
 * 尺寸与画布上的圆盘一致（58px），保证「点哪就是哪」。
 */
.track-canvas__btn {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: transparent;
  border: none;
  cursor: pointer;
}

.track-canvas__btn:disabled {
  cursor: not-allowed;
}

/* 当前关：加一圈呼吸的光晕，把孩子的视线引到「下一步点哪」 */
.track-canvas__btn--current {
  animation: track-pulse 1.8s ease-in-out infinite;
}

/* 标签块整体挂在节点正下方，跟画布上的圆盘对齐 */
.track-canvas__tag {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translate(-50%, 4px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  max-width: 104px;
  pointer-events: none;
}

.track-canvas__name {
  max-width: 100%;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.82);
  color: var(--color-text);
  font-size: var(--font-xs);
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-canvas__btn--locked + .track-canvas__tag .track-canvas__name {
  color: var(--color-text-muted);
  opacity: 0.8;
}

.track-canvas__stars {
  padding: 1px 4px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.78);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@keyframes track-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(58, 134, 255, 0.55);
  }
  50% {
    box-shadow: 0 0 0 12px rgba(58, 134, 255, 0);
  }
}
</style>
