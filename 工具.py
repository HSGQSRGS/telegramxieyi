"""通用工具模块 - 协议工具箱
作者: Lion
提供：手机号提取、时间格式化、消息链接解析、压缩包、邮件备份、代理转换等工具
"""
import re
import os
import json
import asyncio
import zipfile
import random
import string
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs
from 配置 import (
    作者名称, 作者用户名, 项目名称, 项目根目录, 导出目录,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_TO, 日志
)

时区 = timezone(timedelta(hours=8))

def 安全截断(文本: str, 最大长度: int = 200) -> str:
    """安全截断字符串（不在 Emoji 高位截断）"""
    if not 文本:
        return ''
    if len(文本) <= 最大长度:
        return 文本
    return 文本[:最大长度 - 1] + '…'


def 提取手机号(phone):
    return re.sub(r'\D', '', phone)

def 格式化手机号(phone):
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return phone
    if not digits.startswith('+'):
        return f"+{digits}"
    return phone

def 当前时间():
    return datetime.now(时区).strftime("%Y-%m-%d %H:%M:%S")

def 格式化时间戳(ts):
    if ts is None:
        return "-"
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=时区).strftime("%Y-%m-%d %H:%M:%S")
    try:
        return ts.astimezone(时区).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def 随机字符串(长度=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=长度))

def 随机数字(长度=3):
    return ''.join(random.choices(string.digits, k=长度))

def 清理路径(p):
    if not p:
        return p
    return p.strip().replace('"', '').replace("'", "")

def 去掉后缀(p):
    if not p:
        return p
    return p[:-8] if p.endswith(".session") else p

def 解析消息链接(link):
    link = link.strip().replace("https://", "").replace("http://", "")
    if link.startswith("t.me/"):
        link = link[5:]
    elif link.startswith("telegram.me/"):
        link = link[12:]
    parts = link.split("/")
    if len(parts) < 2:
        return None, None
    username = parts[0]
    try:
        msg_id = int(parts[1])
    except ValueError:
        return None, None
    if username.startswith("+"):
        username = username[1:]
    return username, msg_id

def 解析机器人链接(link):
    link = link.strip().replace("https://", "").replace("http://", "")
    if link.startswith("t.me/"):
        link = link[5:]
    elif link.startswith("telegram.me/"):
        link = link[12:]
    parts = link.split("?")
    path = parts[0]
    username = path.split("/")[0].strip().lstrip("@")
    if not username:
        return None, None
    start_param = None
    if len(parts) > 1:
        params = parse_qs(parts[1])
        if "start" in params:
            start_param = params["start"][0]
    return username, start_param

def 解析加群链接(link):
    link = link.strip()
    if "joinchat/" in link:
        h = link.split("joinchat/")[-1].split("?")[0].strip("/")
        return 'hash', h
    if "+" in link:
        h = link.split("+")[-1].split("?")[0].strip("/")
        return 'hash', h
    un = link.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("@", "")
    un = un.split("/")[0].split("?")[0]
    return 'username', un

def 创建压缩包(文件列表, 输出名称):
    export_dir = os.path.join(项目根目录, 导出目录)
    os.makedirs(export_dir, exist_ok=True)
    zip_path = os.path.join(export_dir, 输出名称)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in 文件列表:
            if os.path.exists(f):
                zf.write(f, os.path.basename(f))
    return zip_path

def 保存JSON导出(数据, 文件名):
    export_path = os.path.join(项目根目录, 导出目录, 文件名)
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(数据, f, ensure_ascii=False, indent=2)
    return export_path

def 构建横幅():
    return f"""
╔══════════════════════════════════════════════════════════╗
║     {项目名称}  |  Telegram 协议工具箱                  ║
║     作者: {作者名称}  |  {作者用户名}                               ║
╚══════════════════════════════════════════════════════════╝
"""

def 构建账号信息(account):
    phone = account.get('phone', 'N/A')
    first_name = account.get('first_name', '')
    last_name = account.get('last_name', '')
    username = account.get('username', '')
    user_tg_id = account.get('user_tg_id', '')
    bio = account.get('bio', '')
    device_model = account.get('device_model', 'N/A')
    premium = account.get('premium', 0)
    status = account.get('status', 'unknown')
    added_at = account.get('added_at', '')
    last_check = account.get('last_check', '')
    twofa = account.get('twofa_password', '')
    reg_date = account.get('reg_date', '')
    ip = account.get('ip', '')
    country = account.get('country', '')
    状态图标 = "🟢" if status == 'active' else "🔴"
    会员图标 = "⭐" if premium else ""
    text = f"{状态图标} {会员图标} `{phone}`\n"
    text += f"👤 昵称: {first_name} {last_name}\n"
    if username:
        text += f"📛 用户名: @{username}\n"
    if user_tg_id:
        text += f"🆔 TG ID: `{user_tg_id}`\n"
    if bio:
        text += f"📝 简介: {bio[:80]}\n"
    if reg_date:
        text += f"📅 注册日期: {reg_date}\n"
    if twofa:
        text += f"🔐 两步验证: 已开启\n"
    text += f"📱 设备: {device_model}\n"
    if ip:
        text += f"🌐 IP: {ip} ({country or '未知'})\n"
    text += f"📅 添加时间: {added_at}\n"
    text += f"🔍 最后检查: {last_check}\n"
    return text

def 构建进度条(完成, 总数, 宽度=10):
    if 总数 == 0:
        return "▓" * 宽度
    filled = int((完成 / 总数) * 宽度)
    return "▓" * filled + "░" * (宽度 - filled)

def 标准化代理(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    if "://" in proxy_str:
        return proxy_str
    parts = proxy_str.split(":")
    if len(parts) == 2:
        return f"socks5://{parts[0]}:{parts[1]}"
    if len(parts) == 4:
        return f"socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return None

def 代理转Telethon(proxy_str):
    p = 标准化代理(proxy_str)
    if not p:
        return None
    try:
        if "socks5://" in p:
            url = p.replace("socks5://", "")
            if "@" in url:
                auth, addr = url.split("@")
                user, pwd = auth.split(":")
                host, port = addr.split(":")
                return {
                    'proxy_type': 'socks5',
                    'addr': host,
                    'port': int(port),
                    'username': user,
                    'password': pwd,
                    'rdns': True
                }
            else:
                host, port = url.split(":")
                return {
                    'proxy_type': 'socks5',
                    'addr': host,
                    'port': int(port),
                    'rdns': True
                }
        if "http://" in p or "https://" in p:
            url = p.replace("https://", "").replace("http://", "")
            if "@" in url:
                auth, addr = url.split("@")
                user, pwd = auth.split(":")
                host, port = addr.split(":")
                return {
                    'proxy_type': 'http',
                    'addr': host,
                    'port': int(port),
                    'username': user,
                    'password': pwd
                }
            else:
                host, port = url.split(":")
                return {
                    'proxy_type': 'http',
                    'addr': host,
                    'port': int(port)
                }
    except Exception:
        pass
    return None

async def 检测代理存活(proxy_str):
    try:
        p = 标准化代理(proxy_str)
        if not p:
            return False
        if "socks5://" in p:
            url = p.replace("socks5://", "")
            if "@" in url:
                _, addr = url.split("@")
            else:
                addr = url
            host, port = addr.split(":")
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port)),
                timeout=4
            )
            writer.close()
            return True
    except Exception:
        pass
    return False

async def 发送邮件备份(file_path, subject=None):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        日志.warning("SMTP未配置，跳过邮件备份")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = SMTP_TO
        msg['Subject'] = subject or f"{项目名称} 备份 - {当前时间()}"
        body = f"备份由 {项目名称} 生成\n作者: {作者名称} {作者用户名}\n时间: {当前时间()}"
        msg.attach(MIMEText(body, 'plain'))
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
            msg.attach(part)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [SMTP_TO], msg.as_string())
        日志.info(f"邮件备份已发送至 {SMTP_TO}")
        return True
    except Exception as e:
        日志.error(f"邮件备份失败: {e}")
        return False