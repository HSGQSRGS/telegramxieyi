"""
守护系统模块 - 协议工具箱
作者: Lion
上传 session 后进行账号保护：验证码监控、防盗拦截消耗、自动查杀非白名单设备、主权控制
验证码拦截后转发给指定 bot 作废
"""

import asyncio
import re
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.account import (
    GetAuthorizationsRequest, ResetAuthorizationRequest,
    ResetWebAuthorizationsRequest
)
from telethon.tl.functions.messages import SendMessageRequest
from 配置 import (
    默认API_ID, 默认API_HASH, 项目根目录, 会话目录,
    守护轮询间隔, 守护杀设备间隔, 守护主权小时数, 日志
)
import 数据库 as db
from 会话管理 import 获取账号客户端, 获取登录设备, 踢出设备, 重置网页授权
from 设备伪装 import 白名单ID, 白名单用户名
from 工具 import 提取手机号, 去掉后缀, 当前时间

# 正在运行的守护任务 {user_id: {phone: task}}
_守护任务 = {}

async def 启动守护(user_id, 消耗机器人=None):
    """启动账号守护系统"""
    settings = db.获取用户设置(user_id)
    if not settings:
        await db.注册用户(user_id)

    db.更新用户设置(user_id, 'guardian_active', 1)
    if 消耗机器人:
        db.更新用户设置(user_id, 'guardian_consume_bot', 消耗机器人)

    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return False, "没有活跃账号"

    if user_id not in _守护任务:
        _守护任务[user_id] = {}

    started = 0
    for acc in accounts:
        phone = acc['phone']
        if phone in _守护任务[user_id] and _守护任务[user_id][phone] and not _守护任务[user_id][phone].done():
            continue
        task = asyncio.create_task(_守护单个账号(user_id, acc))
        _守护任务[user_id][phone] = task
        started += 1

    日志.info(f"用户 {user_id} 的守护系统已启动，共 {started} 个账号")
    return True, f"守护已启动，保护 {started} 个账号"

async def 停止守护(user_id):
    """停止账号守护系统"""
    db.更新用户设置(user_id, 'guardian_active', 0)

    if user_id in _守护任务:
        for phone, task in _守护任务[user_id].items():
            if task and not task.done():
                task.cancel()
        _守护任务[user_id].clear()

    日志.info(f"用户 {user_id} 的守护系统已停止")
    return True, "守护已停止"

def 获取守护状态(user_id):
    """获取守护状态"""
    settings = db.获取用户设置(user_id)
    if not settings:
        return {'active': False, 'accounts': 0, 'sovereign': False}

    active = bool(settings.get('guardian_active', 0))
    sovereign = bool(settings.get('sovereign_active', 0))
    running = 0
    if user_id in _守护任务:
        running = len([t for t in _守护任务[user_id].values() if t and not t.done()])

    return {
        'active': active,
        'running': running,
        'sovereign': sovereign,
        'sovereign_since': settings.get('sovereign_since', ''),
        'consume_bot': settings.get('guardian_consume_bot', ''),
        'monitor_code': bool(settings.get('monitor_code', 1)),
        'consume_code': bool(settings.get('consume_code', 1)),
        'auto_kill': bool(settings.get('auto_kill', 0)),
    }

async def _守护单个账号(user_id, account):
    """守护单个账号"""
    phone = account['phone']
    日志.info(f"守护账号 {phone} 开始")

    while True:
        try:
            settings = db.获取用户设置(user_id)
            if not settings or not settings.get('guardian_active', 0):
                break

            client = await 获取账号客户端(account)
            if not client:
                日志.warning(f"守护账号 {phone} 无法连接，等待重试")
                await asyncio.sleep(守护轮询间隔 * 5)
                continue

            try:
                # 检查登录设备
                devices, dev_error = await 获取登录设备(
                    account['session_path'],
                    account['api_id'],
                    account['api_hash']
                )
                if dev_error:
                    日志.warning(f"守护账号 {phone} 获取设备失败: {dev_error}")
                else:
                    await _检查设备安全(user_id, client, account, devices, settings)

                # 检查验证码
                if settings.get('monitor_code', 1):
                    await _检查验证码(user_id, client, account, settings)

                # 主权模式检查
                if settings.get('sovereign_active', 0):
                    await _主权检查(user_id, client, account, settings)

            except Exception as e:
                日志.error(f"守护账号 {phone} 异常: {e}")
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            await asyncio.sleep(守护轮询间隔)

        except asyncio.CancelledError:
            日志.info(f"守护账号 {phone} 被取消")
            break
        except Exception as e:
            日志.error(f"守护账号 {phone} 严重错误: {e}")
            await asyncio.sleep(守护轮询间隔 * 5)

async def _检查设备安全(user_id, client, account, devices, settings):
    """检查设备安全，自动查杀非白名单设备"""
    phone = account['phone']
    if not devices:
        return

    白名单 = settings.get('whitelist_devices', '[]')
    try:
        白名单列表 = json.loads(白名单) if isinstance(白名单, str) else 白名单
    except Exception:
        白名单列表 = []

    auto_kill = settings.get('auto_kill', 0)

    for dev in devices:
        if dev.get('current'):
            continue

        device_model = dev.get('device_model', '')
        is_whitelisted = False

        # 检查是否在白名单
        for w in 白名单列表:
            if isinstance(w, str) and w in device_model:
                is_whitelisted = True
                break
            if isinstance(w, dict) and w.get('hash') == dev.get('hash'):
                is_whitelisted = True
                break

        if is_whitelisted:
            continue

        # 自动杀设备
        if auto_kill:
            success, err = await 踢出设备(
                account['session_path'],
                dev['hash'],
                account['api_id'],
                account['api_hash']
            )
            if success:
                db.添加守护日志(user_id, phone, 'kill_device', json.dumps(dev, ensure_ascii=False))
                日志.info(f"守护账号 {phone} 自动杀设备: {device_model}")
            else:
                日志.warning(f"守护账号 {phone} 杀设备失败: {err}")
        else:
            # 记录可疑设备
            db.添加守护日志(user_id, phone, 'suspicious_device', json.dumps(dev, ensure_ascii=False))
            日志.warning(f"守护账号 {phone} 发现可疑设备: {device_model}")

async def _检查验证码(user_id, client, account, settings):
    """检查验证码并拦截消耗"""
    phone = account['phone']
    consume_code = settings.get('consume_code', 1)
    consume_bot = settings.get('guardian_consume_bot', '')

    # 监听 777000 的消息
    try:
        # 获取最近的 777000 消息
        messages = await client.get_messages(777000, limit=5)
        now = datetime.now()
        for msg in messages:
            if msg.date:
                msg_time = msg.date.replace(tzinfo=None)
                if (now - msg_time).total_seconds() > 120:
                    continue

            text = msg.raw_text or ''
            # 检测验证码
            code_match = re.search(r'\b(\d{5,6})\b', text)
            if code_match:
                code = code_match.group(1)
                db.添加守护日志(user_id, phone, 'code_detected', json.dumps({
                    'code': code,
                    'text': text[:200],
                    'time': current_time()
                }, ensure_ascii=False))
                日志.info(f"守护账号 {phone} 检测到验证码: {code}")

                if consume_code:
                    # 消耗验证码：转发给指定 bot 作废
                    if consume_bot:
                        try:
                            bot_entity = await client.get_entity(consume_bot)
                            await client.send_message(bot_entity, f"/start {code}")
                            日志.info(f"守护账号 {phone} 验证码已转发给 {consume_bot} 作废")
                            db.添加守护日志(user_id, phone, 'code_consumed', json.dumps({
                                'code': code,
                                'bot': consume_bot
                            }, ensure_ascii=False))
                        except Exception as e:
                            日志.warning(f"守护账号 {phone} 转发验证码失败: {e}")
                    else:
                        # 尝试自己消耗
                        try:
                            await client.send_message(777000, code)
                            db.添加守护日志(user_id, phone, 'code_consumed', json.dumps({
                                'code': code,
                                'method': 'self'
                            }, ensure_ascii=False))
                        except Exception:
                            pass
    except Exception as e:
        日志.warning(f"守护账号 {phone} 检查验证码异常: {e}")

async def _主权检查(user_id, client, account, settings):
    """主权模式检查"""
    phone = account['phone']
    sovereign_since = settings.get('sovereign_since', '')

    if not sovereign_since:
        db.更新用户设置(user_id, 'sovereign_since', 当前时间())
        return

    try:
        devices, _ = await 获取登录设备(
            account['session_path'],
            account['api_id'],
            account['api_hash']
        )
        if not devices:
            return

        # 主权模式下杀掉所有非当前设备
        for dev in devices:
            if dev.get('current'):
                continue
            success, _ = await 踢出设备(
                account['session_path'],
                dev['hash'],
                account['api_id'],
                account['api_hash']
            )
            if success:
                db.添加守护日志(user_id, phone, 'sovereign_kill', json.dumps(dev, ensure_ascii=False))
                日志.info(f"主权模式 {phone} 杀设备: {dev.get('device_model')}")

        # 重置网页授权
        await 重置网页授权(account['session_path'], account['api_id'], account['api_hash'])

    except Exception as e:
        日志.error(f"主权检查 {phone} 异常: {e}")

async def 启动主权模式(user_id):
    """启动主权模式"""
    settings = db.获取用户设置(user_id)
    if not settings:
        return False, "请先启动守护"

    if not settings.get('guardian_active', 0):
        return False, "请先启动守护系统"

    db.更新用户设置(user_id, 'sovereign_active', 1)
    db.更新用户设置(user_id, 'sovereign_since', 当前时间())
    db.更新用户设置(user_id, 'auto_kill', 1)
    db.更新用户设置(user_id, 'monitor_code', 1)
    db.更新用户设置(user_id, 'consume_code', 1)

    日志.info(f"用户 {user_id} 主权模式已启动")
    return True, "主权模式已启动！所有非当前设备将被自动清除，验证码自动拦截消耗"

async def 停止主权模式(user_id):
    """停止主权模式"""
    db.更新用户设置(user_id, 'sovereign_active', 0)
    db.更新用户设置(user_id, 'auto_kill', 0)
    return True, "主权模式已停止"

async def 设置白名单设备(user_id, 设备列表):
    """设置白名单设备"""
    db.更新用户设置(user_id, 'whitelist_devices', json.dumps(设备列表, ensure_ascii=False))
    return True, "白名单已更新"

def 获取守护日志(user_id, phone=None, limit=50):
    """获取守护日志"""
    return db.获取守护日志(user_id, phone, limit)

def 查询守护日志格式化(user_id, phone=None, limit=20):
    """获取格式化的守护日志"""
    logs = db.获取守护日志(user_id, phone, limit)
    if not logs:
        return "暂无守护日志"

    text = "📋 守护日志:\n"
    for log in logs:
        event_type = log['event_type']
        event_data = log['event_data']
        created_at = log['created_at']
        phone_num = log['phone']

        icon = "🔍"
        desc = "未知事件"
        if event_type == 'kill_device':
            icon = "🗑️"
            desc = "自动杀设备"
        elif event_type == 'suspicious_device':
            icon = "⚠️"
            desc = "发现可疑设备"
        elif event_type == 'code_detected':
            icon = "📩"
            desc = "检测到验证码"
        elif event_type == 'code_consumed':
            icon = "✅"
            desc = "验证码已消耗"
        elif event_type == 'sovereign_kill':
            icon = "👑"
            desc = "主权模式杀设备"

        extra = ""
        if event_data:
            try:
                data = json.loads(event_data)
                if 'device_model' in data:
                    extra = f" - {data['device_model']}"
                elif 'code' in data:
                    extra = f" - 验证码: {data['code']}"
            except Exception:
                pass

        text += f"\n{icon} {created_at} | {phone_num} | {desc}{extra}"

    return text