# Source Ingestion（信息源摄入）

## 目标

Sources 模块提供统一的「外部信息 → 知识库」摄入管道。不负责分析、不负责生成报告，只负责：
1. 识别来源类型
2. 预览可导入内容
3. 检测冲突
4. 推荐操作
5. 用户确认后写入

## 四类入口

| 入口 | 路径 | 用途 |
|------|------|------|
| YouTube 频道 | `/sources/channels` | 长期跟踪 YouTube 频道，自动发现新视频并分析导入 |
| 网页导入 | `/sources/import` | 粘贴任意网页 URL，解析内容后由用户决定导入方式 |
| 固定信息源 | `/sources/tracked` | 跟踪固定外部网页源（如 All-In Podcast ZH 笔记），定期发现新条目 |
| 文件上传 | `/sources/files/import` | 上传 .md / .txt / .html / .htm 文本文件，提取内容后归档 |

统一入口：`GET /sources`

## 统一处理原则

所有入口遵循同一管道：

```
识别来源 → 生成预览 → 冲突检测 → 推荐操作 → 用户确认入库
```

### 1. 识别来源（Profile）
- 判断来源类型（YouTube、网页、固定源、文件）
- 评估可追踪性
- 不做任何写入

### 2. 生成预览（Preview）
- 解析内容，提取标题、摘要、元数据
- 计算 content_hash
- 判断解析质量（good / degraded / minimal）
- 存储到内存预览存储（`_preview_store` / `_file_preview_store`）
- 不做任何 vault 写入

### 3. 冲突检测（Conflict Detection）
- 按 content_hash 检测完全重复（severity: blocker）
- 按 title 检测标题重复（severity: warning）
- 按 canonical_url 检测 URL 重复（severity: warning）
- 检测已有 Deep Notes 或 Report 关联（severity: info）

### 4. 推荐操作（Recommendation）
- 根据来源类型、冲突、解析质量推荐最佳操作
- 提供备选操作列表
- 用户可选择与推荐不同的操作

### 5. 用户确认入库（Confirm）
- 用户确认后才执行写入
- 写入操作一步完成（不再拆分步骤）
- 文件归档到 SourceArchive 后记录 frontmatter 元数据

## 单网页 URL 导入

`GET /sources/import` → 粘贴 URL → `POST /sources/import/preview` → 查看预览 → `POST /sources/import/confirm`

- 支持的类型：YouTube 视频页、All-In ZH 笔记页、通用网页
- 检测 YouTube 视频 ID → 建议创建 Deep Notes
- 已有 Report 的 YouTube 视频 → 建议关联 Deep Notes
- 已有 Deep Notes 的 YouTube 视频 → 建议覆盖或跳过
- 通用网页 → 建议归档为 SourceArchive

## 固定外部源跟踪

`GET /sources/tracked` → 添加源 → `POST /sources/tracked/profile` → 查看 profiling 结果 → 创建跟踪源 → 刷新 → 导入条目

- 当前仅支持 All-In Podcast ZH 笔记（`allin_zh_notes` adapter）
- 刷新时自动发现新条目，生成预览
- 条目状态：new → preview_ready → imported | skipped | failed
- 重新发现已有条目时标记为 existing（已发现），不重复生成预览
- 不支持跟踪的 URL → 建议改用单网页导入

## Source Profiling

Profiling 是创建固定跟踪源前的预检步骤：
- 基于规则判断（非 LLM），确定性强、可测试
- 分析 URL 页面类型（SourceKind）
- 判断跟踪可行性（TrackingEligibility）
- 推荐操作（SuggestedAction）
- 不做任何 vault/DB 写入，不做 Report/Deep Notes/SourceArchive

## 文本文件上传导入

`GET /sources/files/import` → 选择文件 → `POST /sources/files/preview` → 查看预览 → `POST /sources/files/confirm`

- 支持类型：.md, .txt, .html, .htm
- 文件大小限制：5 MB
- 解析质量评估：good / degraded / minimal
- 默认归档到 SourceArchive
- 内容哈希去重：完全相同的内容自动建议跳过

## SourceArchive / DeepNotes / Report 边界

| 产物 | 触发条件 | 写入位置 |
|------|----------|----------|
| SourceArchive | 通用网页导入、文件上传 | `01_Reports/SourceArchive/*.md` |
| Deep Notes | YouTube 视频导入（有/无关联 Report） | `02_DeepNotes/<episode_slug>.md` |
| Report（投资报告） | 仅通过 YouTube 频道分析流水线生成 | `01_Reports/<yymmdd>_<title>_report.md` |

- **SourceArchive** 是普通资料默认归档位置。不涉及观点抽取。
- **Deep Notes** 仅用于有明确 episode / external notes 场景。
- **Report** 不因网页导入或文件上传触发。

## 统一状态文案

详见 `podcast_research.sources.models.SOURCE_STATUS_LABELS`：

| 内部状态 | 用户文案 |
|----------|----------|
| pending | 待处理 |
| preview_ready | 待确认 |
| new | 新发现 |
| existing | 已发现 |
| imported | 已入库 |
| skipped | 已跳过 |
| failed | 失败 |
| active | 正常 |
| degraded | 解析退化 |
| unsupported | 暂不支持 |
| needs_review | 需人工确认 |

## 统一操作文案

详见 `podcast_research.sources.models.ACTION_LABELS`：

| 操作 | 按钮文案 |
|------|----------|
| preview | 生成预览 |
| confirm_archive | 确认归档 |
| import_as_source_archive | 归档为资料 |
| import_as_deep_notes_linked | 导入为关联精读笔记 |
| import_as_deep_notes_derived_only | 导入为独立精读笔记 |
| skip | 跳过 |
| overwrite_deep_notes | 覆盖精读笔记 |
| refresh | 更新 |
| batch_import | 导入选中项 |
| back | 返回修改 |

## 当前不支持

- PDF 文本层提取
- OCR 图片文字识别
- Office 文档（.docx, .xlsx 等）
- Embedding / 向量检索
- 自动 Claim/Signal 抽取
- 自动生成 Report
- 持久化 import queue
- 定时自动抓取
- RSS feed adapter

## 后续扩展建议

- PDF text layer 提取（PyMuPDF）
- RSS/Atom adapter
- 持久化导入队列（替换内存 `_preview_store`）
- OCR 图片文字（Tesseract local）
- 适配器插件注册机制
