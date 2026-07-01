# P3 Plan: 知识库后端化

> 状态：P3-A 已完成 | P3-B/C/D 计划中 | 2026-07-01
> 基于 P2-S.3.5 完成状态

## 定位

把 podcast_research 从"可运行的数据处理流水线"升级为"可恢复、可审计、可被 Agent 查询的投资知识库后端"。

P2 解决了"能处理什么"，P3 解决"运行时出问题怎么办"和"怎么让别人/别的程序来查询"。

## 主线任务

| 任务 | 简称 | 目标 |
|------|------|------|
| P3-A | 持久化摄入队列 | SQLite ingest_jobs 收编 `_preview_store`，支持重启恢复、状态追踪、失败重试、hash 去重 |
| P3-B | Vault Lint | 扫描 Obsidian vault，检查 frontmatter、死 wikilink、重复报告、孤立卡片、命名一致性 |
| P3-C | Review Queue | 将 Patch Review 泛化为通用 review_items，承接 lint issue、实体合并建议、重复报告等 |
| P3-D | MCP Server | Python mcp 包实现只读 MCP server，让 Claude Code/Codex 可查询报告、观点、信号、实体、频道、lint 结果 |
| P3-E | 文档与操作手册 | 固化 P3 范围、数据表、CLI、验收规则 |

## 分阶段计划

### P3-A：持久化摄入队列 ✅ 已完成（2026-07-01）

**实现摘要：**

- 新增 `IngestJob` SQLAlchemy 模型（22 列）— `db/models.py`
- 新增 `_migrate_ingest_jobs_table` — `db/session.py`
- 新增 `IngestJobManager`（14 个方法）— `sources/ingest_jobs.py`
- **Phase 1 双写模式**：所有摄入入口同时写入内存 `_preview_store` 和 SQLite `ingest_jobs`
- CLI `ingest list/show/retry/resume`
- 54 个专项测试 — `tests/test_ingest_jobs.py`

**当前架构约定（Phase 1）：**

| 层级 | 用途 | 持久化 |
|------|------|--------|
| `_preview_store` / `_file_preview_store` / `_profile_store` | 运行期缓存（优先读取） | 否（进程重启丢失） |
| `ingest_jobs` 表 | 可恢复状态源（后备读取 + 重启恢复） | 是（SQLite） |
| `_import_results_store` | 一次性显示结果 | 否（保持原有，有意义的短期数据） |

- Dashboard 统计：优先从内存 `_preview_store` 读取，为空时回退到 `ingest_jobs`（处理重启场景）
- 写入：所有摄入入口双写（内存 + DB），DB 写入失败不阻塞流程
- 去重：同一 `job_key` + `pending_preview` 状态受部分唯一索引保护

**后续阶段约束：**
- P3-B / P3-C 不应新增对 `_preview_store` / `_file_preview_store` / `_profile_store` 的依赖
- 新功能应直接使用 `IngestJobManager` 或从 `ingest_jobs` 表查询
- Phase 2（完全切换）可在所有 P3 阶段完成后进行

**验收标准：**
- [x] `ingest_jobs` 表创建，包含所有必要字段
- [x] URL 预览双写到 ingest_jobs（同时保留 `_preview_store`）
- [x] 文件上传预览双写到 ingest_jobs（同时保留 `_file_preview_store`）
- [x] Profile 双写到 ingest_jobs（同时保留 `_profile_store`）
- [x] Import results 结果写入 ingest_jobs；`_import_results_store` 保留为一次性显示
- [x] 服务重启后通过 `ingest_jobs` 恢复待确认项（`ingest resume`）  
- [x] source_hash / job_key 去重（部分唯一索引）
- [x] 过期预览自动清理（`expire_old_jobs`）
- [x] Dashboard 统计在内存为空时从 ingest_jobs 查询
- [x] 现有 Sources 模块测试全部通过
- [x] 新增 ingest_jobs 专项测试：54 tests
- [x] ruff clean

**结果：** 1439 tests（1438 passed, 1 pre-existing flaky），ruff clean。

### P3-B：Vault Lint（预计 2-3 天）

**当前问题：**
- Obsidian vault 日积月累会产生质量问题
- frontmatter 格式错误 → Obsidian 插件无法解析
- `[[wikilink]]` 指向不存在的文件 → 死链
- 同一内容的重复报告文件
- 孤立卡片（没有关联报告的 Topic/Company）
- 命名不一致（同一实体在不同卡片中名字不同）
- 缺少 frontmatter 必填字段

**目标状态：**
- `vault_lint` CLI 命令 + web 面板
- 7 类 lint rule，每类可独立开关
- Lint 结果写入 `lint_results` 表（可追溯）
- 可选的 auto-fix（死链删除、frontmatter 补全）

**设计文档：** `docs/VAULT_LINT_REVIEW_QUEUE_DESIGN.md`

**Lint Rules：**

| # | Rule | Severity | Auto-fix |
|---|------|----------|----------|
| 1 | frontmatter 格式错误 | error | 否（需人工） |
| 2 | 必填字段缺失 | warning | 补默认值 |
| 3 | 死 wikilink | warning | 删除链接 |
| 4 | 重复报告（同 content_hash） | warning | 标记 duplicate |
| 5 | 孤立卡片（无关联报告） | info | 标记 orphan |
| 6 | 命名不一致 | info | 建议统一 |
| 7 | 过期卡片（>90 天未更新） | info | 标记 stale |

**验收标准：**
- [ ] `vault_lint` CLI 命令可用
- [ ] 7 条 lint rule 全部实现
- [ ] `lint_results` 表持久化
- [ ] Web 面板显示 lint 结果
- [ ] Lint 结果可关联到 review_items（P3-C）
- [ ] 现有 Vault 相关测试不受影响
- [ ] Lint 专项测试（≥15 tests）
- [ ] ruff clean

### P3-C：Review Queue（预计 2-3 天）

**当前问题：**
- Patch Review 只覆盖 LLM-WIKI 卡片修改
- Claim/Signal backlog 是独立的系统
- Lint 发现问题后没有统一的处理入口
- 用户面对多种"待处理"事项，分散在多个页面

**目标状态：**
- 统一的 `review_items` 表
- 承接来源：lint issues、patch proposals、实体合并建议、重复报告、缺失卡片
- 统一的 review 状态机：pending → in_review → accepted / rejected / deferred
- 统一 Web 面板（`/reviews`）
- 每项可关联源文件、建议操作、优先级

**设计文档：** `docs/VAULT_LINT_REVIEW_QUEUE_DESIGN.md`

**Review Item 类型：**

| Type | 来源 | 自动生成 |
|------|------|----------|
| lint_issue | Vault Lint | ✓ |
| patch_proposal | LLM Patch Generator | ✓ |
| entity_merge | Card Cleanup | ✓ |
| duplicate_report | Conflict Detector | ✓ |
| missing_card | Workspace Scanner | ✓ |
| manual | 用户手动创建 | — |

**验收标准：**
- [ ] `review_items` 表创建
- [ ] 统一状态机实现
- [ ] Web 面板（`/reviews`）可用
- [ ] Lint issues 自动转入 review_items
- [ ] Patch proposals 关联 review_items
- [ ] Entity merge 建议自动生成
- [ ] 现有 Patch Review 测试继续通过
- [ ] Review 专项测试（≥15 tests）
- [ ] ruff clean

### P3-D：MCP Server（预计 2-3 天）

**当前问题：**
- Claude Code 等 AI Agent 无法直接查询 podcast_research 的知识库
- 用户需要手动打开 Web Console 或 CLI 查询
- 知识库的价值受限于交互方式

**目标状态：**
- `python -m podcast_research mcp-serve` 启动 MCP server
- 只读查询：报告、观点、信号、实体、频道、lint 结果
- 可在 Claude Code / Cursor / 其他 MCP 客户端中注册
- 不依赖桌面应用（stdio transport，纯 Python）

**设计文档：** `docs/MCP_SERVER_DESIGN.md`

**MCP Tools（Phase 1）：**

| Tool | 功能 |
|------|------|
| `search_reports` | 搜索报告（关键词 + status 过滤） |
| `get_report` | 获取报告详情（含 views/signals/markdown） |
| `list_entities` | 列出实体（按类型/名称过滤） |
| `get_channel` | 获取频道信息 |
| `search_claims` | 搜索观点（按 target/status 过滤） |
| `search_signals` | 搜索信号（按 target/status 过滤） |
| `get_lint_issues` | 获取 lint 结果 |
| `get_review_items` | 获取 review 队列 |
| `vault_status` | Vault 健康概览 |

**验收标准：**
- [ ] `python -m podcast_research mcp-serve` 可启动
- [ ] 9 个 tool 全部可用
- [ ] 只读验证（不能修改 vault/DB）
- [ ] Claude Desktop 集成测试
- [ ] MCP 专项测试（≥10 tests）
- [ ] ruff clean

### P3-E：文档与操作手册（持续）

**输出：**
- [x] `docs/P3_PLAN.md` — 本文件（P3-A 完成状态已更新）
- [x] `docs/INGEST_QUEUE_DESIGN.md` — P3-A 实现后已补充字段/状态机/CLI
- [x] `docs/VAULT_LINT_REVIEW_QUEUE_DESIGN.md` — 设计文档
- [x] `docs/MCP_SERVER_DESIGN.md` — 设计文档
- [x] `docs/PROJECT_RULES.md` — 工程规范（含 P3 规则）
- [x] `docs/LLM_WIKI_ANALYSIS.md` — 参考项目分析
- [x] `README.md` — 已更新 P3 方向
- [x] `CHANGELOG.md` — 已更新 P3-A 完成

## 不做什么（P3 明确排除）

- 不引入桌面 UI（React/Tauri/Electron）
- 不实现 Deep Research
- 不新增 LLM provider（保持 OpenAI-compatible）
- 不实现自动定时任务
- 不直接复制 nashsu/llm_wiki GPL v3 代码
- 不新增向量数据库（LanceDB 等）
- 不新增 Chrome 扩展
- 不新增 PDF/Office 解析能力

## 测试策略

每阶段独立测试，不依赖后续阶段：

```
P3-A 测试：
  - test_ingest_jobs_crud.py         — DB CRUD 操作
  - test_ingest_jobs_dedup.py        — source_hash 去重
  - test_ingest_jobs_expiry.py       — 过期清理
  - test_ingest_jobs_dashboard.py    — Dashboard 统计一致性
  - test_ingest_jobs_restart.py      — 重启恢复
  - 更新现有 Sources 测试（移除 _preview_store 引用）

P3-B 测试：
  - test_vault_lint_rules.py         — 每条 rule 的检测逻辑
  - test_vault_lint_cli.py           — CLI 命令
  - test_vault_lint_autofix.py       — Auto-fix 安全
  - test_vault_lint_web.py           — Web 面板

P3-C 测试：
  - test_review_items_crud.py        — CRUD + 状态机
  - test_review_from_lint.py         — Lint → Review 流转
  - test_review_from_patch.py        — Patch → Review 关联
  - test_review_web.py               — Web 面板

P3-D 测试：
  - test_mcp_server_startup.py       — 启动/配置
  - test_mcp_tools.py                — 每个 tool 的输入/输出
  - test_mcp_readonly.py             — 只读验证
  - test_mcp_integration.py          — 与真实 MCP client 交互
```

## 风险与边界

| 风险 | 缓解 |
|------|------|
| DB migration 影响现有数据 | P3-A 只新增表，不修改现有表结构；使用 `if not exists` |
| Vault Lint 误报 | 每条 rule 可独立开关；info 级别不阻塞；auto-fix 需 --apply |
| Review Queue 与现有 Patch Review 冲突 | 保留现有 patches/ 路径，review_items 作为上层的统一视图 |
| MCP Server 安全问题 | 只读；仅在 localhost 监听；不需要认证（本地信任模型） |
| 测试数量膨胀 | 复用现有 fixtures（seeded_db, tmp_path）；mock provider 模式 |

## 依赖关系

```
P3-A (持久化摄入队列)
  └─→ P3-B (Vault Lint) — lint 可检测重复报告（复用 content_hash）
        └─→ P3-C (Review Queue) — lint issues → review_items
  
P3-D (MCP Server) — 可独立开发，查询现有 API + P3-A/B/C 新增表

P3-E (文档) — 随各阶段持续更新
```

推荐执行顺序：**P3-A → P3-B → P3-C → P3-D**，P3-D 可在 P3-A 完成后并行启动。
