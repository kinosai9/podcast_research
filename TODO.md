# TODO.md

## P0：CLI 单集分析验证器

> P0 输入源仅限本地 .srt / .txt 字幕文件，不接入小宇宙链接、xyz-dl、真实 LLM API。
> 数据模型只建 5 张核心表：episodes, reports, investment_views, tracking_signals, entities。

### 0. 项目初始化

- [ ] 创建 pyproject.toml（依赖声明 + entry point）
- [ ] 创建 .env.example
- [ ] 创建 .gitignore
- [ ] 创建完整目录骨架 + __init__.py

### 1. 配置与日志

- [ ] 实现 config.py（.env 加载 + mock/real provider 切换）
- [ ] 实现 logging_config.py（console + RotatingFileHandler → logs/）

### 2. 数据模型

- [ ] 实现 Pydantic 数据模型（analysis/models.py：ExtractionResult, InvestmentView, TrackingSignal 等）
- [ ] 实现 SQLAlchemy ORM（db/models.py：episodes, reports, investment_views, tracking_signals, entities）
- [ ] 实现 db/session.py（engine, SessionLocal, init_db）
- [ ] 实现 db/repository.py（基础写入方法）
- [ ] 编写 test_db.py

### 3. 字幕解析与清洗

- [ ] 实现 SRT parser（subtitles/parser.py）
- [ ] 实现 TXT parser
- [ ] 实现 subtitles/cleaner.py（去空行、合并短段、去重、标记疑似广告）
- [ ] 创建 sample.srt 示例文件
- [ ] 编写 test_parser.py
- [ ] 编写 test_cleaner.py

### 4. LLM 抽象

- [ ] 定义 LLMProvider base class（llm/base.py）
- [ ] 实现 MockLLMProvider（llm/mock_provider.py）
- [ ] 设计事实抽取 prompt 模板（llm/prompts.py）
- [ ] 设计报告生成 prompt 模板

### 5. 分析 Pipeline

- [ ] 实现 analyze pipeline（analysis/pipeline.py）
- [ ] 串联：解析 → 清洗 → mock 抽取 → 渲染 → 入库
- [ ] 写出 report_json + report_markdown 到 data/reports/
- [ ] 编写 test_pipeline_mock.py

### 6. Markdown 报告渲染

- [ ] 实现 Jinja2 报告模板（含免责声明、观点矩阵、风险提示、引用）
- [ ] 编写 test_report.py

### 7. CLI

- [ ] 实现 `python -m podcast_research analyze <subtitle_file> --mock`
- [ ] 支持 --focus（关注点过滤）
- [ ] 支持 --output（输出目录）
- [ ] 支持 --verbose（详细日志）
- [ ] 使用 rich 输出进度
- [ ] mock 模式完整跑通
- [ ] 编写 test_cli.py

### 8. 工具函数

- [ ] 实现 utils/hash.py（文件哈希）
- [ ] 实现 utils/timestamp.py（时间戳格式化）

---

## P1：本地报告查看页

- [ ] FastAPI 项目初始化
- [ ] 报告列表 API
- [ ] 报告详情 API
- [ ] InvestmentView 查询 API
- [ ] 简单 HTML 页面

---

## P2：小宇宙链接 + 真实 LLM

- [ ] 小宇宙单集链接解析
- [ ] xyz-dl adapter
- [ ] 字幕下载
- [ ] 真实 LLM provider（OpenAI-compatible）
- [ ] 说话人推断逻辑
- [ ] 元数据获取（podcasts 表）

---

## P3：历史报告全局查询

- [ ] SQLite FTS5
- [ ] 结构化过滤
- [ ] LLM 总结回答
- [ ] 引用来源展示
- [ ] qa_logs 表

---

## P4：多期观点对比

- [ ] 多报告选择
- [ ] 同标的观点聚合
- [ ] 观点变化时间线
- [ ] 对比报告生成