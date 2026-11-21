"""外贸销售分析提示词、JSON 修复重试与请求结果。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.analysis import AnalysisParseError, SalesAnalysis, parse_analysis_json
from app.models.message import CapturedMessage
from app.services.deepseek_service import APIUsageStats, DeepSeekAPIError
from app.services.privacy import redact_messages

_SYSTEM_PROMPT = """你是一名拥有丰富国际贸易经验的资深外贸销售顾问，熟悉进口商、批发商、经销商、OEM/ODM、询价、价格谈判、MOQ、样品、付款、交期、物流和售后。
你的任务不是普通翻译，而是分析客户真实商业意图、采购机会、情绪、顾虑、销售阶段与成交风险，并给出下一步策略。
必须区分客户明确表达、合理推测和未知信息；证据不足时降低置信度，不得因为询价就直接判为高意向，也不得因为没有回复就判为拒绝。
不得编造或擅自承诺未确认的价格、库存、MOQ、交期、认证、售后和付款条件；缺少依据时建议销售人员先确认。
输出严格为一个合法 JSON 对象，不要 Markdown。分析字段使用中文，三条英文回复保持自然商务英文，并分别提供中文翻译、策略和适用场景。三种策略必须是 professional、sales_driven、relationship_building。未知发送方不得猜测。"""


@dataclass
class AnalysisRunResult:
    customer_id: int
    conversation_id: int | None
    analysis: SalesAnalysis
    raw_response: str
    api_calls: list[APIUsageStats]


class SalesAdvisorService:
    def __init__(self, client):
        self.client = client

    def analyze(
        self,
        customer_id: int,
        conversation_id: int | None,
        messages: list[CapturedMessage],
        *,
        company_name: str = "",
        redact: bool = True,
        advanced: bool = False,
    ) -> AnalysisRunResult:
        if not messages:
            raise ValueError("至少需要一条预览消息才能进行 AI 分析")
        prepared = redact_messages(messages, [company_name] if company_name else []) if redact else list(messages)
        request_messages = self._build_request(prepared)
        api_calls = []
        try:
            first = self.client.complete_json(request_messages, advanced=advanced)
        except DeepSeekAPIError as exc:
            self._attach_context(exc, customer_id, conversation_id, api_calls, "")
            raise
        api_calls.append(first.stats)
        try:
            analysis = parse_analysis_json(first.content)
            return AnalysisRunResult(
                customer_id, conversation_id, analysis, first.content, api_calls
            )
        except AnalysisParseError:
            repair_messages = [
                *request_messages,
                {"role": "assistant", "content": first.content},
                {
                    "role": "user",
                    "content": "上一次输出无法通过校验。请根据要求重新输出完整、合法 JSON，不要 Markdown，不要遗漏三种回复。",
                },
            ]
        try:
            second = self.client.complete_json(repair_messages, advanced=advanced)
        except DeepSeekAPIError as exc:
            self._attach_context(exc, customer_id, conversation_id, api_calls, first.content)
            raise
        api_calls.append(second.stats)
        try:
            analysis = parse_analysis_json(second.content)
        except AnalysisParseError as exc:
            combined_raw = f"首次响应：\n{first.content}\n\n修复重试响应：\n{second.content}"
            self._attach_context(exc, customer_id, conversation_id, api_calls, combined_raw)
            raise
        return AnalysisRunResult(
            customer_id, conversation_id, analysis, second.content, api_calls
        )

    @staticmethod
    def _attach_context(error, customer_id, conversation_id, api_calls, raw_response):
        if getattr(error, "stats", None) is not None:
            api_calls.append(error.stats)
        error.api_calls = api_calls
        error.customer_id = customer_id
        error.conversation_id = conversation_id
        error.raw_response = raw_response

    @staticmethod
    def _build_request(messages: list[CapturedMessage]) -> list[dict]:
        sender_labels = {"customer": "客户", "sales": "销售", "unknown": "未知（不得猜测）"}
        visible_messages = [
            {
                "sequence": index,
                "sender": sender_labels[message.sender_type],
                "timestamp": message.timestamp or "未知",
                "content": message.content,
            }
            for index, message in enumerate(messages, start=1)
        ]
        schema = json.dumps(SalesAnalysis.model_json_schema(), ensure_ascii=False)
        content = (
            "请分析以下本次用户主动确认的可见聊天，不得把它当作完整历史。\n"
            f"消息：{json.dumps(visible_messages, ensure_ascii=False)}\n\n"
            "输出必须覆盖最新消息中文翻译、意图及依据、情绪、采购需求、0—100 意向评分及证据、0—1 置信度、销售阶段、顾虑、价格敏感度、风险、机会、策略、下一步问题、三种回复、是否跟进、跟进建议和未知信息。\n"
            f"JSON Schema：{schema}"
        )
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
