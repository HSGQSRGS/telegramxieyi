"""会话管理模块 - 协议工具箱
作者: Lion
账号登录、验证码发送/校验、两步验证、会话导出、踢出设备、重置授权
"""
import os
import re
import json
import asyncio
import zipfile
import glob
import shutil
from pathlib import Path
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, FloodWaitError, PasswordHashInvalidError
)
from telethon.tl.functions.account import (
    GetAuthorizationsRequest, ResetAuthorizationRequest,
    ResetWebAuthorizationsRequest, GetPasswordRequest,
    UpdatePasswordSettingsRequest
)
from telethon.tl.functions.photos import GetUserPhotosRequest, DeletePhotosRequest
from telethon.tl.functions.contacts import GetContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoto
from 配置 import (
    API_ID, API_HASH, 默认API_ID, 默认API_HASH,
    会话目录, 导出目录, 备份目录, 项目根目录, 日志
)
from 设备伪装 import 生成环境, 生成魔法型号, 白名单ID
from 工具 import 提取手机号, 格式化手机号, 清理路径, 去掉后缀, 随机字符串

async def 发送验证码(phone, api_id=None, api_hash=None, 设备类型='desktop'):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    手机号 = 提取手机号(phone)
    会话路径 = os.path.join(项目根目录, 会话目录, 手机号)
    env = 生成环境(设备类型)
    client = TelegramClient(
        会话路径, api_id, api_hash,
        device_model=env['device_model'],
        system_version=env['system_version'],
        app_version=env['app_version'],
        system_lang_code=env['system_lang_code'],
        lang_code=env['lang_code']
    )
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        await client.disconnect()
        return {
            'phone_code_hash': sent.phone_code_hash,
            'session_path': f"{会话路径}.session",
            'timeout': getattr(sent, 'timeout', 60)
        }, None
    except FloodWaitError as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, f"FLOOD_WAIT_{e.seconds}"
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 创建会话(phone, api_id=None, api_hash=None, 设备类型='desktop',
                 password=None, code_callback=None, code=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    手机号 = 提取手机号(phone)
    会话路径 = os.path.join(项目根目录, 会话目录, 手机号)
    env = 生成环境(设备类型)
    client = TelegramClient(
        会话路径, api_id, api_hash,
        device_model=env['device_model'],
        system_version=env['system_version'],
        app_version=env['app_version'],
        system_lang_code=env['system_lang_code'],
        lang_code=env['lang_code']
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            if code is None:
                try:
                    await client.send_code_request(phone)
                except Exception as e:
                    await client.disconnect()
                    return None, None, str(e)
                if code_callback:
                    code = await code_callback()
                else:
                    code = None
            if not code:
                await client.disconnect()
                return None, None, "CODE_TIMEOUT"
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                if password:
                    try:
                        await client.sign_in(password=password)
                    except PasswordHashInvalidError:
                        await client.disconnect()
                        return None, None, "INVALID_2FA"
                else:
                    await client.disconnect()
                    return None, None, "2FA_REQUIRED"
            except PhoneCodeInvalidError:
                await client.disconnect()
                return None, None, "INVALID_CODE"
            except PhoneCodeExpiredError:
                await client.disconnect()
                return None, None, "CODE_EXPIRED"
        me = await client.get_me()
        session_str = StringSession.save(client.session)
        result = {
            'phone': f"+{me.phone}" if me.phone else phone,
            'user_id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or '',
            'session_string': session_str,
            'session_path': f"{会话路径}.session",
            'device_model': env['device_model'],
            'system_version': env['system_version'],
            'app_version': env['app_version'],
            'system_lang_code': env['system_lang_code'],
            'lang_code': env['lang_code'],
            'lang_pack': env['lang_pack'],
            'premium': getattr(me, 'premium', False)
        }
        await client.disconnect()
        return result, session_str, None
    except FloodWaitError as e:
        await client.disconnect()
        return None, None, f"FLOOD_WAIT_{e.seconds}"
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, None, str(e)

async def 验证会话(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    path = 清理路径(会话路径)
    if not path:
        return None, "INVALID_PATH"
    if not os.path.exists(path) and not os.path.exists(path + ".session"):
        return None, "FILE_NOT_FOUND"
    client = TelegramClient(去掉后缀(path), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        me = await client.get_me()
        result = {
            'phone': f"+{me.phone}" if me.phone else None,
            'user_id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or '',
            'premium': getattr(me, 'premium', False)
        }
        await client.disconnect()
        return result, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 转移会话(旧会话路径, api_id=None, api_hash=None, password=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    旧路径 = 清理路径(旧会话路径)
    if not os.path.exists(旧路径):
        return None, "FILE_NOT_FOUND"
    old_client = TelegramClient(去掉后缀(旧路径), api_id, api_hash)
    try:
        await old_client.connect()
        if not await old_client.is_user_authorized():
            await old_client.disconnect()
            return None, "OLD_SESSION_INVALID"
        me = await old_client.get_me()
        phone = f"+{me.phone}" if me.phone else None
        if not phone:
            await old_client.disconnect()
            return None, "NO_PHONE"
        新路径 = os.path.join(项目根目录, 会话目录, f"new_{me.id}")
        env = 生成环境('desktop')
        new_client = TelegramClient(
            新路径, api_id, api_hash,
            device_model=env['device_model'],
            system_version=env['system_version'],
            app_version=env['app_version'],
            system_lang_code=env['system_lang_code'],
            lang_code=env['lang_code']
        )
        await new_client.connect()
        await new_client.send_code_request(phone)
        code = None
        @old_client.on(events.NewMessage(from_users=777000))
        async def handler(event):
            nonlocal code
            m = re.search(r"\b(\d{5,6})\b", event.raw_text)
            if m and not code:
                code = m.group(1)
        for _ in range(60):
            await asyncio.sleep(2)
            if code:
                break
        old_client.remove_event_handler(handler)
        if not code:
            await new_client.disconnect()
            await old_client.disconnect()
            return None, "CODE_TIMEOUT"
        try:
            await new_client.sign_in(phone, code)
        except SessionPasswordNeededError:
            if password:
                await new_client.sign_in(password=password)
            else:
                await new_client.disconnect()
                await old_client.disconnect()
                return None, "2FA_REQUIRED"
        new_session_str = StringSession.save(new_client.session)
        try:
            await old_client.log_out()
        except Exception:
            pass
        if os.path.exists(旧路径):
            try:
                os.remove(旧路径)
            except Exception:
                pass
        await old_client.disconnect()
        await new_client.disconnect()
        return {
            'session_path': f"{新路径}.session",
            'session_string': new_session_str,
            'phone': phone,
            'user_id': me.id
        }, None
    except Exception as e:
        try:
            await old_client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 从字符串加载会话(会话字符串, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(StringSession(会话字符串), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, None, "UNAUTHORIZED"
        me = await client.get_me()
        phone_clean = 提取手机号(f"+{me.phone}" if me.phone else str(me.id))
        会话路径 = os.path.join(项目根目录, 会话目录, phone_clean)
        client.session.save()
        await client.disconnect()
        result = {
            'phone': f"+{me.phone}" if me.phone else None,
            'user_id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or '',
            'session_path': f"{会话路径}.session"
        }
        return result, 会话字符串, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, None, str(e)

async def 获取登录设备(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        auths = await client(GetAuthorizationsRequest())
        devices = []
        for auth in auths.authorizations:
            devices.append({
                'hash': str(auth.hash),
                'device_model': auth.device_model,
                'platform': auth.platform,
                'system_version': auth.system_version,
                'ip': auth.ip,
                'country': auth.country,
                'date_active': auth.date_active.isoformat() if auth.date_active else None,
                'current': getattr(auth, 'current', False)
            })
        await client.disconnect()
        return devices, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 踢出设备(会话路径, 设备哈希, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "UNAUTHORIZED"
        await client(ResetAuthorizationRequest(hash=int(设备哈希)))
        await client.disconnect()
        return True, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)

async def 重置网页授权(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "UNAUTHORIZED"
        await client(ResetWebAuthorizationsRequest())
        await client.disconnect()
        return True, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)

async def 获取两步验证状态(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        pwd = await client(GetPasswordRequest())
        await client.disconnect()
        return {
            'has_password': pwd.has_password,
            'hint': pwd.hint or '',
            'has_recovery': pwd.has_recovery,
            'email_unconfirmed_pattern': pwd.email_unconfirmed_pattern or ''
        }, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 设置两步验证(会话路径, 新密码, 提示='', 当前密码=None, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "UNAUTHORIZED"
        pwd = await client(GetPasswordRequest())
        from telethon.tl.types import PasswordInputSettings, InputCheckPasswordEmpty
        if pwd.has_password:
            if not 当前密码:
                await client.disconnect()
                return False, "CURRENT_PASSWORD_REQUIRED"
            srp = await client.compute_check(pwd, 当前密码)
        else:
            srp = InputCheckPasswordEmpty()
        new_password_hash = pwd.compute_new_password_hash(新密码)
        new_settings = PasswordInputSettings(
            hint=提示,
            new_password_hash=new_password_hash
        )
        await client(UpdatePasswordSettingsRequest(
            password=srp,
            new_settings=new_settings
        ))
        await client.disconnect()
        return True, None
    except PasswordHashInvalidError:
        await client.disconnect()
        return False, "INVALID_PASSWORD"
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)

async def 关闭两步验证(会话路径, 当前密码, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "UNAUTHORIZED"
        pwd = await client(GetPasswordRequest())
        from telethon.tl.types import PasswordInputSettings
        srp = await client.compute_check(pwd, 当前密码)
        new_settings = PasswordInputSettings(
            hint='',
            new_password_hash=None
        )
        await client(UpdatePasswordSettingsRequest(
            password=srp,
            new_settings=new_settings
        ))
        await client.disconnect()
        return True, None
    except PasswordHashInvalidError:
        await client.disconnect()
        return False, "INVALID_PASSWORD"
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)

async def 批量删除信息(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        contacts = await client(GetContactsRequest(hash=0))
        to_delete = []
        for u in contacts.users:
            if u.id not in 白名单ID:
                to_delete.append(u)
        if to_delete:
            await client(DeleteContactsRequest(id=to_delete))
        await client.disconnect()
        return {'contacts_deleted': len(to_delete)}, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 删除头像(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        photos = await client(GetUserPhotosRequest(user_id="me", offset=0, max_id=0, limit=100))
        if photos.photos:
            ids = [p for p in photos.photos if isinstance(p, InputPhoto)]
            if ids:
                await client(DeletePhotosRequest(id=ids))
        await client.disconnect()
        return {'deleted': len(photos.photos)}, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 获取会话客户端(会话路径, api_id, api_hash):
    if not 会话路径 or not api_id:
        return None
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        return client
    except Exception:
        return None

async def 获取账号客户端(account):
    会话路径 = account['session_path']
    api_id = account['api_id']
    api_hash = account['api_hash']
    return await 获取会话客户端(会话路径, api_id, api_hash)

async def 注销账号(会话路径, api_id=None, api_hash=None, reason=''):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    from telethon.tl.functions.account import DeleteAccountRequest
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "UNAUTHORIZED"
        await client(DeleteAccountRequest(reason=reason))
        await client.disconnect()
        return True, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)

async def 完成两步验证登录(会话路径, 密码, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await client.sign_in(password=密码)
            except PasswordHashInvalidError:
                await client.disconnect()
                return None, "INVALID_2FA"
            except SessionPasswordNeededError:
                try:
                    await client.sign_in(password=密码)
                except PasswordHashInvalidError:
                    await client.disconnect()
                    return None, "INVALID_2FA"
                except Exception as e:
                    await client.disconnect()
                    return None, str(e)
            except Exception as e:
                await client.disconnect()
                return None, str(e)
        me = await client.get_me()
        session_str = StringSession.save(client.session)
        result = {
            'phone': f"+{me.phone}" if me.phone else None,
            'user_id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or '',
            'session_string': session_str,
            'premium': getattr(me, 'premium', False)
        }
        await client.disconnect()
        return result, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 导出会话字符串(会话路径, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    client = TelegramClient(去掉后缀(会话路径), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "UNAUTHORIZED"
        ss = StringSession.save(client.session)
        me = await client.get_me()
        await client.disconnect()
        return {
            'session_string': ss,
            'phone': f"+{me.phone}" if me.phone else None,
            'user_id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or ''
        }, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None, str(e)

async def 获取注册日期(client):
    try:
        from telethon.tl.functions.users import GetFullUserRequest
        full = await client(GetFullUserRequest('me'))
        if full.full_user and hasattr(full.full_user, 'about'):
            about = full.full_user.about or ''
            import re as _re
            m = _re.search(r'(?:reg|注册|created|创建)[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', about, _re.IGNORECASE)
            if m:
                return m.group(1)
        photos = await client.get_profile_photos('me', limit=1)
        if photos and photos[0] and photos[0].date:
            return photos[0].date.strftime("%Y-%m-%d")
        return None
    except Exception:
        return None