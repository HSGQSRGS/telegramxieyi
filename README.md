# telegramxieyi
这是一个基于 Python 的 Telegram 协议机器人管理工具包（作者 Lion），约 40 个文件，采用 python-telegram-bot 与 Telethon 双引擎架构。功能模块包括：账号管理（登录、验证码/两步验证、设备伪装）、会话管理（Session 登录/导出/转移）、批量操作（加群、群发、点赞、转发、改名等 30+ 功能）、守护系统（账号保活）、监听系统、举报系统、代理管理与设置管理。另含 FastAPI Web 管理后台（登录页+控制台），配有数据库、工具函数、13 个可插拔封装模块及并发启动脚本，通过 .env 配置凭据，数据存于 data 目录。


---

# 📱 协议工具箱 Telegram Protocol Toolbox

一个基于 **python-telegram-bot + Telethon** 的 Telegram 多账号一体化管理工具箱，通过 Bot 菜单即可完成账号登录、批量操作、守护监控、举报、代理管理等全套流程，并附带 Web 管理后台。

作者：**Lion**

---

## ✨ 功能特性

### 🎛 主程序（Bot 交互入口）
- 多级菜单控制台，中文界面，支持回调按钮操作
- 每个用户独立数据，支持注册、概览、帮助

### 📱 账号管理
- 批量导入账号（.session / .zip / JSON 数据包）
- 验证码 / 两步验证登录
- 账号状态验证、导出（ZIP / Session 字符串 / JSON）
- 云端与本地备份（可选 SMTP 邮件备份）

### 🔑 会话管理
- 手机号验证码登录新账号
- 会话转移（新旧设备无缝切换）
- 会话导出为 ZIP / JSON

### ⚡ 批量操作（30+ 功能）
- 批量加群、群发消息、点赞（表情反应）、转发
- 批量修改昵称 / 用户名 / 简介 / 头像
- 一键锁定隐私设置、批量启动机器人（/start）
- 爬取群成员、导出联系人

### 🚨 举报系统
- 支持 10 种中文举报原因
- 批量举报 / 多目标举报 / 循环定时举报

### 🛡 守护系统
- 验证码实时监控与消耗拦截
- 自动查杀非白名单设备
- 主权模式（独占账号控制权）

### 👂 监听系统
- 群组关键词检测
- 命中关键词自动转发 / 自动回复

### 🌐 代理管理
- socks5 / http 代理，支持 `ip:port` 与 `ip:port:user:pass`
- 代理存活检测、随机 / 轮询轮换

### ⚙️ 设置管理
- 自定义延迟范围、关键词、回复规则、守护参数
- 设置一键导入 / 导出

### 🖥 Web 管理后台
- FastAPI + 登录页 + 控制台（JWT 鉴权）
- 可视化查看与管理

---

## 📦 项目结构

```
协议工具箱/
├── 主程序.py            # Bot 主入口（菜单/命令/回调）
├── 配置.py              # 配置加载与日志
├── 数据库.py            # SQLite 数据层
├── 会话管理.py          # 登录/验证/导出/转移
├── 账号管理.py          # 账号导入/备份/验证
├── 批量操作.py          # 30+ 批量任务
├── 守护系统.py          # 验证码监控/防盗
├── 监听系统.py          # 关键词监听/转发/回复
├── 举报系统.py          # 批量举报
├── 代理管理.py          # 代理导入/检测/轮换
├── 设置管理.py          # 参数自定义
├── 设备伪装.py          # 魔法型号生成
├── 工具.py              # 通用工具函数
├── 并发启动.py          # 多进程并发启动
├── 封装/                # 13 个可插拔子模块
│   ├── 1_封禁机器人.py  ─ 13_扩展功能.py
├── 管理后台/
│   ├── web后台.py       # FastAPI 后端
│   └── 网页前端/        # 登录页 + 控制台
├── data/                # 会话/导出/备份/上传数据
├── .env示例             # 环境变量模板
├── 依赖文件.txt         # Python 依赖清单
└── 启动.sh              # 一键启动脚本
```

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Telegram Bot Token（@BotFather 申请）
- Telegram API ID / API Hash（my.telegram.org 获取）

### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/yourname/protocol-toolbox.git
cd protocol-toolbox

# 2. 安装依赖
pip install -r 依赖文件.txt

# 3. 配置环境变量
cp .env示例 .env
# 编辑 .env：填写 BOT_TOKEN、API_ID、API_HASH

# 4. 启动
python 并发启动.py
# 或使用一键脚本
./启动.sh
```

### .env 关键配置

| 配置项 | 说明 |
|--------|------|
| `BOT_TOKEN` | Telegram Bot 令牌 |
| `API_ID` / `API_HASH` | Telegram 协议 API 凭据 |
| `ADMIN_USER_ID` | 管理员 ID |
| `ADMIN_HOST` / `ADMIN_PORT` | Web 后台监听地址与端口 |
| `CONCURRENT_LIMIT` | 并发任务数上限 |
| `MIN_DELAY` / `MAX_DELAY` | 批量操作随机延迟范围 |

---
