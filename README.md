# XHS Content Agent — 小红书 AI 内容助手

基于 FastAPI + LangChain + OpenAI 构建的小红书内容挖掘与自动生成系统。支持从爬取竞品数据、分析爆款规律、AI 生成文案与配图，到一键发布至小红书的完整闭环。

---

## 功能概览

| 模块 | 说明 |
|------|------|
| 数据采集 | 通过 Playwright 爬取小红书搜索结果，支持按关键词、评论数、点赞数、收藏数过滤，自动跳过视频与广告 |
| 数据分析 | 提取高频关键词、热门标签、标题规律与用户洞察，输出结构化分析报告 |
| 话题生成 | 基于分析结果，调用 LLM 生成若干高质量选题建议（含标题与理由） |
| 内容生成 | 针对每个选题生成多条完整文案：正文、标题、话题标签、互动引导语、图片建议、内容类型 |
| 图片生成 | 调用 OpenAI `gpt-image-1` 生成符合小红书风格的配图，保存至本地 |
| 内容发布 | 支持 MCP 协议（推荐）或 REST API 两种模式发布至小红书 |
| 飞书同步 | 将爬取数据与 AI 生成内容分别同步至飞书多维表格，便于团队协作与审核 |
| MCP Server | 将完整流水线封装为 MCP 工具，可在 Claude Desktop / Cursor 等 AI 工具中直接调用 |
| Web UI | 内置静态前端，提供爬取、生成、发布的图形化操作界面 |

---

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

复制 `.env` 文件并填写必要字段：

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=                  # 可选，代理地址

# 图片生成
IMAGE_MODEL=gpt-image-1

# 飞书多维表格（可选）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_TABLE_ID=                  # 爬虫数据表
FEISHU_PUBLISH_TABLE_ID=          # AI 生成笔记表

# 小红书 MCP 服务（本地）
XHS_MCP_URL=http://localhost:18060
XHS_MCP_ENDPOINT=http://localhost:18060/mcp
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000` 进入 Web UI。

FastAPI 交互文档：`http://127.0.0.1:8000/docs`

---

## 主要 API

| 路由 | 说明 |
|------|------|
| `POST /analysis/analyze` | 分析笔记列表，返回关键词、标签、标题规律、洞察点 |
| `POST /topics/generate` | 根据分析结果生成话题建议 |
| `POST /content/generate` | 根据选题生成图文文案 |
| `POST /agent/run` | 一键运行完整内容生成流水线（分析 → 话题 → 文案） |
| `POST /crawl/search` | 按关键词爬取小红书图文笔记 |
| `POST /publish/prepare` | 组装发布 Payload（REST / MCP 格式） |
| `POST /publish/send` | 发布至小红书 |
| `POST /feishu/sync` | 将生成内容同步至飞书 |
| `POST /feishu/sync-crawled` | 将爬取数据同步至飞书 |
| `GET  /health` | 健康检查 |

---

## MCP Server 使用

将本项目封装为 MCP Server，可在支持 MCP 协议的 AI 工具（Claude Desktop、Cursor 等）中注册使用。

```bash
python mcp_server.py
```

提供以下 MCP 工具：

| 工具 | 说明 |
|------|------|
| `run_content_pipeline` | 完整运行内容生成流水线 |
| `generate_xhs_images` | 根据文案生成配图 |
| `publish_to_xhs` | 生成配图并一键发布至小红书 |
| `check_xhs_login` | 检查小红书登录状态 |

---

## 项目结构

```
xhs_content_agent/
├── app/
│   ├── api/               # FastAPI 路由层
│   ├── core/              # 配置（Settings）
│   ├── models/            # Pydantic 数据模型
│   ├── prompts/           # LLM Prompt 模板
│   └── services/          # 业务逻辑层
│       ├── agent_service.py          # 主流水线编排
│       ├── analysis_service.py       # 笔记数据分析
│       ├── topic_service.py          # 话题生成
│       ├── content_service.py        # 文案生成
│       ├── image_service.py          # 图片生成
│       ├── publish_service.py        # 小红书发布
│       ├── feishu_service.py         # 飞书同步
│       ├── local_site_crawler_service.py  # 小红书爬虫
│       └── mcp_client_service.py     # MCP 客户端
├── static/                # Web 前端页面
├── data/
│   ├── raw/               # 爬取数据 / 样本数据
│   └── output/images/     # 生成的图片
├── mcp_server.py          # MCP Server 入口
├── requirements.txt
└── .env                   # 环境变量配置
```

---

## 技术栈

- **后端框架**：FastAPI + Uvicorn
- **LLM 调用**：LangChain + LangChain-OpenAI（GPT-4o-mini）
- **图片生成**：OpenAI gpt-image-1
- **爬虫**：Playwright（Chromium）
- **MCP 协议**：`mcp` SDK（FastMCP）
- **飞书 API**：飞书多维表格 Open API
- **中文处理**：jieba 分词
- **数据验证**：Pydantic v2

---

## 注意事项

- 爬取功能需要提前完成小红书登录并将 Cookies 保存至 `data/raw/xhs_cookies.json`。
- 发布功能依赖本地运行的小红书 MCP 服务（默认端口 `18060`），需完成扫码登录。
- 图片生成需要 OpenAI API Key 且该 Key 有 `gpt-image-1` 的访问权限。
- 飞书同步为可选功能，未配置时相关接口会返回提示信息而不会报错。