"""内容类型注册表 —— 后台「一套通用 CRUD」的数据源。

为什么要有它：内容有 6 类、字段各异，如果每类都写一遍「列表/新建/更新/下架」，
后台就是 6 份几乎相同的代码，加一类内容要改 5 个文件。这里把差异抽成**数据**：
集合名、id 规则、必填字段、可搜索字段、筛选字段、默认排序。

新增一类内容 = 在 REGISTRY 里加一行 + 在 Repositories 上挂仓储，视图与控制器都不用动。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentTypeSpec:
    key: str  # 仓储属性名（Repositories 上的属性）
    collection: str  # MongoDB 集合名
    label: str  # 中文名（后台显示 / 报错信息）
    id_prefix: str  # 生成 `_id` 的前缀
    id_source: str | None  # 用哪个字段派生 `_id`（如古诗用 title）
    required_on_create: tuple[str, ...] = ()
    searchable: tuple[str, ...] = ()  # keyword 搜索的字段
    filters: tuple[str, ...] = ()  # 允许透传的等值筛选字段
    default_sort: tuple[tuple[str, int], ...] = (("order", 1),)
    unique_fields: tuple[str, ...] = ()
    # 模板下载用：字段说明（字段名 -> 说明），后台「下载模板」据此生成带注释的 JSON
    field_docs: tuple[tuple[str, str], ...] = ()
    # 模板下载用：一条可直接照抄的示例（只含关键字段，避免把示例当规范）
    template_sample: tuple[tuple[str, object], ...] = ()


REGISTRY: dict[str, ContentTypeSpec] = {
    "characters": ContentTypeSpec(
        key="characters",
        collection="characters",
        label="汉字",
        id_prefix="ch_",
        # 汉字 id 由码点派生（与既有内容包一致），不走 id_source
        id_source=None,
        required_on_create=("char",),
        searchable=("char", "meaning", "words", "pinyin"),
        filters=("status", "grade", "level"),
        default_sort=(("grade", 1), ("difficulty", 1)),
        unique_fields=("char",),
        field_docs=(
            ("char", "汉字本体，单字。必填，且是唯一键；_id 由它按码点派生（ch_<hex>），改字等于换一条记录"),
            ("pinyin", "拼音，带声调，如 shuǐ"),
            ("pinyin_plain", "无声调纯字母，如 shui；留空由导入时按 pinyin 推导"),
            ("tone", "声调 1–4；轻声为 0；多音字填默认读音的调"),
            ("is_polyphone", "是否多音字。true 时应同时提供 polyphone_readings"),
            ("polyphone_readings", "多音字读音数组，元素为 {pinyin,tone,meaning,usage,note}"),
            ("radical", "部首，如 氵"),
            ("stroke_count", "笔画数，画一画与笔顺数据都要用它"),
            ("structure", "间架结构：独体/左右/上下/上中下/左中右/半包围/全包围/品字"),
            ("stroke_order_ref", "笔顺数据引用（素材 id）。为空时客户端「写一写」只给米字格描红，无笔顺动画"),
            ("meaning", "释义，40 字以内，越短越好；「给意思选字」题直接用它做题干"),
            ("words", "组词数组，每个词都必须含本字；「组词拼搭」题与例句朗读都用它"),
            ("sentences", "例句数组"),
            ("pictograph", "字形说明文字（可选）"),
            ("glyph", "字源图，有三种形态：① emoji 如 💧 ② 图片链接 https://… ③ 素材 id 如 as_…。「看图选字」的题干主图，图片优先于 emoji；必须是字义联想而非装饰图"),
            ("image_ref", "精细配图的素材 id。留空时客户端回落到 glyph"),
            ("audio_ref", "音频素材 id。留空时客户端用浏览器 TTS 朗读"),
            ("grade", "年级 1–6；0 表示学龄前。缺省时后台归入「未分级」"),
            ("level", "难度层级：easy/mid/hard"),
            ("difficulty", "难度分 1–5，用于排序与出题干扰项选择"),
            ("tags", "标签数组，如 部首/自然/动物"),
            ("similar_chars", "形近字数组，用于出干扰项"),
            ("antonym", "反义词（可选）"),
            ("synonyms", "近义词数组（可选）"),
            ("status", "状态：draft 草稿 / pending_review 待审核 / published 已上架 / offline 已下架。只有 published 会下发给客户端"),
        ),
        template_sample=(
            ("_id", "ch_6c34"),
            ("char", "水"),
            ("pinyin", "shuǐ"),
            ("tone", 3),
            ("radical", "氵"),
            ("stroke_count", 4),
            ("structure", "独体"),
            ("glyph", "💧"),
            ("meaning", "无色无味的液体，人和动物都要喝"),
            ("words", ["水果", "喝水", "河水"]),
            ("sentences", ["我要多喝水。", "小河里的水很清。"]),
            ("grade", 1),
            ("level", "easy"),
            ("difficulty", 1),
            ("tags", ["自然"]),
            ("status", "published"),
        ),
    ),
    "poems": ContentTypeSpec(
        key="poems",
        collection="poems",
        label="古诗",
        id_prefix="poem_",
        id_source="title",
        required_on_create=("title",),
        searchable=("title", "author", "full_text"),
        filters=("status", "grade", "source"),
        default_sort=(("grade", 1), ("difficulty", 1)),
        field_docs=(
            ("title", "诗题。必填；_id 由它派生（poem_<slug>），改题等于换一条记录"),
            ("dynasty", "朝代，如 唐/宋"),
            ("author", "作者"),
            ("lines", "诗句数组，元素为 {text,pinyin,meaning}。text 必填；填字游戏与逐句朗读都靠它"),
            ("full_text", "全文（不含拼音释义），用于整首朗读与搜索"),
            ("audio_ref", "音频素材 id。留空时用浏览器 TTS 逐句朗读"),
            ("appreciation", "译文/赏析（儿童可读的口语化版本）"),
            ("background", "创作背景（可选）"),
            ("key_characters", "重点字（与字库同字面），用于诗内生字标注"),
            ("grade", "年级 1–6；缺省归入「未分级」"),
            ("unit_ref", "所属单元 {unit_id,grade,unit_name}（可选）"),
            ("theme_tags", "主题标签数组：写景/咏物/思乡/友情/励志，取自 03-2 枚举"),
            ("difficulty", "难度分 1–5"),
            ("source", "出处：classic 经典必背 / extension 拓展。可溯源要求见 01-4 第五章"),
            ("status", "状态：draft/pending_review/published/offline"),
        ),
        template_sample=(
            ("_id", "poem_jing-ye-si"),
            ("title", "静夜思"),
            ("dynasty", "唐"),
            ("author", "李白"),
            ("lines", [
                {"text": "床前明月光", "pinyin": "chuáng qián míng yuè guāng", "meaning": "床前洒下明亮的月光"},
                {"text": "疑是地上霜", "pinyin": "yí shì dì shàng shuāng", "meaning": "好像是地上结的白霜"},
                {"text": "举头望明月", "pinyin": "jǔ tóu wàng míng yuè", "meaning": "抬起头望着天上的月亮"},
                {"text": "低头思故乡", "pinyin": "dī tóu sī gù xiāng", "meaning": "低下头思念远方的家乡"},
            ]),
            ("full_text", "床前明月光，疑是地上霜。举头望明月，低头思故乡。"),
            ("appreciation", "夜里看见地上的月光像白霜一样白，想起了自己的家乡。"),
            ("key_characters", ["月", "光", "乡"]),
            ("grade", 1),
            ("theme_tags", ["思乡"]),
            ("difficulty", 1),
            ("source", "classic"),
            ("status", "published"),
        ),
    ),
    "curriculum_units": ContentTypeSpec(
        key="units",
        collection="curriculum_units",
        label="单元",
        id_prefix="unit_",
        id_source="unit_code",
        required_on_create=("title", "unit_code"),
        searchable=("title", "unit_code", "theme"),
        filters=("status", "grade_num"),
        default_sort=(("grade_num", 1), ("semester", 1), ("order", 1)),
        unique_fields=("unit_code",),
    ),
    "lessons": ContentTypeSpec(
        key="lessons",
        collection="lessons",
        label="关卡",
        id_prefix="lesson_",
        id_source="title",
        required_on_create=("title",),
        searchable=("title",),
        filters=("status", "level"),
        default_sort=(("level", 1), ("order", 1)),
    ),
    "stories": ContentTypeSpec(
        key="stories",
        collection="stories",
        label="故事",
        id_prefix="story_",
        id_source="title",
        required_on_create=("title", "text"),
        searchable=("title", "text"),
        filters=("status", "level", "grade"),
        default_sort=(("level", 1), ("grade", 1)),
    ),
    "badges": ContentTypeSpec(
        key="badges",
        collection="badges",
        label="徽章",
        id_prefix="badge_",
        id_source="code",
        required_on_create=("code", "title"),
        searchable=("code", "title", "description"),
        filters=("status",),
        default_sort=(("order", 1),),
        unique_fields=("code",),
    ),
    "readings": ContentTypeSpec(
        key="readings",
        collection="readings",
        label="识字短文",
        id_prefix="rd_",
        id_source="title",
        required_on_create=("title", "text"),
        searchable=("title", "text"),
        filters=("status", "grade", "level"),
        default_sort=(("grade", 1), ("difficulty", 1), ("order", 1)),
        field_docs=(
            ("title", "短文标题。必填；_id 由它派生（rd_<slug>），改题等于换一条记录"),
            ("type", "sentence 单句起步 / passage 多句短文。决定客户端是一句一读还是整篇呈现"),
            ("level", "难度层级：easy/mid/hard"),
            ("grade", "年级 1–6；缺省归入「未分级」"),
            ("difficulty", "难度分 1–5"),
            ("order", "同级内排序，小的靠前"),
            ("theme", "主题，如 校园/自然/家庭"),
            ("sentences", "句子数组，元素为 {text,pinyin,meaning}。text 必填，逐句朗读与高亮逐字都靠它"),
            ("text", "全文（不含拼音释义）。必填；导入时会用 sentences 重建，客户端按它算字数与覆盖率"),
            ("full_pinyin", "全文拼音（空格分隔）"),
            ("character_ids", "文中出现、且已在字库的字的 _id 数组。**覆盖率 = 本数组长度 / character_chars 长度**，客户端据此只推覆盖率 ≥75% 的短文"),
            ("character_chars", "文中出现的全部去重汉字字面（含未入字库的），数组元素必须与正文逐字一致"),
            ("new_character_chars", "文中的生字字面。导入时按正文自动核对，改这里没用（以正文为准）"),
            ("word_count", "字数，导入时自动统计"),
            ("image_ref", "短文配图的素材 id。**必填的期望项**：正文有图才读得下去，配图优先用字义联想图。可空但强烈建议填"),
            ("audio_ref", "整篇朗读音频素材 id。留空时客户端按句用 TTS 朗读"),
            ("tips", "给家长的导读：怎么带读、可以问什么问题"),
            ("status", "状态：draft/pending_review/published/offline"),
        ),
        template_sample=(
            ("_id", "rd_xiao-xi-de-yu"),
            ("title", "小雨滴"),
            ("type", "passage"),
            ("level", "easy"),
            ("grade", 1),
            ("difficulty", 1),
            ("order", 1),
            ("theme", "自然"),
            ("sentences", [
                {"text": "小雨滴落到地上。", "pinyin": "xiǎo yǔ dī luò dào dì shàng", "meaning": "小小的雨点落下来"},
                {"text": "小草绿了。", "pinyin": "xiǎo cǎo lǜ le", "meaning": "小草变绿了"},
                {"text": "我打开伞。", "pinyin": "wǒ dǎ kāi sǎn", "meaning": "我把伞撑开"},
            ]),
            ("text", "小雨滴落到地上。小草绿了。我打开伞。"),
            ("image_ref", "as_0123456789abcdef"),
            ("tips", "问孩子：「小雨滴是什么形状的？」再让他找出文里的「绿」。"),
            ("status", "published"),
        ),
    ),
}

# 内容清单的计数键 → 集合名（与 ContentManifest.counts 对齐）
COUNT_KEYS: dict[str, str] = {
    "characters": "characters",
    "poems": "poems",
    "curriculum_units": "curriculum_units",
    "lessons": "lessons",
    "stories": "stories",
    "badges": "badges",
    "readings": "readings",
}


def spec_for(collection: str) -> ContentTypeSpec | None:
    return REGISTRY.get(collection)


def all_specs() -> list[ContentTypeSpec]:
    return list(REGISTRY.values())


@dataclass(frozen=True)
class ImportSource:
    """内容导入的数据来源描述（仓库文件 / 上传载荷）。"""

    collection: str
    path: str | None = None  # 仓库相对路径
    strip_wrapper: bool = True
    extra_paths: tuple[str, ...] = field(default_factory=tuple)  # 多文件（如按年级分册）


# 内容导入的路径映射：汉字按年级分册，其余单文件。
IMPORT_SOURCES: tuple[ImportSource, ...] = (
    ImportSource(
        collection="characters",
        extra_paths=(
            "content/characters/grade-1.json",
            "content/characters/grade-2.json",
            "content/characters/grade-3.json",
            "content/characters/grade-4.json",
            "content/characters/grade-5.json",
            "content/characters/grade-6.json",
        ),
    ),
    ImportSource(collection="poems", path="content/poems/required-75.json"),
    ImportSource(collection="curriculum_units", path="content/lessons/units.json"),
    ImportSource(collection="lessons", path="content/lessons/lessons.json"),
    ImportSource(collection="stories", path="content/stories/stories.json"),
    ImportSource(collection="badges", path="content/badges/badges.json"),
    ImportSource(collection="readings", path="content/readings/readings.json"),
)


def import_source_for(collection: str) -> ImportSource | None:
    for src in IMPORT_SOURCES:
        if src.collection == collection:
            return src
    return None
