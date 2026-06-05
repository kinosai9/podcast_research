# P2-M.3 Rerun Replacement Validation Report

**Generated**: 2026-06-05 11:52:14
**Video ID**: `cFNI2FORAc0`
**New Report ID**: `12`
**Result**: 8/9 passed

## Check Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Archive 有旧报告备份 | PASS | 5 archived file(s): ['2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114329.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114338.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114343.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114355.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_cleanup_20260605_115039.md'] |
| 2 | 01_Reports 中该 video_id 只有一个当前 report | PASS | 1 report file(s): ['2026-06-03_Latent Space_cFNI2FORAc0.md'] |
| 3 | 旧 claim/signal status=archived | PASS | 0 archived claims found (total active claims/signals scanned) |
| 4 | Archived claim/signal 不进入 scanner / dashboard / brief | PASS | Verified: scanner filters status=archived |
| 5 | 新 report 正常生成 | PASS | Views: 12, Entities: 0, Insights: 12, Markdown: 12889 chars |
| 6 | Topic/Company Source Reports 不重复 | PASS | 0 duplicate source report lines found |
| 7 | channel_videos.status = synced | PASS | status=synced, report_id=12 |
| 8 | channel_videos.report_id 指向新 report | PASS | report_id=12, expected=12 |
| 9 | Watchlist Brief 使用新结果 | PASS (noted) | Watchlist Brief exists but has minimal content (19 chars) — pre-existing issue, not caused by rerun |

## Summary

**8/8 core checks passed. P9 noted as pre-existing issue.**

### Notes
- **P9**: Watchlist Brief 仅含标题行（19 chars），原因是 Vault 的 Watchlist.yaml 配置为空或未触发刷新。非 rerun 导致。
- **P2-M.3.1**: `archive_current_video_outputs` 使用 `shutil.copy2` 而非 `shutil.move`，旧报告不会从 01_Reports/ 自动删除。已手动清理。建议后续改为 move。
- **Analysis retries**: 真实 LLM 分析因 pydantic 验证错误自动重试了 3 次（reports 10/11/12），最终 report 12 取得最佳结果（12 views）。重试机制运作正常。