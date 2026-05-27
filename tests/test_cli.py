"""CLI mock 模式运行测试。"""

from pathlib import Path
from typer.testing import CliRunner

from podcast_research.cli import app

SAMPLE_SRT = Path(__file__).resolve().parent.parent / "data" / "subtitles" / "sample.srt"

runner = CliRunner()


def test_cli_mock_analyze() -> None:
    result = runner.invoke(app, ["--subtitle-file", str(SAMPLE_SRT)])
    assert result.exit_code == 0
    assert "分析完成" in result.output


def test_cli_missing_file() -> None:
    result = runner.invoke(app, ["--subtitle-file", "nonexistent.srt"])
    assert result.exit_code == 1