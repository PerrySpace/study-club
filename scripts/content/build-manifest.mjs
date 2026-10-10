#!/usr/bin/env node
/**
 * 重建内容包清单 —— 贡献者手工编辑 content/ 下的 JSON 后运行本脚本，
 * 重算各文件 checksum 与条目数并写回 content/manifest.json。
 *
 * 用法：node scripts/content/build-manifest.mjs [--bump patch|minor|major]
 */

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../..');
const CONTENT = join(ROOT, 'content');
const manifestPath = join(CONTENT, 'manifest.json');

/**
 * 受清单跟踪的内容文件。
 *
 * ⚠️ `key` 必须显式给出，不能用「路径首段」当聚合键：
 * `lessons/units.json`（单元）与 `lessons/lessons.json`（关卡）同处 `lessons/` 目录，
 * 按目录聚合会把两者加成一个 `lessons: 21`，而客户端读的是
 * `counts.lessons`（关卡数）与 `counts.units`（单元数）两个**不同**的口径。
 */
const TRACKED = [
  { path: 'characters/grade-1.json', key: 'characters' },
  { path: 'poems/required-75.json', key: 'poems' },
  { path: 'lessons/units.json', key: 'units' },
  { path: 'lessons/lessons.json', key: 'lessons' },
  { path: 'stories/stories.json', key: 'stories' },
  { path: 'readings/readings.json', key: 'readings' },
  { path: 'badges/badges.json', key: 'badges' },
];

const bumpArg = process.argv.indexOf('--bump');
const bump = bumpArg >= 0 ? process.argv[bumpArg + 1] : null;

if (!existsSync(manifestPath)) {
  console.error('缺少 content/manifest.json');
  process.exit(1);
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));

function bumpVersion(v, kind) {
  const [maj, min, pat] = v.split('.').map(Number);
  if (kind === 'major') return `${maj + 1}.0.0`;
  if (kind === 'minor') return `${maj}.${min + 1}.0`;
  return `${maj}.${min}.${pat + 1}`;
}

const files = [];
const counts = {};
for (const { path: rel, key } of TRACKED) {
  const full = join(CONTENT, rel);
  if (!existsSync(full)) {
    console.warn(`跳过不存在的文件：${rel}`);
    continue;
  }
  const buf = readFileSync(full);
  const payload = JSON.parse(buf.toString('utf8'));
  const count = Array.isArray(payload.items) ? payload.items.length : 0;
  counts[key] = (counts[key] ?? 0) + count;
  files.push({
    path: rel,
    checksum: 'sha256:' + createHash('sha256').update(buf).digest('hex'),
    bytes: buf.length,
    count,
  });
}

const next = {
  content_version: bump ? bumpVersion(manifest.content_version, bump) : manifest.content_version,
  min_app_version: manifest.min_app_version,
  updated_at: new Date().toISOString(),
  counts,
  files,
};
writeFileSync(manifestPath, JSON.stringify(next, null, 2) + '\n', 'utf8');
console.log('manifest 已更新：', next.content_version, JSON.stringify(counts));
