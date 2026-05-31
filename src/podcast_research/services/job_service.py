"""P2-K.1.1: In-memory job service for analysis progress tracking.

Local single-user tool. Jobs lost on restart. Max 50 jobs.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

_MAX_JOBS = 50

_STAGES = {
    "queued": "已收到请求，准备开始整理",
    "fetching_transcript": "正在获取视频字幕",
    "analyzing": "正在进行 AI 分析",
    "saving": "正在生成报告",
    "success": "整理完成",
    "failed": "整理失败",
}


@dataclass
class AnalysisJob:
    job_id: str
    status: str = "queued"  # queued / running / success / failed
    stage: str = "queued"
    message: str = ""
    youtube_url: str = ""
    focus_areas: list[str] = field(default_factory=list)
    depth: str = "standard"
    mock: bool = False
    report_id: int | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = ""


# In-memory store
_JOBS: dict[str, AnalysisJob] = {}
_lock = threading.Lock()


def create_job(
    youtube_url: str,
    focus_areas: list[str],
    depth: str = "standard",
    mock: bool = False,
) -> AnalysisJob:
    """Create a new analysis job and return it."""
    job_id = uuid.uuid4().hex[:12]
    job = AnalysisJob(
        job_id=job_id,
        status="queued",
        stage="queued",
        message=_STAGES["queued"],
        youtube_url=youtube_url,
        focus_areas=focus_areas,
        depth=depth,
        mock=mock,
    )
    with _lock:
        _JOBS[job_id] = job
        # Prune old jobs if > max
        if len(_JOBS) > _MAX_JOBS:
            oldest = sorted(_JOBS.keys(), key=lambda k: _JOBS[k].created_at)[:10]
            for k in oldest:
                del _JOBS[k]
    return job


def get_job(job_id: str) -> AnalysisJob | None:
    return _JOBS.get(job_id)


def update_job(job_id: str, *, stage: str = "", status: str = "",
               message: str = "", report_id: int | None = None, error: str = "") -> None:
    """Thread-safe job update."""
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        if stage:
            job.stage = stage
            if stage in _STAGES:
                job.message = _STAGES[stage]
        if status:
            job.status = status
        if message:
            job.message = message
        if report_id is not None:
            job.report_id = report_id
        if error:
            job.error = error
        job.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_job(job: AnalysisJob, progress_callback: Callable[[str, str], None] | None = None) -> None:
    """Start job in background thread."""
    def _run():
        update_job(job.job_id, status="running", stage="fetching_transcript")
        try:
            from podcast_research.services.analyze_service import analyze_youtube_url

            def _progress(stage: str, msg: str):
                update_job(job.job_id, stage=stage, message=msg)
                if progress_callback:
                    progress_callback(stage, msg)

            result = analyze_youtube_url(
                youtube_url=job.youtube_url,
                focus_areas=job.focus_areas,
                depth=job.depth,
                mock=job.mock,
                progress_callback=_progress,
            )

            if result.success:
                update_job(job.job_id, status="success", stage="success",
                           report_id=result.report_id, message="整理完成")
            else:
                update_job(job.job_id, status="failed", stage="failed",
                           error=result.message, message=result.message)
        except Exception as e:
            update_job(job.job_id, status="failed", stage="failed",
                       error=str(e), message="整理失败，请稍后重试")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
