# ============================================================
# 协议工具箱 - 增强版会话转换模块
# 作者: Lion
# 支持: session<->tdata, json<->telethon, sqlite<->zip
# ============================================================

import os
import json
import sqlite3
import shutil
import zipfile
import base64
import struct
from typing import Optional, Dict, List, Any
from datetime import datetime


# ============================================================
# Telethon Session 结构
# ============================================================
def 解析telethon会话(session_path: str) -> Dict[str, Any]:
    """解析 telethon session 文件 (sqlite格式)

    返回: {
        'user_id': int,
        'dc_id': int,
        'auth_key': bytes,
        'api_id': int,
        'valid': bool,
        'takeout_id': Optional[int],
        'date': int
    }
    """
    result = {
        'user_id': 0,
        'dc_id': 0,
        'auth_key': b'',
        'api_id': 0,
        'valid': False,
        'takeout_id': None,
        'date': 0,
    }
    try:
        if not os.path.exists(session_path):
            return result
        con = sqlite3.connect(session_path)
        cur = con.cursor()
        try:
            cur.execute('SELECT id FROM entities LIMIT 1')
            r = cur.fetchone()
            if r:
                result['user_id'] = r[0]
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute('SELECT key, value FROM sessions')
            for key, value in cur.fetchall():
                if key == 'dc_id':
                    result['dc_id'] = value
                elif key == 'takeout_id':
                    result['takeout_id'] = value
            cur.execute('SELECT value FROM sessions WHERE key=?', ('auth_key',))
            r = cur.fetchone()
            if r:
                result['auth_key'] = sqlite3.Binary(r[0]).tobytes() if isinstance(r[0], bytes) else r[0]
            cur.execute('SELECT value FROM sessions WHERE key=?', ('user_id',))
            r = cur.fetchone()
            if r:
                result['user_id'] = r[0]
        except sqlite3.OperationalError:
            pass

        # 提取其他信息
        try:
            cur.execute('SELECT key, value FROM other')
            for key, value in cur.fetchall():
                if key == 'date':
                    result['date'] = value
        except sqlite3.OperationalError:
            pass

        con.close()
        result['valid'] = bool(result['auth_key'] and result['user_id'])
    except Exception:
        pass
    return result


def 提取账户信息(session_path: str) -> Dict[str, Any]:
    """提取账户显示信息（无需登录）"""
    info = 解析telethon会话(session_path)
    return {
        'user_id': info['user_id'],
        'dc_id': info['dc_id'],
        'valid': info['valid'],
        'session_file': os.path.basename(session_path),
        'size': os.path.getsize(session_path) if os.path.exists(session_path) else 0,
        'mtime': datetime.fromtimestamp(os.path.getmtime(session_path)).isoformat()
                if os.path.exists(session_path) else '',
    }


# ============================================================
# Session 加密层 (Telethon .session-journal)
# ============================================================
def 解析auth_key(auth_key: bytes) -> Dict[str, Any]:
    """解析 auth_key 并提取可用信息"""
    if not auth_key or len(auth_key) < 200:
        return {'valid': False, 'length': len(auth_key) if auth_key else 0}
    return {
        'valid': len(auth_key) >= 200,
        'length': len(auth_key),
        'fingerprint': hashlib_md5(auth_key[:32]) if _HAS_HASHLIB else '',
        'preview': base64.b64encode(auth_key[:16]).decode('utf-8', errors='ignore'),
    }


import hashlib
_HAS_HASHLIB = True


def hashlib_md5(data: bytes) -> str:
    try:
        return hashlib.md5(data).hexdigest()
    except Exception:
        return ''


# ============================================================
# TData 兼容转换
# ============================================================
def 生成tdata目录(session_path: str, 输出目录: str,
              phone: Optional[str] = None,
              api_id: Optional[int] = None,
              api_hash: Optional[str] = None,
              二维码登录: bool = False) -> Dict[str, Any]:
    """生成 Telegram Desktop tdata 兼容结构

    参数:
        session_path: telethon session 路径
        输出目录: tdata 输出路径
        phone: 手机号（可选）
        api_id: API ID（可选）
        api_hash: API hash（可选）
        二维码登录: 是否启用二维码登录

    返回:
        {'success': bool, 'files': [...], 'message': str}
    """
    info = 解析telethon会话(session_path)
    if not info['valid']:
        return {'success': False, 'message': '无效的 session（缺少 auth_key 或 user_id）', 'files': []}

    try:
        os.makedirs(输出目录, exist_ok=True)
        文件列表 = []

        # 1. 复制 session 文件本身作为后备
        session_name = os.path.basename(session_path)
        for ext in ['', '-journal', '-shm', '-wal']:
            src = session_path + ext
            if os.path.exists(src):
                dst = os.path.join(输出目录, 'telethon_' + os.path.basename(session_path) + ext)
                shutil.copy(src, dst)
                文件列表.append(dst)

        # 2. 写出 tdata 风格的配置文件
        config = {
            'phone': phone or '+',
            'api_id': api_id or 0,
            'api_hash': api_hash or '',
            'user_id': info['user_id'],
            'dc_id': info['dc_id'],
            'app_version': '4.16.8',
            'exported_at': int(datetime.now().timestamp()),
            'source': '协议工具箱',
            'author': 'Lion',
            'qr_login_enabled': 二维码登录,
        }
        config_path = os.path.join(输出目录, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        文件列表.append(config_path)

        # 3. 写出 key_data（模拟 TDesktop auth key 位置）
        key_data_path = os.path.join(输出目录, 'key_data.bin')
        try:
            # 仅前 256 字节（auth_key 的安全子集）
            preview = info['auth_key'][:256] if info['auth_key'] else b'\x00' * 256
            with open(key_data_path, 'wb') as f:
                f.write(preview + b'\x00' * max(0, 1024 - len(preview)))
            文件列表.append(key_data_path)
        except Exception:
            pass

        # 4. 写出 phone.json
        phone_file = os.path.join(输出目录, 'phone.json')
        with open(phone_file, 'w', encoding='utf-8') as f:
            json.dump({
                'phone': phone or '+',
                'phone_hash': '',
                'registered': True,
                'user_id': info['user_id'],
            }, f, indent=2)
        文件列表.append(phone_file)

        return {'success': True, 'message': f'已导出 {len(文件列表)} 个文件', 'files': 文件列表}
    except Exception as e:
        return {'success': False, 'message': str(e)[:200], 'files': []}


# ============================================================
# JSON / Base64 转换
# ============================================================
def session转json(session_path: str) -> str:
    """将 session 转 JSON 字符串（不可逆）"""
    info = 解析telethon会话(session_path)
    return json.dumps({
        'user_id': info['user_id'],
        'dc_id': info['dc_id'],
        'takeout_id': info['takeout_id'],
        'date': info['date'],
        'valid': info['valid'],
        'auth_key_preview': base64.b64encode(info['auth_key'][:64]).decode('utf-8')
                            if info['auth_key'] else '',
        'file_name': os.path.basename(session_path),
        'size': os.path.getsize(session_path),
    }, indent=2, ensure_ascii=False)


def 会话转base64(session_path: str) -> str:
    """将整个 session 文件打包成 base64"""
    try:
        if not os.path.exists(session_path):
            return ''
        with open(session_path, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    except Exception:
        return ''


def base64转会话(b64_data: str, 输出路径: str) -> bool:
    """将 base64 数据还原为 session 文件"""
    try:
        data = base64.b64decode(b64_data)
        os.makedirs(os.path.dirname(输出路径), exist_ok=True)
        with open(输出路径, 'wb') as f:
            f.write(data)
        return True
    except Exception:
        return False


# ============================================================
# 批量会话处理
# ============================================================
def 批量转换(输入目录: str, 输出目录: str, 格式: str = 'tdata') -> Dict[str, Any]:
    """批量将会话转为指定格式

    参数:
        输入目录: 包含 .session 文件
        输出目录: 输出目录
        格式: tdata / json / base64

    返回:
        {'total': N, 'success': N, 'fail': N, 'details': [...]}
    """
    if not os.path.isdir(输入目录):
        return {'total': 0, 'success': 0, 'fail': 0, 'details': [], 'error': '输入目录不存在'}

    results = {'total': 0, 'success': 0, 'fail': 0, 'details': []}

    files = [f for f in os.listdir(输入目录) if f.endswith('.session') and not f.endswith('-journal')]
    results['total'] = len(files)

    for fname in files:
        try:
            src = os.path.join(输入目录, fname)
            name = fname[:-8]  # 去掉 .session
            target_dir = os.path.join(输出目录, name)
            os.makedirs(target_dir, exist_ok=True)
            if 格式 == 'tdata':
                r = 生成tdata目录(src, target_dir)
                if r['success']:
                    results['success'] += 1
                else:
                    results['fail'] += 1
                results['details'].append({'name': name, 'success': r['success'], 'message': r['message']})
            elif 格式 == 'json':
                json_path = os.path.join(target_dir, 'info.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(session转json(src))
                results['success'] += 1
                results['details'].append({'name': name, 'success': True})
            elif 格式 == 'base64':
                b64_path = os.path.join(target_dir, 'session.b64')
                b64 = 会话转base64(src)
                if b64:
                    with open(b64_path, 'w') as f:
                        f.write(b64)
                    results['success'] += 1
                    results['details'].append({'name': name, 'success': True})
                else:
                    results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'name': fname, 'success': False, 'error': str(e)[:80]})

    return results


# ============================================================
# ZIP 打包
# ============================================================
def 打包sessions(sessions: List[str], zip_path: str, 包含tdata: bool = True,
              包含原文件: bool = False) -> str:
    """将会话批量打包到 zip

    返回:
        zip 文件路径
    """
    try:
        os.makedirs(os.path.dirname(zip_path) or '.', exist_ok=True)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for s in sessions:
                if not os.path.exists(s):
                    continue
                name = os.path.basename(s)
                # 写入主 session
                if 包含原文件 or not 包含tdata:
                    zf.write(s, name)
                # 也包含 journal/wal/shm
                for ext in ['-journal', '-shm', '-wal']:
                    if os.path.exists(s + ext):
                        zf.write(s + ext, name + ext)
                # 可选生成 tdata
                if 包含tdata:
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        target = os.path.join(tmpdir, name[:-8] if name.endswith('.session') else name)
                        r = 生成tdata目录(s, target)
                        if r['success']:
                            for f in r['files']:
                                if os.path.exists(f):
                                    arcname = f"{name[:-8]}/{os.path.basename(f)}"
                                    zf.write(f, arcname)
        return zip_path
    except Exception as e:
        return ''


def 解压sessions(zp: str, 输出目录: str) -> Dict[str, Any]:
    """解压 session zip 包并扫描所有会话"""
    try:
        os.makedirs(输出目录, exist_ok=True)
        with zipfile.ZipFile(zp, 'r') as zf:
            zf.extractall(输出目录)
        # 扫描所有 .session
        sessions = []
        for root, dirs, files in os.walk(输出目录):
            for f in files:
                if f.endswith('.session') and not f.endswith('-journal'):
                    sessions.append(os.path.join(root, f))
        return {'success': True, 'count': len(sessions), 'sessions': sessions}
    except Exception as e:
        return {'success': False, 'error': str(e)[:200], 'sessions': []}


# ============================================================
# 会话验证
# ============================================================
def 验证会话完整性(session_path: str) -> Dict[str, Any]:
    """深度验证会话完整性"""
    result = {
        'exists': os.path.exists(session_path),
        'size': 0,
        'valid_db': False,
        'has_auth_key': False,
        'has_user_id': False,
        'has_dc_id': False,
        'json_valid': False,
        'score': 0,
        'notes': [],
    }
    if not result['exists']:
        result['notes'].append('文件不存在')
        return result

    result['size'] = os.path.getsize(session_path)
    if result['size'] < 1024:
        result['notes'].append('文件太小，可能不完整')

    try:
        info = 解析telethon会话(session_path)
        result['valid_db'] = True
        result['has_user_id'] = bool(info['user_id'])
        result['has_dc_id'] = bool(info['dc_id'])
        result['has_auth_key'] = bool(info['auth_key'] and len(info['auth_key']) >= 200)
        result['json_valid'] = True
        score = 0
        if result['has_auth_key']: score += 50
        if result['has_user_id']: score += 20
        if result['has_dc_id']: score += 15
        if result['size'] >= 1024 * 10: score += 15
        result['score'] = score
        if score >= 80:
            result['notes'].append('✅ 会话看起来有效')
        elif score >= 50:
            result['notes'].append('⚠️ 会话部分字段缺失，可能受影响')
        else:
            result['notes'].append('❌ 会话严重不完整，不建议使用')
    except Exception as e:
        result['notes'].append(f'解析失败: {e}')

    return result
