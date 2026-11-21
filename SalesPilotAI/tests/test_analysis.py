from __future__ import annotations

import json

import pytest

from app.database.repositories.analysis_repository import AnalysisRepository, APIUsageRepository
from app.models.analysis import AnalysisParseError, SalesAnalysis, parse_analysis_json
from app.models.message import CapturedMessage
from app.services.deepseek_service import APIUsageStats, Completion
from app.services.sales_advisor_service import AnalysisRunResult, SalesAdvisorService


def payload():
    return {
        "translation": "请提供 500 件的报价。",
        "customer_intent": "询价",
        "customer_intent_explanation": "客户明确提出数量和报价请求。",
        "customer_emotion": "积极、直接",
        "purchase_requirements": ["500 件", "报价"],
        "purchase_intent_score": 68,
        "score_evidence": ["明确数量", "明确询价"],
        "confidence": 0.82,
        "sales_stage": "Inquiry",
        "customer_concerns": ["价格"],
        "price_sensitivity": "中等，证据有限",
        "communication_risks": ["规格尚未确认"],
        "opportunities": ["可进一步确认规格"],
        "recommended_strategy": "先确认规格，再提供准确报价。",
        "next_questions": ["请确认产品规格？"],
        "replies": [
            {
                "type": "professional",
                "english": "Thank you for your inquiry. Could you confirm the specifications?",
                "chinese": "感谢您的询价。请确认产品规格好吗？",
                "strategy": "专业确认需求",
                "use_case": "规格不完整时",
            },
            {
                "type": "sales_driven",
                "english": "Could you also share your target price and delivery schedule?",
                "chinese": "也可以告诉我您的目标价格和交货计划吗？",
                "strategy": "推进采购信息",
                "use_case": "客户明确询价时",
            },
            {
                "type": "relationship_building",
                "english": "We are happy to prepare the details at your pace.",
                "chinese": "我们很乐意按您的节奏准备资料。",
                "strategy": "降低压力",
                "use_case": "建立长期关系时",
            },
        ],
        "followup_required": True,
        "followup_suggestion": "报价后三天礼貌跟进。",
        "unknown_information": ["目标价格", "交货时间"],
    }


def stats(model="deepseek-flash", total=30):
    return APIUsageStats(
        model=model,
        endpoint="https://api.deepseek.com",
        prompt_tokens=10,
        completion_tokens=total - 10,
        total_tokens=total,
        duration_ms=25,
    )


def result_object():
    return AnalysisRunResult(
        customer_id=1,
        conversation_id=None,
        analysis=SalesAnalysis.model_validate(payload()),
        raw_response=json.dumps(payload()),
        api_calls=[stats()],
    )


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def complete_json(self, messages, *, advanced=False):
        self.calls.append({"messages": messages, "advanced": advanced})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_parse_analysis_supports_fenced_json_and_three_reply_types():
    raw = "```json\n" + json.dumps(payload()) + "\n```"

    analysis = parse_analysis_json(raw)

    assert analysis.customer_intent == "询价"
    assert analysis.purchase_intent_score == 68
    assert [reply.type for reply in analysis.replies] == [
        "professional",
        "sales_driven",
        "relationship_building",
    ]


def test_parse_analysis_rejects_invalid_json_and_duplicate_reply_types():
    with pytest.raises(AnalysisParseError, match="JSON"):
        parse_analysis_json("not-json")
    invalid = payload()
    invalid["replies"][1]["type"] = "professional"
    with pytest.raises(AnalysisParseError, match="三种"):
        parse_analysis_json(json.dumps(invalid))


def test_sales_advisor_redacts_messages_and_builds_trade_prompt():
    completion = Completion(json.dumps(payload()), stats())
    client = FakeClient([completion])
    service = SalesAdvisorService(client)
    messages = [
        CapturedMessage(
            "ACME GmbH needs 500 units. Email buyer@acme.example or +49 171 234 5678",
            sender_type="customer",
        )
    ]

    result = service.analyze(
        1,
        12,
        messages,
        company_name="ACME GmbH",
        redact=True,
        advanced=True,
    )

    assert isinstance(result, AnalysisRunResult)
    assert result.customer_id == 1
    assert result.conversation_id == 12
    assert client.calls[0]["advanced"] is True
    prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    assert "buyer@acme.example" not in prompt
    assert "ACME GmbH" not in prompt
    assert "[已脱敏邮箱]" in prompt
    assert "500 units" in prompt
    assert "国际贸易" in prompt
    assert "不得编造" in prompt


def test_sales_advisor_retries_invalid_json_once_and_aggregates_api_calls():
    client = FakeClient(
        [
            Completion("invalid-first", stats(total=10)),
            Completion(json.dumps(payload()), stats(total=20)),
        ]
    )
    service = SalesAdvisorService(client)

    result = service.analyze(1, None, [CapturedMessage("Need price")])

    assert len(client.calls) == 2
    assert len(result.api_calls) == 2
    assert sum(call.total_tokens for call in result.api_calls) == 30
    repair_prompt = client.calls[1]["messages"][-1]["content"]
    assert "合法 JSON" in repair_prompt


def test_sales_advisor_preserves_both_raw_responses_after_retry_failure():
    client = FakeClient(
        [Completion("first-raw", stats()), Completion("second-raw", stats())]
    )
    service = SalesAdvisorService(client)

    with pytest.raises(AnalysisParseError) as caught:
        service.analyze(1, 9, [CapturedMessage("Need price")])

    assert len(client.calls) == 2
    assert "first-raw" in caught.value.raw_response
    assert "second-raw" in caught.value.raw_response
    assert caught.value.customer_id == 1
    assert caught.value.conversation_id == 9
    assert len(caught.value.api_calls) == 2


def test_analysis_repository_saves_structured_result_replies_and_usage(database):
    customer_id = database.connection.execute(
        "INSERT INTO customers(name) VALUES ('Alice')"
    ).lastrowid
    result = result_object()
    repository = AnalysisRepository(database)

    analysis_id = repository.save_result(result)
    APIUsageRepository(database).record(result.api_calls[0])

    row = database.connection.execute(
        "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
    ).fetchone()
    replies = database.connection.execute(
        "SELECT * FROM reply_suggestions WHERE analysis_id = ? ORDER BY id",
        (analysis_id,),
    ).fetchall()
    usage = database.connection.execute("SELECT * FROM api_usage").fetchone()
    assert row["customer_id"] == customer_id
    assert row["status"] == "completed"
    assert row["customer_intent"] == "询价"
    assert row["purchase_intent_score"] == 68
    assert json.loads(row["purchase_requirements_json"]) == ["500 件", "报价"]
    assert row["total_tokens"] == 30
    assert len(replies) == 3
    assert replies[0]["english"].startswith("Thank you")
    assert usage["status"] == "success"
    assert usage["total_tokens"] == 30


def test_analysis_repository_preserves_failed_raw_response(database):
    database.connection.execute("INSERT INTO customers(name) VALUES ('Alice')")
    repository = AnalysisRepository(database)

    analysis_id = repository.save_failure(
        customer_id=1,
        conversation_id=None,
        model="deepseek-flash",
        raw_response="invalid raw",
        error_message="JSON 格式无效",
        api_calls=[stats()],
    )

    row = database.connection.execute(
        "SELECT status, raw_response, error_message FROM analyses WHERE id = ?",
        (analysis_id,),
    ).fetchone()
    assert tuple(row) == ("failed", "invalid raw", "JSON 格式无效")
