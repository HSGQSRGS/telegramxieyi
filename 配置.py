"""配置 - 协议工具箱
作者: Lion
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ============== 机器人基础配置 ==============
机器人令牌 = os.getenv("BOT_TOKEN", "")
管理员ID = int(os.getenv("ADMIN_USER_ID", "0"))

# ============== Telegram API ==============
API_ID = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")
默认API_ID = int(os.getenv("DEFAULT_API_ID", "26223707"))
默认API_HASH = os.getenv("DEFAULT_API_HASH", "baf9a07731d7f698f42e7c56da10a5d9")

# ============== 路径配置 ==============
项目根目录 = str(Path(__file__).parent)
会话目录 = os.getenv("SESSION_DIR", "data/sessions")
导出目录 = os.getenv("EXPORT_DIR", "data/exports")
上传目录 = os.getenv("UPLOAD_DIR", "data/uploads")
备份目录 = os.getenv("BACKUP_DIR", "data/backups")
数据库路径 = os.getenv("DB_PATH", "data/协议工具箱.db")

# ============== Web 路由 ==============
默认端口 = int(os.getenv("WEB_PORT", "8000"))
API_PORT = int(os.getenv("API_PORT", "8765"))
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SESSION_DIR = os.getenv("SESSION_DIR", "data/sessions")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8765")

# ============== 验证码转发 ==============
转发BOT用户名 = os.getenv("FORWARD_BOT_USERNAME", "@okpay")

# ============== 日志 ==============
日志级别 = os.getenv("LOG_LEVEL", "INFO")

# ============== 业务限制 ==============
每用户最大账号 = int(os.getenv("MAX_ACCOUNTS_PER_USER", "50"))
并发限制 = int(os.getenv("CONCURRENT_LIMIT", "20"))
最小延迟 = int(os.getenv("MIN_DELAY", "30"))
最大延迟 = int(os.getenv("MAX_DELAY", "60"))
最小反应延迟 = int(os.getenv("MIN_REACTION_DELAY", "2"))
最大反应延迟 = int(os.getenv("MAX_REACTION_DELAY", "4"))
最小加群延迟 = int(os.getenv("MIN_JOIN_DELAY", "3"))
最大加群延迟 = int(os.getenv("MAX_JOIN_DELAY", "6"))
最小发送延迟 = int(os.getenv("MIN_SEND_DELAY", "5"))
最大发送延迟 = int(os.getenv("MAX_SEND_DELAY", "10"))

# ============== 品牌信息 ==============
作者名称 = os.getenv("AUTHOR_NAME", "Lion")
作者用户名 = os.getenv("AUTHOR_USERNAME", "@Lion")
项目名称 = os.getenv("PROJECT_NAME", "协议工具箱")

# ============== 守护系统 ==============
守护自动启动 = int(os.getenv("GUARDIAN_AUTO_START", "0"))
守护消耗机器人 = os.getenv("GUARDIAN_CONSUME_BOT", "")
守护轮询间隔 = int(os.getenv("GUARDIAN_POLL_INTERVAL", "2"))
守护杀设备间隔 = int(os.getenv("GUARDIAN_KILL_INTERVAL", "15"))
守护主权小时数 = int(os.getenv("GUARDIAN_SOVEREIGN_HOURS", "24"))

# ============== 代理系统 ==============
代理启用 = int(os.getenv("PROXY_ENABLED", "0"))
代理轮换模式 = os.getenv("PROXY_ROTATION_MODE", "random")
代理最大失败 = int(os.getenv("PROXY_MAX_FAILS", "3"))

# ============== 监听系统 ==============
监听启用 = int(os.getenv("MONITOR_ENABLED", "0"))
监听转发目标 = os.getenv("MONITOR_FORWARD_TARGET", "")

# ============== 举报系统 ==============
举报启用 = int(os.getenv("REPORT_ENABLED", "0"))

# ============== SMTP 邮件备份 ==============
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_TO = os.getenv("SMTP_TO", "")

# ============== Web 后台 ==============
后台地址 = os.getenv("ADMIN_HOST", "0.0.0.0")
后台端口 = int(os.getenv("ADMIN_PORT", "8080"))
后台用户名 = os.getenv("ADMIN_USER", "admin")
后台密码 = os.getenv("ADMIN_PASS", "lion@2026")
后台密钥 = os.getenv("ADMIN_SECRET", "协议工具箱-lion-secret-2026")

# 创建必要目录
for d in [会话目录, 导出目录, 上传目录, 备份目录,
          os.path.dirname(数据库路径)]:
    full_path = os.path.join(项目根目录, d)
    os.makedirs(full_path, exist_ok=True)

# 日志配置
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, 日志级别.upper(), logging.INFO)
)
日志 = logging.getLogger("协议工具箱")