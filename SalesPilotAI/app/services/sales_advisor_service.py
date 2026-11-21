"""外贸销售分析提示词、JSON 修复重试与请求结果。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.analysis import AnalysisParseError, SalesAnalysis, parse_analysis_json
from app.models.knowledge import KnowledgeSnippet
from app.models.message import CapturedMessage
from app.services.deepseek_service import APIUsageStats, DeepSeekAPIError
from app.services.privacy import redact_messages

_SYSTEM_PROMPT = """你是一名拥有丰富国际贸易经验的资深外贸销售顾问，熟悉进口商、批发商、经销商、OEM/ODM、询价、价格谈判、MOQ、样品、付款、交期、物流和售后。
你的任务不是普通翻译，而是分析客户真实商业意图、采购机会、情绪、顾虑、销售阶段与成交风险，并给出下一步策略。
必须区分客户明确表达、合理推测和未知信息；证据不足时降低置信度，不得因为询价就直接判为高意向，也不得因为没有回复就判为拒绝。
不得编造或擅自承诺未确认的价格、库存、MOQ、交期、认证、售后和付款条件；缺少依据时建议销售人员先确认。
输出严格为一个合法 JSON 对象，不要 Markdown。分析字段使用中文，三条英文回复保持自然商务英文，并分别提供中文翻译、策略和适用场景。三种策略必须是 professional、sales_driven、relationship_building。未知发送方不得猜测。
如本次聊天中存在值得长期保留、且证据明确的稳定事实，可在 memory_suggestions 中给出 0—5 条建议，每条包含 category、content、evidence；它们只是待人工确认的建议，不得把推测、临时情绪或未经确认的承诺写入。没有合适内容时输出空数组。
必须区分“知识库确认的信息”“客户提供的信息”“AI 推测的信息”；只有知识库参考中明确写出的内容才能作为知识库事实引用，并在 knowledge_references 中列出 source 和 fact，不得把客户说法或推测描述为知识库内容。"""


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
        knowledge_snippets: list[KnowledgeSnippet] | None = None,
        config=None,
    ) -> AnalysisRunResult:
        if not messages:
            raise ValueError("至少需要一条预览消息才能进行 AI 分析")
        prepared = redact_messages(messages, [company_name] if company_name else []) if redact else list(messages)
        request_messages = self._build_request(prepared, knowledge_snippets or [])
        api_calls = []
        request_options = {"advanced": advanced}
        if config is not None:
            request_options["config"] = config
        try:
            first = self.client.complete_json(request_messages, **request_options)
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
            second = self.client.complete_json(repair_messages, **request_options)
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
    def _build_request(
        messages: list[CapturedMessage],
        knowledge_snippets: list[KnowledgeSnippet] | None = None,
    ) -> list[dict]:
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
        if knowledge_snippets:
            references = ["知识库参考（仅以下片段来自本地已导入资料，可视为知识库确认的信息）："]
            for index, snippet in enumerate(knowledge_snippets, start=1):
                references.append(
                    f"[{index}] 来源：{snippet.file_name} | "
                    f"标题：{snippet.title or '—'} | 分类：{snippet.category or '—'}\n"
                    f"{snippet.snippet}"
                )
            knowledge_text = "\n\n".join(references)
        else:
            knowledge_text = "未提供知识库参考。禁止声称任何信息来自知识库。"
        schema = json.dumps(SalesAnalysis.model_json_schema(), ensure_ascii=False)
        content = (
            "请分析以下本次用户主动确认的可见聊天，不得把它当作完整历史。\n"
            f"消息：{json.dumps(visible_messages, ensure_ascii=False)}\n\n"
            f"{knowledge_text}\n\n"
            "引用规则：请区分知识库确认的信息、客户提供的信息和 AI 推测的信息；"
            "客户消息中的说法只能作为客户提供的信息，不得自动当作已确认事实；"
            "知识库未写明的内容必须标为未知或推测，不得编造价格、MOQ、交期、认证、付款和售后条件。\n"
            "输出必须覆盖最新消息中文翻译、意图及依据、情绪、采购需求、0—100 意向评分及证据、0—1 置信度、销售阶段、顾虑、价格敏感度、风险、机会、策略、下一步问题、三种回复、是否跟进、跟进建议、建议跟进天数（0—30，无法判断时可为空）、未知信息和知识库引用。\n"
            f"JSON Schema：{schema}"
        )
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
