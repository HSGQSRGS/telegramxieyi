"""账号管理模块 - 协议工具箱
作者: Lion
账号导入（session/zip/JSON）、会话文件验证、账号备份与恢复
"""
import os
import asyncio
import json
import zipfile
import shutil
import glob
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from 配置 import (
    API_ID, API_HASH, 默认API_ID, 默认API_HASH,
    会话目录, 上传目录, 备份目录, 项目根目录, 每用户最大账号, 日志
)
import 数据库 as db
import 会话管理
from 设备伪装 import 生成环境, 获取IP信息
from 工具 import 提取手机号, 去掉后缀, 清理路径, 创建压缩包, 保存JSON导出

async def 从会话文件导入(文件路径, user_id, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    count = db.获取账号数量(user_id)
    if count >= 每用户最大账号:
        return None, "MAX_ACCOUNTS"
    result, error = await 会话管理.验证会话(文件路径, api_id, api_hash)
    if error:
        return None, error
    existing = db.按手机号查账号(result['phone'], user_id)
    if existing:
        db.保存账号(
            user_id=user_id, phone=result['phone'],
            session_path=文件路径, api_id=api_id, api_hash=api_hash,
            first_name=result['first_name'], last_name=result['last_name'],
            username=result['username'], user_tg_id=result['user_id'],
            premium=1 if result['premium'] else 0
        )
        return result, None
    session_dir = os.path.join(项目根目录, 会话目录)
    os.makedirs(session_dir, exist_ok=True)
    手机号 = 提取手机号(result['phone'])
    目标路径 = os.path.join(session_dir, f"{手机号}.session")
    源路径 = 文件路径 if 文件路径.endswith('.session') else f"{文件路径}.session"
    if os.path.exists(源路径) and 源路径 != 目标路径:
        try:
            shutil.copy2(源路径, 目标路径)
        except Exception:
            pass
        journal = f"{去掉后缀(源路径)}.session-journal"
        if os.path.exists(journal):
            try:
                shutil.copy2(journal, f"{目标路径}-journal")
            except Exception:
                pass
    db.保存账号(
        user_id=user_id, phone=result['phone'], session_path=目标路径,
        api_id=api_id, api_hash=api_hash,
        first_name=result['first_name'], last_name=result['last_name'],
        username=result['username'], user_tg_id=result['user_id'],
        premium=1 if result['premium'] else 0
    )
    return result, None

async def 从压缩包导入(文件路径, user_id, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    解压目录 = os.path.join(项目根目录, 上传目录, f"extract_{user_id}_{os.path.basename(文件路径)}")
    os.makedirs(解压目录, exist_ok=True)
    try:
        with zipfile.ZipFile(文件路径, 'r') as zf:
            zf.extractall(解压目录)
        results = []
        errors = []
        json_files = glob.glob(f"{解压目录}/**/*.json", recursive=True)
        session_files = glob.glob(f"{解压目录}/**/*.session", recursive=True)
        if json_files:
            for jf in json_files:
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    session_string = data.get('session_string') or data.get('session')
                    phone = data.get('phone')
                    password = data.get('password') or data.get('2fa') or data.get('twoFA')
                    device_model = data.get('device_model', '')
                    api_id_file = data.get('api_id', api_id)
                    api_hash_file = data.get('api_hash', api_hash)
                    if session_string and phone:
                        result, _, error = await 会话管理.从字符串加载会话(
                            session_string, api_id_file, api_hash_file
                        )
                        if error:
                            errors.append(f"{phone}: {error}")
                        else:
                            手机号 = 提取手机号(phone)
                            目标路径 = os.path.join(项目根目录, 会话目录, f"{手机号}.session")
                            db.保存账号(
                                user_id=user_id, phone=phone, session_path=目标路径,
                                api_id=api_id_file, api_hash=api_hash_file,
                                first_name=result['first_name'], last_name=result['last_name'],
                                username=result['username'], user_tg_id=result['user_id'],
                                twofa_password=password, device_model=device_model,
                                premium=0
                            )
                            results.append(phone)
                except Exception as e:
                    errors.append(f"{os.path.basename(jf)}: {str(e)}")
        elif session_files:
            for sf in session_files:
                result, error = await 从会话文件导入(sf, user_id, api_id, api_hash)
                if error:
                    errors.append(f"{os.path.basename(sf)}: {error}")
                else:
                    results.append(result['phone'])
        else:
            errors.append("压缩包中未找到有效的会话或JSON文件")
        return results, errors
    except zipfile.BadZipFile:
        return [], ["无效的ZIP文件"]
    finally:
        shutil.rmtree(解压目录, ignore_errors=True)

async def 从JSON字符串导入(json_str, user_id, api_id=None, api_hash=None):
    if api_id is None:
        api_id = 默认API_ID
    if api_hash is None:
        api_hash = 默认API_HASH
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None, "INVALID_JSON"
    session_string = data.get('session_string') or data.get('session')
    phone = data.get('phone')
    if not session_string or not phone:
        return None, "MISSING_FIELDS"
    result, _, error = await 会话管理.从字符串加载会话(session_string, api_id, api_hash)
    if error:
        return None, error
    手机号 = 提取手机号(phone)
    目标路径 = os.path.join(项目根目录, 会话目录, f"{手机号}.session")
    db.保存账号(
        user_id=user_id, phone=phone, session_path=目标路径,
        api_id=api_id, api_hash=api_hash,
        first_name=result['first_name'], last_name=result['last_name'],
        username=result['username'], user_tg_id=result['user_id'],
        premium=0
    )
    return result, None

async def 批量验证账号(user_id):
    accounts = db.获取用户活跃账号(user_id)
    results = []
    for acc in accounts:
        result, error = await 会话管理.验证会话(acc['session_path'], acc['api_id'], acc['api_hash'])
        if error:
            db.更新账号状态(acc['phone'], user_id, 'inactive')
            results.append({'phone': acc['phone'], 'status': 'inactive', 'error': error})
        else:
            results.append({'phone': acc['phone'], 'status': 'active', 'info': result})
    return results

async def 导出账号(user_id):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return None, "NO_ACCOUNTS"
    export_dir = os.path.join(项目根目录, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    文件列表 = []
    for acc in accounts:
        会话路径 = acc['session_path']
        if os.path.exists(会话路径):
            文件列表.append(会话路径)
            journal = f"{会话路径}-journal"
            if os.path.exists(journal):
                文件列表.append(journal)
        json_data = {
            'phone': acc['phone'],
            'user_id': acc['user_tg_id'],
            'first_name': acc['first_name'],
            'last_name': acc['last_name'],
            'username': acc['username'],
            'api_id': acc['api_id'],
            'api_hash': acc['api_hash'],
            'device_model': acc['device_model'],
            'premium': acc['premium'],
            'bio': acc['bio'],
            'twofa_password': acc['twofa_password'],
            'twofa_hint': acc['twofa_hint'],
            'reg_date': acc['reg_date'],
            'ip': acc['ip'],
            'country': acc['country']
        }
        json_path = os.path.join(export_dir, f"{提取手机号(acc['phone'])}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        文件列表.append(json_path)
    zip_name = f"tg_export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = 创建压缩包(文件列表, zip_name)
    for f in 文件列表:
        if f.endswith('.json') and os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    return zip_path, None

async def 导出会话字符串(user_id):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return None, "NO_ACCOUNTS"
    export_data = []
    for acc in accounts:
        result, error = await 会话管理.导出会话字符串(
            acc['session_path'], acc['api_id'], acc['api_hash']
        )
        if not error:
            export_data.append({
                'phone': acc['phone'],
                'session_string': result['session_string'],
                'user_id': result['user_id'],
                'first_name': result['first_name'],
                'last_name': result['last_name'],
                'username': result['username']
            })
    if not export_data:
        return None, "NO_VALID_SESSIONS"
    filename = f"session_strings_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = 保存JSON导出(export_data, filename)
    return path, None

async def 备份账号(会话路径, api_id, api_hash, user_id):
    export_dir = os.path.join(项目根目录, 备份目录)
    os.makedirs(export_dir, exist_ok=True)
    ss_result, ss_error = await 会话管理.导出会话字符串(会话路径, api_id, api_hash)
    if ss_error:
        return None, ss_error
    devices, _ = await 会话管理.获取登录设备(会话路径, api_id, api_hash)
    ip_info = 获取IP信息()
    backup_data = {
        'session_string': ss_result['session_string'],
        'phone': ss_result['phone'],
        'user_id': ss_result['user_id'],
        'first_name': ss_result['first_name'],
        'last_name': ss_result['last_name'],
        'username': ss_result['username'],
        'api_id': api_id,
        'api_hash': api_hash,
        'devices': devices or [],
        'ip_info': ip_info,
        'backup_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'created_by': f"TG协议工具箱 by Lion @SGS520"
    }
    手机号 = 提取手机号(ss_result['phone'])
    json_path = os.path.join(export_dir, f"{手机号}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    zip_name = f"backup_{手机号}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = 创建压缩包([json_path], zip_name)
    try:
        os.remove(json_path)
    except Exception:
        pass
    return zip_path, None

async def 移除账号(account_id, user_id):
    account = db.按ID查账号(account_id)
    if not account or account['user_id'] != user_id:
        return False, "NOT_FOUND"
    db.删除账号(account_id, user_id)
    会话路径 = account['session_path']
    if os.path.exists(会话路径):
        try:
            os.remove(会话路径)
        except Exception:
            pass
    journal = f"{会话路径}-journal"
    if os.path.exists(journal):
        try:
            os.remove(journal)
        except Exception:
            pass
    return True, None