# 投资播客研究助手 / Podcast Investment Research Assistant

将公开播客字幕中的投资观点、标的、风险提示、待验证信号和关键原文引用结构化沉淀。

> **本项目不提供投资建议。** 所有输出仅为播客内容的结构化整理，不构成买入、卖出、持有等决策建议。

## 当前阶段：P0 CLI 单集分析验证器

跑通最短闭环：本地字幕文件 → 解析 → 清洗 → LLM/规则引擎抽取 → Markdown 报告 → SQLite 入库 → CLI 输出。

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# mock 模式分析（P0 默认）
python -m podcast_research --subtitle-file data/subtitles/sample.srt

# 查看报告
cat data/reports/sample_report.md

# 运行测试
python -m pytest tests/ -v
```

## 真实 LLM 使用（后续阶段）

```bash
# 1. 配置 .env（从 .env.example 复制并填入）
cp .env.example .env
# 编辑 .env，设置 LLM_PROVIDER=openai-compatible 和 LLM_API_KEY

# 2. 使用真实 LLM
python -m podcast_research --subtitle-file your_subtitle.srt --no-mock
```

> P0 阶段仅使用规则引擎 mock provider，不调用真实 LLM API。

## 项目结构

```text
src/podcast_research/
  cli.py                 # Typer CLI 命令
  config.py              # .env 加载 + 全局配置
  logging_config.py      # 日志：console + RotatingFileHandler
  analysis/
    models.py            # Pydantic v2 数据模型（两阶段抽取 schema）
    pipeline.py          # 主分析流水线
  subtitles/
    parser.py            # SRT/TXT 解析器
    cleaner.py           # 清洗：去空行、合并短段、去重、标记广告
  llm/
    base.py              # LLMProvider 抽象基类
    mock_provider.py     # 规则引擎 mock（基于关键词匹配）
    openai_compatible_provider.py  # 真实 LLM 预留骨架
    prompts.py           # prompt 模板
  db/
    models.py            # SQLAlchemy ORM（5 张核心表）
    session.py           # SQLite session 管理
    repository.py        # 数据写入方法
  utils/
    hash.py              # 文件哈希（字幕重复检测）
    timestamp.py         # 时间戳格式化
tests/                    # pytest 测试
data/
  subtitles/             # 字幕文件存放
  reports/               # 报告输出
  podcast_analyst.db     # SQLite 数据库（运行时生成）
logs/                     # 日志
```

## 核心原则

1. 不输出买卖建议
2. 不把 AI 归纳伪装成嘉宾原话
3. 核心观点必须绑定原文引用和时间戳
4. 不确定信息必须显式标注
5. 所有外部依赖通过 adapter 隔离

## P0 不做的内容

- 小宇宙链接解析、xyz-dl 字幕下载
- 真实 LLM API 调用（仅 mock）
- FastAPI 后端、前端 UI
- Whisper 转写、多平台 RSS
- 向量数据库、PDF/Word 导出
- 团队协作、云端同步

## 路线图

| 阶段 | 目标 | 状态 |
|------|------|------|
| P0 | CLI 单集分析闭环（本地字幕 + mock LLM） | **进行中** |
| P1 | 本地报告查看页（FastAPI + HTML） | 待启动 |
| P2 | 小宇宙链接导入 + 真实 LLM | 待启动 |
| P3 | 历史报告全局查询（FTS5 + LLM 问答） | 待启动 |
| P4 | 多期观点对比 | 待启动 |

## 许可证

Private / 个人使用