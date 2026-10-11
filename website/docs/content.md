# 内容体系与创作

> 本文是面向用户与贡献者的导读，完整设计见 [01-2 产品定位与内容体系设计](https://gitee.com/perry-space/study-club/blob/master/docs/01-产品规划/02-产品定位与内容体系设计.md) 与 [05-1 内容管理与用户管理体系](https://gitee.com/perry-space/study-club/blob/master/docs/05-管理后台/01-内容管理与用户管理体系.md)（Gitee）。

内容按四个层次组织，从下往上逐层聚合：

| 层 | 内容 | 说明 |
| --- | --- | --- |
| 第四层 | 专题与计划 | 每日任务、单元复习、古诗专题、薄弱字专项 |
| 第三层 | 古诗文内容 | 课标必背、蒙学经典、诗意解读 |
| 第二层 | 字词句内容 | 汉字条目、词语、例句、故事、识字短文 |
| 第一层 | 字库主表 | 课标汉字的结构化条目（**核心资产**） |

**第一层是整个产品的地基。**

## 一、内容即仓库

内容以「**内容即仓库**」方式维护，存放在仓库的 `content/` 目录：

| 环节 | 实现 |
| --- | --- |
| 维护 | `content/**/*.json`（附带 JSON Schema） |
| 校验 | JSON Schema + 校验脚本（拼音一致性、重复条目等） |
| 导入 | `scripts/seed` 按表导入 MongoDB，upsert 幂等 |
| 下发 | `GET /content/bootstrap` 一次拉全量 + 子资源接口按需读取 |
| 版本 | `content_version` + `min_app_version` + `checksum` |

> **改内容不必发版**：内容与代码物理分离，贡献者只需改 JSON → 跑校验 → 导入，即可更新线上内容。

### 内容包结构

```
content/
├── manifest.json           # 清单（版本 + 计数 + checksum）
├── sources.json            # 数据来源与许可登记
├── schema/                 # JSON Schema
├── characters/grade-1.json
├── poems/required-75.json
├── lessons/units.json      # 自编单元
├── lessons/lessons.json    # 关卡
├── stories/stories.json
├── readings/readings.json  # 识字短文
└── badges/badges.json
```

### 内容之间的关联

七类内容不是孤立的——**字库是底座**，其余内容通过 `_id` 或字面引用它：

| 引用方 | 引用字段 | 指向 | 作用 |
| --- | --- | --- | --- |
| 单元 | `character_ids` | 汉字 `_id` | 按主题 / 难度把字编成单元 |
| 关卡 | `character_ids` / `poem_id` / `unit_id` | 汉字 / 古诗 / 单元 | 一关 = 一组字 + 可选一首诗 + 所属单元 |
| 识字短文 | `character_ids` / `character_chars` | 汉字 `_id` / 字面 | 覆盖率 = 已在字库字数 ÷ 去重字数，只推 ≥ 75% 的短文 |
| 古诗 | `key_characters` / `unit_ref` | 汉字字面 / 单元 | 诗内生字标注，可反向跳到字卡 |
| 故事 | `highlight_characters` / `unlock_after_lesson_ids` | 汉字字面 / 关卡 `_id` | 高亮已学字、按关卡解锁 |

> 因此**新增内容时建议按顺序**：汉字 → 单元 → 关卡 / 识字短文 → 故事 / 古诗 → 徽章。引用不到不会报错，但客户端会缺图、缺音或算错覆盖率。

## 二、如何新增一条内容

### 新增一条汉字

1. 在 `content/characters/grade-1.json` 加一条：填 `char` / `pinyin` / `tone` / `radical` / `stroke_count` / `structure` / `meaning` / `words` / `sentences` / `grade` / `level` / `difficulty` / `tags` 等**必填字段**；
2. 若为多音字，填 `polyphone_readings`；象形字填 `pictograph`；
3. 运行 `pnpm content:validate` 校验 Schema 与拼音一致性；
4. 若引用了外部数据，在 `content/sources.json` 登记来源；
5. 跑 `scripts/seed/seed.sh`（或 `--only characters`）导入 MongoDB。

### 新增一首古诗

1. 在 `content/poems/required-75.json` 加一条：`title` / `dynasty` / `author` / `lines`（**结构化诗句数组，不要存成一整段**）/ `full_text` / `appreciation` / `key_characters` / `grade` / `theme_tags` / `source`；
2. **逐句注音字数必须与诗句字数一致**（校验会拦，多音字与标点处理是易错点）；
3. `pnpm content:validate` → `scripts/seed/seed.sh --only poems`。

> 校验脚本与后台表单**共用同一份 JSON Schema**，保证校验规则只有一处定义，避免「后台能存、CI 却报错」。

## 三、来源登记与版权红线

所有外部数据源登记在 `content/sources.json`，逐项标注来源 / 许可 / 署名：

| 数据 | 来源 | 许可 |
| --- | --- | --- |
| 古诗原文 | `chinese-poetry` 开源数据集 | MIT（原文公版） |
| 注音 / 释义 / 赏析 | 自编 | 项目自有 |

**两条内容版权红线**：

- ⛔ **不携带教材映射**：单元按主题 / 难度自编，**不复现任何出版物的单元顺序、课文标题与插图**；「跟课本学」由**用户自定义单元**满足（家长自己勾选字组成单元）。
- ⛔ **不收录来源不明素材**：音频 / 配图必须**可开源授权**（自录 / 自绘 / CC0 / 公版），素材 `copyright` 必填。

## 四、当前内容规模

| 类型 | 条数 |
| --- | --- |
| 汉字 | 83 |
| 古诗 | 3 |
| 单元 | 7 |
| 关卡 | 14 |
| 故事 | 5 |
| 识字短文 | 6 |
| 徽章 | 7 |

> ⚠️ **内容量是当前最大的短板**。系统设计已支撑规模化，但内容尚未达到可用规模；**内容扩容是当前第一优先级**。

## 继续阅读

- 内容怎么下发 → [API 接口](/docs/api)
- 内容存入哪些集合 → [数据设计](/docs/data)
- 想帮忙补内容 → [贡献指南](/docs/contributing)
