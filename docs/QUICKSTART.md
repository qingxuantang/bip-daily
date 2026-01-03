# BIP Quick Start Guide / BIP 快速入门指南

**[English](#english) | [中文](#中文)**

---

<a id="english"></a>
## English

Get BIP running in 5 minutes.

### Prerequisites

- Docker 20.10+ and Docker Compose v2+ (recommended)
- One AI API key (Anthropic, OpenAI, or Gemini)

### Docker Quick Start (Recommended)

```bash
# Clone and configure
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# AI Provider (at least one required)
ANTHROPIC_API_KEY=your-key-here  # or GEMINI_API_KEY or OPENAI_API_KEY

# PROJECTS_DIR: parent directory containing your projects
# Windows: PROJECTS_DIR=D:/git_repo
# Linux:   PROJECTS_DIR=/home/user/projects
# WSL:     PROJECTS_DIR=/mnt/d/git_repo
PROJECTS_DIR=/your/projects/parent

# Project paths (use your native paths - auto-converted for Docker)
PROJECT_1_NAME=my-project
PROJECT_1_PATH=D:/git_repo/my-project   # or /home/user/projects/my-project
PROJECT_1_TYPE=saas
```

Build and run:

```bash
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
docker compose run --rm bip generate
```

See [DOCKER.md](DOCKER.md) for full Docker documentation.

#### Configuration Tiers

BIP uses a 3-tier configuration system:

| Tier | File | Purpose |
|------|------|---------|
| **1** | `.env` | Secrets & API keys (required) |
| **2** | `src/config.py` | Sensible defaults (no changes needed) |
| **3** | `config/bip_settings.yaml` | Advanced customization (optional) |

Most users only need to edit `.env`. See `config/bip_settings.yaml` for advanced options like posting schedules, AI models, and brand colors.

### Next Steps

- **Morning Meetings**: Run `docker compose run --rm bip meeting` for daily project status
- **Calendar**: Run `docker compose run --rm bip calendar` to generate task calendar
- **Full Automation**: Run `docker compose run --rm bip daily-auto` for complete daily workflow
- **Twitter**: See [Twitter API Setup](#twitter-api-setup-en) below
- **Calendar Subscription**: See [Calendar Subscription Setup](#calendar-setup-en) to subscribe from any calendar app

### Twitter API Setup {#twitter-api-setup-en}

BIP uses the Twitter API v2 to automatically post tweets. Follow these steps to set up your Twitter API credentials:

#### 1. Create a Twitter Developer Account

1. Go to [developer.twitter.com](https://developer.twitter.com/en/portal/dashboard)
2. Sign in with your Twitter account
3. Apply for developer access if you haven't already (Free tier works)

#### 2. Create a Project and App

1. In the Developer Portal, click **"+ Create Project"**
2. Name your project (e.g., "BIP Automation")
3. Select your use case (e.g., "Building tools for myself")
4. Create an app within the project

#### 3. Configure App Permissions

1. Go to your app's **"Settings"**
2. Under **"User authentication settings"**, click **"Set up"**
3. Enable **OAuth 1.0a**
4. Set App permissions to **"Read and write"** (required for posting)
5. Set callback URL to `http://localhost` (required but not used)
6. Save changes

#### 4. Generate API Keys and Tokens

1. Go to your app's **"Keys and tokens"** section
2. Generate and save these credentials:
   - **API Key** → `TWITTER_API_KEY`
   - **API Key Secret** → `TWITTER_API_SECRET`
   - **Bearer Token** → `TWITTER_BEARER_TOKEN`
   - **Access Token** → `TWITTER_ACCESS_TOKEN`
   - **Access Token Secret** → `TWITTER_ACCESS_SECRET`

#### 5. Add to .env

Add these to your `.env` file:

```bash
TWITTER_API_KEY=your-api-key
TWITTER_API_SECRET=your-api-secret
TWITTER_BEARER_TOKEN=your-bearer-token
TWITTER_ACCESS_TOKEN=your-access-token
TWITTER_ACCESS_SECRET=your-access-secret
```

Now BIP can automatically post to Twitter using the API!

### Calendar Subscription Setup {#calendar-setup-en}

BIP generates an ICS calendar from your project tasks. To subscribe to it from any calendar app (Google Calendar, Apple Calendar, Outlook):

#### 1. Create a GitHub Personal Access Token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **"Generate new token (classic)"**
3. Name it (e.g., "BIP Calendar")
4. Select only the **`gist`** scope
5. Click **"Generate token"** and copy it

#### 2. Add to .env

```bash
CALENDAR_UPLOAD_GIST=true
GITHUB_GIST_TOKEN=ghp_your_token_here
```

#### 3. Generate and Upload Calendar

```bash
docker compose run --rm bip calendar
```

The first run creates a new GitHub Gist and displays a subscription URL like:
```
https://gist.githubusercontent.com/yourname/abc123/raw/bip-daily-calendar.ics
```

#### 4. Subscribe in Your Calendar App

- **Google Calendar**: Settings → Add calendar → From URL → Paste the URL
- **Apple Calendar**: File → New Calendar Subscription → Paste the URL
- **Outlook**: Add calendar → Subscribe from web → Paste the URL

The calendar auto-updates whenever you run `bip calendar`, `bip reschedule`, or `bip daily-auto`.

#### Alternative Upload Options

**Option 2: GitHub Repository** (if you have push access)
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_GITHUB=true
```

**Option 3: SFTP Server** (self-hosted)
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_SFTP=true
# Also create ftpinfo.json with server credentials
```

See `.env.example` for detailed configuration of all options.

### Alternative: Local Installation (Without Docker)

If you prefer not to use Docker:

#### Prerequisites

- Python 3.12+
- Node.js 18+
- Git

#### Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set up MCP server
cd mcp-servers/social-media-mcp
npm install
npm run build
cd ../..
```

#### Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` with your API keys and project paths:

```bash
ANTHROPIC_API_KEY=your-key-here
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/path/to/my-project
PROJECT_1_TYPE=saas
```

#### Step 3: Initialize and Run

```bash
./bip init
./bip collect
./bip generate
./bip history
```

### Need Help?

- See [README.md](../README.md) for full documentation
- See [DOCKER.md](DOCKER.md) for Docker deployment
- See [SERVER_DEPLOYMENT_GUIDE.md](SERVER_DEPLOYMENT_GUIDE.md) for cloud deployment

---

<a id="中文"></a>
## 中文

5 分钟内让 BIP 运行起来。

### 前置要求

- Docker 20.10+ 和 Docker Compose v2+（推荐）
- 一个 AI API 密钥（Anthropic、OpenAI 或 Gemini）

### Docker 快速开始（推荐）

```bash
# 克隆和配置
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily
cp .env.example .env
```

编辑 `.env` 填入你的设置：

```bash
# AI 提供商（至少需要一个）
ANTHROPIC_API_KEY=你的密钥  # 或 GEMINI_API_KEY 或 OPENAI_API_KEY

# PROJECTS_DIR：包含你项目的父目录
# Windows：PROJECTS_DIR=D:/git_repo
# Linux：  PROJECTS_DIR=/home/user/projects
# WSL：    PROJECTS_DIR=/mnt/d/git_repo
PROJECTS_DIR=/你的/项目/父目录

# 项目路径（使用原生路径 - 自动转换为 Docker 格式）
PROJECT_1_NAME=my-project
PROJECT_1_PATH=D:/git_repo/my-project   # 或 /home/user/projects/my-project
PROJECT_1_TYPE=saas
```

构建并运行：

```bash
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
docker compose run --rm bip generate
```

详见 [DOCKER.md](DOCKER.md) 获取完整的 Docker 文档。

#### 配置层级

BIP 使用 3 层配置系统：

| 层级 | 文件 | 用途 |
|------|------|------|
| **1** | `.env` | 密钥和 API keys（必需） |
| **2** | `src/config.py` | 合理的默认值（无需修改） |
| **3** | `config/bip_settings.yaml` | 高级自定义（可选） |

大多数用户只需要编辑 `.env`。高级选项（如发布时间表、AI 模型、品牌颜色）请参阅 `config/bip_settings.yaml`。

### 下一步

- **早间会议**：运行 `docker compose run --rm bip meeting` 获取每日项目状态
- **日历**：运行 `docker compose run --rm bip calendar` 生成任务日历
- **完整自动化**：运行 `docker compose run --rm bip daily-auto` 执行完整的每日工作流
- **Twitter**：请参阅下方 [Twitter API 设置](#twitter-api-设置-zh)
- **日历订阅**：请参阅 [日历订阅设置](#calendar-setup-zh) 从任何日历应用订阅

### Twitter API 设置 {#twitter-api-设置-zh}

BIP 使用 Twitter API v2 自动发布推文。按照以下步骤设置你的 Twitter API 凭据：

#### 1. 创建 Twitter 开发者账户

1. 访问 [developer.twitter.com](https://developer.twitter.com/en/portal/dashboard)
2. 使用你的 Twitter 账户登录
3. 如果尚未申请，请申请开发者访问权限（免费版即可）

#### 2. 创建项目和应用

1. 在开发者门户中，点击 **"+ Create Project"**
2. 为项目命名（例如 "BIP Automation"）
3. 选择用途（例如 "Building tools for myself"）
4. 在项目中创建一个应用

#### 3. 配置应用权限

1. 进入应用的 **"Settings"**
2. 在 **"User authentication settings"** 下，点击 **"Set up"**
3. 启用 **OAuth 1.0a**
4. 将应用权限设置为 **"Read and write"**（发帖必需）
5. 设置回调 URL 为 `http://localhost`（必填但不会使用）
6. 保存更改

#### 4. 生成 API 密钥和令牌

1. 进入应用的 **"Keys and tokens"** 部分
2. 生成并保存以下凭据：
   - **API Key** → `TWITTER_API_KEY`
   - **API Key Secret** → `TWITTER_API_SECRET`
   - **Bearer Token** → `TWITTER_BEARER_TOKEN`
   - **Access Token** → `TWITTER_ACCESS_TOKEN`
   - **Access Token Secret** → `TWITTER_ACCESS_SECRET`

#### 5. 添加到 .env

将以下内容添加到你的 `.env` 文件：

```bash
TWITTER_API_KEY=你的-api-key
TWITTER_API_SECRET=你的-api-secret
TWITTER_BEARER_TOKEN=你的-bearer-token
TWITTER_ACCESS_TOKEN=你的-access-token
TWITTER_ACCESS_SECRET=你的-access-secret
```

现在 BIP 可以使用 API 自动发布推文了！

### 日历订阅设置 {#calendar-setup-zh}

BIP 从你的项目任务生成 ICS 日历。要在任何日历应用中订阅（Google Calendar、Apple Calendar、Outlook）：

#### 1. 创建 GitHub Personal Access Token

1. 前往 **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. 点击 **"Generate new token (classic)"**
3. 命名（例如 "BIP Calendar"）
4. 只选择 **`gist`** 权限
5. 点击 **"Generate token"** 并复制

#### 2. 添加到 .env

```bash
CALENDAR_UPLOAD_GIST=true
GITHUB_GIST_TOKEN=ghp_你的token
```

#### 3. 生成并上传日历

```bash
docker compose run --rm bip calendar
```

首次运行会创建一个新的 GitHub Gist 并显示订阅 URL：
```
https://gist.githubusercontent.com/yourname/abc123/raw/bip-daily-calendar.ics
```

#### 4. 在日历应用中订阅

- **Google Calendar**: 设置 → 添加日历 → 通过 URL 添加 → 粘贴 URL
- **Apple Calendar**: 文件 → 新建日历订阅 → 粘贴 URL
- **Outlook**: 添加日历 → 从网络订阅 → 粘贴 URL

每当运行 `bip calendar`、`bip reschedule` 或 `bip daily-auto` 时，日历会自动更新。

#### 其他上传选项

**方案二：GitHub 仓库**（如果你有推送权限）
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_GITHUB=true
```

**方案三：SFTP 服务器**（自托管）
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_SFTP=true
# 同时创建包含服务器凭据的 ftpinfo.json
```

详细配置请参阅 `.env.example`。

### 替代方案：本地安装（不使用 Docker）

如果你不想使用 Docker：

#### 前置要求

- Python 3.12+
- Node.js 18+
- Git

#### 第一步：克隆和安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 设置 MCP 服务器
cd mcp-servers/social-media-mcp
npm install
npm run build
cd ../..
```

#### 第二步：配置

```bash
cp .env.example .env
```

编辑 `.env` 填入你的 API 密钥和项目路径：

```bash
ANTHROPIC_API_KEY=你的密钥
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/path/to/my-project
PROJECT_1_TYPE=saas
```

#### 第三步：初始化并运行

```bash
./bip init
./bip collect
./bip generate
./bip history
```

### 需要帮助？

- 查看 [README.md](../README.md) 获取完整文档
- 查看 [DOCKER.md](DOCKER.md) 了解 Docker 部署
- 查看 [SERVER_DEPLOYMENT_GUIDE.md](SERVER_DEPLOYMENT_GUIDE.md) 了解云部署
