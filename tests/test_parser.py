"""字幕解析器测试。"""

from pathlib import Path

from podcast_research.analysis.models import SubtitleSegment
from podcast_research.subtitles.parser import detect_format, parse_subtitle

SAMPLE_SRT = Path(__file__).resolve().parent.parent / "data" / "subtitles" / "sample.srt"


def test_detect_format_srt() -> None:
    assert detect_format(Path("test.srt")) == "srt"


def test_detect_format_txt() -> None:
    assert detect_format(Path("test.txt")) == "txt"


def test_detect_format_unsupported() -> None:
    try:
        detect_format(Path("test.vtt"))
    except ValueError as e:
        assert "不支持" in str(e)


def test_parse_srt_file() -> None:
    segments = parse_subtitle(SAMPLE_SRT)
    assert len(segments) > 0
    assert all(isinstance(s, SubtitleSegment) for s in segments)
    first = segments[0]
    assert first.segment_id.startswith("seg_")
    assert first.start_time.startswith("00:")
    assert first.text.strip() != ""


def test_parse_srt_timestamps() -> None:
    segments = parse_subtitle(SAMPLE_SRT)
    for s in segments:
        assert "." in s.start_time or ":" in s.start_time


def test_parse_txt() -> None:
    from podcast_research.subtitles.parser import _parse_txt
    segments = _parse_txt("第一行\n第二行\n第三行")
    assert len(segments) == 3
    assert segments[0].text == "第一行"
    assert segments[0].start_time == ""