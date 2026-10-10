#!/usr/bin/env node
/**
 * 内容校验（C-02，CI 阻断）—— 无第三方依赖，可直接在 CI 与本地运行。
 *
 * 校验项：
 *   1. manifest 结构 + 各文件 checksum 与磁盘一致
 *   2. 每个实体必填字段与取值枚举
 *   3. 汉字无重复；组词必含本字；释义长度合规
 *   4. 单元 / 关卡的 character_ids 均指向存在且已发布的字
 *   5. 古诗每行 pinyin 的音节数与该行字数一致
 *   6. 所有内容文件均在 content/sources.json 登记来源
 *
 * 用法：node scripts/content/validate.mjs
 */

import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, resolve, relative } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../..');
const CONTENT = join(ROOT, 'content');

const errors = [];
const warnings = [];

function err(msg) {
  errors.push(msg);
}
function warn(msg) {
  warnings.push(msg);
}
function readJson(p) {
  return JSON.parse(readFileSync(p, 'utf8'));
}
function sha256(buf) {
  return 'sha256:' + createHash('sha256').update(buf).digest('hex');
}

// ---- 1. manifest ----
const manifestPath = join(CONTENT, 'manifest.json');
if (!existsSync(manifestPath)) {
  err('缺少 content/manifest.json（先运行 node scripts/content/build-content.mjs）');
  report();
}
const manifest = readJson(manifestPath);

for (const key of ['content_version', 'min_app_version', 'updated_at', 'counts', 'files']) {
  if (!(key in manifest)) err(`manifest 缺少字段 ${key}`);
}
if (!/^\d+\.\d+\.\d+$/.test(manifest.content_version ?? '')) err('manifest.content_version 不是语义化版本');
if (!/^\d+\.\d+\.\d+$/.test(manifest.min_app_version ?? '')) err('manifest.min_app_version 不是语义化版本');

const loaded = {};
for (const file of manifest.files ?? []) {
  const full = join(CONTENT, file.path);
  if (!existsSync(full)) {
    err(`manifest 登记的 ${file.path} 不存在`);
    continue;
  }
  const buf = readFileSync(full);
  const sum = sha256(buf);
  if (sum !== file.checksum) err(`${file.path} checksum 不一致（manifest=${file.checksum.slice(0, 20)}… 实际=${sum.slice(0, 20)}…）`);
  if (buf.length !== file.bytes) err(`${file.path} 字节数不一致`);
  const payload = readJson(full);
  if (!Array.isArray(payload.items)) err(`${file.path} 缺少 items 数组`);
  else if (payload.items.length !== file.count) err(`${file.path} 条目数不一致（manifest=${file.count} 实际=${payload.items.length}）`);
  loaded[file.path] = payload.items ?? [];
}

const characters = loaded['characters/grade-1.json'] ?? [];
const poems = loaded['poems/required-75.json'] ?? [];
const units = loaded['lessons/units.json'] ?? [];
const lessons = loaded['lessons/lessons.json'] ?? [];

// ---- 2/3. 汉字 ----
const REQUIRED_CHAR_FIELDS = [
  '_id', 'char', 'pinyin', 'pinyin_plain', 'tone', 'is_polyphone', 'polyphone_readings', 'radical',
  'stroke_count', 'structure', 'stroke_order_ref', 'meaning', 'words', 'sentences', 'pictograph',
  'image_ref', 'audio_ref', 'grade', 'level', 'difficulty', 'tags', 'similar_chars', 'antonym',
  'synonyms', 'unit_refs', 'status', 'version', 'created_at', 'updated_at',
];
const STRUCTURES = ['独体', '左右', '上下', '半包围', '全包围', '品字'];
const STATUSES = ['draft', 'pending_review', 'published', 'offline', 'deleted'];

const seenChars = new Map();
const charIds = new Set();
for (const c of characters) {
  for (const f of REQUIRED_CHAR_FIELDS) {
    if (!(f in c)) err(`字条 ${c.char ?? c._id} 缺少字段 ${f}`);
  }
  if (seenChars.has(c.char)) err(`汉字重复：${c.char}（${seenChars.get(c.char)} 与 ${c._id}）`);
  else seenChars.set(c.char, c._id);
  charIds.add(c._id);

  if (c.meaning && c.meaning.length > 40) err(`「${c.char}」释义超过 40 字`);
  if (!STRUCTURES.includes(c.structure)) err(`「${c.char}」structure 取值非法：${c.structure}`);
  if (!STATUSES.includes(c.status)) err(`「${c.char}」status 取值非法：${c.status}`);
  if (!Array.isArray(c.words) || c.words.length < 3) err(`「${c.char}」组词少于 3 个`);
  else if (!c.words.some((w) => w.includes(c.char))) err(`「${c.char}」组词中均不含本字`);
  if (!Array.isArray(c.sentences) || c.sentences.length < 1) err(`「${c.char}」缺少例句`);
  if (c.pinyin_plain && !/^[a-zv]+$/.test(c.pinyin_plain)) err(`「${c.char}」pinyin_plain 含非小写字母：${c.pinyin_plain}`);
  if (c.is_polyphone && (!c.polyphone_readings || c.polyphone_readings.length === 0)) {
    err(`「${c.char}」标记为多音字但未给 polyphone_readings`);
  }
}

// ---- 4. 单元与关卡的外键 ----
const unitIds = new Set();
for (const u of units) {
  unitIds.add(u._id);
  for (const id of u.character_ids ?? []) {
    if (!charIds.has(id)) err(`单元 ${u.unit_code} 引用了不存在的字 id：${id}`);
  }
}
for (const l of lessons) {
  for (const id of l.character_ids ?? []) {
    if (!charIds.has(id)) err(`关卡 ${l._id} 引用了不存在的字 id：${id}`);
  }
  if (l.unit_id && !unitIds.has(l.unit_id)) err(`关卡 ${l._id} 引用了不存在的单元：${l.unit_id}`);
}
for (const c of characters) {
  for (const ref of c.unit_refs ?? []) {
    if (!unitIds.has(ref.unit_id)) err(`「${c.char}」的 unit_refs 指向不存在的单元：${ref.unit_id}`);
  }
}

// ---- 5. 古诗音字数 ----
for (const p of poems) {
  if (!Array.isArray(p.lines) || p.lines.length < 2) err(`古诗「${p.title}」行数少于 2`);
  for (const line of p.lines ?? []) {
    const chars = [...line.text].length;
    const syllables = line.pinyin.trim().split(/\s+/).length;
    if (chars !== syllables) {
      err(`古诗「${p.title}」行「${line.text}」字数 ${chars} 与注音音节数 ${syllables} 不一致`);
    }
  }
  if (p.appreciation && p.appreciation.length > 100) err(`古诗「${p.title}」赏析超过 100 字`);
}

// ---- 6. 来源登记 ----
const sourcesPath = join(CONTENT, 'sources.json');
if (!existsSync(sourcesPath)) err('缺少 content/sources.json');
else {
  const sources = readJson(sourcesPath);
  const registered = new Set((sources.self_authored ?? []).map((s) => s.path));
  for (const file of manifest.files ?? []) {
    if (!registered.has(file.path)) err(`内容文件 ${file.path} 未在 sources.json 登记来源（未登记不得入库）`);
  }
}

// ---- 其他：目录里是否有游离文件 ----
const onDisk = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === 'schema') continue;
      walk(full);
    } else if (name.endsWith('.json') && name !== 'manifest.json' && name !== 'sources.json') {
      onDisk.push(relative(CONTENT, full).split('\\').join('/'));
    }
  }
})(CONTENT);
const declared = new Set((manifest.files ?? []).map((f) => f.path));
for (const f of onDisk) if (!declared.has(f)) warn(`目录中存在未登记进 manifest 的文件：${f}`);

function report() {
  if (warnings.length) {
    console.log(`\n⚠️  ${warnings.length} 条警告：`);
    for (const w of warnings) console.log('   - ' + w);
  }
  if (errors.length) {
    console.error(`\n❌ 内容校验失败，共 ${errors.length} 项：`);
    for (const e of errors) console.error('   - ' + e);
    process.exit(1);
  }
  console.log(`\n✅ 内容校验通过：${characters.length} 字 / ${poems.length} 古诗 / ${units.length} 单元 / ${lessons.length} 关卡`);
  process.exit(0);
}

report();
