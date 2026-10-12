"""内容模块路由（04-1 §四）。

**变更**：内容不再随前端包分发、也不对外开放读取 —— 内容已全部由后台管理，
属于「登录后才可见」的受控数据。因此本模块全部接口都要求登录（`get_current_account`）。
唯一的例外是素材文件 `GET /assets/{id}`：`<img>` / `<audio>` 标签无法携带 Authorization 头，
故素材走独立路由并保持公开（详见 views/assets.py 的说明）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.deps import get_current_account, get_repos
from ..core.response import ok, paged
from ..core.runtime_config import GRADE_MAX
from ..models.common import PageParams, page_params
from ..models.content import CharacterListQuery, PoemListQuery
from ..repositories import Repositories
from ..controllers import content_controller

router = APIRouter(prefix="/content", tags=["content"])


# ----------------------------- 一次性引导 -----------------------------
@router.get("/bootstrap")
async def bootstrap(
    grade: int = Query(default=1, ge=0, le=GRADE_MAX),
    include_full_chars: bool = Query(default=True, description="是否带上完整字库（离线缓存用）"),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    """客户端启动只打这一个请求：清单 + 字库 + 古诗 + 单元 + 关卡 + 故事 + 徽章。

    改成服务端存储后，首屏若仍靠 7 个并发请求拼装，就要处理「部分成功」的一致性问题；
    这里一次聚合、一次下发，把首屏依赖收敛到单个请求。
    """
    return ok(await content_controller.bootstrap(repos, grade, include_full_chars))


# ----------------------------- 清单 -----------------------------
@router.get("/manifest")
async def get_manifest(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_manifest(repos))


# ----------------------------- 汉字 -----------------------------
@router.get("/characters")
async def list_characters(
    grade: int | None = Query(default=None, ge=0, le=GRADE_MAX),
    level: str | None = None,
    tags: str | None = None,
    unit_id: str | None = None,
    status: str | None = Query(default=None, description="仅后台可用，默认 published"),
    keyword: str | None = None,
    page: PageParams = Depends(page_params),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    query = CharacterListQuery(
        grade=grade, level=level, tags=tags, unit_id=unit_id, status=status, keyword=keyword
    )
    items, total = await content_controller.list_characters(repos, query, page.skip, page.page_size)
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.get("/characters/by-char/{char}")
async def get_character_by_char(
    char: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_character_by_char(repos, char))


@router.get("/characters/batch")
async def get_characters_batch(
    ids: str = Query(..., description="逗号分隔的汉字 _id 列表"),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    return ok({"items": await content_controller.get_characters_batch(repos, id_list)})


@router.get("/characters/{char_id}")
async def get_character(
    char_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_character(repos, char_id))


@router.get("/characters/{char_id}/similar")
async def get_similar_chars(
    char_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_similar_chars(repos, char_id))


# ----------------------------- 古诗 -----------------------------
@router.get("/poems")
async def list_poems(
    grade: int | None = Query(default=None, ge=0, le=GRADE_MAX),
    theme_tags: str | None = None,
    source: str | None = None,
    keyword: str | None = None,
    page: PageParams = Depends(page_params),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    query = PoemListQuery(grade=grade, theme_tags=theme_tags, source=source, keyword=keyword)
    items, total = await content_controller.list_poems(repos, query, page.skip, page.page_size)
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.get("/poems/by-char/{char}")
async def get_poems_by_char(
    char: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok({"items": await content_controller.get_poems_by_char(repos, char)})


@router.get("/poems/{poem_id}")
async def get_poem(
    poem_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_poem(repos, poem_id))


@router.get("/poems/{poem_id}/quiz")
async def get_poem_quiz(
    poem_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.poem_quiz(repos, poem_id))


# ----------------------------- 故事 -----------------------------
@router.get("/stories")
async def list_stories(
    page: PageParams = Depends(page_params),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    items, total = await content_controller.list_stories(repos, page.skip, page.page_size)
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.get("/stories/{story_id}")
async def get_story(
    story_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_story(repos, story_id))


# ----------------------------- 单元 -----------------------------
@router.get("/units")
async def list_units(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok({"items": await content_controller.list_units(repos)})


@router.get("/units/{unit_id}")
async def get_unit(
    unit_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_unit(repos, unit_id))


# ----------------------------- 关卡 -----------------------------
@router.get("/lessons")
async def list_lessons(
    level: str | None = None,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok({"items": await content_controller.list_lessons(repos, level)})


@router.get("/lessons/{lesson_id}")
async def get_lesson(
    lesson_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_lesson(repos, lesson_id))


@router.get("/lessons/{lesson_id}/questions")
async def get_lesson_questions(
    lesson_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.lesson_questions(repos, lesson_id))


# ----------------------------- 徽章 -----------------------------
@router.get("/badges")
async def list_badges(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok({"items": await content_controller.list_badges(repos)})


@router.get("/badges/{code}")
async def get_badge(
    code: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await content_controller.get_badge(repos, code))
