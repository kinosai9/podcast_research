"""P1-C / P2-I.1: HTML 页面测试 — 复用 seeded_db + api_client fixtures"""

import os


def test_index_redirects(api_client):
    """GET / 返回 302 重定向到 /reports（无 vault 配置时）"""
    resp = api_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    # With no vault configured, redirects to /reports
    assert resp.headers["location"] in ("/reports", "/dashboard")


def test_reports_list_ok(api_client, seeded_db):
    """GET /reports 返回 200 并包含 seeded report"""
    resp = api_client.get("/reports")
    assert resp.status_code == 200
    html = resp.text
    assert "报告库" in html
    assert "宁德时代" in html or "新能源" in html


def test_reports_list_with_source_filter(api_client, seeded_db):
    """GET /reports?source=youtube 过滤来源"""
    resp = api_client.get("/reports?source=youtube")
    assert resp.status_code == 200
    html = resp.text
    assert "abc123" in html or "youtube" in html.lower()


def test_report_detail_ok(api_client, seeded_db):
    """GET /reports/{id} 返回 200 并包含核心观点"""
    resp = api_client.get("/reports/1")
    assert resp.status_code == 200
    html = resp.text
    assert "核心观点矩阵" in html
    assert "宁德时代" in html


def test_report_detail_not_found(api_client):
    """不存在的 report_id 返回 HTML 404"""
    resp = api_client.get("/reports/99999")
    assert resp.status_code == 404
    html = resp.text
    assert "404" in html
    assert "不存在" in html


def test_search_with_query(api_client, seeded_db):
    """GET /search?q=宁德 返回 200 并有结果"""
    resp = api_client.get("/search?q=宁德")
    assert resp.status_code == 200
    html = resp.text
    assert "宁德" in html


def test_search_empty_query(api_client):
    """GET /search 不带 q 返回 200 并显示搜索框"""
    resp = api_client.get("/search")
    assert resp.status_code == 200
    html = resp.text
    assert "搜索" in html


def test_api_endpoints_still_work(api_client, seeded_db):
    """原有 /api/* 路径不受影响"""
    # health
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    # reports list
    resp = api_client.get("/api/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data

    # report detail
    resp = api_client.get("/api/reports/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert len(data["views"]) >= 0

    # search
    resp = api_client.get("/api/search?q=宁德")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


# ── P2-I.1 Dashboard Tests ──────────────────────────────────────

def test_dashboard_loads_without_vault(api_client):
    """Dashboard 在无 vault 配置时显示设置提示"""
    resp = api_client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.text
    assert "Vault 未配置" in html or "OBSIDIAN_VAULT_PATH" in html


def test_dashboard_loads_with_vault(api_client, tmp_path):
    """Dashboard 在 vault 配置后显示概览数据"""
    # Create a mini vault
    vault = tmp_path / "vault"
    for d in ["01_Reports", "02_Topics", "03_Companies", "05_Channels",
              "06_Claims", "07_Signals", "99_System", "00_Inbox/LLM_Patches"]:
        (vault / d).mkdir(parents=True)

    # Add a report
    (vault / "01_Reports" / "test_report.md").write_text("""---
type: report
channel: TestChannel
video_id: abc123
analyzed_at: "2026-05-30 12:00"
tags: []
---
# Test Report Title

## Summary
""", encoding="utf-8")

    # Add a core topic
    (vault / "02_Topics" / "AI Agents.md").write_text("""---
type: topic
status: core
topic: AI Agents
curation_status: enhanced
source_reports: []
---
# AI Agents
""", encoding="utf-8")

    # Add a company
    (vault / "03_Companies" / "NVIDIA.md").write_text("""---
type: company
company: NVIDIA
curation_status: indexed
source_reports: []
---
# NVIDIA
""", encoding="utf-8")

    # Set vault path env
    old_vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)

    try:
        resp = api_client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.text
        # Should show vault path
        assert str(vault) in html or "AI 研究助理" in html
        # Should show AI Agents
        assert "AI Agents" in html
        # Should show AI Agents in topic or brief
        assert "AI Agents" in html or "研究摘要" in html
        # Should show research brief summary
        assert "研究摘要" in html or "AI 研究助理" in html
    finally:
        os.environ["OBSIDIAN_VAULT_PATH"] = old_vault


# ── P2-I.2 Action Tests ──────────────────────────────────────────

class TestDashboardActions:
    def test_refresh_workspace_redirects(self, api_client, tmp_path):
        """POST refresh-workspace redirects back to dashboard"""
        vault = tmp_path / "vault"
        (vault / "01_Reports").mkdir(parents=True)
        (vault / "02_Topics").mkdir(parents=True)
        (vault / "03_Companies").mkdir(parents=True)
        (vault / "06_Claims").mkdir(parents=True)
        (vault / "07_Signals").mkdir(parents=True)
        (vault / "99_System").mkdir(parents=True)
        (vault / "00_Inbox" / "LLM_Patches").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/dashboard/actions/refresh-workspace", follow_redirects=False)
            assert resp.status_code in (303, 302)
            assert "/dashboard" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_claim_status_update(self, api_client, tmp_path):
        """POST claim status updates claim frontmatter"""
        vault = tmp_path / "vault"
        claims_dir = vault / "06_Claims"
        claims_dir.mkdir(parents=True)
        (vault / "99_System").mkdir(parents=True)

        p = claims_dir / "claim_test.md"
        p.write_text("""---
type: claim
status: active
claim: "Test claim"
source_reports: []
related_topics: []
related_companies: []
created_at: "2026-05-30T20:07:34"
updated_at: "2026-05-30T20:07:34"
---
# Claim: Test claim

## Statement
Test.
## Review History
""", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post(
                "/claims/claim_test/status",
                data={"status": "verified", "note": "looks good", "return_to": "dashboard"},
                follow_redirects=False,
            )
            assert resp.status_code in (303, 302)
            content = p.read_text(encoding="utf-8")
            assert "verified" in content
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_signal_status_update(self, api_client, tmp_path):
        """POST signal status updates signal frontmatter"""
        vault = tmp_path / "vault"
        signals_dir = vault / "07_Signals"
        signals_dir.mkdir(parents=True)
        (vault / "99_System").mkdir(parents=True)

        p = signals_dir / "signal_test.md"
        p.write_text("""---
type: signal
status: open
signal: "Test signal"
source_reports: []
related_topics: []
related_companies: []
created_at: "2026-05-30T20:07:34"
updated_at: "2026-05-30T20:07:34"
---
# Signal: Test signal
## What to Watch
Test.
## Updates
""", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post(
                "/signals/signal_test/status",
                data={"status": "watching", "note": "", "return_to": "dashboard"},
                follow_redirects=False,
            )
            assert resp.status_code in (303, 302)
            content = p.read_text(encoding="utf-8")
            assert "watching" in content
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_invalid_claim_status_rejected(self, api_client, tmp_path):
        """Invalid claim status returns error redirect"""
        vault = tmp_path / "vault"
        (vault / "06_Claims").mkdir(parents=True)
        p = vault / "06_Claims" / "c.md"
        p.write_text("---\ntype: claim\nstatus: active\nclaim: T\nsource_reports: []\n---\n# T\n")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post(
                "/claims/c/status",
                data={"status": "bogus", "note": "", "return_to": "dashboard"},
                follow_redirects=False,
            )
            assert resp.status_code in (303, 302)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_invalid_signal_status_rejected(self, api_client, tmp_path):
        """Invalid signal status returns error redirect"""
        vault = tmp_path / "vault"
        (vault / "07_Signals").mkdir(parents=True)
        p = vault / "07_Signals" / "s.md"
        p.write_text("---\ntype: signal\nstatus: open\nsignal: T\nsource_reports: []\n---\n# T\n")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post(
                "/signals/s/status",
                data={"status": "bogus", "note": "", "return_to": "dashboard"},
                follow_redirects=False,
            )
            assert resp.status_code in (303, 302)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old


class TestPatchPages:
    def test_patches_page_loads(self, api_client, tmp_path):
        """GET /patches returns 200"""
        vault = tmp_path / "vault"
        (vault / "00_Inbox" / "LLM_Patches").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/patches")
            assert resp.status_code == 200
            assert "AI 整理建议" in resp.text or "整理建议" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_patch_detail_page_loads(self, api_client, tmp_path):
        """GET /patches/{id} returns 200"""
        vault = tmp_path / "vault"
        patches_dir = vault / "00_Inbox" / "LLM_Patches"
        patches_dir.mkdir(parents=True)

        p = patches_dir / "topic_Test_001.md"
        p.write_text("""---
type: llm_wiki_patch
target_type: topic
target: "Test Topic"
target_card: "02_Topics/Test Topic.md"
status: pending_review
auto_apply: false
generated_at: "2026-05-30T15:00:00Z"
provider: openai_compatible
model: test
source_reports: []
---
# Patch Proposal: Test Topic
## Review Checklist
- [ ] reviewed
""", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/patches/topic_Test_001")
            assert resp.status_code == 200
            assert "Test Topic" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_patch_detail_not_found(self, api_client, tmp_path):
        """GET /patches/nonexistent returns 404"""
        vault = tmp_path / "vault"
        (vault / "00_Inbox" / "LLM_Patches").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/patches/nonexistent")
            assert resp.status_code == 404
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old


# ── P2-J.1 Research Brief Tests ──────────────────────────────────

class TestResearchBrief:
    def test_brief_page_loads(self, api_client, tmp_path):
        """GET /briefs/latest returns 200"""
        vault = tmp_path / "vault"
        for d in ["01_Reports", "02_Topics", "03_Companies", "06_Claims", "07_Signals"]:
            (vault / d).mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/briefs/latest")
            assert resp.status_code == 200
            assert "研究简报" in resp.text or "研究摘要" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_brief_ranks_active_topics(self):
        """Active topic ranking uses weighted scoring"""
        from podcast_research.workspace.research_brief import generate_brief
        from podcast_research.workspace.scanner import WorkspaceSnapshot, TopicInfo, ClaimInfo
        from pathlib import Path

        snapshot = WorkspaceSnapshot(vault_path=Path("/tmp"))
        snapshot.topics = [
            TopicInfo(name="AI Agents", path=Path("."), status="core"),
            TopicInfo(name="Semiconductor", path=Path("."), status="core"),
        ]
        snapshot.claims = [
            ClaimInfo(card_id="c1", path=Path("."), claim="test",
                       related_topics=["AI Agents"], source_reports=["r1"]),
            ClaimInfo(card_id="c2", path=Path("."), claim="test",
                       related_topics=["AI Agents"], source_reports=["r1"]),
            ClaimInfo(card_id="c3", path=Path("."), claim="test",
                       related_topics=["AI Agents"], source_reports=["r1"]),
        ]

        brief = generate_brief(snapshot)
        assert len(brief.active_topics) >= 1
        # AI Agents should rank first with 3 claims
        assert brief.active_topics[0].name == "AI Agents"
        assert brief.active_topics[0].claims == 3

    def test_brief_no_llm_called(self):
        """Research brief uses pure rules, no LLM import"""
        from podcast_research.workspace.research_brief import generate_brief
        from podcast_research.workspace.scanner import WorkspaceSnapshot
        from pathlib import Path

        snapshot = WorkspaceSnapshot(vault_path=Path("/tmp"))
        brief = generate_brief(snapshot)
        assert brief is not None
        assert brief.total_reports == 0


# ── P2-J.2 Watchlist Tests ───────────────────────────────────────

class TestWatchlist:
    def test_watchlist_page_loads(self, api_client, tmp_path):
        """GET /watchlist returns 200"""
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)
        (vault / "06_Claims").mkdir(parents=True)
        (vault / "07_Signals").mkdir(parents=True)
        (vault / "02_Topics").mkdir(parents=True)
        (vault / "03_Companies").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/watchlist")
            assert resp.status_code == 200
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_watchlist_config_load(self, tmp_path):
        """Watchlist config can be loaded from YAML file"""
        from podcast_research.workspace.watchlist import load_watchlist

        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)
        (vault / "99_System" / "Watchlist.yaml").write_text("""
companies:
  - OpenAI
  - NVIDIA
topics:
  - AI Agents
""", encoding="utf-8")

        config = load_watchlist(vault)
        assert "OpenAI" in config.companies
        assert "NVIDIA" in config.companies
        assert "AI Agents" in config.topics

    def test_watchlist_template_created(self, tmp_path):
        """Template is created when config missing"""
        from podcast_research.workspace.watchlist import ensure_watchlist_template

        vault = tmp_path / "vault"
        path = ensure_watchlist_template(vault)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "OpenAI" in content

    def test_watchlist_direct_update(self, tmp_path):
        """Company with direct claim is marked as direct"""
        from podcast_research.workspace.watchlist import generate_watchlist_brief
        from podcast_research.workspace.scanner import WorkspaceSnapshot, ClaimInfo

        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)
        (vault / "99_System" / "Watchlist.yaml").write_text("companies:\n  - OpenAI\n", encoding="utf-8")

        snapshot = WorkspaceSnapshot(vault_path=vault)
        snapshot.claims = [
            ClaimInfo(card_id="c1", path=vault, claim="Test claim about OpenAI",
                       related_companies=["OpenAI"], source_reports=["r1"]),
        ]
        snapshot.companies = []

        items = generate_watchlist_brief(snapshot, vault)
        assert len(items) == 1
        assert items[0].name == "OpenAI"
        assert items[0].status == "direct"

    def test_watchlist_no_evidence(self, tmp_path):
        """Item with no claims/signals returns no_new_evidence"""
        from podcast_research.workspace.watchlist import generate_watchlist_brief
        from podcast_research.workspace.scanner import WorkspaceSnapshot

        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)
        (vault / "99_System" / "Watchlist.yaml").write_text("companies:\n  - NVIDIA\n", encoding="utf-8")

        snapshot = WorkspaceSnapshot(vault_path=vault)
        snapshot.companies = []

        items = generate_watchlist_brief(snapshot, vault)
        assert items[0].status == "no_new_evidence"

    def test_dashboard_shows_watchlist(self, api_client, tmp_path):
        """Dashboard shows watchlist section when configured"""
        vault = tmp_path / "vault"
        for d in ["01_Reports", "02_Topics", "03_Companies", "06_Claims",
                   "07_Signals", "99_System"]:
            (vault / d).mkdir(parents=True)

        (vault / "99_System" / "Watchlist.yaml").write_text(
            "companies:\n  - OpenAI\ntopics:\n  - AI Agents\n", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/dashboard")
            assert resp.status_code == 200
            assert "我的关注" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old


# ── P2-J.3 Watchlist Settings Tests ──────────────────────────────

class TestWatchlistSettings:
    def test_settings_page_loads(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/watchlist/settings")
            assert resp.status_code == 200
            assert "关注设置" in resp.text or "company" in resp.text.lower()
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_add_company(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/watchlist/settings/add",
                                   data={"item_type": "company", "name": "OpenAI"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
            assert "success" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_add_topic(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/watchlist/settings/add",
                                   data={"item_type": "topic", "name": "AI Agents"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_duplicate_rejected(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            api_client.post("/watchlist/settings/add",
                           data={"item_type": "company", "name": "OpenAI"})
            resp = api_client.post("/watchlist/settings/add",
                                   data={"item_type": "company", "name": "OpenAI"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
            # Duplicate should return error msg (URL-encoded Chinese in location)
            assert "msg=error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_remove_company(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)
        (vault / "99_System" / "Watchlist.yaml").write_text(
            "companies:\n  - OpenAI\n", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/watchlist/settings/remove",
                                   data={"item_type": "company", "name": "OpenAI"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_empty_name_rejected(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/watchlist/settings/add",
                                   data={"item_type": "company", "name": "  "},
                                   follow_redirects=False)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_invalid_type_rejected(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/watchlist/settings/add",
                                   data={"item_type": "bogus", "name": "X"},
                                   follow_redirects=False)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_dashboard_has_settings_link(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        for d in ["01_Reports", "02_Topics", "03_Companies", "06_Claims",
                   "07_Signals", "99_System"]:
            (vault / d).mkdir(parents=True)
        (vault / "99_System" / "Watchlist.yaml").write_text(
            "companies:\n  - OpenAI\n", encoding="utf-8")

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/dashboard")
            assert "/watchlist/settings" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old


# ── P2-J.4 Entity Resolution Tests ───────────────────────────────

class TestEntityResolution:
    def test_exact_match_linked(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("NVIDIA", "company", {"NVIDIA", "OpenAI"}, set())
        assert r["match_status"] == "linked"
        assert r["canonical_name"] == "NVIDIA"

    def test_alias_match_chinese(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("英伟达", "company", {"NVIDIA", "OpenAI"}, set())
        assert r["match_status"] == "alias"
        assert r["canonical_name"] == "NVIDIA"

    def test_fuzzy_match_spaceless(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("Core Weave", "company", {"CoreWeave", "NVIDIA"}, set())
        assert r["match_status"] in ("fuzzy", "alias")  # alias map also catches this
        assert r["canonical_name"] == "CoreWeave"

    def test_topic_alias(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("AI Agent", "topic", set(), {"AI Agents", "Enterprise AI"})
        assert r["match_status"] in ("alias", "fuzzy")

    def test_theme_with_related_topics(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("Agent 工具链", "theme", set(), {"AI Agents", "Developer Tools"})
        assert r["match_status"] == "custom"
        assert "AI Agents" in r["related_topics"]

    def test_unknown_company_missing(self):
        from podcast_research.workspace.watchlist import resolve_watchlist_name
        r = resolve_watchlist_name("FakeCo", "company", {"NVIDIA"}, set())
        assert r["match_status"] == "missing"

    def test_normalize_spaceless(self):
        from podcast_research.workspace.watchlist import _normalize
        assert _normalize("Core Weave") == _normalize("CoreWeave")
        assert _normalize("AI-Agent") == _normalize("AI Agent")


# ── P2-K.1 Add New Content Tests ─────────────────────────────────

class TestContentNew:
    def test_content_new_page_loads(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/content/new")
            assert resp.status_code == 200
            assert "YouTube" in resp.text or "添加新内容" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_dashboard_has_add_content_link(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        for d in ["01_Reports", "02_Topics", "99_System"]:
            (vault / d).mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/dashboard")
            assert "/content/new" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_analyze_empty_url_rejected(self, api_client, tmp_path):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/content/analyze",
                                   data={"youtube_url": "  ", "focus": "", "depth": "standard"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_analyze_invalid_url_rejected(self, api_client, tmp_path, monkeypatch):
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        # Mock is_youtube_url to return False (invalid)
        monkeypatch.setattr(
            "podcast_research.utils.youtube.is_youtube_url", lambda u: False
        )

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/content/analyze",
                                   data={"youtube_url": "not-a-url", "focus": "", "depth": "standard"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
            assert "error" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_analyze_redirects_to_job(self, api_client, tmp_path, monkeypatch):
        """POST /content/analyze now redirects to job progress page."""
        monkeypatch.setattr(
            "podcast_research.utils.youtube.is_youtube_url", lambda u: True
        )

        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.post("/content/analyze",
                                   data={"youtube_url": "https://youtube.com/watch?v=test",
                                         "focus": "AI Agents", "depth": "standard"},
                                   follow_redirects=False)
            assert resp.status_code in (303, 302)
            assert "/content/jobs/" in resp.headers.get("location", "")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_job_page_loads(self, api_client, tmp_path):
        """GET /content/jobs/{id} — job page for valid id or not_found"""
        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            resp = api_client.get("/content/jobs/nonexistent123")
            assert resp.status_code == 200
            assert "不存在" in resp.text or "not_found" in resp.text
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

    def test_job_status_api(self, api_client, tmp_path, monkeypatch):
        """GET /content/jobs/{id}/status returns JSON"""
        from podcast_research.services.job_service import create_job
        monkeypatch.setattr(
            "podcast_research.utils.youtube.is_youtube_url", lambda u: True
        )

        vault = tmp_path / "vault"
        (vault / "99_System").mkdir(parents=True)

        old = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
        try:
            # Create a job and check its status
            resp = api_client.post("/content/analyze",
                                   data={"youtube_url": "https://youtube.com/watch?v=test",
                                         "focus": "AI Agents", "depth": "standard"},
                                   follow_redirects=False)
            location = resp.headers.get("location", "")
            job_id = location.rstrip("/").split("/")[-1]

            status_resp = api_client.get(f"/content/jobs/{job_id}/status")
            assert status_resp.status_code == 200
            data = status_resp.json()
            assert "status" in data
            assert data["status"] in ("queued", "running", "success", "failed")
        finally:
            os.environ["OBSIDIAN_VAULT_PATH"] = old

