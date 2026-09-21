"""账号安全 — 协议工具箱
作者: Lion

合并自 GAFBot:
- xiaohui.py   销毁账号（client.log_out）
- tishebei.py  踢出其他设备（GetAuthorizationsRequest + ResetAuthorizationRequest）
- xiugai2fa.py 修改/重置 2FA 密码
- passkey.py   PassKey 创建/验证/删除
- fangzhaohui.py  防解封处理（登录后清理）
"""

import asyncio
import json
import os
import random
from datetime import datetime
from typing import Optional, List, Dict

try:
    from telethon import TelegramClient, errors
    from telethon.tl.functions.account import (
        GetAuthorizationsRequest,
        ResetAuthorizationRequest,
        GetPasswordRequest,
        UpdatePasswordSettingsRequest,
        CheckPasswordRequest,
    )
    from telethon.tl.types import (
        account as account_types,
        InputCheckPasswordSRP,
    )
    TELETHON_AVAILABLE = True
except Exception:
    TELETHON_AVAILABLE = False

try:
    from passlib.hash import pbkdf2_sha256
    PASSLIB_AVAILABLE = True
except Exception:
    PASSLIB_AVAILABLE = False

from 配置 import 日志
import 数据库 as db
from 会话管理 import 获取账号客户端


# ============================================================
# 销毁账号 (xiaohui)
# ============================================================
async def 销毁账号(accounts: List[dict], 进度回调=None) -> Dict:
    """注销账号（client.log_out）

    注意：调用后 session 文件会失效。"""
    if not TELETHON_AVAILABLE:
        return {'success': 0, 'fail': len(accounts), 'error': 'TELETHON_NOT_AVAILABLE'}

    results = {'success': [], 'fail': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'].append({'phone': acc.get('phone'), 'error': 'CLIENT_FAILED'})
            continue
        try:
            me = await client.get_me()
            phone = me.phone if me else acc.get('phone')
            await client.log_out()
            results['success'].append({'phone': phone, 'status': 'destroyed'})
        except Exception as e:
            results['fail'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ============================================================
# 踢出其他设备 (tishebei)
# ============================================================
async def 踢出其他设备(accounts: List[dict], 进度回调=None) -> Dict:
    """列出并踢出所有非当前设备

    返回：
        {'success': [...], 'kicked_count': int, 'fail': [...]}
    """
    if not TELETHON_AVAILABLE:
        return {'success': 0, 'fail': len(accounts), 'error': 'TELETHON_NOT_AVAILABLE'}

    results = {'success': [], 'fail': [], 'kicked_count': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'].append({'phone': acc.get('phone'), 'error': 'CLIENT_FAILED'})
            continue
        try:
            me = await client.get_me()
            my_hash = me.session_user_id if me else None

            r = await client(GetAuthorizationsRequest())
            kicked = 0
            for auth in r.authorizations:
                # 当前设备 hash 等于 self_user_id，踢出其他
                if auth.hash != my_hash and getattr(auth, 'current', False) is False:
                    try:
                        await client(ResetAuthorizationRequest(hash=auth.hash))
                        kicked += 1
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    except errors.FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception:
                        pass
            results['success'].append({
                'phone': acc.get('phone'),
                'status': 'kicked',
                'count': kicked,
                'total': len(r.authorizations),
            })
            results['kicked_count'] += kicked
        except Exception as e:
            results['fail'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(1, 2))
    return results


# ============================================================
# 修改/重置 2FA (xiugai2fa)
# ============================================================
async def 获取2FA状态(client):
    """返回 2FA 配置是否启用 + 线索"""
    if not TELETHON_AVAILABLE:
        return None
    try:
        pwd = await client(GetPasswordRequest())
        return {
            'has_password': bool(pwd.has_password),
            'hint': getattr(pwd, 'hint', ''),
            'email': getattr(pwd, 'email', ''),
        }
    except Exception:
        return None


async def 修改2FA(client, 旧密码: Optional[str], 新密码: str,
                邮箱: Optional[str] = None, 邮箱代码: Optional[str] = None) -> bool:
    """修改或设置 2FA 密码"""
    if not TELETHON_AVAILABLE:
        return False
    try:
        pwd = await client(GetPasswordRequest())
        if pwd.has_password:
            if not 旧密码:
                return False
            # 走 SRP
            from telethon.tl.functions.account import CheckPasswordRequest
            check = await client(CheckPasswordRequest(password=旧密码))
            if not check:
                return False
        # 设置新密码
        settings = account_types.PasswordInputSettings(
            new_password=new_password_hash(new密码),
            hint='',
            email=邮箱 or '',
        )
        await client(UpdatePasswordSettingsRequest(password=旧密码 or '', new_settings=settings))
        return True
    except Exception as e:
        日志.error(f"[xiugai2fa] 失败: {e}")
        return False


def new_password_hash(明文: str) -> bytes:
    """Telegram 2FA 密码哈希算法（简化版：使用 SHA-256 + 16 字节前缀）"""
    import hashlib
    h = hashlib.sha512(明文.encode('utf-8')).digest()
    return h[:64]


# ============================================================
# PassKey (passkey)
# ============================================================
_数据目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'passkey_data.json')


def 生成PassKey(长度: int = 16) -> str:
    """生成随机 PassKey（字母+数字）"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(长度))


def 创建PassKey(username: str, passkey: Optional[str] = None) -> Dict:
    """创建并存储 PassKey"""
    if not PASSLIB_AVAILABLE:
        return {'error': 'passlib 未安装，PassKey 创建不可用'}
    try:
        data = {}
        if os.path.exists(_数据目录):
            with open(_数据目录, 'r', encoding='utf-8') as f:
                data = json.load(f)
        pk = passkey or 生成PassKey()
        data[username.lower()] = {
            'passkey_hash': pbkdf2_sha256.hash(pk),
            'username': username,
            'created_at': datetime.now().isoformat(),
        }
        with open(_数据目录, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {'passkey': pk, 'username': username}
    except Exception as e:
        return {'error': str(e)[:100]}


def 验证PassKey(username: str, passkey: str) -> bool:
    """验证 PassKey"""
    if not PASSLIB_AVAILABLE:
        return False
    try:
        if not os.path.exists(_数据目录):
            return False
        with open(_数据目录, 'r', encoding='utf-8') as f:
            data = json.load(f)
        record = data.get(username.lower())
        if not record:
            return False
        return pbkdf2_sha256.verify(passkey, record['passkey_hash'])
    except Exception:
        return False


def 删除PassKey(username: str) -> bool:
    """删除用户的 PassKey"""
    try:
        if not os.path.exists(_数据目录):
            return False
        with open(_数据目录, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if username.lower() in data:
            del data[username.lower()]
            with open(_数据目录, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception:
        return False


# ============================================================
# 防解封 (fangzhaohui)
# ============================================================
async def 登录后防解封(client, 删除PassKey: bool = False) -> Dict:
    """登录成功后立刻踢出所有其他设备 + 可选清理 PassKey

    流程：
      1. 拉取所有设备授权
      2. 踢除其他设备
      3. 删除本地 PassKey 记录（如果 删除PassKey=True）
    """
    if not TELETHON_AVAILABLE:
        return {'error': 'TELETHON_NOT_AVAILABLE'}

    me = await client.get_me()
    my_hash = me.session_user_id if me else None

    r = await client(GetAuthorizationsRequest())
    kicked = 0
    for auth in r.authorizations:
        if auth.hash != my_hash and not getattr(auth, 'current', False):
            try:
                await client(ResetAuthorizationRequest(hash=auth.hash))
                kicked += 1
                await asyncio.sleep(random.uniform(0.5, 1.0))
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception:
                pass

    result = {'kicked': kicked, 'total_devices': len(r.authorizations)}
    if 删除PassKey and me and me.phone:
        删除成功 = 删除PassKey(me.phone)
        result['passkey_deleted'] = 删除成功
    return result


# ============================================================
# 综合安全操作（一次性执行：踢 + 销毁 + 修改 2FA）
# ============================================================
async def 综合安全操作(accounts: List[dict], 操作: str = 'kick',
                      新密码: Optional[str] = None,
                      进度回调=None) -> Dict:
    """批量执行安全操作
    操作: 'kick' 踢出其他设备
          'destroy' 销毁账号
          '2fa' 修改 2FA（需提供 新密码）
          'all' 全部依次执行
    """
    if 操作 == 'kick':
        return await 踢出其他设备(accounts, 进度回调)
    elif 操作 == 'destroy':
        return await 销毁账号(accounts, 进度回调)
    elif 操作 == '2fa' and 新密码:
        results = {'success': [], 'fail': []}
        for i, acc in enumerate(accounts):
            client = await 获取账号客户端(acc)
            if not client:
                results['fail'].append({'phone': acc.get('phone'), 'error': 'CLIENT_FAILED'})
                continue
            try:
                ok = await 修改2FA(client, None, 新密码)
                results['success' if ok else 'fail'].append(acc.get('phone'))
            except Exception as e:
                results['fail'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
        return results
    return {'error': f'UNKNOWN_OPERATION: {操作}'}


# 公开 API
公开API = [
    '销毁账号', '踢出其他设备', '获取2FA状态', '修改2FA',
    '生成PassKey', '创建PassKey', '验证PassKey', '删除PassKey',
    '登录后防解封', '综合安全操作',
]
