/**
 * @study-club/subject-hanzi —— 识字学科包
 *
 * `packages/core` 必须学科无关；所有识字专属逻辑（拼音、笔顺、字源、题型）
 * 一律落在本包。将来扩科时新增 `packages/subject-english` 等，core 不动。
 */

export * from './pinyin';
export * from './questions';
export * from './reading';
export * from './stage';
