"""学习模块请求模型（04-1 §五 / 03-2 §五）。

本地优先下学习数据主存储在前端，这里只承载「前端上报的增量」。
`client_record_id` 用于离线补偿上报的幂等去重（04-1 §1.5）。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    child_id: str
    character_id: str
    char: str | None = None  # 冗余汉字，可选；缺省时服务端按 character_id 回填
    question_type: str
    answer: str = ""
    correct_answer: str = ""
    is_correct: bool
    response_ms: int = Field(default=0, ge=0)
    session_id: str | None = None
    occurred_at: datetime | None = None
    client_record_id: str | None = None


class AnswerBatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    child_id: str
    records: list[AnswerSubmit] = Field(default_factory=list, max_length=500)


class ResolveWrongQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    resolved: bool = True


class LessonCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    child_id: str
    lesson_id: str | None = None
    event_type: str = "lesson_complete"
    character_ids: list[str] = Field(default_factory=list)
    score: int | None = None
    total: int | None = None
    accuracy: float | None = Field(default=None, ge=0, le=1)
    stars: int | None = Field(default=None, ge=0, le=3)
    duration_ms: int = Field(default=0, ge=0)
    occurred_at: datetime | None = None
    client_record_id: str | None = None
