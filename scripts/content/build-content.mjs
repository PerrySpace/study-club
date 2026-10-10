#!/usr/bin/env node
/**
 * 内容构建工具（C-03 内容批量导入工具的雏形）。
 *
 * 把下面「作者表」里人工校订过的紧凑数据，展开为符合 content/schema/*.json 的完整内容包，
 * 并计算各文件 checksum 写入 content/manifest.json。
 *
 * 用法：
 *   node scripts/content/build-content.mjs
 *
 * 纪律（见 docs/01-产品规划/04-免费开放与开源策略.md 第五章）：
 *   - 本文件的作者表是**自编内容**，不含任何教材映射（不复制出版物单元顺序与课文标题）。
 *   - 引入第三方数据（拼音、笔顺、古诗原文）必须登记到 content/sources.json。
 */

import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../..');
const CONTENT = join(ROOT, 'content');

const CONTENT_VERSION = '1.0.0';
const MIN_APP_VERSION = '0.1.0';

// ---------------------------------------------------------------------------
// 声调工具（生成期使用，运行时版本在 packages/subject-hanzi/src/pinyin.ts）
// ---------------------------------------------------------------------------
const TONE_MARKS = {
  ā: ['a', 1], á: ['a', 2], ǎ: ['a', 3], à: ['a', 4],
  ō: ['o', 1], ó: ['o', 2], ǒ: ['o', 3], ò: ['o', 4],
  ē: ['e', 1], é: ['e', 2], ě: ['e', 3], è: ['e', 4],
  ī: ['i', 1], í: ['i', 2], ǐ: ['i', 3], ì: ['i', 4],
  ū: ['u', 1], ú: ['u', 2], ǔ: ['u', 3], ù: ['u', 4],
  ǖ: ['v', 1], ǘ: ['v', 2], ǚ: ['v', 3], ǜ: ['v', 4],
};

function analysePinyin(pinyin) {
  let plain = '';
  let tone = 0;
  for (const ch of pinyin) {
    const hit = TONE_MARKS[ch];
    if (hit) {
      plain += hit[0];
      tone = hit[1];
    } else {
      plain += ch;
    }
  }
  return { plain: plain.replace(/ü/g, 'v'), tone };
}

// ---------------------------------------------------------------------------
// 作者表 · 一年级字表（自编，60 字）
// [字, 拼音, 部首, 笔画, 结构, 释义(≤40字), 组词[], 例句[], 难度1-5, 主题标签[], 字源说明|null, 反义字|null]
// ---------------------------------------------------------------------------
const GRADE1 = [
  ['一', 'yī', '一', 1, '独体', '数字，最小的正整数', ['一个', '一起', '第一'], ['我有一本书。', '我们一起玩。'], 1, ['数字'], '一横表示数目「一」。', null],
  ['二', 'èr', '二', 2, '独体', '数字，一加一', ['二月', '第二', '二手'], ['二月里天气还很冷。'], 1, ['数字'], null, null],
  ['三', 'sān', '一', 3, '独体', '数字，二加一', ['三天', '三角', '再三'], ['我三天前种下的豆子发芽了。'], 1, ['数字'], null, null],
  ['四', 'sì', '囗', 5, '全包围', '数字，三加一', ['四季', '四方', '四周'], ['一年有四季。'], 1, ['数字'], null, null],
  ['五', 'wǔ', '二', 4, '独体', '数字，四加一', ['五月', '五官', '五彩'], ['五月一日是劳动节。'], 1, ['数字'], null, null],
  ['六', 'liù', '八', 4, '上下', '数字，五加一', ['六月', '六只', '六边'], ['六月里荷花开了。'], 1, ['数字'], null, null],
  ['七', 'qī', '一', 2, '独体', '数字，六加一', ['七天', '七彩', '七巧板'], ['彩虹有七种颜色。'], 1, ['数字'], null, null],
  ['八', 'bā', '八', 2, '独体', '数字，七加一', ['八月', '八方', '八哥'], ['八月十五是中秋节。'], 1, ['数字'], null, null],
  ['九', 'jiǔ', '丿', 2, '独体', '数字，八加一', ['九月', '九天', '九牛一毛'], ['九月开学了。'], 1, ['数字'], null, null],
  ['十', 'shí', '十', 2, '独体', '数字，九加一', ['十分', '十月', '十足'], ['我数到十就停下来。'], 1, ['数字'], null, null],

  ['人', 'rén', '人', 2, '独体', '会说话、会劳动的人', ['人们', '大人', '人口'], ['公园里人很多。'], 1, ['人体'], '像一个侧身站立的人。', null],
  ['口', 'kǒu', '口', 3, '独体', '嘴；也用作量词', ['开口', '口水', '一口'], ['请张开你的口。'], 1, ['人体'], '像一张张开的嘴。', null],
  ['手', 'shǒu', '手', 4, '独体', '人体上肢的末端，能拿东西', ['双手', '手心', '手工'], ['我用双手捧起水。'], 1, ['人体'], '像一只五指张开的手。', null],
  ['足', 'zú', '足', 7, '上下', '脚；也指足够', ['足球', '满足', '足下'], ['我参加了足球比赛。'], 2, ['人体'], null, null],
  ['目', 'mù', '目', 5, '独体', '眼睛', ['目光', '题目', '耳目'], ['他抬起头，目光很亮。'], 2, ['人体'], '像一只竖起来的眼睛。', null],
  ['耳', 'ěr', '耳', 6, '独体', '听觉器官', ['耳朵', '木耳', '耳目'], ['小兔子的耳朵很长。'], 2, ['人体'], null, null],

  ['日', 'rì', '日', 4, '独体', '太阳；也指一天', ['日出', '生日', '日子'], ['日出的时候天边红了。'], 1, ['自然'], '像一轮圆圆的太阳。', null],
  ['月', 'yuè', '月', 4, '独体', '月亮；也指月份', ['月亮', '月光', '一月'], ['月亮弯弯像小船。'], 1, ['自然'], '像一弯新月。', null],
  ['水', 'shuǐ', '水', 4, '独体', '没有颜色、没有味道的液体', ['喝水', '水果', '水面'], ['多喝水对身体好。'], 1, ['自然'], '像流动的水纹。', null],
  ['火', 'huǒ', '火', 4, '独体', '东西燃烧时发出的光和热', ['火车', '火苗', '大火'], ['火苗在风中跳来跳去。'], 1, ['自然'], '像跳动的火焰。', null],
  ['木', 'mù', '木', 4, '独体', '树木；也指木头', ['树木', '木头', '木马'], ['院子里种了一棵小树。'], 2, ['自然'], '像一棵有枝有根的树。', null],
  ['金', 'jīn', '金', 8, '上下', '金属；也指钱', ['金子', '金色', '金属'], ['秋天的稻田一片金色。'], 3, ['自然'], null, null],
  ['土', 'tǔ', '土', 3, '独体', '地面上的泥沙', ['土地', '泥土', '土豆'], ['花种在泥土里。'], 1, ['自然'], '像地面隆起的一堆土。', null],
  ['天', 'tiān', '大', 4, '独体', '天空；也指一天', ['天空', '白天', '天气'], ['天空飘着白云。'], 1, ['自然'], null, null],
  ['地', 'dì', '土', 6, '左右', '地面；也指地方', ['土地', '地面', '大地'], ['大地披上了绿衣裳。'], 2, ['自然'], null, null],
  ['山', 'shān', '山', 3, '独体', '地面上高高隆起的部分', ['高山', '山脚', '山上'], ['远处的山高高的。'], 1, ['自然'], '像三座连着的山峰。', null],
  ['石', 'shí', '石', 5, '独体', '石头', ['石头', '石子', '化石'], ['河边有很多石头。'], 2, ['自然'], null, null],
  ['田', 'tián', '田', 5, '全包围', '种庄稼的土地', ['田地', '稻田', '田野'], ['稻田里的稻子黄了。'], 2, ['自然'], '像一块块分好的田地。', null],

  ['上', 'shàng', '一', 3, '独体', '位置在高处', ['上面', '上学', '早上'], ['书包放在桌子上。'], 1, ['方位'], null, '下'],
  ['下', 'xià', '一', 3, '独体', '位置在低处', ['下面', '下雨', '下午'], ['小鱼躲到水下面。'], 1, ['方位'], null, '上'],
  ['大', 'dà', '大', 3, '独体', '体积或数量多', ['大人', '长大', '大声'], ['大象的耳朵很大。'], 1, ['形容'], null, '小'],
  ['小', 'xiǎo', '小', 3, '独体', '体积或数量少', ['小心', '大小', '小鸟'], ['小蚂蚁在搬米粒。'], 1, ['形容'], null, '大'],
  ['多', 'duō', '夕', 6, '上下', '数量大', ['多少', '许多', '多么'], ['花园里有许多蝴蝶。'], 2, ['数量'], null, '少'],
  ['少', 'shǎo', '小', 4, '独体', '数量小', ['多少', '少数', '少年'], ['今天来的人很少。'], 2, ['数量'], null, '多'],
  ['好', 'hǎo', '女', 6, '左右', '优点多，让人满意', ['好人', '好听', '你好'], ['你好，很高兴认识你。'], 1, ['形容'], null, null],

  ['学', 'xué', '子', 8, '上下', '学习', ['学生', '上学', '学习'], ['我每天都要学习。'], 1, ['学习'], null, null],
  ['生', 'shēng', '生', 5, '独体', '生长；也指学生', ['生长', '学生', '生日'], ['小树在小院里生长。'], 2, ['学习'], null, null],
  ['书', 'shū', '乛', 4, '独体', '装订成册的读物', ['看书', '书本', '书包'], ['我最喜欢看书。'], 1, ['学习'], null, null],
  ['本', 'běn', '木', 5, '独体', '本子；也指根本', ['本子', '书本', '本来'], ['我把本子交给老师。'], 2, ['学习'], null, null],
  ['文', 'wén', '文', 4, '独体', '文字；也指文章', ['语文', '文字', '作文'], ['语文课上我们读课文。'], 2, ['学习'], null, null],

  ['门', 'mén', '门', 3, '独体', '房屋的出入口', ['大门', '门口', '开门'], ['请把大门关上。'], 1, ['生活'], '像一扇双开的门。', null],
  ['车', 'chē', '车', 4, '独体', '陆地上的交通工具', ['汽车', '火车', '车站'], ['汽车在马路上一辆接一辆。'], 1, ['生活'], null, null],

  ['马', 'mǎ', '马', 3, '独体', '一种善跑的动物', ['马路', '木马', '小马'], ['小马在草地上跑。'], 1, ['动物'], '像一匹有鬃毛的马。', null],
  ['牛', 'niú', '牛', 4, '独体', '一种家畜', ['水牛', '牛奶', '小牛'], ['水牛在田里慢慢走。'], 2, ['动物'], '像牛头的形状。', null],
  ['羊', 'yáng', '羊', 6, '独体', '一种家畜', ['山羊', '绵羊', '羊毛'], ['小羊在山上吃草。'], 2, ['动物'], null, null],
  ['鸟', 'niǎo', '鸟', 5, '独体', '有羽毛和翅膀的动物', ['小鸟', '鸟窝', '飞鸟'], ['小鸟在树上唱歌。'], 2, ['动物'], null, null],
  ['鱼', 'yú', '鱼', 8, '上下', '生活在水里的动物', ['金鱼', '小鱼', '鱼儿'], ['金鱼在水里游来游去。'], 2, ['动物'], null, null],
  ['虫', 'chóng', '虫', 6, '独体', '昆虫', ['虫子', '昆虫', '毛虫'], ['毛毛虫慢慢爬。'], 2, ['动物'], null, null],

  ['花', 'huā', '艹', 7, '上下', '植物开出的花朵', ['花朵', '花园', '开花'], ['花园里开满了花。'], 1, ['植物'], null, null],
  ['草', 'cǎo', '艹', 9, '上下', '草本植物', ['小草', '草地', '青草'], ['小草从土里钻出来。'], 2, ['植物'], null, null],
  ['树', 'shù', '木', 9, '左右', '木本植物', ['大树', '树叶', '树木'], ['大树下面很凉快。'], 2, ['植物'], null, null],
  ['果', 'guǒ', '木', 8, '上下', '果实', ['水果', '苹果', '果树'], ['我喜欢吃水果。'], 2, ['植物'], null, null],

  ['风', 'fēng', '风', 4, '半包围', '空气的流动', ['大风', '风雨', '风车'], ['大风把树叶吹跑了。'], 2, ['自然'], null, null],
  ['云', 'yún', '二', 4, '独体', '天上的水汽凝成的一片', ['白云', '云朵', '乌云'], ['天上有一片白云。'], 1, ['自然'], null, null],
  ['雨', 'yǔ', '雨', 8, '独体', '从云中落下来的水', ['下雨', '雨水', '大雨'], ['下雨了，记得带伞。'], 1, ['自然'], null, null],
  ['白', 'bái', '白', 5, '独体', '像雪一样的颜色', ['白云', '白天', '明白'], ['小兔子的毛是白的。'], 1, ['颜色'], null, '黑'],
  ['红', 'hóng', '纟', 6, '左右', '像血一样的颜色', ['红色', '红花', '火红'], ['红红的苹果挂满枝头。'], 2, ['颜色'], null, null],

  ['来', 'lái', '木', 7, '独体', '从别处到这里', ['回来', '出来', '来到'], ['春天来了，燕子飞回来了。'], 2, ['动作'], null, '去'],
  ['去', 'qù', '厶', 5, '上下', '从这里到别处', ['出去', '回去', '去年'], ['去年我学会了游泳。'], 2, ['动作'], null, '来'],
  ['看', 'kàn', '目', 9, '上下', '用眼睛观察', ['看书', '看见', '好看'], ['我在阳台上看星星。'], 1, ['动作'], null, null],
];

// ---------------------------------------------------------------------------
// 作者表 · 自编单元（按主题 / 字形规律组织，**不复制任何出版物单元顺序**）
// ---------------------------------------------------------------------------
const UNITS = [
  {
    unit_code: 'u-g1-01', title: '数字一家', theme: '数字',
    organize_by: 'theme', unit_type: '识字', order: 1,
    focus: '认识一至十，学会数数并读出数字。',
    chars: ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'],
  },
  {
    unit_code: 'u-g1-02', title: '我的身体', theme: '人与身体',
    organize_by: 'theme', unit_type: '识字', order: 2,
    focus: '认识人、口、手、足、目、耳，能说说它们的作用。',
    chars: ['人', '口', '手', '足', '目', '耳'],
  },
  {
    unit_code: 'u-g1-03', title: '天地山水', theme: '自然',
    organize_by: 'theme', unit_type: '识字', order: 3,
    focus: '认识自然界的常见事物，感受汉字的象形之美。',
    chars: ['日', '月', '水', '火', '木', '金', '土', '天', '地', '山', '石', '田', '风', '云', '雨'],
  },
  {
    unit_code: 'u-g1-04', title: '身边的大小', theme: '方位与比较',
    organize_by: 'radical', unit_type: '识字', order: 4,
    focus: '学会上/下、大/小、多/少这几对相反的字。',
    chars: ['上', '下', '大', '小', '多', '少', '好'],
  },
  {
    unit_code: 'u-g1-05', title: '读书写字', theme: '学习',
    organize_by: 'theme', unit_type: '识字', order: 5,
    focus: '认识与学习生活有关的字，学会说一句完整的话。',
    chars: ['学', '生', '书', '本', '文', '门', '车'],
  },
  {
    unit_code: 'u-g1-06', title: '动物朋友', theme: '动物',
    organize_by: 'theme', unit_type: '识字', order: 6,
    focus: '认识常见动物，并说出它们住在哪里。',
    chars: ['马', '牛', '羊', '鸟', '鱼', '虫'],
  },
  {
    unit_code: 'u-g1-07', title: '花草树木', theme: '植物',
    organize_by: 'radical', unit_type: '识字', order: 7,
    focus: '认识草字头与木字旁，发现偏旁和意思的关系。',
    chars: ['花', '草', '树', '果', '白', '红', '来', '去', '看'],
  },
];

// ---------------------------------------------------------------------------
// 作者表 · 关卡
// ---------------------------------------------------------------------------
const LESSONS = [
  { title: '数一数', unit: 'u-g1-01', chars: ['一', '二', '三', '四', '五'], games: ['image-choice', 'audio-choice'] },
  { title: '接着数', unit: 'u-g1-01', chars: ['六', '七', '八', '九', '十'], games: ['image-choice', 'pinyin-match'] },
  { title: '认识我自己', unit: 'u-g1-02', chars: ['人', '口', '手'], games: ['image-choice', 'word-build'] },
  { title: '五官本领大', unit: 'u-g1-02', chars: ['足', '目', '耳'], games: ['image-choice', 'audio-choice'] },
  { title: '太阳和月亮', unit: 'u-g1-03', chars: ['日', '月', '水', '火', '木'], games: ['image-choice', 'pinyin-match'] },
  { title: '大地与山川', unit: 'u-g1-03', chars: ['金', '土', '天', '地', '山'], games: ['image-choice', 'word-build'] },
  { title: '石头和田地', unit: 'u-g1-03', chars: ['石', '田', '风', '云', '雨'], games: ['image-choice', 'audio-choice'] },
  { title: '上面和下面', unit: 'u-g1-04', chars: ['上', '下', '大', '小'], games: ['image-choice', 'pinyin-match'] },
  { title: '多一点少一点', unit: 'u-g1-04', chars: ['多', '少', '好'], games: ['image-choice', 'word-build'] },
  { title: '我要上学', unit: 'u-g1-05', chars: ['学', '生', '书', '本'], games: ['image-choice', 'audio-choice'] },
  { title: '读书和出门', unit: 'u-g1-05', chars: ['文', '门', '车'], games: ['image-choice', 'pinyin-match'] },
  { title: '动物朋友', unit: 'u-g1-06', chars: ['马', '牛', '羊', '鸟', '鱼', '虫'], games: ['image-choice', 'audio-choice'] },
  { title: '花草树木', unit: 'u-g1-07', chars: ['花', '草', '树', '果'], games: ['image-choice', 'word-build'] },
  { title: '颜色和动作', unit: 'u-g1-07', chars: ['白', '红', '来', '去', '看'], games: ['image-choice', 'pinyin-match'] },
];

// ---------------------------------------------------------------------------
// 作者表 · 古诗（原文属公有领域；逐字注音自校）
// ---------------------------------------------------------------------------
const POEMS = [
  {
    id: 'po_jingyesi',
    title: '静夜思', dynasty: '唐', author: '李白',
    lines: [
      ['床前明月光', 'chuáng qián míng yuè guāng', '床前洒满了明亮的月光'],
      ['疑是地上霜', 'yí shì dì shàng shuāng', '好像是地上结了一层白霜'],
      ['举头望明月', 'jǔ tóu wàng míng yuè', '抬起头望着天上的明月'],
      ['低头思故乡', 'dī tóu sī gù xiāng', '低下头就想起了远方的家乡'],
    ],
    appreciation: '诗人离家在外，夜里看到月光，想起了家乡。短短四句话，写出了想家的心情。',
    background: '李白在外旅行时写下这首诗。',
    key_characters: ['月', '明', '光', '思', '乡'],
    grade: 1, difficulty: 1, source: '课标必背', theme_tags: ['思乡'],
  },
  {
    id: 'po_yonge',
    title: '咏鹅', dynasty: '唐', author: '骆宾王',
    lines: [
      ['鹅', 'é', '大白鹅'],
      ['曲项向天歌', 'qū xiàng xiàng tiān gē', '弯着脖子对着天空唱歌'],
      ['白毛浮绿水', 'bái máo fú lǜ shuǐ', '雪白的羽毛浮在碧绿的水面上'],
      ['红掌拨清波', 'hóng zhǎng bō qīng bō', '红红的脚掌拨动着清清的水波'],
    ],
    appreciation: '诗人小时候看鹅游泳，把鹅的样子写得很像。白毛、绿水、红掌，颜色真好看。',
    background: '相传是骆宾王七岁时写的。',
    key_characters: ['鹅', '白', '水', '红'],
    grade: 1, difficulty: 1, source: '课标必背', theme_tags: ['咏物'],
  },
  {
    id: 'po_chunxiao',
    title: '春晓', dynasty: '唐', author: '孟浩然',
    lines: [
      ['春眠不觉晓', 'chūn mián bù jué xiǎo', '春天睡得香，不知不觉天就亮了'],
      ['处处闻啼鸟', 'chù chù wén tí niǎo', '到处都听见小鸟在叫'],
      ['夜来风雨声', 'yè lái fēng yǔ shēng', '想起夜里听到的风雨声'],
      ['花落知多少', 'huā luò zhī duō shǎo', '不知道有多少花被吹落了'],
    ],
    appreciation: '诗人一觉醒来，听到鸟叫，想起昨晚的风雨，心里惦记着院子里的花。',
    background: '孟浩然隐居时写的春天小诗。',
    key_characters: ['春', '鸟', '风', '雨', '花'],
    grade: 1, difficulty: 2, source: '课标必背', theme_tags: ['写景'],
  },
];

// ---------------------------------------------------------------------------
// 作者表 · 儿歌（自编）
// ---------------------------------------------------------------------------
const STORIES = [
  {
    id: 'st_xiaotuzi',
    title: '小兔子数星星',
    type: 'rhyme', grade: 1,
    text: '小兔子，看天上，一二三四五六七。\n星星亮，月亮圆，数来数去数不完。',
    highlight: ['一', '二', '三', '四', '五', '六', '七', '日', '月'],
  },
];

// ---------------------------------------------------------------------------
// 作者表 · 徽章
// ---------------------------------------------------------------------------
const BADGES = [
  { code: 'first_lesson', title: '第一课', description: '完成第一个关卡', type: 'lesson_count', value: 1, order: 1 },
  { code: 'lesson_10', title: '十关小达人', description: '累计完成 10 个关卡', type: 'lesson_count', value: 10, order: 2 },
  { code: 'char_50', title: '认识五十字', description: '累计学习 50 个字', type: 'char_count', value: 50, order: 3 },
  { code: 'char_100', title: '认识一百字', description: '累计学习 100 个字', type: 'char_count', value: 100, order: 4 },
  { code: 'streak_3', title: '坚持三天', description: '连续学习 3 天', type: 'streak_days', value: 3, order: 5 },
  { code: 'streak_7', title: '坚持一周', description: '连续学习 7 天', type: 'streak_days', value: 7, order: 6 },
  { code: 'poem_3', title: '小小诗人', description: '学会 3 首古诗', type: 'poem_count', value: 3, order: 7 },
];

// ---------------------------------------------------------------------------
// 构建
// ---------------------------------------------------------------------------
function charId(char) {
  const hex = [...char].map((c) => c.codePointAt(0).toString(16)).join('');
  return `ch_${hex}`;
}

const now = new Date().toISOString();

function buildCharacters() {
  const charToUnits = new Map();
  for (const unit of UNITS) {
    for (const ch of unit.chars) {
      const list = charToUnits.get(ch) ?? [];
      list.push(unit);
      charToUnits.set(ch, list);
    }
  }

  return GRADE1.map((row) => {
    const [char, pinyin, radical, stroke, structure, meaning, words, sentences, difficulty, tags, pictograph, antonym] = row;
    const { plain, tone } = analysePinyin(pinyin);
    const units = charToUnits.get(char) ?? [];
    return {
      _id: charId(char),
      char,
      pinyin,
      pinyin_plain: plain,
      tone,
      is_polyphone: false,
      polyphone_readings: [],
      radical,
      stroke_count: stroke,
      structure,
      stroke_order_ref: null,
      meaning,
      words,
      sentences,
      pictograph: pictograph ?? null,
      image_ref: null,
      audio_ref: null,
      grade: 1,
      level: 'grade1',
      difficulty,
      tags,
      similar_chars: [],
      antonym: antonym ?? null,
      synonyms: [],
      unit_refs: units.map((u, index) => ({
        unit_id: u.unit_code,
        unit_name: u.title,
        group_name: null,
        order: u.chars.indexOf(char) >= 0 ? u.chars.indexOf(char) + 1 : index + 1,
      })),
      status: 'published',
      version: 1,
      created_at: now,
      updated_at: now,
    };
  });
}

function buildUnits() {
  return UNITS.map((u, index) => ({
    _id: u.unit_code,
    unit_code: u.unit_code,
    title: u.title,
    theme: u.theme,
    grade: '一年级上',
    grade_num: 1,
    semester: '上',
    organize_by: u.organize_by,
    character_ids: u.chars.map(charId),
    focus: u.focus,
    unit_type: u.unit_type,
    order: index + 1,
    status: 'published',
  }));
}

function buildLessons() {
  let prev = null;
  return LESSONS.map((l, index) => {
    const id = `ls_g1_${String(index + 1).padStart(2, '0')}`;
    const lesson = {
      _id: id,
      title: l.title,
      level: 'grade1',
      order: index + 1,
      character_ids: l.chars.map(charId),
      game_types: l.games,
      unlock_rules: { required_lesson_id: prev, min_stars: prev ? 1 : 0 },
      poem_id: null,
      unit_id: l.unit,
      status: 'published',
      created_at: now,
    };
    prev = id;
    return lesson;
  });
}

function buildPoems() {
  return POEMS.map((p) => ({
    _id: p.id,
    title: p.title,
    dynasty: p.dynasty,
    author: p.author,
    lines: p.lines.map(([text, pinyin, meaning]) => ({ text, pinyin, meaning })),
    full_text: p.lines.map(([t]) => t).join('，'),
    audio_ref: null,
    appreciation: p.appreciation,
    background: p.background,
    key_characters: p.key_characters,
    grade: p.grade,
    unit_ref: null,
    theme_tags: p.theme_tags,
    difficulty: p.difficulty,
    source: p.source,
    status: 'published',
    created_at: now,
    updated_at: now,
  }));
}

function buildStories() {
  return STORIES.map((s) => ({
    _id: s.id,
    title: s.title,
    type: s.type,
    level: 'grade1',
    grade: s.grade,
    text: s.text,
    highlight_characters: s.highlight,
    audio_ref: null,
    unlock_after_lesson_ids: [],
    word_count: [...s.text.replace(/\s/g, '')].length,
    status: 'published',
  }));
}

function buildBadges() {
  return BADGES.map((b, i) => ({
    _id: `bd_${b.code}`,
    code: b.code,
    title: b.title,
    description: b.description,
    icon_ref: null,
    condition: { type: b.type, value: b.value },
    order: b.order ?? i + 1,
    status: 'active',
  }));
}

function writeJson(relPath, payload) {
  const full = join(CONTENT, relPath);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, JSON.stringify(payload, null, 2) + '\n', 'utf8');
  const buf = readFileSync(full);
  return {
    path: relPath,
    checksum: 'sha256:' + createHash('sha256').update(buf).digest('hex'),
    bytes: buf.length,
    count: Array.isArray(payload.items) ? payload.items.length : 0,
  };
}

const characters = buildCharacters();
const units = buildUnits();
const lessons = buildLessons();
const poems = buildPoems();
const stories = buildStories();
const badges = buildBadges();

const files = [];
files.push(writeJson('characters/grade-1.json', { content_version: CONTENT_VERSION, items: characters }));
files.push(writeJson('poems/required-75.json', { content_version: CONTENT_VERSION, items: poems }));
files.push(writeJson('lessons/units.json', { content_version: CONTENT_VERSION, items: units }));
files.push(writeJson('lessons/lessons.json', { content_version: CONTENT_VERSION, items: lessons }));
files.push(writeJson('stories/stories.json', { content_version: CONTENT_VERSION, items: stories }));
files.push(writeJson('badges/badges.json', { content_version: CONTENT_VERSION, items: badges }));

const manifest = {
  content_version: CONTENT_VERSION,
  min_app_version: MIN_APP_VERSION,
  updated_at: now,
  counts: {
    characters: characters.length,
    poems: poems.length,
    units: units.length,
    lessons: lessons.length,
    stories: stories.length,
    badges: badges.length,
  },
  files,
};
writeJson('manifest.json', manifest);

console.log('内容包已生成 →', CONTENT);
console.log('  ' + JSON.stringify(manifest.counts));
for (const f of files) console.log(`  ${f.path}  ${f.count} 条  ${(f.bytes / 1024).toFixed(1)}KB`);
