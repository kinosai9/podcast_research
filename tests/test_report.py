"""Markdown 报告生成测试。"""

from podcast_research.analysis.models import ExtractionResult, InvestmentView, Risk, TrackingSignal, Entity
from podcast_research.llm.mock_provider import MockLLMProvider


def test_mock_provider_extract_facts() -> None:
    provider = MockLLMProvider()
    result = provider.extract_facts("test text", "segments")
    assert isinstance(result, ExtractionResult)
    assert len(result.investment_views) > 0
    assert len(result.mentioned_entities) > 0


def test_mock_provider_render_report() -> None:
    provider = MockLLMProvider()
    extraction = provider.extract_facts("test", "test")
    report = provider.render_report(extraction)
    assert "免责声明" in report
    assert "核心观点矩阵" in report
    assert "风险提示" in report
    assert "待验证信号" in report
    assert "关键原文引用" in report


def test_report_includes_view_matrix() -> None:
    provider = MockLLMProvider()
    extraction = provider.extract_facts("test", "test")
    report = provider.render_report(extraction)
    for v in extraction.investment_views:
        assert v.target_name in report
        assert (v.view_direction_label or v.view_direction) in report