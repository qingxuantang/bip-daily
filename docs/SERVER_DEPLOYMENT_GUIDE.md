# BIP Server Deployment Guide / BIP 服务器部署指南

**[English](#english) | [中文](#中文)**

---

<a id="english"></a>
## English

### Comprehensive Guide for 24/7 Cloud Deployment

**Created:** 2025-12-26
**Purpose:** Move the Build-in-Public (BIP) automation system from local machine to a cloud server for 24/7 operation

---

### Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Requirements](#2-system-requirements)
3. [VPS Provider Comparison](#3-vps-provider-comparison)
4. [Deployment Options](#4-deployment-options)
5. [Step-by-Step Deployment](#5-step-by-step-deployment)
6. [Playwright/Browser Automation](#6-playwrightbrowser-automation)
7. [Security Best Practices](#7-security-best-practices)
8. [Monitoring and Maintenance](#8-monitoring-and-maintenance)
9. [Cost Analysis](#9-cost-analysis)
10. [Troubleshooting](#10-troubleshooting)
11. [MCP Server Dependency](#11-mcp-server-dependency)

---

### 1. Executive Summary

The BIP system can be deployed to a cloud VPS for 24/7 operation. Recommended approach:

| Aspect | Recommendation |
|--------|----------------|
| **VPS Provider** | Hetzner (best value) or DigitalOcean (best docs) |
| **Server Specs** | 4GB RAM, 2 vCPU, 80GB SSD minimum |
| **Deployment Method** | Docker with docker-compose |
| **Process Manager** | systemd service with auto-restart |
| **Estimated Cost** | $4-24/month depending on provider |

#### Key Considerations

1. **Playwright/Browser Automation** - Requires headless browser setup with Xvfb
2. **API Keys Security** - Use environment variables, never hardcode
3. **Cookie Management** - Transfer existing cookies or re-authenticate
4. **SFTP Access** - Server needs SSH key for calendar uploads

---

### 2. System Requirements

#### Minimum Server Specifications

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 2GB | 4GB |
| **CPU** | 1 vCPU | 2 vCPU |
| **Storage** | 40GB SSD | 80GB NVMe |
| **Bandwidth** | 1TB/month | 2TB/month |
| **OS** | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

#### Why 4GB RAM is Recommended

- Playwright/Chromium needs ~500MB-1GB per browser instance
- Python runtime + dependencies: ~200-500MB
- AI API calls can buffer large responses
- SQLite operations and file I/O caching

---

### 3. VPS Provider Comparison

#### Price Comparison (4GB RAM, 2025)

| Provider | Plan | Price/Month | vCPU | RAM | Storage | Best For |
|----------|------|-------------|------|-----|---------|----------|
| **[Hetzner](https://www.hetzner.com/cloud)** | CX22 | ~$7 | 2 (x86) | 4GB | 40GB NVMe | Best value |
| **[Vultr](https://www.vultr.com/)** | Regular | $24 | 2 | 4GB | 80GB NVMe | Global coverage |
| **[DigitalOcean](https://www.digitalocean.com/)** | Basic | $24 | 2 | 4GB | 80GB SSD | Great docs |

#### Recommendation

**Primary: Hetzner CX22** (~$7/month)
- Best price-to-performance ratio
- x86 architecture (full Python compatibility)
- EU/US data centers available

**Alternative: DigitalOcean** ($24/month)
- Better documentation and tutorials
- More global data centers
- Easier for beginners

---

### 4. Deployment Options

#### Option A: Docker (Recommended)

**Pros:**
- Isolated environment
- Easy to replicate
- `restart: always` handles crashes
- No Python version conflicts

**Cons:**
- Slightly higher resource usage

#### Option B: Systemd Service (Direct)

**Pros:**
- Lower overhead
- Native Linux integration

**Cons:**
- Manual dependency management
- Virtual environment required

#### Recommended: Docker + Systemd

Combine Docker for isolation with systemd for boot management.

---

### 5. Step-by-Step Deployment

#### Step 1: Provision VPS

1. Create account at [Hetzner Cloud](https://www.hetzner.com/cloud)
2. Create new project
3. Add SSH key (generate with `ssh-keygen -t ed25519`)
4. Create server: Ubuntu 24.04, CX22 (2 vCPU, 4GB RAM)

#### Step 2: Initial Server Setup

```bash
# Connect to server
ssh root@YOUR_SERVER_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install docker-compose
apt install docker-compose-plugin -y

# Create non-root user (recommended)
adduser bipuser
usermod -aG docker bipuser
usermod -aG sudo bipuser
```

#### Step 3: Transfer Project Files

```bash
# From local machine
scp -r /path/to/bip-daily bipuser@YOUR_SERVER_IP:~/bip
```

#### Step 4: Configure Environment

```bash
cd ~/bip
cp .env.example .env
# Edit .env with your API keys
chmod 600 .env
```

#### Step 5: Build and Test

```bash
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
```

#### Step 6: Start Service

```bash
# Start in background
docker compose up -d

# Check logs
docker compose logs -f

# Enable on boot via systemd
```

---

### 6. Playwright/Browser Automation

#### Headless Mode

BIP uses Playwright for Twitter publishing. On servers without display:
1. Use headless mode (default)
2. Xvfb for headed mode if needed

#### Handling Login Sessions

**Option A: Transfer existing cookies**
```bash
scp config/*_cookies.json user@server:~/bip/config/
```

**Option B: Use API-based publishing (Twitter)**
The MCP server supports API publishing without browser automation.

---

### 7. Security Best Practices

#### API Keys

```bash
# Never commit .env to git
echo ".env" >> .gitignore
chmod 600 .env ftpinfo.json config/*_cookies.json
```

#### SSH Access

```bash
# Disable password auth
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

#### Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

---

### 8. Monitoring and Maintenance

#### Log Management

```bash
docker compose logs -f --tail=100
```

#### Backup Strategy

```bash
tar -czvf bip-backup-$(date +%Y%m%d).tar.gz ~/bip/data/
```

---

### 9. Cost Analysis

#### Monthly Costs

| Item | Hetzner | DigitalOcean |
|------|---------|--------------|
| VPS (4GB) | $7 | $24 |
| Backups | +$1.40 | +$4.80 |
| **Total** | **~$8.50** | **~$29** |

#### API Costs (Variable)

| Service | Estimated Monthly |
|---------|-------------------|
| Anthropic Claude | $5-20 |
| OpenAI | $1-5 |
| Gemini | $0-10 |
| **Total** | **$6-35** |

---

### 10. Troubleshooting

#### Container won't start
```bash
docker compose logs bip
docker compose build --no-cache
```

#### Playwright browser errors
```bash
# Ensure shm_size is set in docker-compose.yml
shm_size: '2gb'
```

#### Permission denied errors
```bash
sudo chown -R 1000:1000 ~/bip/data
```

---

### 11. MCP Server Dependency

#### Twitter Publishing Architecture

BIP has **two methods** for Twitter publishing:

| Method | Description | MCP Required |
|--------|-------------|--------------|
| **API Publishing** | Uses `direct-post.js` to call Twitter API v2 | **YES** |
| **Playwright** | Browser automation with manual login | No |

#### Minimal MCP Files Required

```
mcp-servers/
└── social-media-mcp/
    ├── .env                 # Twitter API keys
    ├── direct-post.js       # Main posting script
    ├── package.json         # Node.js dependencies
    └── node_modules/        # After npm install
```

---

**Last Updated:** 2025-12-27

---

<a id="中文"></a>
## 中文

### 24/7 云部署完整指南

**创建日期：** 2025-12-26
**目的：** 将 Build-in-Public (BIP) 自动化系统从本地机器迁移到云服务器，实现 24/7 运行

---

### 目录

1. [摘要](#1-摘要)
2. [系统需求](#2-系统需求)
3. [VPS 提供商对比](#3-vps-提供商对比)
4. [部署方案](#4-部署方案)
5. [分步部署指南](#5-分步部署指南)
6. [Playwright/浏览器自动化](#6-playwright浏览器自动化)
7. [安全最佳实践](#7-安全最佳实践)
8. [监控和维护](#8-监控和维护)
9. [成本分析](#9-成本分析)
10. [故障排除](#10-故障排除)
11. [MCP 服务器依赖](#11-mcp-服务器依赖)

---

### 1. 摘要

BIP 系统可以部署到云 VPS 实现 24/7 运行。推荐方案：

| 方面 | 推荐 |
|------|------|
| **VPS 提供商** | Hetzner（性价比最高）或 DigitalOcean（文档最好） |
| **服务器配置** | 最低 4GB RAM，2 vCPU，80GB SSD |
| **部署方式** | Docker 配合 docker-compose |
| **进程管理** | systemd 服务，自动重启 |
| **预估成本** | 每月 $4-24，取决于提供商 |

#### 关键考虑因素

1. **Playwright/浏览器自动化** - 需要使用 Xvfb 设置无头浏览器
2. **API 密钥安全** - 使用环境变量，绝不硬编码
3. **Cookie 管理** - 迁移现有 cookies 或重新认证
4. **SFTP 访问** - 服务器需要 SSH 密钥用于日历上传

---

### 2. 系统需求

#### 最低服务器规格

| 资源 | 最低 | 推荐 |
|------|------|------|
| **内存** | 2GB | 4GB |
| **CPU** | 1 vCPU | 2 vCPU |
| **存储** | 40GB SSD | 80GB NVMe |
| **带宽** | 1TB/月 | 2TB/月 |
| **操作系统** | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

#### 为什么推荐 4GB RAM

- Playwright/Chromium 每个浏览器实例需要约 500MB-1GB
- Python 运行时 + 依赖：约 200-500MB
- AI API 调用可能缓冲大量响应
- SQLite 操作和文件 I/O 缓存

---

### 3. VPS 提供商对比

#### 价格对比（4GB RAM，2025年）

| 提供商 | 套餐 | 月费 | vCPU | RAM | 存储 | 最适合 |
|--------|------|------|------|-----|------|--------|
| **[Hetzner](https://www.hetzner.com/cloud)** | CX22 | ~$7 | 2 (x86) | 4GB | 40GB NVMe | 性价比最高 |
| **[Vultr](https://www.vultr.com/)** | Regular | $24 | 2 | 4GB | 80GB NVMe | 全球覆盖 |
| **[DigitalOcean](https://www.digitalocean.com/)** | Basic | $24 | 2 | 4GB | 80GB SSD | 文档优秀 |

#### 推荐

**首选：Hetzner CX22**（约 $7/月）
- 最佳性价比
- x86 架构（完全 Python 兼容）
- 欧盟/美国数据中心可选

**备选：DigitalOcean**（$24/月）
- 更好的文档和教程
- 更多全球数据中心
- 对新手更友好

---

### 4. 部署方案

#### 方案 A：Docker（推荐）

**优点：**
- 隔离环境
- 易于复制
- `restart: always` 处理崩溃
- 无 Python 版本冲突

**缺点：**
- 资源开销略高

#### 方案 B：Systemd 服务（直接部署）

**优点：**
- 更低开销
- 原生 Linux 集成

**缺点：**
- 手动依赖管理
- 需要虚拟环境

#### 推荐：Docker + Systemd

结合 Docker 实现隔离和 systemd 管理启动。

---

### 5. 分步部署指南

#### 第一步：创建 VPS

1. 在 [Hetzner Cloud](https://www.hetzner.com/cloud) 创建账号
2. 创建新项目
3. 添加 SSH 密钥（使用 `ssh-keygen -t ed25519` 生成）
4. 创建服务器：Ubuntu 24.04，CX22（2 vCPU，4GB RAM）

#### 第二步：初始服务器设置

```bash
# 连接到服务器
ssh root@你的服务器IP

# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# 安装 docker-compose
apt install docker-compose-plugin -y

# 创建非 root 用户（推荐）
adduser bipuser
usermod -aG docker bipuser
usermod -aG sudo bipuser
```

#### 第三步：传输项目文件

```bash
# 从本地机器
scp -r /path/to/bip-daily bipuser@你的服务器IP:~/bip
```

#### 第四步：配置环境

```bash
cd ~/bip
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
chmod 600 .env
```

#### 第五步：构建和测试

```bash
docker compose build
docker compose run --rm bip init
docker compose run --rm bip collect
```

#### 第六步：启动服务

```bash
# 后台启动
docker compose up -d

# 查看日志
docker compose logs -f

# 通过 systemd 开机自启
```

---

### 6. Playwright/浏览器自动化

#### 无头模式

BIP 使用 Playwright 进行 Twitter 发布。在没有显示器的服务器上：
1. 使用无头模式（默认）
2. Xvfb 用于有头模式（调试时需要）

#### 处理登录会话

**方案 A：迁移现有 cookies**
```bash
scp config/*_cookies.json user@server:~/bip/config/
```

**方案 B：使用基于 API 的发布（Twitter）**
MCP 服务器支持无需浏览器自动化的 API 发布。

---

### 7. 安全最佳实践

#### API 密钥

```bash
# 绝不将 .env 提交到 git
echo ".env" >> .gitignore
chmod 600 .env ftpinfo.json config/*_cookies.json
```

#### SSH 访问

```bash
# 禁用密码认证
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

#### 防火墙

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

---

### 8. 监控和维护

#### 日志管理

```bash
docker compose logs -f --tail=100
```

#### 备份策略

```bash
tar -czvf bip-backup-$(date +%Y%m%d).tar.gz ~/bip/data/
```

---

### 9. 成本分析

#### 月度成本

| 项目 | Hetzner | DigitalOcean |
|------|---------|--------------|
| VPS (4GB) | $7 | $24 |
| 备份 | +$1.40 | +$4.80 |
| **合计** | **约 $8.50** | **约 $29** |

#### API 成本（可变）

| 服务 | 预估月费 |
|------|----------|
| Anthropic Claude | $5-20 |
| OpenAI | $1-5 |
| Gemini | $0-10 |
| **合计** | **$6-35** |

---

### 10. 故障排除

#### 容器无法启动
```bash
docker compose logs bip
docker compose build --no-cache
```

#### Playwright 浏览器错误
```bash
# 确保在 docker-compose.yml 中设置了 shm_size
shm_size: '2gb'
```

#### 权限被拒绝
```bash
sudo chown -R 1000:1000 ~/bip/data
```

---

### 11. MCP 服务器依赖

#### Twitter 发布架构

BIP 有**两种方法**进行 Twitter 发布：

| 方法 | 描述 | 需要 MCP |
|------|------|----------|
| **API 发布** | 使用 `direct-post.js` 调用 Twitter API v2 | **是** |
| **Playwright** | 使用浏览器自动化，需手动登录 | 否 |

#### 最小 MCP 文件需求

```
mcp-servers/
└── social-media-mcp/
    ├── .env                 # Twitter API 密钥
    ├── direct-post.js       # 主发布脚本
    ├── package.json         # Node.js 依赖
    └── node_modules/        # npm install 后生成
```

---

**最后更新：** 2025-12-27
