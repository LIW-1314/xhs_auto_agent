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
### 3. 获取创作者中心专属通行证 (核心步骤)
由于小红书主站和创作者中心的缓存不互通，必须单独扫码获取创作者中心的登录态：

运行独立的登录脚本：python login_creator.py

在弹出的浏览器中，使用小红书 App 扫码登录。

等待创作者后台完全加载出来后，在终端按下回车键。

确保 data/raw/creator_state.json 文件已成功生成。

### 4. 启动服务(双服务运行)
由于采用了 MCP 架构，需要开启两个终端窗口分别运行服务：
#### 终端一：启动底层自动化发布服务 (MCP Server)
```bash
conda activate xhs_agent
python app/services/xhs_mcp_server.py
```

#### 终端二：启动 AI 业务主程序
```bash
conda activate xhs_agent
python run.py
```
全部启动后，访问主程序提供的本地网页端口，即可开始全自动生成与发布！

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

## 踩坑实录
### 问题： 配置了 API Key，但运行或发布时一直报 401 无效的令牌 或 Incorrect API key。
解决方法： 这通常是因为 .env 文件格式不规范（比如多写了引号或空格），或者 Windows 系统/VS Code 终端里悄悄缓存了旧的环境变量。你需要确保 .env 里是纯文本输入，然后在运行代码的终端里执行 $env:OPENAI_API_KEY="" (PowerShell) 或 set OPENAI_API_KEY= (CMD) 强制清空系统缓存，并彻底关闭、重启终端。
### 问题： AI 生成完成后，进入发布阶段时前端瞬间弹出 500 Internal Server Error，且终端没有详细红字报错。
解决方法： 这是由于 MCP 后台发布脚本执行完毕后，没有向主程序返回（Return）标准格式的数据，导致主程序解析时触发了 NoneType 崩溃。你必须确保 MCP 服务的最后，无论成功还是失败，都严格使用 return {"success": True/False, "message": "..."} 的字典格式进行对接回复。
### 问题： 启动自动发布时，浏览器没有进入“发布图文”页面，而是被强制跳回了登录页（URL 中带有 redirectReason=401
）。
解决方法： 这是因为小红书主站和创作者中心的本地存储是不互通的。直接拿主站扫码的凭证去进创作者中心会被拦截。你必须专门写一个脚本，直接在创作者中心扫码，生成专属的 creator_state.json 登录凭证，并在代码的 new_context 中专门加载它。
### 问题： 浏览器卡在网页上不动，终端报错 Timeout 30000ms exceeded，提示找不到“上传图文”按钮、输入框，或者传图片卡死。
解决方法： 现代前端框架有极强的防自动化机制。对于按钮切换，不要用普通的 click，必须用 evaluate("node => node.click()") 进行 JS 强行突破；对于传图片，弃用直接塞 input 的方式，改用 expect_file_chooser() 截获系统真实的物理弹窗；对于填写正文，放弃容易变动的 class 名称，直接定位 [contenteditable='true'] 属性，并使用 page.keyboard.type() 模拟真人键盘敲击来触发网页的字数保存机制。
### 问题： 运行过程中报错 Element is outside of the viewport。
解决方法： Playwright 默认的浏览器窗口比较小，导致右侧或下方的网页元素被挤出了屏幕外无法点击。需要在初始化 context 时，添加参数强制撑大浏览器视口，例如设置 viewport={'width': 1920, 'height': 1080}，确保所有 UI 元素都正常暴露在可见范围内。