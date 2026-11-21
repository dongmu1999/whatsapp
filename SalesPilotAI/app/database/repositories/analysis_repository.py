"""AI 分析、回复建议与 API 用量的本地持久化。"""

from __future__ import annotations

import json

from app.database.connection import Database
from app.services.deepseek_service import APIUsageStats
from app.services.sales_advisor_service import AnalysisRunResult


def _json(values) -> str:
    return json.dumps(values, ensure_ascii=False)


def _totals(api_calls):
    return (
        sum(call.prompt_tokens for call in api_calls),
        sum(call.completion_tokens for call in api_calls),
        sum(call.total_tokens for call in api_calls),
        sum(call.duration_ms for call in api_calls),
    )


class AnalysisRepository:
    def __init__(self, database: Database):
        self.database = database

    def save_result(self, result: AnalysisRunResult) -> int:
        analysis = result.analysis
        prompt, completion, total, duration = _totals(result.api_calls)
        model = result.api_calls[-1].model if result.api_calls else None
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO analyses(
                    customer_id, conversation_id, model, status,
                    latest_message_translation, customer_intent, customer_intent_explanation,
                    customer_emotion, purchase_requirements_json, purchase_intent_score,
                    score_evidence_json, confidence, sales_stage, customer_concerns_json,
                    price_sensitivity, communication_risks_json, opportunities_json,
                    recommended_strategy, next_questions_json, followup_required,
                    followup_suggestion, unknown_information_json, raw_response,
                    prompt_tokens, completion_tokens, total_tokens, duration_ms
                ) VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.customer_id,
                    result.conversation_id,
                    model,
                    analysis.translation,
                    analysis.customer_intent,
                    analysis.customer_intent_explanation,
                    analysis.customer_emotion,
                    _json(analysis.purchase_requirements),
                    analysis.purchase_intent_score,
                    _json(analysis.score_evidence),
                    analysis.confidence,
                    analysis.sales_stage,
                    _json(analysis.customer_concerns),
                    analysis.price_sensitivity,
                    _json(analysis.communication_risks),
                    _json(analysis.opportunities),
                    analysis.recommended_strategy,
                    _json(analysis.next_questions),
                    int(analysis.followup_required),
                    analysis.followup_suggestion,
                    _json(analysis.unknown_information),
                    result.raw_response,
                    prompt,
                    completion,
                    total,
                    duration,
                ),
            )
            analysis_id = int(cursor.lastrowid)
            for reply in analysis.replies:
                connection.execute(
                    """
                    INSERT INTO reply_suggestions(
                        analysis_id, type, english, chinese, strategy, use_case
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        reply.type,
                        reply.english,
                        reply.chinese,
                        reply.strategy,
                        reply.use_case,
                    ),
                )
        return analysis_id

    def save_failure(
        self,
        *,
        customer_id: int,
        conversation_id: int | None,
        model: str | None,
        raw_response: str,
        error_message: str,
        api_calls: list[APIUsageStats],
    ) -> int:
        prompt, completion, total, duration = _totals(api_calls)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO analyses(
                    customer_id, conversation_id, model, status, raw_response,
                    error_message, prompt_tokens, completion_tokens, total_tokens, duration_ms
                ) VALUES (?, ?, ?, 'failed', ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    conversation_id,
                    model,
                    raw_response,
                    error_message,
                    prompt,
                    completion,
                    total,
                    duration,
                ),
            )
        return int(cursor.lastrowid)


class APIUsageRepository:
    def __init__(self, database: Database):
        self.database = database

    def record(self, stats: APIUsageStats) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO api_usage(
                    model, endpoint, prompt_tokens, completion_tokens, total_tokens,
                    duration_ms, status, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stats.model,
                    stats.endpoint,
                    stats.prompt_tokens,
                    stats.completion_tokens,
                    stats.total_tokens,
                    stats.duration_ms,
                    stats.status,
                    stats.error_type,
                ),
            )
        return int(cursor.lastrowid)
