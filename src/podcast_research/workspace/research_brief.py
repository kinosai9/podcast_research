"""P2-J.1: Rule-based Research Brief generator.

Generates structured research insights from WorkspaceSnapshot.
No LLM, no external APIs, pure deterministic rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from podcast_research.workspace.scanner import WorkspaceSnapshot


@dataclass
class TopicInsight:
    name: str
    score: float
    reports: int
    claims: int
    signals: int
    summary: str = ""


@dataclass
class CompanyInsight:
    name: str
    score: float
    reports: int
    claims: int
    signals: int
    summary: str = ""


@dataclass
class ResearchBrief:
    generated_at: str
    summary: list[str] = field(default_factory=list)
    active_topics: list[TopicInsight] = field(default_factory=list)
    active_companies: list[CompanyInsight] = field(default_factory=list)
    reinforced_claims: list[str] = field(default_factory=list)
    new_signals: list[str] = field(default_factory=list)
    recommended_reports: list[dict] = field(default_factory=list)
    total_reports: int = 0
    total_claims: int = 0
    total_signals: int = 0


def generate_brief(snapshot: WorkspaceSnapshot) -> ResearchBrief:
    """Generate a research brief from vault snapshot. Pure rules, no LLM."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    brief = ResearchBrief(generated_at=now)
    brief.total_reports = len(snapshot.reports)
    brief.total_claims = len(snapshot.claims)
    brief.total_signals = len(snapshot.signals)

    # ── Active Topics (weighted scoring) ──
    topic_scores = []
    for t in snapshot.topics:
        c_count = snapshot.claims_count_for(t.name)
        s_count = snapshot.signals_count_for(t.name)
        r_count = len(t.source_reports)
        score = c_count * 2.0 + s_count * 1.5 + r_count * 1.0
        if score > 0 or t.status == "core":
            topic_scores.append(TopicInsight(
                name=t.name, score=score,
                reports=r_count, claims=c_count, signals=s_count,
            ))

    topic_scores.sort(key=lambda x: x.score, reverse=True)
    brief.active_topics = topic_scores[:5]

    # ── Active Companies (weighted scoring) ──
    company_scores = []
    for c in snapshot.companies:
        c_count = snapshot.claims_count_for(c.name)
        s_count = snapshot.signals_count_for(c.name)
        r_count = len(c.source_reports)
        score = c_count * 2.0 + s_count * 1.5 + r_count * 1.0
        if score > 0:
            company_scores.append(CompanyInsight(
                name=c.name, score=score,
                reports=r_count, claims=c_count, signals=s_count,
            ))

    company_scores.sort(key=lambda x: x.score, reverse=True)
    brief.active_companies = company_scores[:5]

    # ── Reinforced Claims (claims tied to multiple reports or core topics) ──
    core_topic_names = {t.name for t in snapshot.core_topics()}
    reinforced = []
    for c in snapshot.claims:
        sr_count = len(c.source_reports)
        has_core_topic = any(t in core_topic_names for t in c.related_topics)
        if sr_count >= 2 or (has_core_topic and sr_count >= 1):
            text = c.claim[:120] if c.claim else c.card_id
            reinforced.append(text)
    brief.reinforced_claims = reinforced[:5]

    # ── New Signals (recently updated watching/open) ──
    watching = [s for s in snapshot.signals if s.status in ("watching", "open")]
    watching.sort(key=lambda s: s.updated_at or "", reverse=True)
    new_signals = []
    for s in watching[:5]:
        text = s.signal[:120] if s.signal else s.card_id
        new_signals.append(text)
    brief.new_signals = new_signals

    # ── Recommended Reports (most recent, rich in claims/signals) ──
    recs = []
    for r in snapshot.recent_reports(5):
        recs.append({
            "title": r.title or r.filename,
            "filename": r.filename,
            "channel": r.channel or "",
        })
    brief.recommended_reports = recs

    # ── Summary bullets (natural language, rule-generated) ──
    summary = _build_summary(brief, snapshot)
    brief.summary = summary

    return brief


def _build_summary(brief: ResearchBrief, snapshot: WorkspaceSnapshot) -> list[str]:
    """Build 3-5 natural language summary bullets from brief data."""
    bullets = []

    # 1. Most active topic
    if brief.active_topics and brief.active_topics[0].score > 0:
        t = brief.active_topics[0]
        bullets.append(
            f"「{t.name}」是当前最活跃的研究主题，"
            f"关联 {t.claims} 条重要判断和 {t.signals} 个观察点。"
        )

    # 2. Most active company
    if brief.active_companies and brief.active_companies[0].score > 0:
        c = brief.active_companies[0]
        parts = [f"「{c.name}」相关讨论最为集中"]
        if c.claims > 0:
            parts.append(f"涉及 {c.claims} 条判断")
        if c.signals > 0:
            parts.append(f"{c.signals} 个观察点")
        bullets.append("，".join(parts) + "。")

    # 3. Recent report impact
    if brief.recommended_reports:
        bullets.append(
            f"最近分析的报告覆盖了 {len(snapshot.channels)} 个频道，"
            f"知识库已积累 {brief.total_claims} 条判断和 {brief.total_signals} 个观察点。"
        )

    # 4. What to watch
    core_topics = snapshot.core_topics()
    if core_topics and brief.new_signals:
        active_core = [t.name for t in core_topics
                       if snapshot.claims_count_for(t.name) > 0
                       or snapshot.signals_count_for(t.name) > 0]
        if active_core:
            bullets.append(
                f"本周值得持续关注的方向：{'、'.join(active_core[:4])}。"
            )

    # 5. Reinforced claims summary
    if brief.reinforced_claims:
        bullets.append(
            f"有 {len(brief.reinforced_claims)} 条判断被多份报告交叉验证，"
            f"可信度较高，建议优先阅读。"
        )

    return bullets[:5]
