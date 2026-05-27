"""Markdown 报告生成测试。"""

from podcast_research.analysis.models import ExtractionResult, InvestmentView, Risk, TrackingSignal, Entity
from podcast_research.llm.mock_provider import MockLLMProvider

# 用包含投资关键词的测试文本模拟真实字幕
MOCK_SEGMENTS = (
    "[00:00:01.000-00:00:10.000] 嘉宾A：我认为宁德时代在储能赛道是看多的方向。\n"
    "[00:00:11.000-00:00:20.000] 不过海外政策风险也需要警惕。\n"
    "[00:00:21.000-00:00:30.000] 港股红利估值偏低，适合防御配置。\n"
    "[00:00:31.000-00:00:40.000] 嘉宾B：我不同意，港股红利的吸引力已经减弱。\n"
)
MOCK_TEXT = (
    "嘉宾A：我认为宁德时代在储能赛道是看多的方向。"
    "不过海外政策风险也需要警惕。"
    "港股红利估值偏低，适合防御配置。"
    "嘉宾B：我不同意，港股红利的吸引力已经减弱。"
)


def test_mock_provider_extract_facts() -> None:
    provider = MockLLMProvider()
    result = provider.extract_facts(MOCK_TEXT, MOCK_SEGMENTS)
    assert isinstance(result, ExtractionResult)
    assert len(result.investment_views) > 0
    assert len(result.mentioned_entities) > 0
    # 验证观点来源于实际输入内容
    for v in result.investment_views:
        assert v.target_name in MOCK_TEXT


def test_mock_provider_empty_input() -> None:
    provider = MockLLMProvider()
    result = provider.extract_facts("普通文字没有投资内容", "[]")
    assert isinstance(result, ExtractionResult)
    # 无投资关键词时应产出 0 条观点
    assert len(result.investment_views) == 0


def test_mock_provider_render_report() -> None:
    provider = MockLLMProvider()
    extraction = provider.extract_facts(MOCK_TEXT, MOCK_SEGMENTS)
    report = provider.render_report(extraction)
    assert "免责声明" in report
    assert "核心观点矩阵" in report
    assert "风险提示" in report
    assert "待验证信号" in report


def test_report_includes_view_matrix() -> None:
    provider = MockLLMProvider()
    extraction = provider.extract_facts(MOCK_TEXT, MOCK_SEGMENTS)
    report = provider.render_report(extraction)
    for v in extraction.investment_views:
        assert v.target_name in report
        assert (v.view_direction_label or v.view_direction) in report