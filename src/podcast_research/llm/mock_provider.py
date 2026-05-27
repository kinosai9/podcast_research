"""Mock LLM Provider：返回固定结构化数据，用于测试和 CLI 验证。"""

from podcast_research.analysis.models import (
    ExtractionResult,
    InvestmentView,
    Evidence,
    TrackingSignal,
    Entity,
    Risk,
)
from podcast_research.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    def extract_facts(self, cleaned_text: str, segments_text: str) -> ExtractionResult:
        return ExtractionResult(
            metadata={"source": "mock", "model": "mock-v1"},
            mentioned_entities=[
                Entity(name="宁德时代", normalized_name="宁德时代", entity_type="stock"),
                Entity(name="港股红利", normalized_name="港股红利", entity_type="asset_class"),
            ],
            investment_views=[
                InvestmentView(
                    target_name="宁德时代",
                    target_type="stock",
                    view_direction="bullish",
                    view_direction_label="看多",
                    logic_chain="储能需求增长带动电池出货，海外业务仍有扩张空间",
                    time_horizon="medium",
                    confidence="cautious",
                    evidence=Evidence(
                        evidence_type="行业数据",
                        evidence_detail="储能出货数据增长",
                        evidence_strength="medium",
                    ),
                    risk_warning="海外政策与价格竞争风险",
                    speaker_label="嘉宾A",
                    speaker_role="guest",
                    speaker_confidence="medium",
                    source_quote="储能需求增长带动电池出货，海外业务仍有扩张空间",
                    timestamp_start="00:00:19.000",
                    timestamp_end="00:00:42.000",
                ),
                InvestmentView(
                    target_name="港股红利",
                    target_type="asset_class",
                    view_direction="neutral",
                    view_direction_label="中性",
                    logic_chain="估值偏低适合防御配置，但汇率和地缘风险需警惕",
                    evidence=Evidence(
                        evidence_type="个人判断",
                        evidence_detail="基于估值和风险判断",
                        evidence_strength="weak",
                    ),
                    risk_warning="汇率波动和地缘政治风险",
                    speaker_label="嘉宾A",
                    speaker_role="guest",
                    speaker_confidence="medium",
                    source_quote="港股高股息标的目前估值偏低，适合防御型配置",
                    timestamp_start="00:00:51.000",
                    timestamp_end="00:01:05.000",
                ),
                InvestmentView(
                    target_name="港股红利",
                    target_type="asset_class",
                    view_direction="bearish",
                    view_direction_label="看空",
                    logic_chain="高股息公司利润增速放缓，吸引力减弱",
                    evidence=Evidence(
                        evidence_type="个人判断",
                        evidence_detail="利润增速趋势判断",
                        evidence_strength="weak",
                    ),
                    speaker_label="嘉宾B",
                    speaker_role="guest",
                    speaker_confidence="low",
                    source_quote="很多高股息公司利润增速已经在放缓",
                    timestamp_start="00:01:13.000",
                    timestamp_end="00:01:20.000",
                ),
            ],
            risks=[
                Risk(
                    description="海外政策与价格竞争风险",
                    target_name="宁德时代",
                    speaker_label="嘉宾A",
                    source_quote="海外政策与价格竞争风险也需要警惕",
                    timestamp="00:00:36.000",
                ),
                Risk(
                    description="汇率波动和地缘政治风险",
                    target_name="港股红利",
                    speaker_label="嘉宾A",
                    source_quote="要注意汇率波动和地缘政治风险",
                    timestamp="00:00:59.000",
                ),
            ],
            tracking_signals=[
                TrackingSignal(
                    target_name="宁德时代",
                    signal="关注储能订单数据",
                    trigger_condition="储能出货量环比增速",
                    expected_date="下一季度",
                    source_quote="储能需求增长带动电池出货",
                    timestamp="00:00:19.000",
                ),
            ],
            key_quotes=[
                "储能需求增长带动电池出货，海外业务仍有扩张空间",
                "港股高股息标的目前估值偏低，适合防御型配置",
                "很多高股息公司利润增速已经在放缓",
            ],
            uncertain_items=[
                "嘉宾B对港股红利的判断缺乏具体数据支撑",
            ],
        )

    def render_report(self, extraction: ExtractionResult) -> str:
        lines = [
            "# 投资播客研究报告",
            "",
            "> **免责声明**：本报告仅为播客内容的结构化整理，不构成任何投资建议。",
            "> 所有观点均来自播客嘉宾原文，不代表分析工具的判断。",
            "",
            "---",
            "",
            "## 执行摘要",
            "",
        ]

        # Summary
        view_count = len(extraction.investment_views)
        entity_names = ", ".join(e.name for e in extraction.mentioned_entities)
        lines.append(f"本期讨论涉及 **{entity_names}**，共提取 **{view_count}** 条投资观点。")

        # View matrix
        lines.append("")
        lines.append("## 核心观点矩阵")
        lines.append("")
        lines.append("| 标的 | 方向 | 逻辑 | 证据类型 | 发言人 | 时间戳 |")
        lines.append("|------|------|------|----------|--------|--------|")
        for v in extraction.investment_views:
            lines.append(
                f"| {v.target_name} | {v.view_direction_label or v.view_direction} "
                f"| {v.logic_chain[:40]} | {v.evidence.evidence_type} "
                f"| {v.speaker_label} | {v.timestamp_start} |"
            )

        # Risks
        lines.append("")
        lines.append("## 风险提示")
        lines.append("")
        for r in extraction.risks:
            lines.append(f"- **{r.description}**（{r.target_name}，{r.speaker_label} @ {r.timestamp}）")

        # Tracking signals
        lines.append("")
        lines.append("## 待验证信号")
        lines.append("")
        for s in extraction.tracking_signals:
            lines.append(f"- {s.signal}（{s.target_name}，触发条件：{s.trigger_condition}，预期时间：{s.expected_date}）")

        # Key quotes
        lines.append("")
        lines.append("## 关键原文引用")
        lines.append("")
        for q in extraction.key_quotes:
            lines.append(f"> {q}")

        # Uncertain items
        if extraction.uncertain_items:
            lines.append("")
            lines.append("## 不确定项")
            lines.append("")
            for u in extraction.uncertain_items:
                lines.append(f"- {u}")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*分析模型：mock-v1 | 分析时间：自动生成*")

        return "\n".join(lines)