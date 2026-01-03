<div align="center">

# BIP - Build-in-Public Automation System

**[English](#english)** | **[中文](#中文)**

</div>

---

<a name="english"></a>

An AI-powered automation system for Build-in-Public content creation. Monitor your projects, generate social media posts from your actual work, and publish automatically.

### Video Tutorial

[![BIP Tutorial](https://img.youtube.com/vi/Zbn9Vd5FF9c/maxresdefault.jpg)](https://youtu.be/Zbn9Vd5FF9c)

> Click the image above to watch the tutorial on YouTube

## Features

- **Multi-Project Management** - Monitor multiple Git repositories simultaneously
- **AI Content Generation** - Generate posts from your actual commits and work using Claude, GPT-4, or Gemini
- **Automated Scheduling** - Schedule and publish posts to Twitter/X
- **Morning Meetings** - Daily AI-powered standup reports across all projects
- **Calendar Generation** - Extract tasks from launch plans into ICS calendar files
- **Voice Processing** - Convert voice memos and ideas into posts
- **24/7 Operation** - Run continuously on a cloud server (optional)

## Environment Compatibility

| Environment | Native Support | Via Docker | How to Run |
|-------------|----------------|------------|------------|
| **WSL/Linux** | Yes | Yes | `./bip <command>` |
| **macOS** | Yes | Yes | `./bip <command>` |
| **Windows PowerShell** | Partial | Yes | `python -m src.cli <command>` |
| **Windows CMD** | Partial | Yes | `python -m src.cli <command>` |

> **Note:** The `./bip` script is bash-based. On Windows without WSL, use `python -m src.cli` or Docker.

## Docker Quick Start

For easy deployment with Docker:

```bash
# Clone and configure
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily
cp .env.example .env
cp config/projects.yaml.example config/projects.yaml

# Edit .env with your API keys
# Set project paths to /projects/your-project-name

# Set your projects directory
export PROJECTS_DIR=~/my-projects

# Build and run
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
docker compose run --rm bip generate
```

See [Docker Deployment Guide](docs/DOCKER.md) for full documentation.


## Installation without Docker

### Prerequisites

- Python 3.12+
- Node.js 18+ (for Twitter API integration)
- At least one AI API key (Anthropic, OpenAI, or Google Gemini)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright for browser automation
playwright install chromium

# Set up MCP server for Twitter
cd mcp-servers/social-media-mcp
npm install
npm run build
cd ../..
```

### Configuration

BIP uses a 3-tier configuration system:

| Tier | File | Purpose |
|------|------|---------|
| **1** | `.env` | Secrets, API keys, project paths (required) |
| **2** | `src/config.py` | Sensible defaults (no changes needed) |
| **3** | `config/bip_settings.yaml` | Advanced customization (optional) |

```bash
# Copy example config
cp .env.example .env

# Edit .env with your API keys and project paths
# Most users only need to configure .env
```

For advanced customization (AI models, posting schedules, brand colors), edit `config/bip_settings.yaml`.

### Initialize

```bash
./bip init
```

### Daily Usage

```bash
# Run the full daily automation
./bip daily-auto

# Or run individual commands:
./bip collect          # Collect data from projects
./bip generate         # Generate posts
./bip meeting          # Run morning meeting
./bip calendar         # Generate calendar
./bip schedule         # View/manage scheduled posts
```


## Commands

| Command | Description |
|---------|-------------|
| `./bip init` | Initialize database and directories |
| `./bip collect` | Collect commits and data from monitored projects |
| `./bip generate` | Generate AI posts from collected data |
| `./bip select` | Select and save a post as markdown |
| `./bip publish <id>` | Publish a post to Xiaohongshu |
| `./bip publish-twitter <id>` | Publish a post to Twitter/X |
| `./bip schedule` | View scheduled posts |
| `./bip meeting` | Run morning meeting report |
| `./bip calendar` | Generate ICS calendar from launch plans |
| `./bip history` | View post history |
| `./bip daily-auto` | Full daily automation workflow |

## Project Structure

```
bip-daily/
├── src/                    # Python source code
│   ├── cli.py              # CLI commands
│   ├── config.py           # Configuration management
│   ├── models.py           # Database models
│   ├── collectors/         # Data collectors
│   ├── generators/         # Content generators
│   ├── managers/           # Meeting manager
│   ├── publishers/         # Social media publishers
│   └── schedulers/         # Post scheduling
├── mcp-servers/            # MCP server for Twitter API
│   └── social-media-mcp/
├── config/                 # Configuration files
├── data/                   # Runtime data (gitignored)
├── docs/                   # Documentation
├── templates/              # Jinja2 templates
└── tests/                  # Test files
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Required |
|----------|-------------|----------|
| `AI_PROVIDER` | AI provider: `anthropic`, `openai`, or `gemini` | Yes |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | If using Claude |
| `OPENAI_API_KEY` | OpenAI API key | If using GPT |
| `GEMINI_API_KEY` | Google Gemini API key | If using Gemini |
| `TWITTER_USERNAME` | Twitter username (for Playwright) | For Twitter |
| `TWITTER_PASSWORD` | Twitter password (for Playwright) | For Twitter |
| `PROJECT_N_NAME` | Name of project N | Yes |
| `PROJECT_N_PATH` | Path to project N | Yes |
| `PROJECT_N_TYPE` | Type of project N | Yes |
| `CALENDAR_UPLOAD_GIST` | Upload calendar to GitHub Gist | No (default: true) |
| `GITHUB_GIST_TOKEN` | GitHub token with gist scope | For Gist upload |
| `CALENDAR_UPLOAD_GITHUB` | Push calendar to git repo | No (default: false) |
| `CALENDAR_UPLOAD_SFTP` | Upload calendar via SFTP | No (default: false) |

### Project Configuration (config/projects.yaml)

```yaml
projects:
  - name: my-project
    path: ../my-project
    type: saas
    description: "My SaaS product"
    public: true
    keywords:
      - SaaS
      - automation
```

## Calendar Subscription

BIP generates `.ics` calendar files from your project tasks. Subscribe from any calendar app (Google Calendar, Apple Calendar, Outlook):

### Option 1: GitHub Gist (Recommended)

The easiest method - works for anyone, no repository needed:

1. Create a Personal Access Token at: GitHub → Settings → Developer settings → Personal access tokens
2. Select scope: 'gist' only (minimal permissions)
3. Add to `.env`:
   ```bash
   CALENDAR_UPLOAD_GIST=true
   GITHUB_GIST_TOKEN=ghp_your_token_here
   GITHUB_GIST_ID=just-leave-it-blank-will-be-auto-generated
   ```
4. Run `./bip calendar`
5. Subscribe to the URL shown (auto-updates on each run)

### Option 2: GitHub Repository

If you fork/own a repository with push access:

1. Set `CALENDAR_UPLOAD_GITHUB=true` in `.env`
2. Calendar is committed and pushed automatically
3. Subscribe URL: `https://raw.githubusercontent.com/USER/REPO/main/data/bip-daily-calendar.ics`

### Option 3: SFTP Server

For self-hosted solutions:

1. Set `CALENDAR_UPLOAD_SFTP=true` in `.env`
2. Create `ftpinfo.json` with your server credentials
3. Calendar uploads to your server automatically

See [Quick Start Guide](docs/QUICKSTART.md#calendar-setup-en) for detailed setup instructions.

## Server Deployment

For 24/7 operation, deploy to a cloud server. See [Server Deployment Guide](docs/SERVER_DEPLOYMENT_GUIDE.md).

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting a PR.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [Claude Code](https://claude.ai/claude-code)
- Uses [Model Context Protocol](https://modelcontextprotocol.io/) for social media integration

---

<div align="center">

**[Back to Top](#bip---build-in-public-automation-system)** | **[Switch to 中文](#中文)**

</div>

---

<a name="中文"></a>

# 中文

# BIP - Build-in-Public 自动化系统

一个基于 AI 的 Build-in-Public 内容创作自动化系统。监控你的项目，从实际工作中生成社交媒体帖子，并自动发布。

### 视频教程

[![BIP 教程](https://img.youtube.com/vi/Zbn9Vd5FF9c/maxresdefault.jpg)](https://youtu.be/Zbn9Vd5FF9c)

> 点击上方图片在 YouTube 观看教程

## 功能特性

- **多项目管理** - 同时监控多个 Git 仓库
- **AI 内容生成** - 使用 Claude、GPT-4 或 Gemini 从你的实际提交和工作中生成帖子
- **自动排期发布** - 定时发布帖子到 Twitter/X
- **早间会议** - 每日 AI 驱动的跨项目站会报告
- **日历生成** - 从启动计划中提取任务到 ICS 日历文件
- **语音处理** - 将语音备忘录和想法转换为帖子
- **24/7 运行** - 可选部署到云服务器持续运行

## 环境兼容性

| 环境 | 原生支持 | Docker 支持 | 运行方式 |
|------|----------|-------------|----------|
| **WSL/Linux** | 是 | 是 | `./bip <命令>` |
| **macOS** | 是 | 是 | `./bip <命令>` |
| **Windows PowerShell** | 部分 | 是 | `python -m src.cli <命令>` |
| **Windows CMD** | 部分 | 是 | `python -m src.cli <命令>` |

> **注意：** `./bip` 脚本基于 bash。在没有 WSL 的 Windows 上，请使用 `python -m src.cli` 或 Docker。

## Docker 快速开始

使用 Docker 轻松部署：

```bash
# 克隆和配置
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily
cp .env.example .env
cp config/projects.yaml.example config/projects.yaml

# 编辑 .env 填入你的 API 密钥
# 将项目路径设置为 /projects/你的项目名称

# 设置项目目录
export PROJECTS_DIR=~/my-projects

# 构建和运行
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
docker compose run --rm bip generate
```

详见 [Docker 部署指南](docs/DOCKER.md) 获取完整文档。


## 不使用 Docker 安装

### 前置要求

- Python 3.12+
- Node.js 18+（用于 Twitter API 集成）
- 至少一个 AI API 密钥（Anthropic、OpenAI 或 Google Gemini）

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 用于浏览器自动化
playwright install chromium

# 设置 MCP 服务器用于 Twitter
cd mcp-servers/social-media-mcp
npm install
npm run build
cd ../..
```

### 配置

BIP 使用 3 层配置系统：

| 层级 | 文件 | 用途 |
|------|------|------|
| **1** | `.env` | 密钥、API keys、项目路径（必需） |
| **2** | `src/config.py` | 合理的默认值（无需修改） |
| **3** | `config/bip_settings.yaml` | 高级自定义（可选） |

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 填入你的 API 密钥和项目路径
# 大多数用户只需要配置 .env
```

高级自定义（AI 模型、发布时间表、品牌颜色）请编辑 `config/bip_settings.yaml`。

### 初始化

```bash
./bip init
```

### 日常使用

```bash
# 运行完整的每日自动化
./bip daily-auto

# 或者运行单独的命令：
./bip collect          # 从项目收集数据
./bip generate         # 生成帖子
./bip meeting          # 运行早间会议
./bip calendar         # 生成日历
./bip schedule         # 查看/管理已排期的帖子
```


## 命令列表

| 命令 | 描述 |
|------|------|
| `./bip init` | 初始化数据库和目录 |
| `./bip collect` | 从监控的项目收集提交和数据 |
| `./bip generate` | 从收集的数据生成 AI 帖子 |
| `./bip select` | 选择并保存帖子为 markdown |
| `./bip publish <id>` | 发布帖子到小红书 |
| `./bip publish-twitter <id>` | 发布帖子到 Twitter/X |
| `./bip schedule` | 查看已排期的帖子 |
| `./bip meeting` | 运行早间会议报告 |
| `./bip calendar` | 从启动计划生成 ICS 日历 |
| `./bip history` | 查看帖子历史 |
| `./bip daily-auto` | 完整的每日自动化工作流 |

## 项目结构

```
bip-daily/
├── src/                    # Python 源代码
│   ├── cli.py              # CLI 命令
│   ├── config.py           # 配置管理
│   ├── models.py           # 数据库模型
│   ├── collectors/         # 数据收集器
│   ├── generators/         # 内容生成器
│   ├── managers/           # 会议管理器
│   ├── publishers/         # 社交媒体发布器
│   └── schedulers/         # 帖子排期
├── mcp-servers/            # Twitter API 的 MCP 服务器
│   └── social-media-mcp/
├── config/                 # 配置文件
├── data/                   # 运行时数据（已忽略）
├── docs/                   # 文档
├── templates/              # Jinja2 模板
└── tests/                  # 测试文件
```

## 配置说明

### 环境变量 (.env)

| 变量 | 描述 | 必需 |
|------|------|------|
| `AI_PROVIDER` | AI 提供商：`anthropic`、`openai` 或 `gemini` | 是 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API 密钥 | 使用 Claude 时 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 使用 GPT 时 |
| `GEMINI_API_KEY` | Google Gemini API 密钥 | 使用 Gemini 时 |
| `TWITTER_USERNAME` | Twitter 用户名（用于 Playwright） | 发布到 Twitter 时 |
| `TWITTER_PASSWORD` | Twitter 密码（用于 Playwright） | 发布到 Twitter 时 |
| `PROJECT_N_NAME` | 项目 N 的名称 | 是 |
| `PROJECT_N_PATH` | 项目 N 的路径 | 是 |
| `PROJECT_N_TYPE` | 项目 N 的类型 | 是 |
| `CALENDAR_UPLOAD_GIST` | 上传日历到 GitHub Gist | 否（默认：true） |
| `GITHUB_GIST_TOKEN` | 带 gist 权限的 GitHub token | Gist 上传时 |
| `CALENDAR_UPLOAD_GITHUB` | 推送日历到 git 仓库 | 否（默认：false） |
| `CALENDAR_UPLOAD_SFTP` | 通过 SFTP 上传日历 | 否（默认：false） |

### 项目配置 (config/projects.yaml)

```yaml
projects:
  - name: my-project
    path: ../my-project
    type: saas
    description: "我的 SaaS 产品"
    public: true
    keywords:
      - SaaS
      - 自动化
```

## 日历订阅

BIP 从你的项目任务生成 `.ics` 日历文件。可从任何日历应用订阅（Google Calendar、Apple Calendar、Outlook）：

### 方案一：GitHub Gist（推荐）

最简单的方法 - 任何用户都可使用，无需创建仓库：
1. Create a Personal Access Token at: GitHub → Settings → Developer settings → Personal access tokens
2. Select scope: 'gist' only (minimal permissions)

1. 创建仅带 `gist` 权限的 GitHub Personal Access Token (GitHub → Settings → Developer settings → Personal access tokens)
2. 权限仅选择 `Gist` 的读写
3. 添加到 `.env`：
   ```bash
   CALENDAR_UPLOAD_GIST=true
   GITHUB_GIST_TOKEN=ghp_你的token
   ```
4. 运行 `./bip calendar`
5. 订阅显示的 URL（每次运行自动更新）

### 方案二：GitHub 仓库

如果你 fork 或拥有有推送权限的仓库：

1. 在 `.env` 中设置 `CALENDAR_UPLOAD_GITHUB=true`
2. 日历会自动提交并推送
3. 订阅链接：`https://raw.githubusercontent.com/用户名/仓库名/main/data/bip-daily-calendar.ics`

### 方案三：SFTP 服务器

自托管方案：

1. 在 `.env` 中设置 `CALENDAR_UPLOAD_SFTP=true`
2. 创建包含服务器凭据的 `ftpinfo.json`
3. 日历会自动上传到你的服务器

详细设置说明请参阅 [快速入门指南](docs/QUICKSTART.md#calendar-setup-zh)。

## 服务器部署

如需 24/7 运行，请部署到云服务器。参阅 [服务器部署指南](docs/SERVER_DEPLOYMENT_GUIDE.md)。

## 贡献

欢迎贡献！请在提交 PR 前阅读贡献指南。

1. Fork 仓库
2. 创建功能分支
3. 进行修改
4. 提交 Pull Request

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

## 致谢

- 使用 [Claude Code](https://claude.ai/claude-code) 构建
- 使用 [Model Context Protocol](https://modelcontextprotocol.io/) 进行社交媒体集成

---

<div align="center">

**[回到顶部](#bip---build-in-public-automation-system)** | **[Switch to English](#english)**

</div>
