"""增强设备 — 协议工具箱
作者: Lion

合并自封禁机器人 /bot/cooldown.py + /bot/device.py + /bot/patch.py + /bot/proxy.py
- 设备指纹池（15 设备 × 16 语言）
- Telethon InitConnection 猴子补丁
- 冷却期管理
- SOCKS 代理转换
"""

import json
import os
import random
import time
from typing import Optional

try:
    from telethon import TelegramClient
    from telethon.tl.types import (
        JsonObject, JsonObjectValue, JsonNumber, JsonString,
    )
    TELETHON_AVAILABLE = True
except Exception:
    TELETHON_AVAILABLE = False

try:
    import socks
    SOCKS_AVAILABLE = True
except Exception:
    SOCKS_AVAILABLE = False

from 配置 import 日志


# ============================================================
# 设备指纹池（合并自 device.py）
# ============================================================
DEVICE_POOL = [
    {'device_model': 'iPhone 15 Pro',     'system_version': 'iOS 17.4.1',  'app_version': '10.6.2'},
    {'device_model': 'iPhone 14',         'system_version': 'iOS 17.2',    'app_version': '10.5.1'},
    {'device_model': 'iPhone 13 Pro',     'system_version': 'iOS 16.7.2',  'app_version': '10.4.4'},
    {'device_model': 'iPhone 12',         'system_version': 'iOS 16.5',    'app_version': '10.3.0'},
    {'device_model': 'iPhone 15 Pro Max', 'system_version': 'iOS 17.5',    'app_version': '10.6.2'},
    {'device_model': 'iPhone SE (3rd gen)','system_version': 'iOS 16.3',   'app_version': '10.2.1'},
    {'device_model': 'Samsung Galaxy S24','system_version': 'Android 14',  'app_version': '10.6.0'},
    {'device_model': 'Samsung Galaxy S23','system_version': 'Android 13',  'app_version': '10.5.0'},
    {'device_model': 'Samsung Galaxy A54','system_version': 'Android 14',  'app_version': '10.4.0'},
    {'device_model': 'Pixel 8 Pro',       'system_version': 'Android 14',  'app_version': '10.6.1'},
    {'device_model': 'Pixel 7',           'system_version': 'Android 13',  'app_version': '10.3.2'},
    {'device_model': 'Xiaomi 14',         'system_version': 'Android 14',  'app_version': '10.5.1'},
    {'device_model': 'OnePlus 12',        'system_version': 'Android 14',  'app_version': '10.4.3'},
    {'device_model': 'Huawei P60 Pro',    'system_version': 'Android 12',  'app_version': '10.3.0'},
    {'device_model': 'iPhone 16 Pro',     'system_version': 'iOS 18.0',    'app_version': '10.7.0'},
]

LANG_POOL = [
    ('en', 'US'), ('en', 'GB'), ('zh', 'CN'), ('ja', 'JP'),
    ('ko', 'KR'), ('de', 'DE'), ('fr', 'FR'), ('es', 'ES'),
    ('ru', 'RU'), ('pt', 'BR'), ('it', 'IT'), ('tr', 'TR'),
    ('id', 'ID'), ('vi', 'VN'), ('th', 'TH'), ('ar', 'SA'),
]


_设备分配缓存 = {}
_设备分配文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'device_assign.json')


def _加载设备分配():
    global _设备分配缓存
    try:
        if os.path.exists(_设备分配文件):
            with open(_设备分配文件, 'r', encoding='utf-8') as f:
                _设备分配缓存 = json.load(f)
    except Exception:
        pass
    return _设备分配缓存


def _保存设备分配():
    try:
        with open(_设备分配文件, 'w', encoding='utf-8') as f:
            json.dump(_设备分配缓存, f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[device] 保存失败: {e}")


def 获取设备(session_key: str) -> dict:
    """为每个 session 持久化分配一个随机设备指纹"""
    _加载设备分配()
    if session_key in _设备分配缓存:
        return _设备分配缓存[session_key]
    device = random.choice(DEVICE_POOL)
    lang_code, lang = random.choice(LANG_POOL)
    assignment = {
        'device_model': device['device_model'],
        'system_version': device['system_version'],
        'app_version': device['app_version'],
        'lang_code': lang_code,
        'system_lang_code': lang,
    }
    _设备分配缓存[session_key] = assignment
    _保存设备分配()
    return assignment


def 重置所有设备():
    """重置所有设备分配（管理员触发）"""
    global _设备分配缓存
    _设备分配缓存 = {}
    _保存设备分配()


# ============================================================
# Telethon InitConnection monkey-patch
# ============================================================
_original_connect = TelegramClient.connect if TELETHON_AVAILABLE else None


def _build_random_params():
    """构建随机 JsonObject 用于 InitConnection"""
    values = []
    TZ_POOL = [0, 3600, 7200, 10800]
    values.append(JsonObjectValue(
        key='tz_offset',
        value=JsonNumber(random.choice(TZ_POOL))
    ))
    if random.random() > 0.5:
        values.append(JsonObjectValue(
            key='theme',
            value=JsonString(random.choice(['light', 'dark']))
        ))
    if random.random() > 0.7:
        values.append(JsonObjectValue(
            key='battery',
            value=JsonNumber(random.randint(10, 100))
        ))
    if random.random() > 0.7:
        values.append(JsonObjectValue(
            key='sw',
            value=JsonNumber(random.choice([393, 414, 360, 428, 375]))
        ))
    return JsonObject(values=values)


def _patched_connect(self, *args, **kwargs):
    if hasattr(self, '_init_request') and self._init_request is not None:
        try:
            self._init_request.params = _build_random_params()
        except Exception:
            pass
    return _original_connect(self, *args, **kwargs)


_补丁已应用 = False


def 应用Telethon补丁():
    """应用 Telethon 猴子补丁（仅一次）"""
    global _补丁已应用
    if _补丁已应用 or not TELETHON_AVAILABLE:
        return
    try:
        TelegramClient.connect = _patched_connect
        _补丁已应用 = True
        日志.info('[patch] Telethon InitConnection 随机化已启用')
    except Exception as e:
        日志.warning(f'[patch] 应用失败: {e}')


# ============================================================
# 冷却期管理（合并自 cooldown.py）
# ============================================================
_冷却文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cooldown.json')
_冷却期秒 = 30 * 60  # 30 分钟


def 加载冷却():
    try:
        if os.path.exists(_冷却文件):
            with open(_冷却文件, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def 保存冷却(data: dict):
    try:
        with open(_冷却文件, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[cooldown] 保存失败: {e}")


def 在冷却中(session_key: str) -> bool:
    cd = 加载冷却()
    if session_key not in cd:
        return False
    elapsed = time.time() - cd[session_key]
    return elapsed < _冷却期秒


def 设置冷却(session_key: str):
    cd = 加载冷却()
    cd[session_key] = time.time()
    保存冷却(cd)


def 冷却剩余(session_key: str) -> int:
    cd = 加载冷却()
    if session_key not in cd:
        return 0
    elapsed = time.time() - cd[session_key]
    return max(0, int(_冷却期秒 - elapsed))


def 冷却摘要(sessions: list) -> str:
    """返回 'X可用 / Y休息中'"""
    avail = sum(1 for s in sessions if not 在冷却中(s))
    rest = sum(1 for s in sessions if 在冷却中(s))
    return f'{avail}可用 / {rest}休息中'


def 获取可用session(sessions: list) -> list:
    return [s for s in sessions if not 在冷却中(s)]


def 获取冷却中session(sessions: list) -> list:
    return [s for s in sessions if 在冷却中(s)]


# ============================================================
# 代理加载（合并自 proxy.py）
# ============================================================
_代理文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proxies.json')


def 加载代理() -> list:
    try:
        if os.path.exists(_代理文件):
            with open(_代理文件, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def 保存代理(data: list):
    try:
        with open(_代理文件, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[proxy] 保存失败: {e}")


def 取session代理(index: int) -> Optional[tuple]:
    """根据索引轮询取代理，返回 Telethon 可用 tuple 或 None"""
    if not SOCKS_AVAILABLE:
        return None
    proxies = 加载代理()
    if not proxies:
        return None
    proxy = proxies[index % len(proxies)]
    ptype = proxy.get('type', 'socks5')
    mapping = {'socks5': socks.SOCKS5, 'socks4': socks.SOCKS4, 'http': socks.HTTP}
    proto = mapping.get(ptype)
    if proto is None:
        return None
    return (proto, proxy['host'], int(proxy['port']))


# ============================================================
# 验证 session 文件（启动时清理）
# ============================================================
import sqlite3


def 验证session文件(文件路径: str) -> bool:
    """用 sqlite3 验证文件是否是合法 session"""
    try:
        if not os.path.exists(文件路径) or os.path.getsize(文件路径) == 0:
            return False
        conn = sqlite3.connect(f'file:{文件路径}?mode=ro', uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False


def 清理损坏session(目录: str) -> tuple:
    """清理损坏的 session 文件，返回 (保留, 删除)"""
    if not os.path.isdir(目录):
        return (0, 0)
    kept, deleted = 0, 0
    for f in os.listdir(目录):
        if not f.endswith('.session'):
            continue
        path = os.path.join(目录, f)
        if 验证session文件(path):
            kept += 1
        else:
            try:
                os.remove(path)
                deleted += 1
            except OSError:
                pass
    return (kept, deleted)


# ============================================================
# 公开 API
# ============================================================
公开API = [
    '获取设备', '重置所有设备',
    '应用Telethon补丁',
    '在冷却中', '设置冷却', '冷却剩余', '冷却摘要', '获取可用session', '获取冷却中session',
    '加载代理', '保存代理', '取session代理',
    '验证session文件', '清理损坏session',
]
