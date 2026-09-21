"""
监听系统模块 - 协议工具箱
作者: Lion
监听群组消息，匹配关键词（如"飞机号"、"协议号"等），将提醒发送到目标群组
支持关键词检测和自动回复
"""

import asyncio
import re
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityTextUrl, MessageEntityMention
from 配置 import (
    默认API_ID, 默认API_HASH, 项目根目录, 会话目录, 日志
)
import 数据库 as db
from 会话管理 import 获取账号客户端
from 工具 import 提取手机号, 去掉后缀, 当前时间

# 正在运行的监听任务 {user_id: {'monitor': task, 'auto_reply': task}}
_监听任务 = {}
_关键词列表 = {}

async def 设置关键词(user_id, 关键词列表):
    """设置监听的触发关键词"""
    if isinstance(关键词列表, str):
        try:
            关键词列表 = json.loads(关键词列表)
        except Exception:
            关键词列表 = [k.strip() for k in 关键词列表.split(',') if k.strip()]

    if not isinstance(关键词列表, list):
        return False, "关键词格式错误，请提供逗号分隔的关键词或JSON数组"

    db.更新用户设置(user_id, 'monitor_keywords', json.dumps(关键词列表, ensure_ascii=False))
    _关键词列表[user_id] = 关键词列表
    return True, f"关键词已更新: {', '.join(关键词列表)}"

def 获取关键词(user_id):
    """获取当前设置的关键词"""
    if user_id in _关键词列表:
        return _关键词列表[user_id]

    settings = db.获取用户设置(user_id)
    if settings and settings.get('monitor_keywords'):
        try:
            keywords = json.loads(settings['monitor_keywords'])
            _关键词列表[user_id] = keywords
            return keywords
        except Exception:
            pass
    return []

async def 设置转发目标(user_id, 目标):
    """设置监听到关键词后转发的目标群组"""
    db.更新用户设置(user_id, 'monitor_forward_target', 目标)
    return True, f"转发目标已设置为: {目标}"

async def 设置自动回复(user_id, 回复配置):
    """
    设置自动回复规则
    回复配置格式: {"关键词1": "回复内容1", "关键词2": "回复内容2"}
    或 JSON 字符串
    """
    if isinstance(回复配置, str):
        try:
            回复配置 = json.loads(回复配置)
        except Exception:
            return False, "回复配置格式错误，请提供JSON格式"

    if not isinstance(回复配置, dict):
        return False, "回复配置格式错误"

    db.更新用户设置(user_id, 'monitor_auto_reply', json.dumps(回复配置, ensure_ascii=False))
    return True, f"自动回复规则已设置（{len(回复配置)} 条规则）"

def 获取回复规则(user_id):
    """获取自动回复规则"""
    settings = db.获取用户设置(user_id)
    if settings and settings.get('monitor_auto_reply'):
        try:
            return json.loads(settings['monitor_auto_reply'])
        except Exception:
            pass
    return {}

async def 启动监听(user_id, 监听账号索引=0):
    """
    启动消息监听
    监听账号索引: 使用哪个账号来监听，默认第一个
    """
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return False, "没有活跃账号"

    if 监听账号索引 >= len(accounts):
        return False, "账号索引超出范围"

    settings = db.获取用户设置(user_id)
    if not settings:
        await db.注册用户(user_id)
        settings = db.获取用户设置(user_id)

    db.更新用户设置(user_id, 'monitor_active', 1)

    if user_id in _监听任务:
        await 停止监听(user_id)

    account = accounts[监听账号索引]
    _监听任务[user_id] = {}

    # 启动监听任务
    task = asyncio.create_task(_监听消息(user_id, account, settings))
    _监听任务[user_id]['monitor'] = task

    # 检查是否有自动回复配置
    auto_reply = settings.get('monitor_auto_reply', '{}')
    try:
        auto_reply = json.loads(auto_reply) if isinstance(auto_reply, str) else auto_reply
    except Exception:
        auto_reply = {}

    if auto_reply:
        reply_task = asyncio.create_task(_自动回复监听(user_id, account, auto_reply))
        _监听任务[user_id]['auto_reply'] = reply_task

    日志.info(f"用户 {user_id} 监听已启动，使用账号 {account['phone']}")
    return True, f"监听已启动，使用账号 {account['phone']}"

async def 停止监听(user_id):
    """停止消息监听"""
    db.更新用户设置(user_id, 'monitor_active', 0)

    if user_id in _监听任务:
        for name, task in _监听任务[user_id].items():
            if task and not task.done():
                task.cancel()
        _监听任务[user_id].clear()

    日志.info(f"用户 {user_id} 监听已停止")
    return True, "监听已停止"

def 获取监听状态(user_id):
    """获取监听状态"""
    settings = db.获取用户设置(user_id)
    if not settings:
        return {'active': False, 'keywords': [], 'forward_target': '', 'auto_reply': {}}

    running = False
    if user_id in _监听任务 and _监听任务[user_id].get('monitor'):
        running = not _监听任务[user_id]['monitor'].done()

    keywords = []
    try:
        keywords = json.loads(settings.get('monitor_keywords', '[]'))
    except Exception:
        pass

    auto_reply = {}
    try:
        auto_reply = json.loads(settings.get('monitor_auto_reply', '{}'))
    except Exception:
        pass

    return {
        'active': bool(settings.get('monitor_active', 0)),
        'running': running,
        'keywords': keywords,
        'forward_target': settings.get('monitor_forward_target', ''),
        'auto_reply': auto_reply
    }

async def _监听消息(user_id, account, settings):
    """核心消息监听循环"""
    phone = account['phone']
    关键词列表 = 获取关键词(user_id)
    转发目标 = settings.get('monitor_forward_target', '')

    while True:
        try:
            settings = db.获取用户设置(user_id)
            if not settings or not settings.get('monitor_active', 0):
                break

            client = await 获取账号客户端(account)
            if not client:
                日志.warning(f"监听账号 {phone} 无法连接，等待重试")
                await asyncio.sleep(30)
                continue

            try:
                # 监听所有对话
                @client.on(events.NewMessage(incoming=True))
                async def handler(event):
                    try:
                        message_text = event.raw_text or ''
                        if not message_text:
                            return

                        sender = await event.get_sender()
                        chat = await event.get_chat()

                        # 检查关键词
                        for keyword in 关键词列表:
                            if keyword.lower() in message_text.lower():
                                # 找到匹配
                                sender_name = ''
                                if sender:
                                    sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                                    if sender.username:
                                        sender_name += f" (@{sender.username})"

                                chat_name = getattr(chat, 'title', '') or '私聊'

                                日志.info(f"监听 {phone} 命中关键词 [{keyword}] 在 [{chat_name}]")

                                # 转发到目标群组
                                if 转发目标:
                                    try:
                                        forward_msg = (
                                            f"🔔 **关键词提醒**\n"
                                            f"├─ 关键词: `{keyword}`\n"
                                            f"├─ 来源群组: {chat_name}\n"
                                            f"├─ 发送者: {sender_name}\n"
                                            f"├─ 消息内容:\n"
                                            f"```\n{message_text[:500]}\n```\n"
                                            f"└─ 时间: {当前时间()}"
                                        )
                                        await client.send_message(转发目标, forward_msg)
                                    except Exception as e:
                                        日志.warning(f"转发消息失败: {e}")

                                # 记录到数据库
                                db.添加守护日志(
                                    user_id, phone, 'keyword_match',
                                    json.dumps({
                                        'keyword': keyword,
                                        'chat': chat_name,
                                        'sender': sender_name,
                                        'text': message_text[:200],
                                        'time': 当前时间()
                                    }, ensure_ascii=False)
                                )

                                break  # 只触发一次

                    except Exception as e:
                        日志.error(f"消息处理异常: {e}")

                # 保持连接
                日志.info(f"监听账号 {phone} 已连接，关键词: {关键词列表}")
                while True:
                    settings = db.获取用户设置(user_id)
                    if not settings or not settings.get('monitor_active', 0):
                        break
                    await asyncio.sleep(5)

                client.remove_event_handler(handler)

            except Exception as e:
                日志.error(f"监听账号 {phone} 异常: {e}")
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            await asyncio.sleep(10)

        except asyncio.CancelledError:
            日志.info(f"监听账号 {phone} 被取消")
            break
        except Exception as e:
            日志.error(f"监听账号 {phone} 严重错误: {e}")
            await asyncio.sleep(30)

async def _自动回复监听(user_id, account, 回复规则):
    """自动回复监听"""
    phone = account['phone']

    while True:
        try:
            settings = db.获取用户设置(user_id)
            if not settings or not settings.get('monitor_active', 0):
                break

            client = await 获取账号客户端(account)
            if not client:
                await asyncio.sleep(30)
                continue

            try:
                @client.on(events.NewMessage(incoming=True))
                async def reply_handler(event):
                    try:
                        message_text = event.raw_text or ''
                        if not message_text:
                            return

                        for keyword, reply_text in 回复规则.items():
                            if keyword.lower() in message_text.lower():
                                try:
                                    await event.reply(reply_text)
                                    日志.info(f"自动回复 {phone}: 关键词 [{keyword}] -> [{reply_text[:50]}]")
                                except Exception as e:
                                    日志.warning(f"自动回复失败: {e}")
                                break

                    except Exception as e:
                        日志.error(f"自动回复处理异常: {e}")

                日志.info(f"自动回复监听 {phone} 已连接，规则数: {len(回复规则)}")
                while True:
                    settings = db.获取用户设置(user_id)
                    if not settings or not settings.get('monitor_active', 0):
                        break
                    await asyncio.sleep(5)

                client.remove_event_handler(reply_handler)

            except Exception as e:
                日志.error(f"自动回复监听 {phone} 异常: {e}")
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            await asyncio.sleep(10)

        except asyncio.CancelledError:
            日志.info(f"自动回复监听 {phone} 被取消")
            break
        except Exception as e:
            日志.error(f"自动回复监听 {phone} 严重错误: {e}")
            await asyncio.sleep(30)

async def 添加关键词(user_id, 关键词):
    """添加单个关键词"""
    keywords = 获取关键词(user_id)
    if 关键词 not in keywords:
        keywords.append(关键词)
    return await 设置关键词(user_id, keywords)

async def 删除关键词(user_id, 关键词):
    """删除单个关键词"""
    keywords = 获取关键词(user_id)
    if 关键词 in keywords:
        keywords.remove(关键词)
    return await 设置关键词(user_id, keywords)

async def 添加回复规则(user_id, 关键词, 回复内容):
    """添加一条自动回复规则"""
    rules = 获取回复规则(user_id)
    rules[关键词] = 回复内容
    return await 设置自动回复(user_id, rules)

async def 删除回复规则(user_id, 关键词):
    """删除一条自动回复规则"""
    rules = 获取回复规则(user_id)
    if 关键词 in rules:
        del rules[关键词]
    return await 设置自动回复(user_id, rules)

def 获取监听日志(user_id, limit=50):
    """获取监听日志"""
    logs = db.获取守护日志(user_id, limit=limit)
    keyword_logs = []
    for log in logs:
        if log['event_type'] == 'keyword_match':
            keyword_logs.append(log)
    return keyword_logs

def 格式化监听日志(user_id, limit=20):
    """格式化监听日志"""
    logs = 获取监听日志(user_id, limit)
    if not logs:
        return "暂无监听日志"

    text = "📋 监听日志:\n"
    for log in logs:
        try:
            data = json.loads(log['event_data'])
            text += f"\n🔔 {log['created_at']} | {log['phone']}\n"
            text += f"   关键词: {data.get('keyword', '')}\n"
            text += f"   群组: {data.get('chat', '')}\n"
            text += f"   发送者: {data.get('sender', '')}\n"
            text += f"   内容: {data.get('text', '')[:100]}"
        except Exception:
            text += f"\n🔔 {log['created_at']} | {log['phone']} | {log['event_data'][:100]}"
    return text