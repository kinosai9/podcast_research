"""P2-K.1: Analyze service — reusable wrapper for YouTube analysis pipeline."""

from dataclasses import dataclass, field
from pathlib import Path

from podcast_research.adapters.youtube_transcript import YouTubeTranscriptAdapter
from podcast_research.analysis.pipeline import analyze_from_transcript
from podcast_research.config import TRANSCRIPT_CACHE_DIR, ensure_dirs


@dataclass
class AnalyzeResult:
    success: bool
    report_id: int = 0
    message: str = ""
    error_type: str = ""  # invalid_url / no_subtitle / llm_config / token_limit / unknown


def analyze_youtube_url(
    youtube_url: str,
    focus_areas: list[str] | None = None,
    depth: str = "standard",
    mock: bool = False,
    progress_callback=None,
) -> AnalyzeResult:
    """Analyze a YouTube video and generate a research report.

    Args:
        youtube_url: Full YouTube video URL.
        focus_areas: List of focus areas for the analysis.
        depth: Analysis depth (standard / deep).
        mock: Use mock LLM provider (for testing).
        progress_callback: Optional callable(stage, message) for progress updates.

    Returns:
        AnalyzeResult with success status, report_id, and user-friendly message.
    """
    ensure_dirs()

    if focus_areas is None:
        focus_areas = ["通用投资研究"]

    provider = "mock" if mock else "openai-compatible"

    # 1. Fetch transcript
    if progress_callback:
        progress_callback("fetching_transcript", "正在获取视频字幕")
    try:
        adapter = YouTubeTranscriptAdapter(cache_dir=TRANSCRIPT_CACHE_DIR)
        transcript = adapter.fetch(url=youtube_url)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "no transcript" in msg or "subtitles are disabled" in msg:
            return AnalyzeResult(
                success=False,
                error_type="no_subtitle",
                message="该视频暂时无法获取字幕，可能是作者关闭了字幕或 YouTube 暂未生成字幕。",
            )
        return AnalyzeResult(
            success=False,
            error_type="invalid_url",
            message=f"无法获取该视频的字幕。请确认链接是否有效。",
        )

    # 2. Run pipeline
    if progress_callback:
        progress_callback("analyzing", "正在进行 AI 分析")
    try:
        result = analyze_from_transcript(
            transcript,
            provider_name=provider,
            focus_areas=focus_areas,
            analysis_depth=depth,
        )
        report_id = result.get("report_id", 0)
        return AnalyzeResult(
            success=True,
            report_id=report_id,
            message=f"分析完成，已生成报告 #{report_id}",
        )
    except Exception as e:
        msg = str(e).lower()
        if "api key" in msg or "unauthorized" in msg or "authentication" in msg:
            return AnalyzeResult(
                success=False,
                error_type="llm_config",
                message="AI 分析服务尚未配置，请检查 .env 中的 LLM_API_KEY。",
            )
        if "token" in msg or "too long" in msg or "maximum context" in msg:
            return AnalyzeResult(
                success=False,
                error_type="token_limit",
                message="视频较长，当前分析失败。后续将支持长视频自动分段整理。",
            )
        return AnalyzeResult(
            success=False,
            error_type="unknown",
            message="整理失败，请稍后重试。若持续失败可查看日志排查。",
        )
