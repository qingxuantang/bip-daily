# Docker Deployment Guide / Docker 部署指南

**[English](#english) | [中文](#中文)**

---

<a id="english"></a>
## English

Deploy BIP using Docker for easy setup and consistent environments.

### Prerequisites

- Docker 20.10+
- Docker Compose v2+
- At least one AI API key (Anthropic, OpenAI, or Google Gemini)

### Quick Start

#### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# Copy configuration template
cp .env.example .env

# Edit .env with your API keys and project paths
nano .env
```

**Configuration Tiers**: BIP uses a 3-tier config system. For Docker, you only need `.env` (Tier 1). Advanced settings are in `config/bip_settings.yaml` (Tier 3, optional).

#### 2. Configure PROJECTS_DIR (Required)

Set `PROJECTS_DIR` in your `.env` file to the **parent directory** containing all your projects:

```bash
# In .env - set the parent directory containing your projects
# Windows (Docker Desktop):
PROJECTS_DIR=D:/git_repo

# Linux/macOS:
PROJECTS_DIR=/home/user/projects

# WSL (use Linux-style path):
PROJECTS_DIR=/mnt/d/git_repo
```

#### 3. Configure Project Paths

Set your project paths in `.env`. You can use your **native paths** - BIP auto-converts them for Docker:

```bash
# Windows users - use your normal Windows paths:
PROJECT_1_NAME=my-project
PROJECT_1_PATH=D:/git_repo/my-project
PROJECT_1_TYPE=saas

# Linux/macOS users:
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/home/user/projects/my-project
PROJECT_1_TYPE=saas
```

**How it works**: BIP automatically converts paths like `D:/git_repo/my-project` to `/projects/my-project` inside the Docker container.

#### 4. Build and Run

```bash
# Build the Docker image
docker compose build

# Initialize the database
docker compose run --rm bip init

# Test collection
docker compose run --rm bip collect
```

### Usage

#### Common Commands

```bash
# Initialize system
docker compose run --rm bip init

# Collect data from projects
docker compose run --rm bip collect

# Generate posts
docker compose run --rm bip generate

# View generated posts
docker compose run --rm bip history

# Run morning meeting
docker compose run --rm bip meeting

# Generate calendar
docker compose run --rm bip calendar

# Full daily automation
docker compose run --rm bip daily-auto

# Get help
docker compose run --rm bip --help
```

#### Interactive Shell

```bash
# Start a shell inside the container
docker compose run --rm --entrypoint bash bip

# Inside container, run commands directly
python -m src.cli collect
python -m src.cli generate
```

#### Running Specific Commands

```bash
# Publish a post to Twitter
docker compose run --rm bip publish-twitter 123

# Schedule posts
docker compose run --rm bip schedule

# View a specific post
docker compose run --rm bip view 123
```

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./data/` | `/app/data/` | Database, generated content |
| `./config/` | `/app/config/` | projects.yaml, session cookies |
| `./logs/` | `/app/logs/` | Application logs |
| `$PROJECTS_DIR` | `/projects/` | Monitored Git repositories (read-only) |

### Configuration

#### Environment Variables

Essential variables for Docker:

```bash
# AI Provider (required)
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

# Project paths (use container paths)
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/projects/my-project
PROJECT_1_TYPE=saas

# Database (container path)
DATABASE_URL=sqlite:////app/data/posts.db

# Timezone
TIMEZONE=Asia/Shanghai

# Calendar subscription (optional but recommended)
CALENDAR_UPLOAD_GIST=true
GITHUB_GIST_TOKEN=ghp_your_token_here
```

#### Calendar Subscription

Subscribe to your task calendar from Google Calendar, Apple Calendar, or Outlook:

**Option 1: GitHub Gist (Recommended)**
1. Create a GitHub Personal Access Token with `gist` scope
2. Add to `.env`:
   ```bash
   CALENDAR_UPLOAD_GIST=true
   GITHUB_GIST_TOKEN=ghp_your_token
   ```
3. Run `docker compose run --rm bip calendar`
4. Subscribe to the URL shown in output

**Option 2: GitHub Repository** (if you have push access)
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_GITHUB=true
```

**Option 3: SFTP Server** (self-hosted)
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_SFTP=true
# Create ftpinfo.json with server credentials
```

The calendar auto-updates on each `bip calendar` or `bip daily-auto` run.

#### Project Directory Structure

Organize your projects like this on the host:

```
~/projects/                 # This is $PROJECTS_DIR
├── my-saas-app/           # Maps to /projects/my-saas-app
├── my-api/                # Maps to /projects/my-api
└── my-tool/               # Maps to /projects/my-tool
```

### Building Options

#### Rebuild After Changes

```bash
# Rebuild with no cache
docker compose build --no-cache

# Rebuild and start
docker compose up --build
```

#### Custom Image Tag

```bash
docker build -t bip:latest .
docker build -t bip:v1.0.0 .
```

### Troubleshooting

#### Permission Errors

If you see permission errors with mounted volumes:

```bash
# Create directories with correct permissions
mkdir -p data config logs
chmod 755 data config logs
```

#### Database Locked

If SQLite reports database locked:

```bash
# Ensure only one container is running
docker compose ps
docker compose down

# Then run your command
docker compose run --rm bip collect
```

#### Projects Not Found

If BIP can't find your projects:

1. Check `PROJECTS_DIR` is set correctly
2. Verify paths in `.env` use `/projects/` prefix
3. Ensure projects exist in the mounted directory:

```bash
# Check what's mounted
docker compose run --rm --entrypoint ls bip /projects
```

#### Playwright/Browser Issues

If browser automation fails:

```bash
# Check Playwright installation
docker compose run --rm --entrypoint bash bip -c "playwright --version"

# Reinstall browsers if needed
docker compose run --rm --entrypoint bash bip -c "playwright install chromium"
```

### Advanced Usage

#### Running as a Service

For 24/7 operation with scheduled tasks:

```yaml
# docker-compose.override.yml
services:
  bip:
    command: ["schedule"]
    restart: unless-stopped
```

```bash
# Start as background service
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

#### Multi-Platform Build

```bash
# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 -t bip:latest .
```

### Image Size

The Docker image is approximately 1.5GB due to:
- Python 3.12 runtime
- Node.js 18 runtime
- Playwright with Chromium browser
- Python and Node.js dependencies

To reduce size, you can create a variant without Playwright (not recommended for full functionality).

---

<a id="中文"></a>
## 中文

使用 Docker 部署 BIP，轻松设置和保持环境一致性。

### 前置要求

- Docker 20.10+
- Docker Compose v2+
- 至少一个 AI API 密钥（Anthropic、OpenAI 或 Google Gemini）

### 快速开始

#### 1. 克隆和配置

```bash
# 克隆仓库
git clone https://github.com/yourusername/bip-daily.git
cd bip-daily

# 复制配置模板
cp .env.example .env
cp config/projects.yaml.example config/projects.yaml

# 编辑 .env 填入你的 API 密钥和设置
nano .env
```

#### 2. 配置 PROJECTS_DIR（必需）

在 `.env` 文件中设置 `PROJECTS_DIR`，指向包含你所有项目的**父目录**：

```bash
# 在 .env 中 - 设置包含你项目的父目录
# Windows（Docker Desktop）：
PROJECTS_DIR=D:/git_repo

# Linux/macOS：
PROJECTS_DIR=/home/user/projects

# WSL（使用 Linux 风格路径）：
PROJECTS_DIR=/mnt/d/git_repo
```

#### 3. 配置项目路径

在 `.env` 中设置项目路径。你可以使用**原生路径** - BIP 会自动转换为 Docker 格式：

```bash
# Windows 用户 - 使用正常的 Windows 路径：
PROJECT_1_NAME=my-project
PROJECT_1_PATH=D:/git_repo/my-project
PROJECT_1_TYPE=saas

# Linux/macOS 用户：
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/home/user/projects/my-project
PROJECT_1_TYPE=saas
```

**工作原理**：BIP 会自动将 `D:/git_repo/my-project` 这样的路径转换为 Docker 容器内的 `/projects/my-project`。

#### 4. 构建和运行

```bash
# 构建 Docker 镜像
docker compose build

# 初始化数据库
docker compose run --rm bip init

# 测试收集
docker compose run --rm bip collect
```

### 使用方法

#### 常用命令

```bash
# 初始化系统
docker compose run --rm bip init

# 从项目收集数据
docker compose run --rm bip collect

# 生成帖子
docker compose run --rm bip generate

# 查看生成的帖子
docker compose run --rm bip history

# 运行早间会议
docker compose run --rm bip meeting

# 生成日历
docker compose run --rm bip calendar

# 完整的每日自动化
docker compose run --rm bip daily-auto

# 获取帮助
docker compose run --rm bip --help
```

#### 交互式 Shell

```bash
# 在容器内启动 shell
docker compose run --rm --entrypoint bash bip

# 在容器内直接运行命令
python -m src.cli collect
python -m src.cli generate
```

### 卷挂载

| 主机路径 | 容器路径 | 用途 |
|---------|---------|------|
| `./data/` | `/app/data/` | 数据库、生成的内容 |
| `./config/` | `/app/config/` | projects.yaml、会话 cookies |
| `./logs/` | `/app/logs/` | 应用日志 |
| `$PROJECTS_DIR` | `/projects/` | 监控的 Git 仓库（只读） |

### 配置

#### 环境变量

Docker 必需的变量：

```bash
# AI 提供商（必需）
AI_PROVIDER=gemini
GEMINI_API_KEY=你的密钥

# 项目路径（使用容器路径）
PROJECT_1_NAME=my-project
PROJECT_1_PATH=/projects/my-project
PROJECT_1_TYPE=saas

# 数据库（容器路径）
DATABASE_URL=sqlite:////app/data/posts.db

# 时区
TIMEZONE=Asia/Shanghai

# 日历订阅（可选但推荐）
CALENDAR_UPLOAD_GIST=true
GITHUB_GIST_TOKEN=ghp_你的token
```

#### 日历订阅

从 Google Calendar、Apple Calendar 或 Outlook 订阅你的任务日历：

**方案一：GitHub Gist（推荐）**
1. 创建带有 `gist` 权限的 GitHub Personal Access Token
2. 添加到 `.env`：
   ```bash
   CALENDAR_UPLOAD_GIST=true
   GITHUB_GIST_TOKEN=ghp_你的token
   ```
3. 运行 `docker compose run --rm bip calendar`
4. 订阅输出中显示的 URL

**方案二：GitHub 仓库**（如果你有推送权限）
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_GITHUB=true
```

**方案三：SFTP 服务器**（自托管）
```bash
CALENDAR_UPLOAD_GIST=false
CALENDAR_UPLOAD_SFTP=true
# 创建包含服务器凭据的 ftpinfo.json
```

每次运行 `bip calendar` 或 `bip daily-auto` 时日历会自动更新。

### 作为服务运行

24/7 运行：

```bash
# 后台启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

### 故障排除

#### 权限错误

```bash
# 创建正确权限的目录
mkdir -p data config logs
chmod 755 data config logs
```

#### 找不到项目

1. 检查 `PROJECTS_DIR` 设置是否正确
2. 确认 `.env` 中的路径使用 `/projects/` 前缀
3. 验证项目存在于挂载的目录中

#### Playwright/浏览器问题

```bash
# 检查 Playwright 安装
docker compose run --rm --entrypoint bash bip -c "playwright --version"
```

### 镜像大小

Docker 镜像约 1.5GB，包含：
- Python 3.12 运行时
- Node.js 18 运行时
- Playwright 和 Chromium 浏览器
- Python 和 Node.js 依赖
