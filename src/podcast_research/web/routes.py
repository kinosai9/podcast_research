"""P1-C / P2-I.2: HTML pages + actions — /dashboard /reports /patches /search + POST actions"""

import os
import re
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader

from podcast_research.db.repository import (
    get_report_detail,
    list_reports,
    search_reports,
)
from podcast_research.db.session import get_session, init_db

router = APIRouter(tags=["web"])

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
    cache_size=0,
)


def _get_vault_path() -> str:
    return os.getenv("OBSIDIAN_VAULT_PATH", "")


def _flash(request: Request) -> dict:
    """Extract flash messages from query params: ?msg=type:content"""
    msg = request.query_params.get("msg", "")
    if ":" in msg:
        msg_type, content = msg.split(":", 1)
        if msg_type in ("success", "error"):
            return {"flash_type": msg_type, "flash_msg": content}
    return {}


def _get_session():
    init_db()
    return get_session()


def _highlight_text(text: str, query: str) -> str:
    """Wrap matching terms in <mark> tags, case-insensitive.
    Handles mixed CJK/ASCII by extracting ASCII words + CJK bigrams.
    """
    if not query or not text:
        return text

    terms: list[str] = []
    # Extract ASCII words (keep as-is)
    ascii_words = re.findall(r'[A-Za-z0-9+_-]{2,}', query)
    terms.extend(w.lower() for w in ascii_words)

    # Extract CJK characters, create overlapping 2-char bigrams
    cjk_chars = re.findall(r'[一-鿿]', query)
    for i in range(len(cjk_chars) - 1):
        terms.append(cjk_chars[i] + cjk_chars[i + 1])

    # Also add single CJK chars if only 1-2 total
    if len(cjk_chars) <= 2:
        terms.extend(cjk_chars)

    if not terms:
        return text

    # Deduplicate and sort by length descending (longer matches first)
    terms = sorted(set(terms), key=len, reverse=True)

    pattern = re.compile(
        '(' + '|'.join(re.escape(t) for t in terms) + ')',
        re.IGNORECASE,
    )
    return pattern.sub(r'<mark>\1</mark>', text)


def _render(name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    template = _env.get_template(name)
    return HTMLResponse(template.render(context), status_code=status_code)


def _build_recommendations(
    pending_patches: list[dict],
    review_claims: list[dict],
    review_signals: list[dict],
    recent_reports: list[dict],
    core_topics: list[dict],
    summary: dict,
) -> list[dict]:
    """Build 1-3 priority recommendations for the 'Today' section. Rule-based, no LLM."""
    items: list[dict] = []

    # Priority 1: pending AI suggestions (first pending patch)
    for p in pending_patches[:1]:
        items.append({
            "icon": "📋", "action": "view_patch", "action_label": "查看",
            "patch_id": p["patch_id"],
            "target": p["target"],
            "text": f"AI 整理了「{p['target']}」的最新内容，建议确认后采纳",
            "reason": f"该主题已有 {next((t['claims'] for t in core_topics if t['name'] == p['target']), 0)} 条重要判断",
            "post_url": "",
        })

    # Priority 2: watching signal
    if review_signals and len(items) < 3:
        s = review_signals[0]
        signal_text = s['signal'][:70]
        items.append({
            "icon": "🔔", "action": "follow_signal", "action_label": "关注",
            "card_id": s["card_id"],
            "target": "",
            "text": f"关注：{signal_text}",
            "reason": "该信号已标记为需持续观察",
            "post_url": f"/signals/{s['card_id']}/status",
        })

    # Priority 3: active claim that needs review
    if review_claims and len(items) < 3:
        c = review_claims[0]
        claim_text = c['claim'][:120]
        items.append({
            "icon": "💡", "action": "accept_claim", "action_label": "采纳",
            "card_id": c["card_id"],
            "target": "",
            "text": f"{claim_text}",
            "reason": "来自最新报告的核心观点",
            "post_url": f"/claims/{c['card_id']}/status",
        })

    # Fallback: recent report
    if len(items) < 2 and recent_reports:
        r = recent_reports[0]
        items.append({
            "icon": "📄", "action": "view_report", "action_label": "查看",
            "card_id": "",
            "target": "",
            "text": f"阅读最新报告：{r['channel']} — {r['title'][:50]}",
            "reason": f"最新分析内容，{r['date']}",
            "post_url": "",
        })

    return items


def _build_dashboard_context(vault_path: Path) -> dict:
    """Build dashboard data from vault scan. Returns context dict or error info."""
    from podcast_research.workspace.scanner import VaultScanner

    scanner = VaultScanner(vault_path)
    snapshot = scanner.scan()

    summary = {
        "reports": len(snapshot.reports),
        "topics": len(snapshot.topics),
        "core_topics": len(snapshot.core_topics()),
        "companies": len(snapshot.companies),
        "core_companies": len(snapshot.core_companies()),
        "claims": len(snapshot.claims),
        "active_claims": len(snapshot.active_claims()),
        "signals": len(snapshot.signals),
        "open_signals": len(snapshot.open_signals()),
        "watching_signals": len(snapshot.watching_signals()),
        "patches": len(snapshot.llm_patches),
        "pending_patches": len(snapshot.pending_patches()),
        "channels": len(snapshot.channels),
    }

    core_topics = []
    for t in sorted(snapshot.core_topics(), key=lambda x: x.name):
        core_topics.append({
            "name": t.name, "reports": len(t.source_reports),
            "claims": snapshot.claims_count_for(t.name),
            "signals": snapshot.signals_count_for(t.name),
            "curation": t.curation_status or "unknown",
        })

    core_companies = []
    for c in sorted(snapshot.core_companies(), key=lambda x: x.name):
        core_companies.append({
            "name": c.name, "reports": len(c.source_reports),
            "claims": snapshot.claims_count_for(c.name),
            "signals": snapshot.signals_count_for(c.name),
            "curation": c.curation_status or "unknown",
        })

    pending_patches = []
    all_pending = sorted(snapshot.pending_patches(), key=lambda x: x.generated_at, reverse=True)
    for p in all_pending[:5]:
        pending_patches.append({
            "target": p.target, "type": p.target_type,
            "generated": p.generated_at[:10] if p.generated_at else "?",
            "patch_id": p.patch_id,
        })

    from podcast_research.workspace.generators import _sort_claims_by_priority, _sort_signals_by_priority

    review_claims = []
    for c in _sort_claims_by_priority(snapshot.review_claims())[:5]:
        review_claims.append({
            "card_id": c.card_id, "status": c.status,
            "claim": c.claim if c.claim else c.card_id,
        })

    review_signals = []
    for s in _sort_signals_by_priority(snapshot.review_signals())[:5]:
        review_signals.append({
            "card_id": s.card_id, "status": s.status,
            "signal": s.signal if s.signal else s.card_id,
        })

    recent_reports = []
    for r in snapshot.recent_reports(10):
        recent_reports.append({
            "filename": r.filename, "channel": r.channel or "?",
            "title": r.title or r.filename,
            "date": r.analyzed_at[:10] if r.analyzed_at else "?",
        })

    # Build recommendations (rule-based, max 3)
    recommendations = _build_recommendations(
        pending_patches, review_claims, review_signals,
        recent_reports, core_topics, summary,
    )

    # Build research brief (rule-based insights)
    try:
        from podcast_research.workspace.research_brief import generate_brief
        research_brief = generate_brief(snapshot)
    except Exception:
        research_brief = None

    # Build watchlist brief
    try:
        from podcast_research.workspace.watchlist import (
            load_watchlist, generate_watchlist_brief, ensure_watchlist_template,
        )
        wl_config = load_watchlist(vault_path)
        watchlist_items = generate_watchlist_brief(snapshot, vault_path) if (
            wl_config.companies or wl_config.topics
        ) else []
        watchlist_configured = bool(wl_config.companies or wl_config.topics)
        if not watchlist_configured:
            ensure_watchlist_template(vault_path)
    except Exception:
        watchlist_items = []
        watchlist_configured = False

    return {
        "vault_configured": True,
        "summary": summary,
        "research_brief": research_brief,
        "watchlist_items": watchlist_items,
        "watchlist_configured": watchlist_configured,
        "recommendations": recommendations,
        "core_topics": core_topics,
        "core_companies": core_companies,
        "pending_patches": pending_patches,
        "review_claims": review_claims,
        "review_signals": review_signals,
        "recent_reports": recent_reports,
        "error": None,
    }


# ── GET Routes ────────────────────────────────────────────────────

@router.get("/")
def page_index(request: Request):
    if _get_vault_path():
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/reports", status_code=302)


@router.get("/dashboard")
def page_dashboard(request: Request):
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": False, "vault_path": vault_path_str,
           "summary": {}, "recommendations": [], "watchlist_items": [],
           "watchlist_configured": False,
           "core_topics": [], "core_companies": [],
           "pending_patches": [], "review_claims": [], "review_signals": [], "recent_reports": []}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("dashboard.html", ctx)

    vp = Path(vault_path_str)
    if not vp.exists():
        ctx["vault_missing"] = True
        return _render("dashboard.html", ctx)

    try:
        ctx.update(_build_dashboard_context(vp))
    except Exception as e:
        ctx["error"] = str(e)
    return _render("dashboard.html", ctx)


@router.get("/reports")
def page_reports(request: Request, limit: int = 50, source: str | None = None):
    session = _get_session()
    try:
        reports = list_reports(session, limit=limit, source_type=source)
    finally:
        session.close()
    ctx = {"request": request, "reports": reports}
    ctx.update(_flash(request))
    return _render("reports_list.html", ctx)


@router.get("/reports/{report_id}")
def page_report_detail(request: Request, report_id: int, hl: str = ""):
    session = _get_session()
    try:
        report = get_report_detail(session, report_id)
    finally:
        session.close()
    if not report:
        ctx = {"request": request, "status_code": 404, "detail": f"报告 ID={report_id} 不存在"}
        ctx.update(_flash(request))
        return _render("error.html", ctx, status_code=404)
    if hl and report.get("report_markdown"):
        report["report_markdown_highlighted"] = _highlight_text(report["report_markdown"], hl)
    else:
        report["report_markdown_highlighted"] = report.get("report_markdown", "")
    ctx = {"request": request, "report": report, "hl": hl}
    ctx.update(_flash(request))
    return _render("report_detail.html", ctx)


@router.get("/briefs/latest")
def page_research_brief(request: Request):
    """P2-J.1: Latest Research Brief — rule-based insights from knowledge graph."""
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str),
           "brief": None}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("research_brief.html", ctx)

    vp = Path(vault_path_str)
    if not vp.exists():
        return _render("research_brief.html", ctx)

    try:
        from podcast_research.workspace.scanner import VaultScanner
        from podcast_research.workspace.research_brief import generate_brief
        from podcast_research.workspace.watchlist import load_watchlist, generate_watchlist_brief

        scanner = VaultScanner(vp)
        snapshot = scanner.scan()
        brief = generate_brief(snapshot)
        ctx["brief"] = brief

        wl_config = load_watchlist(vp)
        ctx["watchlist_items"] = generate_watchlist_brief(snapshot, vp) if (
            wl_config.companies or wl_config.topics
        ) else []
    except Exception as e:
        ctx["error"] = str(e)

    return _render("research_brief.html", ctx)


@router.get("/watchlist")
def page_watchlist(request: Request):
    """P2-J.2: Watchlist Brief page."""
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str),
           "items": [], "config_exists": False}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("watchlist.html", ctx)

    vp = Path(vault_path_str)
    if not vp.exists():
        return _render("watchlist.html", ctx)

    config_path = vp / "99_System" / "Watchlist.yaml"
    ctx["config_exists"] = config_path.exists()

    if not config_path.exists():
        from podcast_research.workspace.watchlist import ensure_watchlist_template
        ensure_watchlist_template(vp)
        ctx["config_created"] = True

    try:
        from podcast_research.workspace.scanner import VaultScanner
        from podcast_research.workspace.watchlist import generate_watchlist_brief

        scanner = VaultScanner(vp)
        snapshot = scanner.scan()
        ctx["items"] = generate_watchlist_brief(snapshot, vp)
    except Exception as e:
        ctx["error"] = str(e)

    return _render("watchlist.html", ctx)


@router.get("/watchlist/settings")
def page_watchlist_settings(request: Request):
    """P2-J.3: Watchlist settings page — add/remove items."""
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str),
           "config": None}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("watchlist_settings.html", ctx)

    vp = Path(vault_path_str)
    if not vp.exists():
        return _render("watchlist_settings.html", ctx)

    from podcast_research.workspace.watchlist import load_watchlist, ensure_watchlist_template
    ensure_watchlist_template(vp)
    config = load_watchlist(vp)
    ctx["config"] = config

    # Check card existence and suggestions
    try:
        from podcast_research.workspace.scanner import VaultScanner
        from podcast_research.workspace.watchlist import (
            get_suggested_companies, get_suggested_topics, resolve_watchlist_name,
        )
        scanner = VaultScanner(vp)
        snapshot = scanner.scan()
        known_companies = {c.name for c in snapshot.companies}
        known_topics = {t.name for t in snapshot.topics}
        ctx["known_companies"] = known_companies
        ctx["known_topics"] = known_topics
        ctx["suggested_companies"] = get_suggested_companies(snapshot)
        ctx["suggested_topics"] = get_suggested_topics(snapshot)

        # Resolve each config item
        resolved_items = []
        for name in config.companies:
            r = resolve_watchlist_name(name, "company", known_companies, known_topics)
            resolved_items.append({"name": name, "type": "company", **r})
        for name in config.topics:
            r = resolve_watchlist_name(name, "topic", known_companies, known_topics)
            resolved_items.append({"name": name, "type": "topic", **r})
        for name in config.themes:
            r = resolve_watchlist_name(name, "theme", known_companies, known_topics)
            resolved_items.append({"name": name, "type": "theme", **r})
        ctx["resolved_items"] = resolved_items
    except Exception:
        ctx["known_companies"] = set()
        ctx["known_topics"] = set()
        ctx["suggested_companies"] = []
        ctx["suggested_topics"] = []
        ctx["resolved_items"] = []

    return _render("watchlist_settings.html", ctx)


@router.post("/watchlist/settings/add")
def action_watchlist_add(request: Request, item_type: str = Form(...), name: str = Form(...)):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/watchlist/settings?msg=error:Vault 未配置", status_code=303)

    from podcast_research.workspace.watchlist import add_watchlist_item
    _, msg = add_watchlist_item(Path(vault_path_str), item_type, name)
    msg_type = "success" if "已添加" in msg else "error"
    return RedirectResponse(url=f"/watchlist/settings?msg={msg_type}:{msg}", status_code=303)


@router.post("/watchlist/settings/remove")
def action_watchlist_remove(request: Request, item_type: str = Form(...), name: str = Form(...)):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/watchlist/settings?msg=error:Vault 未配置", status_code=303)

    from podcast_research.workspace.watchlist import remove_watchlist_item
    _, msg = remove_watchlist_item(Path(vault_path_str), item_type, name)
    msg_type = "success" if "已移除" in msg else "error"
    return RedirectResponse(url=f"/watchlist/settings?msg={msg_type}:{msg}", status_code=303)


# ── P2-K.1: Add New Content ──────────────────────────────────────

@router.get("/content/new")
def page_content_new(request: Request):
    """P2-K.1: Add new content form page."""
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str)}
    ctx.update(_flash(request))

    # Load watchlist topics as focus suggestions
    focus_suggestions = ["AI Agents", "Enterprise AI", "AI Infrastructure",
                         "Semiconductor", "AI Applications", "Business Model"]
    if vault_path_str:
        vp = Path(vault_path_str)
        try:
            from podcast_research.workspace.watchlist import load_watchlist
            config = load_watchlist(vp)
            if config.topics:
                focus_suggestions = config.topics[:6]
        except Exception:
            pass
    ctx["focus_suggestions"] = focus_suggestions
    return _render("content_new.html", ctx)


@router.post("/content/analyze")
def action_content_analyze(
    request: Request,
    youtube_url: str = Form(...),
    focus: str = Form(""),
    depth: str = Form("standard"),
    mock_mode: bool = Form(False),
):
    """Submit a YouTube URL for analysis."""
    from podcast_research.utils.youtube import is_youtube_url, extract_video_id

    # Validate URL
    url = youtube_url.strip()
    if not url:
        return RedirectResponse(
            url="/content/new?msg=error:请输入 YouTube 链接", status_code=303)

    if not is_youtube_url(url):
        return RedirectResponse(
            url="/content/new?msg=error:无法识别该 YouTube 链接，请检查链接是否完整", status_code=303)

    # Parse focus areas
    focus_areas = [f.strip() for f in focus.replace("，", ",").split(",") if f.strip()]
    if not focus_areas:
        focus_areas = ["通用投资研究"]

    if depth not in ("standard", "deep"):
        depth = "standard"

    # Create job and start background analysis
    from podcast_research.services.job_service import create_job, start_job
    job = create_job(
        youtube_url=url,
        focus_areas=focus_areas,
        depth=depth,
        mock=mock_mode,
    )
    start_job(job)
    return RedirectResponse(url=f"/content/jobs/{job.job_id}", status_code=303)


@router.get("/content/jobs/{job_id}")
def page_content_job(request: Request, job_id: str):
    """P2-K.1.1: Analysis job progress page."""
    from podcast_research.services.job_service import get_job
    job = get_job(job_id)
    ctx = {"request": request, "job_id": job_id, "job": job,
           "not_found": job is None}
    return _render("content_job.html", ctx)


@router.get("/content/jobs/{job_id}/status")
def api_job_status(job_id: str):
    """P2-K.1.1: Job status JSON endpoint for polling."""
    from fastapi.responses import JSONResponse
    from podcast_research.services.job_service import get_job

    job = get_job(job_id)
    if not job:
        return JSONResponse({"status": "not_found", "error": "任务不存在或已过期"}, status_code=404)

    return JSONResponse({
        "status": job.status,
        "stage": job.stage,
        "message": job.message,
        "report_id": job.report_id,
        "report_url": f"/reports/{job.report_id}" if job.report_id else None,
        "error": job.error,
    })


@router.get("/search")
def page_search(request: Request, q: str = ""):
    ctx = {"request": request, "q": "", "results": [], "count": 0}
    ctx.update(_flash(request))
    if not q.strip():
        return _render("search.html", ctx)
    ctx["q"] = q.strip()
    session = _get_session()
    try:
        ctx["results"] = search_reports(session, q.strip(), limit=20)
        ctx["count"] = len(ctx["results"])
    finally:
        session.close()
    return _render("search.html", ctx)


# ── Patch pages ───────────────────────────────────────────────────

@router.get("/patches")
def page_patches(request: Request):
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str),
           "patches": [], "vault_path": vault_path_str}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("patches_list.html", ctx)

    vp = Path(vault_path_str)
    if not vp.exists():
        return _render("patches_list.html", ctx)

    patches_dir = vp / "00_Inbox" / "LLM_Patches"
    if patches_dir.exists():
        from podcast_research.claim_signal.review import _parse_frontmatter
        patches = []
        for p in sorted(patches_dir.glob("*.md"), reverse=True):
            try:
                content = p.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)

                # Fallback for patches without frontmatter (mock patches)
                target = fm.get("target", "")
                target_type = fm.get("target_type", "")
                status = fm.get("status", "")

                if not target:
                    # Try to extract from H1: "# Patch Proposal: TargetName"
                    for line in content.split("\n"):
                        if line.startswith("# ") and "Patch Proposal:" in line:
                            target = line.split("Patch Proposal:", 1)[-1].strip()
                            break
                    if not target:
                        target = p.stem

                if not target_type:
                    # Guess from filename
                    target_type = "topic" if p.stem.startswith("topic_") else "company"

                if not status:
                    status = "unknown"

                patches.append({
                    "patch_id": p.stem,
                    "target": target,
                    "target_type": target_type,
                    "status": status,
                    "generated_at": fm.get("generated_at", "")[:10],
                    "target_card": fm.get("target_card", ""),
                })
            except Exception:
                continue
        ctx["patches"] = patches
    return _render("patches_list.html", ctx)


@router.get("/patches/{patch_id}")
def page_patch_detail(request: Request, patch_id: str):
    vault_path_str = _get_vault_path()
    ctx = {"request": request, "vault_configured": bool(vault_path_str),
           "patch_id": patch_id, "not_found": False, "patch": None}
    ctx.update(_flash(request))

    if not vault_path_str:
        return _render("patch_detail.html", ctx)

    patch_path = Path(vault_path_str) / "00_Inbox" / "LLM_Patches" / f"{patch_id}.md"
    if not patch_path.exists():
        ctx["not_found"] = True
        return _render("patch_detail.html", ctx, status_code=404)

    from podcast_research.claim_signal.review import _parse_frontmatter
    content = patch_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content)

    # Extract body below frontmatter
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:]

    ctx["patch"] = {
        "patch_id": patch_id,
        "target": fm.get("target", ""),
        "target_type": fm.get("target_type", ""),
        "target_card": fm.get("target_card", ""),
        "status": fm.get("status", ""),
        "generated_at": fm.get("generated_at", ""),
        "provider": fm.get("provider", ""),
        "model": fm.get("model", ""),
        "source_reports": fm.get("source_reports", []),
        "body": body,
    }
    return _render("patch_detail.html", ctx)


# ── POST Actions ──────────────────────────────────────────────────

@router.post("/dashboard/actions/refresh-workspace")
def action_refresh_workspace(request: Request):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/dashboard?msg=error:Vault 未配置", status_code=303)

    vp = Path(vault_path_str)
    try:
        from podcast_research.workspace import (
            backfill_relations, refresh_curation_status,
            polish_report_metadata, refresh_workspace,
        )
        r1 = backfill_relations(vp, dry_run=False, apply=True)
        r2 = refresh_curation_status(vp, dry_run=False)
        r3 = polish_report_metadata(vp, dry_run=False, apply=True)
        refresh_workspace(vp, dry_run=False)

        t_added = r1["stats"].get("topics_added", 0) + r1["stats"].get("companies_added", 0)
        c_updated = r2["stats"].get("topics_updated", 0) + r2["stats"].get("companies_updated", 0)
        m = f"relations +{t_added}, curation {c_updated} updated, metadata {r3['stats'].get('titles_updated',0)} titles"
        return RedirectResponse(url=f"/dashboard?msg=success:工作区已刷新 — {m}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/dashboard?msg=error:刷新失败 — {e}", status_code=303)


@router.post("/patches/{patch_id}/apply")
def action_patch_apply(request: Request, patch_id: str):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/patches?msg=error:Vault 未配置", status_code=303)

    vp = Path(vault_path_str)
    try:
        from podcast_research.llm_wiki.applier import apply_patch
        patch_rel = f"00_Inbox/LLM_Patches/{patch_id}.md"
        patch_path = vp / patch_rel
        if not patch_path.exists():
            return RedirectResponse(url=f"/patches?msg=error:Patch 不存在: {patch_id}", status_code=303)
        apply_patch(vault_path=vp, patch_rel_path=patch_rel, dry_run=False, confirm_reviewed=True)
        return RedirectResponse(url=f"/patches/{patch_id}?msg=success:已应用 Patch 到目标卡片", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/patches/{patch_id}?msg=error:Apply 失败 — {e}", status_code=303)


@router.post("/patches/{patch_id}/reject")
def action_patch_reject(request: Request, patch_id: str, reason: str = Form("")):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/patches?msg=error:Vault 未配置", status_code=303)

    vp = Path(vault_path_str)
    try:
        from podcast_research.llm_wiki.rollback import reject_patch
        patch_path = vp / "00_Inbox" / "LLM_Patches" / f"{patch_id}.md"
        if not patch_path.exists():
            return RedirectResponse(url=f"/patches?msg=error:Patch 不存在: {patch_id}", status_code=303)
        reject_patch(vault_path=vp, patch_path=patch_path, reason=reason or None)
        return RedirectResponse(url=f"/patches/{patch_id}?msg=success:已拒绝 Patch", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/patches/{patch_id}?msg=error:Reject 失败 — {e}", status_code=303)


@router.post("/claims/{claim_id}/status")
def action_claim_status(request: Request, claim_id: str, status: str = Form(...),
                         note: str = Form(""), return_to: str = Form("dashboard")):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/dashboard?msg=error:Vault 未配置", status_code=303)

    vp = Path(vault_path_str)
    VALID = {"active", "verified", "challenged", "outdated", "archived"}
    if status not in VALID:
        return RedirectResponse(url=f"/dashboard?msg=error:无效状态: {status}", status_code=303)

    try:
        from podcast_research.claim_signal.review import update_claim_status
        ok = update_claim_status(vp, claim_id, status, note=note)
        if not ok:
            return RedirectResponse(url=f"/dashboard?msg=error:Claim 不存在: {claim_id}", status_code=303)
        target = "/dashboard" if return_to == "dashboard" else "/patches"
        return RedirectResponse(url=f"{target}?msg=success:Claim 状态已更新为 {status}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/dashboard?msg=error:更新失败 — {e}", status_code=303)


@router.post("/signals/{signal_id}/status")
def action_signal_status(request: Request, signal_id: str, status: str = Form(...),
                          note: str = Form(""), return_to: str = Form("dashboard")):
    vault_path_str = _get_vault_path()
    if not vault_path_str:
        return RedirectResponse(url="/dashboard?msg=error:Vault 未配置", status_code=303)

    vp = Path(vault_path_str)
    VALID = {"open", "watching", "resolved", "invalidated", "archived"}
    if status not in VALID:
        return RedirectResponse(url=f"/dashboard?msg=error:无效状态: {status}", status_code=303)

    try:
        from podcast_research.claim_signal.review import update_signal_status
        ok = update_signal_status(vp, signal_id, status, note=note)
        if not ok:
            return RedirectResponse(url=f"/dashboard?msg=error:Signal 不存在: {signal_id}", status_code=303)
        target = "/dashboard" if return_to == "dashboard" else "/patches"
        return RedirectResponse(url=f"{target}?msg=success:Signal 状态已更新为 {status}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/dashboard?msg=error:更新失败 — {e}", status_code=303)
