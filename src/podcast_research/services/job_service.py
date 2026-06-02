"""P2-K.2.1: Unified in-memory job service — analysis, sync, and future task types.

Local single-user tool. Jobs lost on restart. Max 50 jobs.

Status lifecycle:
    queued → running → long_running → success
    queued → running → long_running → failed
    queued → running → long_running → stale (no heartbeat)

Heartbeat thresholds are module-level for easy monkeypatching in tests.
"""

from __future__ import annotations

import threading
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

_MAX_JOBS = 50

# Heartbeat thresholds (seconds) — monkeypatchable for tests
LONG_JOB_THRESHOLD = 300   # 5 min: running → long_running
STALE_THRESHOLD = 600       # 10 min without heartbeat → stale

# Stage → user-visible message (shared across job types)
_ALL_STAGES: dict[str, str] = {
    # Analysis stages
    "queued": "已收到请求",
    "fetching_transcript": "正在获取视频字幕",
    "cleaning": "正在整理字幕内容",
    "analyzing": "正在进行 AI 分析",
    "analyzing_chunk": "正在分析",
    "saving": "正在生成报告",
    # Sync stages
    "exporting_report": "正在导出报告到知识库",
    "updating_cards": "正在更新主题和公司",
    "updating_relations": "正在建立知识关联",
    "refreshing_brief": "正在刷新研究摘要",
    "refreshing_watchlist": "正在刷新我的关注",
    # Full_flow stages
    "saving_report": "正在保存报告",
    "syncing_knowledge_base": "正在更新知识库",
    # Terminal
    "success": "任务已完成",
    "failed": "任务失败",
}

# Job-type → human-readable label
JOB_TYPE_LABELS: dict[str, str] = {
    "analysis": "生成报告",
    "sync": "同步知识库",
    "full_flow": "整理进知识库",
}

# Job-type → page title/description
JOB_TYPE_TITLES: dict[str, str] = {
    "analysis": "正在生成研究报告",
    "sync": "正在同步到知识库",
    "full_flow": "正在整理进知识库",
}

JOB_TYPE_DESCRIPTIONS: dict[str, str] = {
    "analysis": "AI 正在获取字幕、拆解观点并生成研究报告。",
    "sync": "系统正在更新 Obsidian、研究摘要和我的关注。",
    "full_flow": "系统会先生成研究报告，再更新知识库、研究摘要和我的关注。长视频可能需要较长时间，你可以离开页面，稍后从「整理任务」查看结果。",
}


def _now_epoch() -> float:
    return _time.time()


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class AnalysisJob:
    """Unified job model for all background task types.

    Backward-compatible with P2-K.1/P2-K.2 code that references .job_id,
    .job_type, .status, .stage, .message, .youtube_url, .focus_areas, .depth,
    .mock, .report_id, .error, .created_at, .updated_at.
    """

    job_id: str
    job_type: str = "analysis"  # "analysis" | "sync"
    status: str = "queued"      # queued | running | long_running | success | failed | stale
    stage: str = "queued"
    message: str = ""
    title: str = ""
    source_url: str = ""

    # Analysis-specific
    youtube_url: str = ""
    focus_areas: list[str] = field(default_factory=list)
    depth: str = "standard"
    mock: bool = False
    auto_sync: bool = False  # P2-K.3: auto chain sync after analysis

    # Common
    report_id: int | None = None
    error: str | None = None

    # Timing & heartbeat
    created_at: str = field(default_factory=_now_iso)
    started_at: str = ""
    updated_at: str = ""
    last_heartbeat_at: float = 0.0

    # Step progress
    current_step: int | None = None
    total_steps: int | None = None

    # UX flags
    can_leave_page: bool = False

    # Result links (populated on success)
    result_links: dict[str, str] = field(default_factory=dict)


# In-memory store
_JOBS: dict[str, AnalysisJob] = {}
_lock = threading.Lock()


def create_job(
    youtube_url: str,
    focus_areas: list[str],
    depth: str = "standard",
    mock: bool = False,
    auto_sync: bool = False,
) -> AnalysisJob:
    """Create a new analysis job.

    Args:
        auto_sync: If True, job_type="full_flow" — analysis + sync chained automatically.
    """
    job_type = "full_flow" if auto_sync else "analysis"
    job_id = uuid.uuid4().hex[:12]
    job = AnalysisJob(
        job_id=job_id,
        job_type=job_type,
        status="queued",
        stage="queued",
        message=_stage_message("queued"),
        title=JOB_TYPE_TITLES.get(job_type, ""),
        youtube_url=youtube_url,
        focus_areas=focus_areas,
        depth=depth,
        mock=mock,
        auto_sync=auto_sync,
        source_url=youtube_url,
    )
    with _lock:
        _JOBS[job_id] = job
        _prune_if_needed()
    return job


def create_sync_job(report_id: int) -> AnalysisJob:
    """Create a new knowledge sync job."""
    job_id = uuid.uuid4().hex[:12]
    job = AnalysisJob(
        job_id=job_id,
        job_type="sync",
        status="queued",
        stage="queued",
        message=_stage_message("queued"),
        title=JOB_TYPE_TITLES.get("sync", ""),
        report_id=report_id,
    )
    with _lock:
        _JOBS[job_id] = job
        _prune_if_needed()
    return job


def _prune_if_needed() -> None:
    if len(_JOBS) > _MAX_JOBS:
        oldest = sorted(_JOBS.keys(), key=lambda k: _JOBS[k].created_at)[:10]
        for k in oldest:
            del _JOBS[k]


def get_job(job_id: str) -> AnalysisJob | None:
    return _JOBS.get(job_id)


def list_jobs(limit: int = 20) -> list[AnalysisJob]:
    """Return recent jobs for the unified task list page."""
    with _lock:
        jobs = sorted(_JOBS.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]


def count_active_jobs() -> int:
    """Count jobs that are still active (queued/running/long_running)."""
    with _lock:
        return sum(1 for j in _JOBS.values() if j.status in ("queued", "running", "long_running"))


def update_job(
    job_id: str,
    *,
    stage: str = "",
    status: str = "",
    message: str = "",
    report_id: int | None = None,
    error: str = "",
    current_step: int | None = None,
    total_steps: int | None = None,
) -> None:
    """Thread-safe job update. Always bumps last_heartbeat_at."""
    now = _now_epoch()
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        if stage:
            job.stage = stage
            if not message:
                job.message = _stage_message(stage)
        if status:
            job.status = status
        if message:
            job.message = message
        if report_id is not None:
            job.report_id = report_id
        if error:
            job.error = error
        if current_step is not None:
            job.current_step = current_step
        if total_steps is not None:
            job.total_steps = total_steps
        job.updated_at = _now_iso()
        job.last_heartbeat_at = now
        if not job.started_at:
            job.started_at = _now_iso()


def _stage_message(stage: str) -> str:
    return _ALL_STAGES.get(stage, stage)


def _check_heartbeat(job: AnalysisJob, now: float) -> str:
    """Determine effective status based on heartbeat health.

    Returns one of: running, long_running, stale (or unchanged for terminal states).
    """
    if job.status in ("success", "failed"):
        return job.status

    if job.last_heartbeat_at == 0:
        return "queued"

    elapsed = now - job.last_heartbeat_at
    total_elapsed = now - (job.last_heartbeat_at - _time.time() + now)  # approximate
    # More direct: compute from started
    if job.started_at:
        try:
            started_dt = datetime.strptime(job.started_at, "%Y-%m-%d %H:%M:%S")
            total_elapsed = now - started_dt.timestamp()
        except (ValueError, OSError):
            total_elapsed = 0
    else:
        total_elapsed = 0

    if elapsed >= STALE_THRESHOLD:
        return "stale"
    if total_elapsed >= LONG_JOB_THRESHOLD and elapsed < STALE_THRESHOLD:
        return "long_running"
    if job.status in ("queued",):
        return "running" if job.started_at else "queued"
    return "running"


def _compute_elapsed(job: AnalysisJob, now: float) -> int:
    """Compute elapsed seconds since job started."""
    if not job.started_at:
        return 0
    try:
        started_dt = datetime.strptime(job.started_at, "%Y-%m-%d %H:%M:%S")
        return max(0, int(now - started_dt.timestamp()))
    except (ValueError, OSError):
        return 0


def _build_can_leave(job: AnalysisJob, now: float) -> bool:
    """Determine if user can safely leave the page."""
    if job.status in ("success", "failed", "stale"):
        return True
    elapsed = _compute_elapsed(job, now)
    return elapsed >= LONG_JOB_THRESHOLD


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Return unified status dict for GET /tasks/{id}/status polling.

    Computes heartbeat health, elapsed, can_leave_page, result_links on each call.
    """
    job = get_job(job_id)
    if not job:
        return None

    now = _now_epoch()
    effective_status = _check_heartbeat(job, now)
    elapsed = _compute_elapsed(job, now)
    can_leave = _build_can_leave(job, now)

    # Build result_links based on job_type and status
    result_links: dict[str, str] = {}
    if effective_status == "success":
        if job.job_type == "analysis" and job.report_id:
            result_links["report"] = f"/reports/{job.report_id}"
            result_links["sync"] = f"/reports/{job.report_id}/sync"
        elif job.job_type == "sync":
            result_links["brief"] = "/briefs/latest"
            result_links["watchlist"] = "/watchlist"
            result_links["dashboard"] = "/dashboard"
            if job.report_id:
                result_links["report"] = f"/reports/{job.report_id}"
        elif job.job_type == "full_flow":
            result_links["brief"] = "/briefs/latest"
            result_links["watchlist"] = "/watchlist"
            result_links["dashboard"] = "/dashboard"
            if job.report_id:
                result_links["report"] = f"/reports/{job.report_id}"
    elif effective_status == "failed" and job.job_type == "full_flow" and job.report_id:
        # Sync failed after analysis succeeded — preserve report + retry links
        result_links["report"] = f"/reports/{job.report_id}"
        result_links["sync"] = f"/reports/{job.report_id}/sync"

    # Build stage_progress for chunk display
    stage_progress = None
    if job.current_step is not None and job.total_steps is not None and job.total_steps > 0:
        stage_progress = {
            "current": job.current_step,
            "total": job.total_steps,
        }

    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "job_type_label": JOB_TYPE_LABELS.get(job.job_type, job.job_type),
        "status": effective_status,
        "stage": job.stage,
        "message": job.message,
        "title": job.title or JOB_TYPE_TITLES.get(job.job_type, ""),
        "source_url": job.source_url,
        "report_id": job.report_id,
        "report_url": f"/reports/{job.report_id}" if job.report_id else None,
        "error": job.error,
        "elapsed_seconds": elapsed,
        "current_step": job.current_step,
        "total_steps": job.total_steps,
        "stage_progress": stage_progress,
        "can_leave_page": can_leave,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "result_links": result_links,
    }


def start_job(job: AnalysisJob, progress_callback: Callable | None = None) -> None:
    """Start analysis job in background daemon thread.

    If job.auto_sync is True (full_flow), chains sync_report_to_knowledge_base
    after analysis succeeds. Sync failure preserves the report link.
    """
    def _run():
        now = _now_epoch()
        with _lock:
            if job.job_id in _JOBS:
                _JOBS[job.job_id].status = "running"
                _JOBS[job.job_id].stage = "fetching_transcript"
                _JOBS[job.job_id].message = _stage_message("fetching_transcript")
                _JOBS[job.job_id].started_at = _now_iso()
                _JOBS[job.job_id].last_heartbeat_at = now

        try:
            from podcast_research.services.analyze_service import analyze_youtube_url

            def _progress(stage: str, msg: str, **kwargs: Any) -> None:
                update_job(
                    job.job_id, stage=stage, message=msg,
                    current_step=kwargs.get("current_step"),
                    total_steps=kwargs.get("total_steps"),
                )
                if progress_callback:
                    try:
                        progress_callback(stage, msg, **kwargs)
                    except TypeError:
                        progress_callback(stage, msg)

            result = analyze_youtube_url(
                youtube_url=job.youtube_url,
                focus_areas=job.focus_areas,
                depth=job.depth,
                mock=job.mock,
                progress_callback=_progress,
            )

            if not result.success:
                update_job(job.job_id, status="failed", stage="failed",
                           error=result.message, message=result.message)
                return

            # Analysis succeeded
            report_id = result.report_id
            update_job(job.job_id, report_id=report_id)

            if job.auto_sync:
                # Full flow: chain sync after analysis
                update_job(job.job_id, stage="saving_report",
                           message="正在保存报告")

                from podcast_research.services.sync_service import sync_report_to_knowledge_base

                def _sync_progress(stage: str, msg: str, **kwargs: Any) -> None:
                    # Map sync stages to job updates; skip "success" stage from sync
                    update_job(job.job_id, stage=stage, message=msg,
                               current_step=kwargs.get("current_step"),
                               total_steps=kwargs.get("total_steps"))

                sync_result = sync_report_to_knowledge_base(
                    report_id=report_id,
                    progress_callback=_sync_progress,
                )

                if sync_result.error:
                    # Report generated but sync failed — user can retry
                    update_job(
                        job.job_id, status="failed", stage="failed",
                        error=sync_result.error,
                        message="报告已生成，但知识库更新失败。",
                    )
                    _set_result_links_failed_sync(job.job_id, report_id)
                else:
                    update_job(job.job_id, status="success", stage="success",
                               message="知识库已更新")
                    _set_result_links(job.job_id, "full_flow", report_id)
            else:
                # Analysis only
                update_job(job.job_id, status="success", stage="success",
                           message="报告已生成")
                _set_result_links(job.job_id, "analysis", report_id)

        except Exception as e:
            update_job(job.job_id, status="failed", stage="failed",
                       error=str(e), message="整理失败，请稍后重试")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def start_sync_job(job: AnalysisJob) -> None:
    """Start knowledge sync job in background daemon thread."""
    def _run():
        now = _now_epoch()
        with _lock:
            if job.job_id in _JOBS:
                _JOBS[job.job_id].status = "running"
                _JOBS[job.job_id].stage = "exporting_report"
                _JOBS[job.job_id].message = _stage_message("exporting_report")
                _JOBS[job.job_id].started_at = _now_iso()
                _JOBS[job.job_id].last_heartbeat_at = now

        try:
            from podcast_research.services.sync_service import sync_report_to_knowledge_base

            def _progress(stage: str, msg: str, **kwargs: Any) -> None:
                update_job(
                    job.job_id, stage=stage, message=msg,
                    current_step=kwargs.get("current_step"),
                    total_steps=kwargs.get("total_steps"),
                )

            result = sync_report_to_knowledge_base(
                report_id=job.report_id or 0,
                progress_callback=_progress,
            )

            if result.error:
                update_job(job.job_id, status="failed", stage="failed",
                           error=result.error, message=f"同步失败: {result.error}")
            else:
                update_job(job.job_id, status="success", stage="success",
                           message="知识库已更新")
                _set_result_links(job.job_id, "sync", job.report_id)
        except Exception as e:
            update_job(job.job_id, status="failed", stage="failed",
                       error=str(e), message="同步失败，请稍后重试或查看日志。")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _set_result_links(job_id: str, job_type: str, report_id: int | None) -> None:
    """Populate result_links on job success."""
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        links: dict[str, str] = {}
        if job_type in ("analysis",) and report_id:
            links["report"] = f"/reports/{report_id}"
            links["sync"] = f"/reports/{report_id}/sync"
        elif job_type == "sync":
            links["brief"] = "/briefs/latest"
            links["watchlist"] = "/watchlist"
            links["dashboard"] = "/dashboard"
            if report_id:
                links["report"] = f"/reports/{report_id}"
        elif job_type == "full_flow" and report_id:
            links["report"] = f"/reports/{report_id}"
            links["brief"] = "/briefs/latest"
            links["watchlist"] = "/watchlist"
            links["dashboard"] = "/dashboard"
        job.result_links = links


def _set_result_links_failed_sync(job_id: str, report_id: int | None) -> None:
    """Populate result_links when sync fails after successful analysis (full_flow).

    The report was generated, so provide report + retry sync links.
    """
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        links: dict[str, str] = {}
        if report_id:
            links["report"] = f"/reports/{report_id}"
            links["sync"] = f"/reports/{report_id}/sync"  # retry
        job.result_links = links
