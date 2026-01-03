# Data Directory

This directory stores BIP runtime data. All files except this README are gitignored.

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `meetings/` | Morning meeting reports (markdown files) |
| `temp_posts/` | Temporary post ideas and drafts |
| `selected_posts/` | Posts selected for publishing |
| `post-images/` | Generated post images |
| `cache/` | Temporary cache files |
| `history/` | Historical data |

## Files

| File | Purpose |
|------|---------|
| `posts.db` | SQLite database storing post history |
| `*.ics` | Generated calendar files |

## Notes

- Database (`posts.db`) is created automatically on first run via `./bip init`
- Meeting reports are timestamped: `meeting_YYYYMMDD_HHMMSS.md`
- Temp posts can be organized in subdirectories by topic
- All runtime data in this directory is excluded from version control


# 数据目录

此目录存储 BIP 运行时数据。除了此 README 外的所有文件都已被 gitignore。

## 目录结构

| 目录 | 用途 |
|------|------|
| `meetings/` | 早间会议报告（markdown 文件） |
| `temp_posts/` | 临时帖子想法和草稿 |
| `selected_posts/` | 已选择发布的帖子 |
| `post-images/` | 生成的帖子图片 |
| `cache/` | 临时缓存文件 |
| `history/` | 历史数据 |

## 文件

| 文件 | 用途 |
|------|------|
| `posts.db` | 存储帖子历史的 SQLite 数据库 |
| `*.ics` | 生成的日历文件 |

## 说明

- 数据库（`posts.db`）在首次运行 `./bip init` 时自动创建
- 会议报告带有时间戳：`meeting_YYYYMMDD_HHMMSS.md`
- 临时帖子可以按主题在子目录中组织
- 此目录中的所有运行时数据都被排除在版本控制之外
