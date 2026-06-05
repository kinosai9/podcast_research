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
            "video_id": r.video_id or "",
        })
    brief.recommended_reports = recs

    # ── Summary bullets (natural language, rule-generated) ──
    summary = _build_summary(brief, snapshot)
    brief.summary = summary

    return brief


def _build_summary(brief: ResearchBrief, snapshot: WorkspaceSnapshot) -> list[str]:
    """Build 3-5 explanatory summary bullets. Rule-based, no LLM.

    P2-N.2: Upgraded from statistical counting to contextual explanation.
    Each bullet now explains WHY a topic/company matters, not just HOW MANY.
    """
    from podcast_research.utils.display import clean_display_text

    bullets = []

    # 1. Most active topic — explain focus areas and related companies
    if brief.active_topics and brief.active_topics[0].score > 0:
        t = brief.active_topics[0]
        # Find related companies for this topic
        related_companies = _find_related_companies(t.name, snapshot)
        # Find representative claim text for context
        context_phrase = _derive_topic_context(t.name, snapshot)
        parts = [f"{t.name} 是当前最活跃主题"]
        if context_phrase:
            parts.append(f"讨论集中在{context_phrase}")
        if related_companies:
            parts.append(f"相关公司包括 {'、'.join(related_companies[:3])}")
        bullets.append("，".join(parts) + "。")

    # 2. Most active company — explain what's being discussed
    if brief.active_companies and brief.active_companies[0].score > 0:
        c = brief.active_companies[0]
        related_topics = _find_related_topics(c.name, snapshot)
        parts = [f"{c.name} 在近期报告中讨论最为集中"]
        if related_topics:
            parts.append(f"主要涉及 {'、'.join(related_topics[:3])}")
        if c.claims > 0:
            parts.append(f"涵盖 {c.claims} 条关键判断")
        bullets.append("，".join(parts) + "。")

    # 3. Coverage summary — reports + channels + knowledge accumulation
    if brief.recommended_reports:
        channels = snapshot.channels or []
        channel_names = [ch.name for ch in channels[:4]]
        parts = [f"知识库已积累 {brief.total_claims} 条判断"]
        if brief.total_signals > 0:
            parts.append(f"{brief.total_signals} 个观察点")
        if channel_names:
            parts.append(f"来自 {'、'.join(channel_names)} 等 {len(channels)} 个频道")
        parts.append(f"共 {brief.total_reports} 份报告")
        bullets.append("，".join(parts) + "。")

    # 4. What to watch — actionable signals
    core_topics = snapshot.core_topics()
    watching_signals = snapshot.watching_signals()
    if watching_signals:
        active_core = [t.name for t in core_topics
                       if snapshot.claims_count_for(t.name) > 0
                       or snapshot.signals_count_for(t.name) > 0]
        if active_core:
            bullets.append(
                f"值得持续关注的方向：{'、'.join(active_core[:4])}。"
                f"另有 {len(watching_signals)} 个跟踪信号建议审阅。"
            )

    # 5. Reinforced claims — what's gaining confidence
    if brief.reinforced_claims:
        cleaned = [clean_display_text(c, 60) for c in brief.reinforced_claims[:2]]
        snippets = "；".join(cleaned)
        bullets.append(
            f"{len(brief.reinforced_claims)} 条判断被多份报告交叉验证，可信度较高。"
            f"如：{snippets}"
        )

    return bullets[:5]


def _find_related_companies(topic_name: str, snapshot: WorkspaceSnapshot) -> list[str]:
    """Find companies that appear alongside this topic in claims."""
    companies = set()
    for claim in snapshot.claims:
        if topic_name in claim.related_topics:
            for comp in claim.related_companies:
                companies.add(comp)
    return sorted(companies)[:5]


def _find_related_topics(company_name: str, snapshot: WorkspaceSnapshot) -> list[str]:
    """Find topics that appear alongside this company in claims."""
    topics = set()
    for claim in snapshot.claims:
        if company_name in claim.related_companies:
            for t in claim.related_topics:
                topics.add(t)
    return sorted(topics)[:5]


def _derive_topic_context(topic_name: str, snapshot: WorkspaceSnapshot) -> str:
    """Extract a short context phrase from claims related to this topic."""
    related_claims = [
        c for c in snapshot.claims
        if topic_name in c.related_topics
    ]
    if not related_claims:
        return ""

    # Use the first few words from the highest-quality claim
    from podcast_research.utils.display import clean_display_text
    for claim in related_claims[:5]:
        text = clean_display_text(claim.claim, 120)
        # Try to extract the subject matter
        if "模型" in text or "model" in text.lower():
            return "模型能力演进和竞争格局"
        if "Agent" in text or "agent" in text.lower():
            return "Agent 应用和企业自动化"
        if "infra" in text.lower() or "基础设施" in text:
            return "算力基础设施和投资周期"
        if "企业" in text or "enterprise" in text.lower():
            return "企业采用和商业落地"
        if "市场" in text or "market" in text.lower() or "估值" in text:
            return "市场趋势和估值变化"
        if "安全" in text or "safety" in text.lower():
            return "AI 安全和治理"

    # Fallback: use first 40 chars of first claim
    if related_claims:
        return clean_display_text(related_claims[0].claim, 40)

    return ""
