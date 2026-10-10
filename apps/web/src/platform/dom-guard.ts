/**
 * 交互防误触守卫（全局，只装一次）—— 见 02-2 §3.3。
 *
 * 背景：孩子是**整只手掌按在屏幕上**操作学习界面的，浏览器默认行为会不断捣乱：
 * 长按选中一段文字、把字卡拖出残影、双指把页面捏大 —— 每一样都会让学习中断，
 * 而且孩子自己退不回来。
 *
 * 分工（**先 CSS 后 JS**，别把纯样式问题写成事件拦截）：
 *   - `apps/web/src/styles/base.css` 负责大头：`user-select` / `touch-action` /
 *     `-webkit-touch-callout` / `-webkit-user-drag` / `overscroll-behavior`。
 *   - 本文件只补 CSS **管不到或不可靠**的三处：
 *       ① `selectstart` —— 少数 WebKit 版本在「先建立选区、再应用样式」的时序下仍会闪一次蓝底；
 *       ② `dragstart` —— `-webkit-user-drag` 在旧版 Safari / 部分安卓内核无效，兜底拦截；
 *       ③ `gesturestart/change/end` + `ctrl+wheel` —— iOS 10+ 起 Safari **忽略**
 *          viewport 的 `user-scalable=no`，捏合缩放只能靠事件拦；桌面端触控板捏合
 *          走的是 `wheel + ctrlKey`，同理。
 *
 * ⚠️ 这里是**唯一**允许直接写 `document` 的事件绑定处之一（另一个是 main.ts 的挂载），
 *    与 06-1 §2.9.2 一致：视图层不出现浏览器 API。
 */

/** 需要保留原生行为（能选中、能右键、能拖）的元素：可编辑控件与显式标了 `.selectable` 的区域。 */
const PROTECTED_SELECTOR = [
  'input',
  'textarea',
  'select',
  '[contenteditable=""]',
  '[contenteditable="true"]',
  '.selectable',
].join(',');

/** Safari 的私有捏合事件（lib.dom 里没有，用字符串绑）。 */
const GESTURE_EVENTS = ['gesturestart', 'gesturechange', 'gestureend'] as const;

function isProtected(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(PROTECTED_SELECTOR) !== null;
}

/**
 * 安装全局守卫。幂等：重复调用只装一次（模块级标记）。
 *
 * 返回卸载函数，主要给测试与热更新用；生产流程里活到页面结束即可。
 */
let installed = false;

export function installInteractionGuards(): () => void {
  if (installed) return () => undefined;
  installed = true;

  /** 阻止选区：`selectstart` 早于选区建立，preventDefault 即「这次选中根本没发生」。 */
  const onSelectStart = (event: Event): void => {
    if (!isProtected(event.target)) event.preventDefault();
  };

  /** 阻止拖拽：不拦的话触屏上会拖出半透明残影，松手还可能触发一次导航。 */
  const onDragStart = (event: Event): void => {
    if (!isProtected(event.target)) event.preventDefault();
  };

  /**
   * 阻止长按 / 右键菜单。
   * `.selectable` 与输入框放行 —— 家长在报告页要能右键复制一段分析。
   */
  const onContextMenu = (event: Event): void => {
    if (!isProtected(event.target)) event.preventDefault();
  };

  /** 阻止 Safari 捏合缩放。 */
  const onGesture = (event: Event): void => {
    event.preventDefault();
  };

  /**
   * 阻止桌面端缩放：
   *   - `ctrl+wheel`（触控板捏合 / Ctrl+滚轮）—— 唯一能在网页里拦住的缩放入口，必须 `passive: false`；
   *   - 浏览器自身的 Ctrl + / - / 0 快捷键拦不住（属浏览器 UI 层），这是已知且可接受的缺口：
   *     学习场景是触屏设备，桌面浏览器缩放不会影响孩子。
   */
  const onWheel = (event: WheelEvent): void => {
    if (event.ctrlKey) event.preventDefault();
  };

  document.addEventListener('selectstart', onSelectStart);
  document.addEventListener('dragstart', onDragStart);
  document.addEventListener('contextmenu', onContextMenu);
  document.addEventListener('wheel', onWheel, { passive: false });
  for (const type of GESTURE_EVENTS) {
    document.addEventListener(type, onGesture, { passive: false });
  }

  return () => {
    installed = false;
    document.removeEventListener('selectstart', onSelectStart);
    document.removeEventListener('dragstart', onDragStart);
    document.removeEventListener('contextmenu', onContextMenu);
    document.removeEventListener('wheel', onWheel);
    for (const type of GESTURE_EVENTS) {
      document.removeEventListener(type, onGesture);
    }
  };
}
