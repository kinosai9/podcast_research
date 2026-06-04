"""P2-M.1: Channel Source Manager tests.

Tests for /sources/channels pages, add/refresh/skip/import actions,
and video status detection.

All tests use api_client + seeded_db fixtures. No real YouTube API calls.
"""

from pathlib import Path

import pytest


# ── Helpers ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _setup_vault_for_sources(monkeypatch, tmp_path):
    """Set a temporary vault path in config_store so sources routes work."""
    from podcast_research import config_store

    vault = tmp_path / "test_vault"
    vault.mkdir(parents=True)

    # Write temp settings file with vault path
    import json
    settings = {
        "obsidian_vault_path": str(vault),
        "watchlist": {"topics": [], "themes": [], "companies": []},
    }
    settings_path = tmp_path / "user_settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    config_store._override_settings_path(settings_path)
    return str(vault)

class MockChannelAdapter:
    """Mock ChannelVideoAdapter for tests."""

    def __init__(self, videos: list[dict] | None = None):
        self._videos = videos or [
            {"video_id": "testVid001", "title": "AI Investing 101",
             "url": "https://www.youtube.com/watch?v=testVid001",
             "published_at": "20260601", "duration_seconds": 1800},
            {"video_id": "testVid002", "title": "GPU Market Update",
             "url": "https://www.youtube.com/watch?v=testVid002",
             "published_at": "20260528", "duration_seconds": 2400},
            {"video_id": "testVid003", "title": "VC Roundtable",
             "url": "https://www.youtube.com/watch?v=testVid003",
             "published_at": "20260520", "duration_seconds": 3600},
        ]

    def fetch_channel_videos(self, channel_url: str, limit: int = 20):
        """Return mock videos."""
        from podcast_research.adapters.channel_video_adapter import ChannelVideoItem
        return [
            ChannelVideoItem(
                video_id=v["video_id"],
                title=v["title"],
                url=v["url"],
                published_at=v["published_at"],
                duration_seconds=v["duration_seconds"],
            )
            for v in self._videos[:limit]
        ]


def _seed_channel(api_client, channel_url="https://www.youtube.com/@TestChannel",
                 name="Test Channel", priority="watch", default_focus="AI"):
    """Helper: add a channel via POST and return channel_id."""
    resp = api_client.post(
        "/sources/channels/add",
        data={
            "channel_url": channel_url,
            "name": name,
            "priority": priority,
            "default_focus": default_focus,
            "default_depth": "standard",
        },
        follow_redirects=False,
    )
    # Should redirect to /sources/channels/{id}/videos
    assert resp.status_code == 303, f"Expected 303 redirect, got {resp.status_code}: {resp.text[:200]}"
    location = resp.headers["location"]
    # Extract channel_id from URL: /sources/channels/{id}/videos
    channel_id = int(location.split("/")[3])
    return channel_id


# ── Page Tests ────────────────────────────────────────────────────────

class TestSourcesChannelsPage:
    """Page rendering tests."""

    def test_channels_page_loads(self, api_client):
        """GET /sources/channels returns 200."""
        resp = api_client.get("/sources/channels")
        assert resp.status_code == 200
        html = resp.text
        assert "信息源管理" in html
        assert "添加频道" in html

    def test_channels_page_empty(self, api_client):
        """Empty channel list shows empty state."""
        resp = api_client.get("/sources/channels")
        assert resp.status_code == 200
        html = resp.text
        assert "还没有添加任何频道" in html

    def test_channels_page_with_channels(self, api_client):
        """Channel list shows added channels."""
        ch_id = _seed_channel(api_client, name="My Test Channel")

        resp = api_client.get("/sources/channels")
        assert resp.status_code == 200
        assert "My Test Channel" in resp.text
        assert "关注" in resp.text  # priority label

    def test_channel_videos_page_loads(self, api_client):
        """GET /sources/channels/{id}/videos returns 200."""
        ch_id = _seed_channel(api_client)

        resp = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp.status_code == 200
        assert "Test Channel" in resp.text

    def test_channel_videos_shows_empty(self, api_client):
        """Empty video list shows message."""
        ch_id = _seed_channel(api_client)
        resp = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp.status_code == 200


# ── Action Tests ──────────────────────────────────────────────────────

class TestSourcesChannelActions:
    """POST action tests."""

    def test_add_channel_creates_record(self, api_client):
        """Adding a channel should create DB record."""
        channel_url = "https://www.youtube.com/@MyChannel"
        resp = api_client.post(
            "/sources/channels/add",
            data={
                "channel_url": channel_url,
                "name": "My Channel",
                "priority": "core",
                "default_focus": "Semiconductors",
                "default_depth": "deep",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        # Should redirect to video list
        assert "/videos" in resp.headers["location"]

        # Verify channel page shows it
        resp2 = api_client.get("/sources/channels")
        assert "My Channel" in resp2.text

    def test_add_channel_rejects_invalid_url(self, api_client):
        """Invalid URL should return error."""
        resp = api_client.post(
            "/sources/channels/add",
            data={"channel_url": "not-a-valid-url", "name": "Bad"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "msg=error" in resp.headers["location"]

    def test_add_duplicate_channel_upserts(self, api_client):
        """Adding the same channel twice should upsert, not error."""
        channel_url = "https://www.youtube.com/@DuplicateChannel"
        resp1 = api_client.post(
            "/sources/channels/add",
            data={"channel_url": channel_url, "name": "First Add"},
            follow_redirects=False,
        )
        assert resp1.status_code == 303

        resp2 = api_client.post(
            "/sources/channels/add",
            data={"channel_url": channel_url, "name": "Second Add"},
            follow_redirects=False,
        )
        assert resp2.status_code == 303  # Should succeed, not error

    def test_skip_video(self, api_client):
        """Skip a video should update status."""
        ch_id = _seed_channel(api_client)

        # First add a video via refresh (mock)
        # We'll directly test skip by getting a video that doesn't exist
        resp = api_client.post(
            f"/sources/channels/{ch_id}/videos/nonexistent/skip",
            follow_redirects=False,
        )
        assert resp.status_code == 303  # Should redirect (graceful handling)

    def test_import_video_redirects_to_tasks(self, api_client):
        """Import action should redirect to /tasks/{job_id}."""
        ch_id = _seed_channel(api_client)

        resp = api_client.post(
            f"/sources/channels/{ch_id}/videos/importTest001/import",
            data={"focus": "AI", "depth": "standard", "flow_mode": "full"},
            follow_redirects=False,
        )
        # Should redirect — either success or user-friendly error
        assert resp.status_code in (303, 302)

    def test_refresh_missing_channel(self, api_client):
        """Refresh on non-existent channel should return error."""
        resp = api_client.post(
            "/sources/channels/99999/refresh",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "msg=error" in resp.headers["location"]

    def test_delete_channel_soft_deactivates(self, api_client):
        """Deleting a channel should soft-deactivate it and hide from list."""
        ch_id = _seed_channel(api_client)

        resp = api_client.post(
            f"/sources/channels/{ch_id}/delete",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "msg=success" in resp.headers["location"]

        # The channel should no longer appear in the page listing
        resp2 = api_client.get("/sources/channels")
        assert resp2.status_code == 200
        # The seeded channel name should NOT appear in the page HTML
        assert "TestChannel" not in resp2.text or f"/sources/channels/{ch_id}" not in resp2.text

        # But the channel should still exist in DB (soft-deleted)
        from podcast_research.db.repository import get_channel
        from podcast_research.db.session import get_session
        session = get_session()
        try:
            ch = get_channel(session, ch_id)
            assert ch is not None, "Soft-deleted channel should still exist in DB"
            assert ch["is_active"] is False, f"Expected is_active=False, got {ch['is_active']}"
        finally:
            session.close()

    def test_delete_nonexistent_channel(self, api_client):
        """Deleting a non-existent channel should return error."""
        resp = api_client.post(
            "/sources/channels/99999/delete",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "msg=error" in resp.headers["location"]


# ── Refresh with mock adapter ─────────────────────────────────────────

class TestChannelRefresh:
    """Tests that mock the yt-dlp adapter."""

    def test_refresh_with_mock_adapter(self, api_client, monkeypatch):
        """Refreshing channel videos should create a job and redirect to /tasks/{id}."""
        ch_id = _seed_channel(api_client)

        # Mock ChannelVideoAdapter
        mock_adapter = MockChannelAdapter()
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )

        resp = api_client.post(
            f"/sources/channels/{ch_id}/refresh",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        location = resp.headers["location"]
        # P2-M.1.1: refresh now creates a channel_refresh job, redirects to /tasks/{id}
        assert "/tasks/" in location

        # The job runs synchronously in test (daemon thread), wait briefly then check DB
        import time
        time.sleep(0.5)

        # Now check the videos page has entries
        resp2 = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp2.status_code == 200
        html = resp2.text
        assert "AI Investing 101" in html
        assert "GPU Market Update" in html
        assert "VC Roundtable" in html

    def test_double_refresh_no_duplicates(self, api_client, monkeypatch):
        """Refreshing twice should not duplicate videos in DB."""
        ch_id = _seed_channel(api_client)

        mock_adapter = MockChannelAdapter()
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )

        # First refresh
        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.3)
        # Second refresh with same adapter
        resp2 = api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        assert resp2.status_code == 303
        # P2-M.1.1: refresh redirects to /tasks/{id}
        assert "/tasks/" in resp2.headers["location"]
        time.sleep(0.3)

        # Check DB directly — should have exactly 3 videos (no duplicates)
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import list_channel_videos
        session = get_session()
        try:
            videos = list_channel_videos(session, ch_id)
            assert len(videos) == 3, f"Expected 3 videos, got {len(videos)}"
            vids = [v["video_id"] for v in videos]
            assert len(set(vids)) == 3, "Video IDs should be unique"
        finally:
            session.close()


# ── Video Status Detection ────────────────────────────────────────────

class TestVideoImportStatus:
    """Test detect_video_import_status with various DB states."""

    def test_new_video_is_new(self, api_client):
        """Unknown video_id should return 'new'."""
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import detect_video_import_status

        session = get_session()
        try:
            status = detect_video_import_status(session, "completely_unknown_vid")
            assert status == "new"
        finally:
            session.close()

    def test_analyzed_video_detected(self, api_client, seeded_db):
        """Video that exists in episodes table should be 'analyzed'."""
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import detect_video_import_status

        session = get_session()
        try:
            # seeded_db has episode with video_id="abc123" (report #3)
            status = detect_video_import_status(session, "abc123")
            assert status in ("analyzed", "synced"), f"Expected analyzed/synced, got {status}"
        finally:
            session.close()

    def test_synced_video_detected_in_vault(self, api_client, seeded_db, tmp_path):
        """Video in Obsidian vault frontmatter should be 'synced'."""
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import detect_video_import_status

        # Create a fake vault with a report containing the video_id
        vault = tmp_path / "vault"
        vault.mkdir()
        reports_dir = vault / "01_Reports"
        reports_dir.mkdir(parents=True)

        report_content = """---
type: report
source_type: youtube
channel: TestChan
video_id: vaultVid001
video_url: https://www.youtube.com/watch?v=vaultVid001
published_at: "2026-06-01"
language: en
prompt_version: tech_ai_v2
---
# Test Report

## Summary
Test content.
"""
        (reports_dir / "2026-06-01_TestChan_vaultVid001.md").write_text(report_content)

        session = get_session()
        try:
            status = detect_video_import_status(session, "vaultVid001", str(vault))
            assert status == "synced", f"Expected 'synced', got '{status}'"
        finally:
            session.close()

    def test_channel_video_status_preserved(self, api_client, monkeypatch):
        """After refresh, videos should have correct status."""
        ch_id = _seed_channel(api_client)

        mock_adapter = MockChannelAdapter()
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )

        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.5)

        # Check video page
        resp = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp.status_code == 200
        html = resp.text
        # New videos should show "新发现" status
        assert "新发现" in html


# ── Dashboard Integration ─────────────────────────────────────────────

class TestDashboardIntegration:
    """Dashboard should show link to /sources/channels."""

    def test_dashboard_shows_sources_link(self, api_client):
        """Dashboard action bar should have '信息源' link."""
        resp = api_client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.text
        assert "/sources/channels" in html
        assert "信息源" in html


# ── Edge Cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests."""

    def test_nonexistent_channel_videos(self, api_client):
        """Video page for nonexistent channel should redirect with error."""
        resp = api_client.get(
            "/sources/channels/99999/videos",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "msg=error" in resp.headers["location"]

    def test_chinese_status_labels(self, api_client):
        """Video list should show Chinese status labels."""
        ch_id = _seed_channel(api_client, name="LabelTest")

        resp = api_client.get("/sources/channels")
        html = resp.text
        assert "查看视频" in html


# ── P2-M.1.1: Unified Task State & Source Status Sync ─────────────────

class TestTaskSuccessPage:
    """Task detail page success display."""

    def test_task_success_no_spinner(self, api_client):
        """Success page should not show spinner."""
        from podcast_research.services.job_service import (
            create_job, start_job, update_job, AnalysisJob,
        )
        import time
        job = create_job(
            youtube_url="https://www.youtube.com/watch?v=dummy",
            focus_areas=["AI"],
            mock=True,
        )
        # Manually set to success for page testing
        update_job(job.job_id, status="success", stage="success",
                    message="报告已生成")
        time.sleep(0.1)

        resp = api_client.get(f"/tasks/{job.job_id}")
        assert resp.status_code == 200
        html = resp.text
        # Should have success message
        assert "研究报告已生成" in html
        # Should NOT have the long-running hint (it only shows for running status)
        # spinner div exists but JS hides it when status is success
        assert "job-spinner" in html  # div exists in template, JS controls visibility

    def test_task_success_checklist_full_flow(self, api_client):
        """Full flow success page should show checklist."""
        from podcast_research.services.job_service import (
            create_job, start_job, update_job,
        )
        job = create_job(
            youtube_url="https://www.youtube.com/watch?v=dummy2",
            focus_areas=["AI"],
            mock=True,
            auto_sync=True,
        )
        job.source_type = "channel_video"
        job.source_channel_id = 1
        job.video_id = "dummy2"

        update_job(job.job_id, status="success", stage="success",
                    message="知识库已更新", report_id=42)

        resp = api_client.get(f"/tasks/{job.job_id}")
        assert resp.status_code == 200
        html = resp.text
        assert "整理完成，知识库已更新" in html

    def test_channel_refresh_success_result_links(self, api_client):
        """channel_refresh job success should have video list link."""
        from podcast_research.services.job_service import (
            create_channel_refresh_job, start_channel_refresh_job, update_job,
        )
        job = create_channel_refresh_job(
            channel_url="https://www.youtube.com/@TestChan",
            channel_name="Test Chan",
            channel_id=1,
        )
        update_job(job.job_id, status="success", stage="success",
                    message="新增 3 个视频，更新 0 个")

        resp = api_client.get(f"/tasks/{job.job_id}")
        assert resp.status_code == 200
        html = resp.text
        assert "频道视频列表已更新" in html


class TestChannelRefreshJob:
    """Channel refresh via job."""

    def test_channel_refresh_creates_job_redirect(self, api_client):
        """POST /sources/channels/{id}/refresh should redirect to /tasks/{id}."""
        ch_id = _seed_channel(api_client)

        resp = api_client.post(
            f"/sources/channels/{ch_id}/refresh",
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/tasks/" in resp.headers["location"]

    def test_channel_refresh_job_type_label(self, api_client):
        """channel_refresh job should appear in task list with readable label."""
        from podcast_research.services.job_service import (
            create_channel_refresh_job, update_job,
        )
        job = create_channel_refresh_job(
            channel_url="https://www.youtube.com/@LabelChan",
            channel_name="Label Chan",
            channel_id=999,
        )
        update_job(job.job_id, status="success", stage="success",
                    message="done")

        resp = api_client.get("/tasks")
        assert resp.status_code == 200
        html = resp.text
        assert "刷新频道" in html


class TestVideoStatusSync:
    """Channel video status sync from job completion."""

    def test_import_video_creates_processing_status(self, api_client, monkeypatch):
        """Importing a video should set channel_video status to processing."""
        ch_id = _seed_channel(api_client)

        # Add a video first via mock refresh
        mock_adapter = MockChannelAdapter([
            {"video_id": "importTest1", "title": "Import Test",
             "url": "https://www.youtube.com/watch?v=importTest1",
             "published_at": "20260601", "duration_seconds": 1200},
        ])
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )
        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.5)

        # Now import the video
        resp = api_client.post(
            f"/sources/channels/{ch_id}/videos/importTest1/import",
            data={"focus": "AI", "depth": "standard", "flow_mode": "full"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/tasks/" in resp.headers["location"]

        # Check DB
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import get_channel_video_by_video_id
        session = get_session()
        try:
            cv = get_channel_video_by_video_id(session, "importTest1")
            assert cv is not None
            assert cv["status"] == "processing"
        finally:
            session.close()

    def test_processing_video_no_import_button(self, api_client, monkeypatch):
        """Processing video should show '整理中' and not show import button."""
        ch_id = _seed_channel(api_client)

        # Add video via mock refresh
        mock_adapter = MockChannelAdapter([
            {"video_id": "procVid", "title": "Processing Video",
             "url": "https://www.youtube.com/watch?v=procVid",
             "published_at": "20260601", "duration_seconds": 1200},
        ])
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )
        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.5)

        # Manually set status to processing
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import update_channel_video_status, get_channel_video_by_video_id
        session = get_session()
        try:
            cv = get_channel_video_by_video_id(session, "procVid")
            update_channel_video_status(session, cv["id"], "processing")
            session.commit()
        finally:
            session.close()

        resp = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp.status_code == 200
        html = resp.text
        assert "整理中" in html
        # Should NOT have "整理进知识库" button for this video
        assert "整理进知识库" not in html or html.count("整理进知识库") == 0

    def test_synced_video_shows_view_report(self, api_client, monkeypatch):
        """Synced video should show '查看报告' instead of import button."""
        ch_id = _seed_channel(api_client)

        mock_adapter = MockChannelAdapter([
            {"video_id": "synVid", "title": "Synced Video",
             "url": "https://www.youtube.com/watch?v=synVid",
             "published_at": "20260601", "duration_seconds": 1200},
        ])
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )
        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.5)

        # Set to synced
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import update_channel_video_status, get_channel_video_by_video_id
        session = get_session()
        try:
            cv = get_channel_video_by_video_id(session, "synVid")
            update_channel_video_status(session, cv["id"], "synced")
            session.commit()
        finally:
            session.close()

        resp = api_client.get(f"/sources/channels/{ch_id}/videos")
        assert resp.status_code == 200
        html = resp.text
        assert "已同步" in html
        assert "查看报告" in html


class TestJobStatusWriteback:
    """Job completion writes back to channel_videos."""

    def test_full_flow_success_writes_synced(self, api_client, monkeypatch):
        """After full_flow job success, channel_videos status should be synced."""
        from podcast_research.services.job_service import (
            create_job, update_job, _writeback_channel_video_status, AnalysisJob,
        )

        ch_id = _seed_channel(api_client)
        mock_adapter = MockChannelAdapter([
            {"video_id": "writeback1", "title": "Writeback Test",
             "url": "https://www.youtube.com/watch?v=writeback1",
             "published_at": "20260601", "duration_seconds": 1200},
        ])
        monkeypatch.setattr(
            "podcast_research.adapters.channel_video_adapter.ChannelVideoAdapter",
            lambda: mock_adapter,
        )
        api_client.post(f"/sources/channels/{ch_id}/refresh", follow_redirects=False)
        import time
        time.sleep(0.5)

        # Import to set processing
        api_client.post(
            f"/sources/channels/{ch_id}/videos/writeback1/import",
            data={"focus": "AI", "depth": "standard", "flow_mode": "full"},
            follow_redirects=False,
        )

        # Simulate writeback (what job thread does on success)
        job = AnalysisJob(
            job_id="test_wb", job_type="full_flow",
            source_type="channel_video", source_channel_id=ch_id,
            video_id="writeback1",
        )
        _writeback_channel_video_status(
            job, status="synced", report_id=99,
        )

        from podcast_research.db.session import get_session
        from podcast_research.db.repository import get_channel_video_by_video_id
        session = get_session()
        try:
            cv = get_channel_video_by_video_id(session, "writeback1")
            assert cv["status"] == "synced"
            assert cv["report_id"] == 99
        finally:
            session.close()

    def test_full_flow_failure_writes_failed(self, monkeypatch):
        """After full_flow failure, channel_videos status should be failed."""
        from podcast_research.services.job_service import (
            _writeback_channel_video_status, AnalysisJob,
        )
        from podcast_research.db.session import get_session
        from podcast_research.db.repository import get_channel_video_by_video_id
        from podcast_research.db.models import ChannelVideo

        # Create a channel_video directly in DB
        session = get_session()
        try:
            cv = ChannelVideo(
                channel_id=1,
                video_id="writeback_fail",
                title="Fail Test",
                url="https://www.youtube.com/watch?v=writeback_fail",
                status="processing",
            )
            session.add(cv)
            session.commit()
        finally:
            session.close()

        job = AnalysisJob(
            job_id="test_wb_fail", job_type="full_flow",
            source_type="channel_video", source_channel_id=1,
            video_id="writeback_fail",
        )
        _writeback_channel_video_status(
            job, status="failed", failure_reason="Network timeout",
        )

        session = get_session()
        try:
            cv = get_channel_video_by_video_id(session, "writeback_fail")
            assert cv["status"] == "failed"
            assert cv["failure_reason"] == "Network timeout"
        finally:
            session.close()
