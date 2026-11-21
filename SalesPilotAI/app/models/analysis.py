"""AI 结构化销售分析模型与安全 JSON 解析。"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.models.memory import MemorySuggestion

ReplyType = Literal["professional", "sales_driven", "relationship_building"]
REPLY_TYPES = ("professional", "sales_driven", "relationship_building")


class AnalysisParseError(ValueError):
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response
        self.api_calls = []
        self.customer_id = None
        self.conversation_id = None


class ReplySuggestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    type: ReplyType
    english: str = Field(min_length=1)
    chinese: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    use_case: str = Field(min_length=1)


class KnowledgeReference(BaseModel):
    """本次分析明确引用的知识库事实。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(min_length=1)
    fact: str = Field(min_length=1)


class SalesAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    translation: str = Field(min_length=1)
    customer_intent: str = Field(min_length=1)
    customer_intent_explanation: str = Field(min_length=1)
    customer_emotion: str = Field(min_length=1)
    purchase_requirements: list[str]
    purchase_intent_score: int = Field(ge=0, le=100)
    score_evidence: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    sales_stage: str = Field(min_length=1)
    customer_concerns: list[str]
    price_sensitivity: str = Field(min_length=1)
    communication_risks: list[str]
    opportunities: list[str]
    recommended_strategy: str = Field(min_length=1)
    next_questions: list[str]
    replies: list[ReplySuggestion] = Field(min_length=3, max_length=3)
    followup_required: bool
    followup_suggestion: str
    followup_due_days: int | None = Field(default=None, ge=0, le=30)
    unknown_information: list[str]
    memory_suggestions: list[MemorySuggestion] = Field(default_factory=list)
    knowledge_references: list[KnowledgeReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reply_types(self):
        if {reply.type for reply in self.replies} != set(REPLY_TYPES):
            raise ValueError("必须包含 professional、sales_driven、relationship_building 三种回复")
        return self


def parse_analysis_json(raw_response: str) -> SalesAnalysis:
    text = str(raw_response or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().casefold() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        start = text.index("{")
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except (ValueError, json.JSONDecodeError) as exc:
        raise AnalysisParseError("AI 返回的 JSON 格式无效", raw_response) from exc
    try:
        return SalesAnalysis.model_validate(value)
    except ValidationError as exc:
        raise AnalysisParseError(f"AI 结构化结果无效：{exc}", raw_response) from exc
