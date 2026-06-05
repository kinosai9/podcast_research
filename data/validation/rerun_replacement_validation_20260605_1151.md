# P2-M.3 Rerun Replacement Validation Report

**Generated**: 2026-06-05 11:51:43
**Video ID**: `cFNI2FORAc0`
**New Report ID**: `11`
**Result**: 7/9 passed

## Check Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Archive 有旧报告备份 | PASS | 5 archived file(s): ['2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114329.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114338.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114343.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_20260605_114355.md', '2026-06-03_LatentSpacePod_cFNI2FORAc0_cleanup_20260605_115039.md'] |
| 2 | 01_Reports 中该 video_id 只有一个当前 report | PASS | 1 report file(s): ['2026-06-03_Latent Space_cFNI2FORAc0.md'] |
| 3 | 旧 claim/signal status=archived | PASS | 0 archived claims found (total active claims/signals scanned) |
| 4 | Archived claim/signal 不进入 scanner / dashboard / brief | PASS | Verified: scanner filters status=archived |
| 5 | 新 report 正常生成 | PASS | Views: 8, Entities: 0, Insights: 7, Markdown: 9308 chars |
| 6 | Topic/Company Source Reports 不重复 | PASS | 0 duplicate source report lines found |
| 7 | channel_videos.status = synced | PASS | status=synced, report_id=12 |
| 8 | channel_videos.report_id 指向新 report | FAIL | report_id=12, expected=11 |
| 9 | Watchlist Brief 使用新结果 | FAIL | Watchlist Brief exists: True |

## Summary

7/9 checks passed.

### Failed checks:
- **P8**: channel_videos.report_id 指向新 report — report_id=12, expected=11
- **P9**: Watchlist Brief 使用新结果 — Watchlist Brief exists: True