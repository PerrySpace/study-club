"""内容控制器（MVC —— Controller 层）。

职责：把仓储数据组装成**前台可消费的内容结构**，并处理素材 URL 展开、题目生成等业务逻辑。
不接触 motor：所有查询都经 `Repositories`。

内容主路径已从「内容即仓库」切换为「MongoDB 唯一真源 + 后台管理」：
`content/*.json` 只在导入时读一次（见 content_import_controller.py）。
"""

from __future__ import annotations

import uuid
from typing import Iterable

from ..core import errors as E
from ..core import runtime_config
from ..models.content import CharacterListQuery, PoemListQuery
from ..repositories import Repositories

# 内容文档里的素材引用字段 → 出参的 URL 字段
_ASSET_FIELDS_CHARACTER = {
    "image_ref": "image_url",
    "audio_ref": "audio_url",
    "stroke_order_ref": "stroke_order_url",
}
_ASSET_FIELDS_POEM = {"audio_ref": "audio_url"}
_ASSET_FIELDS_STORY = {"audio_ref": "audio_url"}
_ASSET_FIELDS_BADGE = {"icon_ref": "icon_url"}

# 题型 → 题面。客户端按 type 决定渲染方式（图片 / 音频 / 语音输入 / 笔顺）。
QUESTION_STEMS: dict[str, str] = {
    "image-choice": "看图片，选出对应的汉字",
    "audio-choice": "听读音，选出正确的汉字",
    "pinyin-match": "根据拼音，选出正确的汉字",
    "word-build": "选出能组成词语的汉字",
    "meaning-choice": "根据意思，选出正确的汉字",
    "speak": "大声读一读，让小朋友听听对不对",
    "stroke": "按笔顺写一写这个字",
}
# 前台可用题型（后台可在 lessons.game_types 里自由组合）
GAME_TYPES: tuple[str, ...] = tuple(QUESTION_STEMS)


# ---------------------------------------------------------------------------
# 素材 URL 展开
# ---------------------------------------------------------------------------
async def _attach_asset_urls(
    repos: Repositories, docs: list[dict], mapping: dict[str, str]
) -> list[dict]:
    """批量把 `*_ref` 解析为可访问 URL，附加为 `*_url`（不覆盖 ref 字段）。"""
    refs: list[str] = []
    for doc in docs:
        for ref_field in mapping:
            ref = doc.get(ref_field)
            if ref:
                refs.append(str(ref))
    url_map = await repos.assets.url_map(refs) if refs else {}
    out: list[dict] = []
    for doc in docs:
        enriched = dict(doc)
        for ref_field, url_field in mapping.items():
            ref = doc.get(ref_field)
            enriched[url_field] = url_map.get(str(ref)) if ref else None
        out.append(enriched)
    return out


# ---------------------------------------------------------------------------
# 清单
# ---------------------------------------------------------------------------
async def get_manifest(repos: Repositories) -> dict:
    doc = await repos.manifest.get_current()
    if doc is None:
        return {
            "content_version": "0.0.0",
            "min_app_version": "0.0.0",
            "updated_at": None,
            "counts": await repos.content_counts(),
            "files": [],
        }
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# 汉字
# ---------------------------------------------------------------------------
async def list_characters(
    repos: Repositories, query: CharacterListQuery, skip: int, limit: int
) -> tuple[list[dict], int]:
    flt = repos.characters.build_filter(
        status=query.status,
        grade=query.grade,
        level=query.level,
        unit_id=query.unit_id,
        tags=query.tag_list,
        keyword=query.keyword,
    )
    docs, total = await repos.characters.list_page(flt, skip=skip, limit=limit)
    return await _attach_asset_urls(repos, docs, _ASSET_FIELDS_CHARACTER), total


async def get_character(repos: Repositories, char_id: str) -> dict:
    doc = await repos.characters.find_one({"_id": char_id})
    if doc is None:
        raise E.BizException(E.CHARACTER_NOT_FOUND, "汉字不存在")
    return (await _attach_asset_urls(repos, [doc], _ASSET_FIELDS_CHARACTER))[0]


async def get_character_by_char(repos: Repositories, char: str) -> dict:
    doc = await repos.characters.get_by_char(char)
    if doc is None:
        raise E.BizException(E.CHARACTER_NOT_FOUND, "汉字不存在")
    return (await _attach_asset_urls(repos, [doc], _ASSET_FIELDS_CHARACTER))[0]


async def get_characters_batch(repos: Repositories, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    docs = await repos.characters.find_by_ids(ids)
    # 按传入顺序返回，保证字表顺序稳定
    by_id = {d["_id"]: d for d in docs}
    ordered = [by_id[i] for i in ids if i in by_id]
    return await _attach_asset_urls(repos, ordered, _ASSET_FIELDS_CHARACTER)


async def get_similar_chars(repos: Repositories, char_id: str) -> dict:
    doc = await repos.characters.find_one({"_id": char_id})
    if doc is None:
        raise E.BizException(E.CHARACTER_NOT_FOUND, "汉字不存在")
    similar = doc.get("similar_chars") or []
    if not similar:
        return {"char": doc["char"], "items": []}
    items = await repos.characters.find_many({"char": {"$in": similar}}, limit=len(similar))
    return {"char": doc["char"], "items": [{"_id": it["_id"], "char": it["char"]} for it in items]}


# ---------------------------------------------------------------------------
# 古诗
# ---------------------------------------------------------------------------
async def list_poems(
    repos: Repositories, query: PoemListQuery, skip: int, limit: int
) -> tuple[list[dict], int]:
    flt = repos.poems.build_filter(
        grade=query.grade,
        theme_tags=query.theme_tag_list,
        source=query.source,
        keyword=query.keyword,
    )
    docs, total = await repos.poems.list_page(flt, skip=skip, limit=limit)
    return await _attach_asset_urls(repos, docs, _ASSET_FIELDS_POEM), total


async def get_poem(repos: Repositories, poem_id: str) -> dict:
    doc = await repos.poems.find_one({"_id": poem_id})
    if doc is None:
        raise E.BizException(E.POEM_NOT_FOUND, "古诗不存在")
    return (await _attach_asset_urls(repos, [doc], _ASSET_FIELDS_POEM))[0]


async def get_poems_by_char(repos: Repositories, char: str) -> list[dict]:
    return await repos.poems.by_key_character(char)


async def poem_quiz(repos: Repositories, poem_id: str) -> dict:
    poem = await get_poem(repos, poem_id)
    questions: list[dict] = []
    for idx, line in enumerate(poem.get("lines", [])):
        text = line.get("text", "")
        if len(text) < 2:
            continue
        # 挖去一个字作为填空（选择题型 poem-fill）
        blank_pos = idx % len(text)
        answer = text[blank_pos]
        stem = text[:blank_pos] + "□" + text[blank_pos + 1 :]
        questions.append(
            {
                "question_id": f"q_{uuid.uuid4().hex}",
                "type": "poem-fill",
                "poem_id": poem_id,
                "line_index": idx,
                "stem": stem,
                "answer": answer,
                "pinyin": line.get("pinyin"),
            }
        )
    return {
        "poem_id": poem_id,
        "title": poem.get("title"),
        "audio_url": poem.get("audio_url"),
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# 故事 / 单元
# ---------------------------------------------------------------------------
async def list_stories(repos: Repositories, skip: int, limit: int) -> tuple[list[dict], int]:
    docs, total = await repos.stories.paginate(
        {"status": "published"},
        sort=[("level", 1), ("grade", 1)],
        skip=skip,
        limit=limit,
    )
    return await _attach_asset_urls(repos, docs, _ASSET_FIELDS_STORY), total


async def get_story(repos: Repositories, story_id: str) -> dict:
    doc = await repos.stories.find_one({"_id": story_id})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "故事不存在")
    return (await _attach_asset_urls(repos, [doc], _ASSET_FIELDS_STORY))[0]


# ---------------------------------------------------------------------------
# 单元
# ---------------------------------------------------------------------------
async def list_units(repos: Repositories) -> list[dict]:
    return await repos.units.list_published(limit=500)


async def get_unit(repos: Repositories, unit_id: str) -> dict:
    doc = await repos.units.find_one({"_id": unit_id})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "单元不存在")
    char_ids = doc.get("character_ids") or []
    chars = await repos.characters.briefs(char_ids)
    result = dict(doc)
    result["characters"] = [
        {"_id": c["_id"], "char": c.get("char"), "pinyin": c.get("pinyin")} for c in chars
    ]
    return result


# ---------------------------------------------------------------------------
# 关卡与题目
# ---------------------------------------------------------------------------
async def list_lessons(repos: Repositories, level: str | None) -> list[dict]:
    return await repos.lessons.list_by_level(level)


async def get_lesson(repos: Repositories, lesson_id: str) -> dict:
    doc = await repos.lessons.find_one({"_id": lesson_id})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "关卡不存在")
    return doc


async def lesson_questions(repos: Repositories, lesson_id: str) -> dict:
    lesson = await repos.lessons.find_one({"_id": lesson_id})
    if lesson is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "关卡不存在")

    char_ids = lesson.get("character_ids") or []
    chars = await repos.characters.find_by_ids(char_ids)
    chars = await _attach_asset_urls(repos, chars, _ASSET_FIELDS_CHARACTER)
    by_id = {c["_id"]: c for c in chars}
    ordered = [by_id[i] for i in char_ids if i in by_id]

    # 玩法开关（后台可改）在这里**服务端**先过滤一次：客户端即便缓存了旧配置，
    # 也拿不到被关掉的题型。客户端侧还会再过滤一次（双保险，且关闭的题型不能靠改前端绕过）。
    enabled = set(runtime_config.gameplay_config()["enabled_question_types"])
    chosen = [t for t in (lesson.get("game_types") or []) if t in QUESTION_STEMS and t in enabled]
    game_types = chosen or ["image-choice"]
    grade = ordered[0].get("grade", 1) if ordered else 1
    distractors = await repos.characters.distractor_pool(grade, char_ids, limit=12)
    distractor_pool = [{"id": d["_id"], "char": d["char"]} for d in distractors]

    questions: list[dict] = []
    for i, char in enumerate(ordered):
        cid = char["_id"]
        qtype = game_types[i % len(game_types)]
        options = [{"id": cid, "char": char["char"]}]
        for d in distractor_pool:
            if len(options) >= 4:
                break
            if d["id"] != cid:
                options.append(d)
        questions.append(
            {
                "question_id": f"q_{uuid.uuid4().hex}",
                "type": qtype,
                "character_id": cid,
                "char": char.get("char"),
                # 题面需要的一切都在这里，客户端不必二次请求
                "pinyin": char.get("pinyin"),
                "meaning": char.get("meaning"),
                "words": char.get("words") or [],
                "sentences": char.get("sentences") or [],
                "pictograph": char.get("pictograph"),
                "image_url": char.get("image_url"),
                "audio_url": char.get("audio_url"),
                "stroke_order_url": char.get("stroke_order_url"),
                "stem": QUESTION_STEMS.get(qtype, "选出正确的汉字"),
                "options": options,
                "answer_character_id": cid,
                "answer": char.get("char"),
            }
        )
    return {"lesson_id": lesson_id, "title": lesson.get("title"), "questions": questions}


# ---------------------------------------------------------------------------
# 徽章
# ---------------------------------------------------------------------------
async def list_badges(repos: Repositories) -> list[dict]:
    docs = await repos.badges.list_active(limit=200)
    return await _attach_asset_urls(repos, docs, _ASSET_FIELDS_BADGE)


async def get_badge(repos: Repositories, code: str) -> dict:
    doc = await repos.badges.find_one({"code": code})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "徽章不存在")
    return (await _attach_asset_urls(repos, [doc], _ASSET_FIELDS_BADGE))[0]


# ---------------------------------------------------------------------------
# 一次性引导（服务端存储后，客户端启动只需一个请求）
# ---------------------------------------------------------------------------
async def bootstrap(repos: Repositories, grade: int, include_full_chars: bool = True) -> dict:
    """把「客户端启动所需的一整份内容」一次下发。

    为什么值得单开接口：改成服务端存储后，客户端每次启动都要拉全部内容，
    原来 7 个并行请求既慢又要处理「部分成功」。这里一次聚合，且**故意不带分页**——
    目的就是让首屏只依赖一个请求。
    """
    manifest = await get_manifest(repos)
    units = await repos.units.list_published(limit=500)
    lessons = await repos.lessons.list_published(limit=1000)
    badges = await list_badges(repos)
    stories = await repos.stories.list_published(limit=500)

    # ⚠️ build_filter 的 grade 是**等值**条件，而这里要的是「该年级及以下」的学习池。
    # 客户端固定传 `grade=6` 意图是「一次拉全量」（见 core 的 CONTENT_FETCH_MAX_GRADE），
    # 若照搬等值就只会取到 `grade == 6` 的诗 —— 而内容包里古诗全是 grade=1，
    # 结果是**一首都拉不到**，首页「古诗学习」永远显示「暂无古诗内容」。
    # 汉字下方用 `$lte` 是同一原因；两处语义必须一致，否则修一处坏一处。
    poem_flt = repos.poems.build_filter()
    poem_flt["grade"] = {"$lte": grade}
    poem_docs, _ = await repos.poems.list_page(poem_flt, skip=0, limit=300)
    poems = await _attach_asset_urls(repos, poem_docs, _ASSET_FIELDS_POEM)

    characters: list[dict] = []
    if include_full_chars:
        char_flt = repos.characters.build_filter()
        # build_filter 的 grade 是等值条件，这里要的是「该年级及以下」的学习池
        char_flt["grade"] = {"$lte": grade}
        docs, _ = await repos.characters.paginate(
            char_flt, sort=[("grade", 1), ("difficulty", 1), ("_id", 1)], skip=0, limit=3000
        )
        characters = await _attach_asset_urls(repos, docs, _ASSET_FIELDS_CHARACTER)

    return {
        "manifest": manifest,
        "grade": grade,
        "characters": characters,
        "poems": poems,
        "units": units,
        "lessons": lessons,
        "stories": stories,
        "badges": badges,
        "game_types": list(GAME_TYPES),
        # 玩法配置随内容包一起下发：客户端「一次启动请求」就能拿到
        # 内容 + 该按什么玩法呈现，不必再单独打一次 /config
        "gameplay": runtime_config.gameplay_config(),
    }


def stem_for(question_type: str) -> str:
    return QUESTION_STEMS.get(question_type, "选出正确的汉字")


def known_game_types(types: Iterable[str]) -> list[str]:
    return [t for t in types if t in QUESTION_STEMS]
