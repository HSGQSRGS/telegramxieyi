"""会话转换 — 协议工具箱
作者: Lion

合并自 GAFBot:
- huzhuan.py: session ↔ tdata 双向转换
- chaibao.py: zip 解压 + session/tdata 分析
- i18n.py: 三语文案
"""

import asyncio
import io
import json
import os
import re
import shutil
import zipfile
from typing import Optional, Tuple, List, Dict

from 配置 import 日志


# ============================================================
# 多语言文案（合并自 i18n.py）
# ============================================================
STRINGS = {
    'zh-CN': {
        'welcome': '👋 欢迎使用协议工具箱 v{LION} ！',
        'session_ok': '✅ Session 转换成功！',
        'session_fail': '❌ Session 转换失败：{err}',
        'tdata_ok': '✅ tdata 转换成功！',
        'pack_ok': '✅ 已打包 {count} 个账号到 {path}',
        'pack_fail': '❌ 打包失败：{err}',
        'enter_2fa': '请输入该账号的两步验证密码：',
        'need_2fa': '⚠️ 需要两步验证（请上传含 json 凭据的文件）：',
        'session_uploaded': '📤 已接收 {count} 个 session',
        'merge_complete': '🎉 合并完成！共 {count} 个账号',
    },
    'zh-TW': {
        'welcome': '👋 歡迎使用协议工具箱 v{LION} ！',
        'session_ok': '✅ Session 轉換成功！',
        'session_fail': '❌ Session 轉換失敗：{err}',
        'tdata_ok': '✅ tdata 轉換成功！',
        'pack_ok': '✅ 已打包 {count} 個帳號到 {path}',
        'pack_fail': '❌ 打包失敗：{err}',
        'enter_2fa': '請輸入該帳號的兩步驗證密碼：',
        'need_2fa': '⚠️ 需要兩步驗證',
        'session_uploaded': '📤 已接收 {count} 個 session',
        'merge_complete': '🎉 合併完成！共 {count} 個帳號',
    },
    'en': {
        'welcome': '👋 Welcome to Protocol Toolbox v{LION}!',
        'session_ok': '✅ Session conversion success!',
        'session_fail': '❌ Session conversion failed: {err}',
        'tdata_ok': '✅ tdata conversion success!',
        'pack_ok': '✅ Packed {count} accounts to {path}',
        'pack_fail': '❌ Pack failed: {err}',
        'enter_2fa': 'Please enter 2FA password:',
        'need_2fa': '⚠️ 2FA required',
        'session_uploaded': '📤 Received {count} sessions',
        'merge_complete': '🎉 Merge complete: {count} accounts',
    },
}


_LION_TAG = 'LION'


def tr(key: str, lang: str = 'zh-CN') -> str:
    """查表取文案，找不到回退"""
    if lang in STRINGS and key in STRINGS[lang]:
        s = STRINGS[lang][key]
        if s and '{LION}' in s:
            s = s.replace('{LION}', _LION_TAG)
        return s
    if key in STRINGS.get('zh-CN', {}):
        return STRINGS['zh-CN'][key].replace('{LION}', _LION_TAG)
    return key


def lang_from_code(language_code: str) -> str:
    """根据 Telegram language_code 推断"""
    code = (language_code or 'zh-CN').lower()
    if code.startswith('zh-tw') or code.startswith('zh-hk'):
        return 'zh-TW'
    if code.startswith('zh') or code == '':
        return 'zh-CN'
    if code.startswith('en'):
        return 'en'
    return 'zh-CN'


def get_env_i18n(key: str, lang: str = 'zh-CN') -> str:
    """从环境变量获取自定义文案（未设置时回退默认）"""
    env_key = f'I18N_{key.upper()}'
    val = os.environ.get(env_key)
    if val:
        return val
    return tr(key, lang)


# ============================================================
# Session → tdata 转换（合并自 huzhuan.convert_session_to_tdata）
# ============================================================
def convert_session_to_tdata(session_path: str, 输出目录: str,
                              api_id: int, api_hash: str,
                              phone: Optional[str] = None) -> str:
    """将 Telethon session 转为 Telegram Desktop tdata 目录

    简化实现：直接复制 session 字节并生成 tdata 标记文件。生产环境
    应使用 TDesktop.ToTelethon + 自定义 Python 转换逻辑。
    """
    try:
        os.makedirs(输出目录, exist_ok=True)
        # 生成 tdata 目录结构（注意：完整转换需要 opustns 等附加库，
        # 这里提供降级实现：完整复制 session + 写出 phone.json 配置）
        for fname in os.listdir(os.path.dirname(session_path)):
            if fname.endswith('.session') or fname.endswith('.session-journal'):
                src = os.path.join(os.path.dirname(session_path), fname)
                dst = os.path.join(输出目录, fname)
                shutil.copy(src, dst)
        # 写出 phone.json 供 tdata 读取
        phone_file = os.path.join(输出目录, 'phone.json')
        with open(phone_file, 'w', encoding='utf-8') as f:
            json.dump({
                'phone': phone or '+',
                'api_id': api_id,
                'api_hash': api_hash,
                'app_version': '5.13.1',
                'reg_time': int(os.path.getmtime(session_path)),
            }, f, ensure_ascii=False, indent=2)
        return 输出目录
    except Exception as e:
        日志.error(f"[huzhuan] session→tdata 失败: {e}")
        return ''


def convert_tdata_to_session(tdata_dir: str, 输出目录: str,
                              api_id: int, api_hash: str,
                              phone: Optional[str] = None,
                              twofa_password: Optional[str] = None) -> Optional[str]:
    """将 Telegram Desktop tdata 转为 Telethon session（占位实现）"""
    try:
        os.makedirs(输出目录, exist_ok=True)
        # 实际转换依赖 opustns / tdesktop-python 库；
        # 此处生成占位 session + JSON 配置
        phone_name = (phone or 'unknown').replace('+', '').replace(' ', '')
        session_name = f'session_{phone_name[-4:] if phone_name else "0000"}'
        session_path = os.path.join(输出目录, f'{session_name}.session')
        # 写入最小 sqlite 数据库（仅占位，需用户后续运行正式转换）
        import sqlite3
        conn = sqlite3.connect(session_path)
        conn.close()

        json_path = os.path.join(输出目录, f'{session_name}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'phone': phone or '',
                'api_id': api_id,
                'api_hash': api_hash,
                'app_version': '10.6.2',
                'twofa': twofa_password or '',
                'reg_time': int(os.path.getmtime(tdata_dir)),
                'source': 'tdata_convert',
            }, f, ensure_ascii=False, indent=2)
        return session_path
    except Exception as e:
        日志.error(f"[huzhuan] tdata→session 失败: {e}")
        return None


# ============================================================
# Zip 处理（合并自 chaibao.py）
# ============================================================
def 分析zip(文件路径: str) -> Dict:
    """分析 zip 包内的 session 和 tdata 数量"""
    info = {'sessions': [], 'tdatas': [], 'jsons': [], 'total_files': 0}
    try:
        with zipfile.ZipFile(文件路径, 'r') as z:
            for name in z.namelist():
                info['total_files'] += 1
                if name.endswith('.session'):
                    info['sessions'].append(name)
                elif name.startswith('tdata/'):
                    info['tdatas'].append(name)
                elif name.endswith('.json'):
                    info['jsons'].append(name)
    except Exception as e:
        日志.error(f"[chaibao] 分析zip失败: {e}")
    return info


def 解压zip(文件路径: str, 输出目录: str) -> Dict:
    """解压 zip 到目录"""
    try:
        os.makedirs(输出目录, exist_ok=True)
        with zipfile.ZipFile(文件路径, 'r') as z:
            z.extractall(输出目录)
        return {'success': True, 'count': len(os.listdir(输出目录))}
    except Exception as e:
        日志.error(f"[chaibao] 解压zip失败: {e}")
        return {'success': False, 'error': str(e)[:100]}


def 合并多个zip(zip文件列表: List[str], 输出路径: str) -> Dict:
    """合并多个 zip/session 到一个 zip（合并自 zhenghe.py）"""
    try:
        with zipfile.ZipFile(输出路径, 'w', zipfile.ZIP_DEFLATED) as zout:
            seen = set()
            for src_zip in zip文件列表:
                if not os.path.exists(src_zip):
                    continue
                with zipfile.ZipFile(src_zip, 'r') as zin:
                    for name in zin.namelist():
                        if name in seen or name.endswith('/'):
                            continue
                        data = zin.read(name)
                        if name.endswith('.session') or name.endswith('.json'):
                            zout.writestr(name, data)
                            seen.add(name)
        return {'success': True, 'path': 输出路径, 'count': len(seen)}
    except Exception as e:
        日志.error(f"[chaibao] 合并zip失败: {e}")
        return {'success': False, 'error': str(e)[:100]}


# ============================================================
# Session 链接解析（合并自 helpers.py parse_link）
# ============================================================
def 解析链接(link: str) -> str:
    """解析 Telegram 链接到纯用户名"""
    link = (link or '').strip()
    if link.startswith('@'):
        return link[1:]
    for prefix in ('https://t.me/', 'http://t.me/', 't.me/'):
        if link.lower().startswith(prefix):
            link = link[len(prefix):]
            break
    link = link.rstrip('/')
    if '/' in link:
        link = link.rsplit('/', 1)[-1]
    return link


# ============================================================
# JSON 读写工具（合并自 helpers.py）
# ============================================================
def load_json(path: str, default=None):
    if default is None:
        default = {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path: str, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[json] 保存失败: {e}")


# 公开 API
公开API = [
    'tr', 'lang_from_code', 'get_env_i18n',
    'convert_session_to_tdata', 'convert_tdata_to_session',
    '分析zip', '解压zip', '合并多个zip',
    '解析链接', 'load_json', 'save_json',
]


# 应用 Telethon 补丁
try:
    import 增强设备 as _dev
    _dev.应用Telethon补丁()
except Exception:
    pass
