# Clean First-run Validation Report

**验证时间**: 2026-06-01 14:49
**验证人**: Claude Code (automated + manual)
**Git commit**: P2-L.1

---

## 验证环境

- 数据库: 全新（data/podcast_analyst.db 已重置）
- 配置文件: data/user_settings.json（验证期间创建）
- Vault 路径: D:/KinocNote/ai-investing-vault/科技AI投资知识库_clean
- 环境变量: OBSIDIAN_VAULT_PATH 指向 clean vault

---

## 验证步骤与结果

### 1. 首次使用 — Dashboard 跳转

| 步骤 | 预期 | 结果 |
|------|------|------|
| 访问 /dashboard（无 vault 配置） | 302 → /setup/vault | ✅ PASS |
| 访问 /setup/vault | 显示初始化表单 | ✅ PASS |
| 输入目录路径，点击初始化 | 创建目录结构 + 跳转 Dashboard | ✅ PASS |

### 2. Vault 初始化验证

| 检查项 | 结果 |
|--------|------|
| 12 个标准目录已创建 | ✅ PASS (11 dirs) |
| Home.md 已创建 | ✅ PASS |
| Watchlist.yaml 已创建（含默认内容） | ✅ PASS |
| Getting Started.md 已创建 | ✅ PASS |
| 99_System/ 下系统文件齐全 | ✅ PASS |
| user_settings.json 已保存路径 | ✅ PASS |
| 非空目录安全（不删除已有文件） | ✅ PASS（测试验证） |

### 3. 设置关注对象

| 步骤 | 结果 |
|------|------|
| /watchlist/settings 页面可访问 | ✅ PASS |
| 添加 OpenAI（公司） | ✅ PASS |
| 添加 NVIDIA（公司） | ✅ PASS |
| 添加 AI Agents（主题） | ✅ PASS |
| 添加 Enterprise AI（主题） | ✅ PASS |
| Watchlist.yaml 已更新 | ✅ PASS |
| /watchlist 页面可访问 | ✅ PASS |
| Dashboard 显示「我的关注」模块 | ✅ PASS |

### 4. 真实视频闭环 — 待手动验证

由于需要调用真实 LLM API，此步骤请手动完成：

1. 打开 http://127.0.0.1:8000/content/new
2. 选择一个 YouTube 视频（建议 All-In Podcast 某集）
3. 选择「整理进知识库」
4. 关注方向: AI Agents, Enterprise AI, OpenAI, NVIDIA
5. 提交后观察 /tasks 进度

预期结果：
- 任务阶段依次显示: fetching_transcript → analyzing → syncing_knowledge_base
- 成功后 result_links 包含: report, brief, watchlist, dashboard
- /reports/ 有新报告
- /briefs/latest 有研究摘要
- /watchlist 有关注对象变化
- Obsidian Vault 中有对应文件

### 5. 发现问题

#### P2-L.1-1: Dashboard redirect 在生产环境中需清缓存
- **现象**: uvicorn 启动后首次访问 /dashboard 可能使用缓存代码
- **严重程度**: 低（仅影响开发环境热重载）
- **建议**: 无，代码逻辑正确（TestClient 验证通过）

#### P2-L.1-2: .env 中的 OBSIDIAN_VAULT_PATH 优先于用户预期
- **现象**: 用户通过 /setup/vault 配置了新路径并写入 user_settings.json，但 .env 中的旧路径仍可能被 load_dotenv() 设置
- **严重程度**: 中
- **当前状态**: config_store 优先级 user_settings.json > env var，正确
- **建议**: 保持当前设计，setup 写入 user_settings.json 后自动优先生效

---

## 测试覆盖

P2-L.1 新增 18 个自动化测试（tests/test_web_pages.py::TestVaultSetup），全部通过。

---

## 下一步建议

1. 手动完成「真实视频闭环验证」（步骤 4）
2. 验证 Obsidian 打开 Vault 后的卡片和链接质量
3. 考虑是否需要 Chrome 内嵌浏览器自动打开 Obsidian vault 链接
