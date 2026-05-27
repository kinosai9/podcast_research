---

# CLAUDE.md

## 项目名称

投资播客研究助手 / Podcast Investment Research Assistant

## 项目定位

本项目是一个面向非 IT 用户的本地化播客研究工具，用于将公开播客字幕中的投资观点、标的、风险提示、待验证信号和关键原文引用结构化沉淀。

本项目不是投资建议工具，不提供买入、卖出、持有等决策建议。

## 当前阶段

当前阶段为 P0：单集分析 CLI 验证器。

优先目标是跑通：

本地字幕文件 → 字幕解析 → 字幕清洗 → LLM/mock 结构化抽取 → Markdown 报告 → SQLite 入库 → CLI 输出。

## 核心原则

1. 先跑通最短闭环，再做 UI。
2. 先支持本地字幕文件，再接入小宇宙链接和 xyz-dl。
3. 先使用 mock LLM，确保测试可稳定运行。
4. 所有核心投资观点必须绑定原文引用和时间戳。
5. 不允许输出投资建议。
6. 不允许将 AI 推断伪装成嘉宾原话。
7. 对不确定内容必须显式标注。
8. 所有外部依赖必须通过 adapter 隔离。
9. 面向非 IT 用户，错误提示要可理解。
10. 每次修改后必须说明改动内容、测试结果和下一步建议。

## 禁止在 P0 实现的内容

- Tauri 桌面封装
- Next.js 完整前端
- 小宇宙节目搜索
- 批量字幕探测
- Whisper 本地转写
- 多平台 RSS 支持
- 钉钉/微信推送
- PDF/Word 导出
- 团队协作
- 云端同步
- 向量数据库

## 技术栈

- Python 3.12+
- Typer
- Pydantic v2
- SQLAlchemy 2.x
- SQLite
- Jinja2
- httpx
- python-dotenv
- pytest
- rich
- logging

## 推荐目录结构

详见 README.md。

## LLM 输出约束

LLM 分析必须分两阶段：

1. 事实抽取 JSON
2. 报告 Markdown 生成

核心观点字段至少包括：

- target_name
- target_type
- view_direction
- logic_chain
- evidence_type
- evidence_strength
- risk_warning
- speaker_label
- speaker_confidence
- source_quote
- timestamp
- uncertainty

没有 source_quote 和 timestamp 的内容不得进入核心观点矩阵。

## 数据安全

1. API Key 不得写入代码。
2. `.env` 不得提交 Git。
3. 字幕和报告默认保存在本地 `data/`。
4. 日志不得打印完整 API Key。
5. 后续接入小宇宙认证信息时，必须通过配置文件或环境变量读取。

## 测试要求

每次新增核心功能必须补测试。

P0 最低测试覆盖：

- 字幕解析
- 字幕清洗
- mock LLM pipeline
- SQLite 写入
- Markdown 报告生成
- CLI mock 模式运行

## 每次任务完成后的汇报格式

请按以下格式汇报：

```markdown
## 本轮完成

- ...

## 修改文件

- ...

## 运行命令

```bash  
```

## 测试结果

- ...

## 风险与待确认

- ...

## 下一步建议

- ...
