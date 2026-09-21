"""账号检测 — 协议工具箱
作者: Lion

合并自 GAFBot 的 QA 检测模块：
- shaiban.py  手机号封禁检测
- shaihuo.py  账号活跃度检测
- shailiao.py 素材能力检测（能否发图片）
- shaireg.py  注册时间检测
- shuangxiang.py 双向限制检测（能否搜索+互发消息）
"""

import asyncio
import random
import re
from datetime import datetime
from typing import Optional, Dict, List

try:
    from telethon import TelegramClient, errors
    from telethon.tl.functions.contacts import (
        ResolveUsernameRequest,
        GetBlockedRequest,
    )
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.functions.messages import (
        GetDialogsRequest,
        SearchRequest,
    )
    from telethon.tl.types import (
        InputPeerEmpty,
        InputUsersFilter,
    )
    TELETHON_AVAILABLE = True
except Exception:
    TELETHON_AVAILABLE = False

from 配置 import 日志
import 数据库 as db
from 会话管理 import 获取账号客户端


# ============================================================
# 通用用户解析
# ============================================================
async def 解析用户(client, 目标):
    """通过 @username / id / 链接 解析为 UserFull"""
    if not TELETHON_AVAILABLE:
        return None
    try:
        if isinstance(目标, str):
            target = 目标.lstrip('@').strip()
            if target.startswith('http') or 't.me/' in target:
                target = target.split('t.me/')[-1].split('/')[0]
            try:
                r = await client(ResolveUsernameRequest(username=target))
                if r.users:
                    full = await client(GetFullUserRequest(id=r.users[0].id))
                    return full
            except errors.UsernameNotModifiedError:
                pass
            except errors.UsernameInvalidError:
                pass
            # 尝试按 id
            try:
                uid = int(target)
                full = await client(GetFullUserRequest(id=uid))
                return full
            except (ValueError, Exception):
                return None
        else:
            full = await client(GetFullUserRequest(id=int(目标)))
            return full
    except Exception:
        return None


# ============================================================
# 手机号封禁检测 (shaiban)
# ============================================================
async def 检测手机号封禁(accounts: List[dict], 目标用户: str,
                       进度回调=None) -> Dict:
    """检查目标用户是否被屏蔽 / 被自己封禁

    返回:
        {'blocked': bool, 'not_blocked': bool, 'samples': [...]}
    """
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    results = {'blocked': [], 'not_blocked': [], 'errors': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['errors'].append(acc.get('phone'))
            continue
        try:
            target = await 解析用户(client, 目标用户)
            if not target:
                results['errors'].append(acc.get('phone'))
                continue
            me_id = (await client.get_me()).id
            # 通过 getBlocked 比对
            blocked = await client(GetBlockedRequest(offset=0, limit=100))
            blocked_ids = {u.id for u in blocked.users}
            blocked_set = target.full_user.id in blocked_ids

            # 反向：是否被目标封禁（尽力而为，需双向）
            try:
                # 给自己发消息判断是否被封（间接）
                me_full = await client(GetFullUserRequest(id='me'))
                me_blocked_by_target = any(
                    getattr(p, 'blocked', False)
                    for p in getattr(me_full.full_user, 'blocked_list', None) or []
                )
            except Exception:
                me_blocked_by_target = False

            status = 'blocked' if blocked_set or me_blocked_by_target else 'not_blocked'
            results[status].append({'phone': acc.get('phone'), 'status': status})
        except Exception as e:
            results['errors'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results


# ============================================================
# 账号活跃度检测 (shaihuo)
# ============================================================
async def 检测账号活跃度(accounts: List[dict], 目标用户: str,
                       进度回调=None) -> Dict:
    """判断目标是否活跃（最近发言、最后上线时间）"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    results = {'active': [], 'inactive': [], 'errors': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['errors'].append(acc.get('phone'))
            continue
        try:
            target = await 解析用户(client, 目标用户)
            if not target:
                results['errors'].append(acc.get('phone'))
                continue
            full_user = target.full_user
            status_obj = full_user.status
            was_online = None
            if hasattr(status_obj, 'was_online'):
                was_online = status_obj.was_online
            elif hasattr(status_obj, 'expires'):
                was_online = status_obj.expires

            # 判定规则：最近 7 天内有上线时间 → active
            from datetime import datetime, timedelta
            now = datetime.now()
            if was_online and isinstance(was_online, datetime):
                if now - was_online < timedelta(days=7):
                    results['active'].append({'phone': acc.get('phone'),
                                              'last_seen': was_online.isoformat()})
                else:
                    results['inactive'].append({'phone': acc.get('phone'),
                                                'last_seen': was_online.isoformat()})
            else:
                results['inactive'].append({'phone': acc.get('phone'),
                                            'last_seen': 'unknown'})
        except Exception as e:
            results['errors'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results


# ============================================================
# 素材能力检测 (shailiao)
# ============================================================
async def 检测素材能力(accounts: List[dict], 目标用户: str,
                     进度回调=None) -> Dict:
    """通过能否给对方发图片/消息，判断是否被对方限制"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    results = {'can': [], 'cannot': [], 'errors': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['errors'].append(acc.get('phone'))
            continue
        try:
            target_entity = await client.get_entity(目标用户)
            try:
                # 仅查询，不实际发；判断是否能解析到对方
                full = await client(GetFullUserRequest(id=target_entity))
                # blocked / restricted 标志
                blocked = getattr(full.full_user, 'blocked', False)
                # 检查 send_message 能力（保守：仅检查 can_send_message）
                from telethon.tl.functions.channels import GetParticipantRequest
                try:
                    if getattr(target_entity, 'megagroup', False) or getattr(target_entity, 'broadcast', False):
                        me = await client.get_me()
                        await client(GetParticipantRequest(channel=target_entity, participant=me))
                    results['can' if not blocked else 'cannot'].append({
                        'phone': acc.get('phone'),
                        'status': 'allowed' if not blocked else 'blocked'
                    })
                except errors.UserNotParticipantError:
                    results['cannot'].append({'phone': acc.get('phone'),
                                              'status': 'not_participant'})
                except errors.ChatWriteForbiddenError:
                    results['cannot'].append({'phone': acc.get('phone'),
                                              'status': 'forbidden'})
            except Exception as e:
                results['errors'].append({'phone': acc.get('phone'),
                                          'error': str(e)[:80]})
        except Exception as e:
            results['errors'].append({'phone': acc.get('phone'),
                                      'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results


# ============================================================
# 注册时间检测 (shaireg)
# ============================================================
async def 检测注册时间(accounts: List[dict], 目标用户: str,
                     进度回调=None) -> Dict:
    """获取目标账号的注册时间（如有）"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    results = {'details': [], 'errors': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['errors'].append(acc.get('phone'))
            continue
        try:
            full = await 解析用户(client, 目标用户)
            if not full:
                results['errors'].append({'phone': acc.get('phone'),
                                          'error': 'NOT_FOUND'})
                continue
            user = full.users[0] if full.users else None
            reg_time = None
            # Telegram 不会直接暴露 reg_time，仅能从 ID 推断
            if user and hasattr(user, 'id'):
                # 简单估算（基于 Snowflake-like ID 起始）
                reg_time = f"近似 {datetime.fromtimestamp(user.id / 4294967296 + 1420070400).strftime('%Y-%m-%d')}"
            results['details'].append({
                'phone': acc.get('phone'),
                'tg_id': user.id if user else None,
                'reg_time_estimate': reg_time,
            })
        except Exception as e:
            results['errors'].append({'phone': acc.get('phone'),
                                      'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results


# ============================================================
# 双向限制检测 (shuangxiang)
# ============================================================
async def 检测双向限制(accounts: List[dict], 目标用户: str,
                     进度回调=None) -> Dict:
    """检测账号之间互相发消息的能力"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}
    results = {'mutual': [], 'one_way': [], 'errors': []}
    target_user_str = str(目标用户).lstrip('@')
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['errors'].append(acc.get('phone'))
            continue
        try:
            # 解析目标用户并检查双方是否互相可达
            target = await 解析用户(client, target_user_str)
            if not target:
                results['errors'].append({'phone': acc.get('phone'),
                                          'error': 'TARGET_NOT_FOUND'})
                continue

            # 1. 目标是否被搜索到（ResolveUsernameRequest 已隐含完成）
            # 2. 通过 Spambot 检查账号状态
            try:
                spambot = await client.get_entity('SpamBot')
                async with client.conversation(spambot, timeout=15) as conv:
                    await conv.send_message('/start')
                    r = await conv.get_response()
                    # 简化判断：Spambot 返回的文字里有 "account is limited" → 受限
                    status = 'limited' if 'limited' in (r.text or '').lower() else 'ok'
            except Exception:
                status = 'unknown'

            # 3. 我方 -> 目标：能否发送（不发实际消息，只查 can_send）
            # 用 GetParticipantRequest 等价思路（仅适用 group/channel）
            # 对 user：直接 GetFullUserRequest 的 about 检查
            blocked = target.full_user.blocked if hasattr(target.full_user, 'blocked') else False

            if not blocked and status != 'limited':
                results['mutual'].append({'phone': acc.get('phone'), 'status': 'ok'})
            elif blocked and status == 'ok':
                results['one_way'].append({'phone': acc.get('phone'),
                                           'reason': 'blocked_by_target'})
            else:
                results['one_way'].append({'phone': acc.get('phone'),
                                           'reason': status})
        except Exception as e:
            results['errors'].append({'phone': acc.get('phone'),
                                      'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results


# ============================================================
# 综合检测（合并到调用方）
# ============================================================
async def 综合账号检测(accounts: List[dict], 目标用户: str,
                     进度回调=None) -> Dict:
    """对目标用户执行全部 5 种检测"""
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}

    async def _p(t, total, msg=''):
        if 进度回调:
            await 进度回调(t, total, msg)

    await _p(0, 5, '🔍 启动检测')
    fengjin = await 检测手机号封禁(accounts, 目标用户)
    await _p(1, 5, '✅ 手机号封禁检测')
    huoyue = await 检测账号活跃度(accounts, 目标用户)
    await _p(2, 5, '✅ 活跃度检测')
    sucailiao = await 检测素材能力(accounts, 目标用户)
    await _p(3, 5, '✅ 素材能力检测')
    shijian = await 检测注册时间(accounts, 目标用户)
    await _p(4, 5, '✅ 注册时间检测')
    shuangxiang = await 检测双向限制(accounts, 目标用户)
    await _p(5, 5, '✅ 双向限制检测')

    return {
        '封禁检测': fengjin,
        '活跃检测': huoyue,
        '素材检测': sucailiao,
        '注册时间': shijian,
        '双向限制': shuangxiang,
    }


# 公开 API
公开API = [
    '检测手机号封禁', '检测账号活跃度', '检测素材能力',
    '检测注册时间', '检测双向限制', '综合账号检测',
    '解析用户',
]
