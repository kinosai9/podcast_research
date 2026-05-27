"""字幕解析器：支持 SRT 和 TXT 格式，输出 SubtitleSegment 列表。"""

import re
from pathlib import Path

from podcast_research.analysis.models import SubtitleSegment


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".srt":
        return "srt"
    if ext == ".txt":
        return "txt"
    raise ValueError(f"不支持的字幕格式: {ext}，仅支持 .srt 和 .txt")


def parse_subtitle(path: Path) -> list[SubtitleSegment]:
    fmt = detect_format(path)
    text = path.read_text(encoding="utf-8")
    if fmt == "srt":
        return _parse_srt(text)
    return _parse_txt(text)


_SRT_TIMESTAMP = re.compile(
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
)


def _parse_srt(text: str) -> list[SubtitleSegment]:
    blocks = re.split(r"\n\s*\n", text.strip())
    segments = []
    idx = 0
    for block in blocks:
        lines = block.strip().split("\n")
        ts_match = _SRT_TIMESTAMP.search(lines[1] if len(lines) > 1 else "")
        if not ts_match:
            continue
        start = ts_match.group(1).replace(",", ".")
        end = ts_match.group(2).replace(",", ".")
        content_lines = lines[2:] if len(lines) > 2 else []
        content = " ".join(content_lines).strip()
        if not content:
            continue
        idx += 1
        segments.append(
            SubtitleSegment(
                segment_id=f"seg_{idx:03d}",
                start_time=start,
                end_time=end,
                text=content,
            )
        )
    return segments


def _parse_txt(text: str) -> list[SubtitleSegment]:
    """TXT 格式无时间戳，每行一段，时间戳留空。"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    segments = []
    for i, line in enumerate(lines, 1):
        segments.append(
            SubtitleSegment(
                segment_id=f"seg_{i:03d}",
                start_time="",
                end_time="",
                text=line,
            )
        )
    return segments