"""代理管理模块 - 协议工具箱
作者: Lion
支持 socks5/http 代理的导入、存活检测、轮换（随机/轮询）、统计
"""
import os
import asyncio
import random
import json
from datetime import datetime
from 配置 import (
    项目根目录, 代理启用, 代理轮换模式, 代理最大失败, 日志
)
import 数据库 as db
from 工具 import 标准化代理, 代理转Telethon, 检测代理存活, 当前时间

# 代理轮换状态 {user_id: {'index': n, 'proxy_list': [...], 'mode': 'random'/'round_robin'}}
_轮换状态 = {}

def 获取代理轮换状态(user_id):
    if user_id not in _轮换状态:
        proxies = db.获取代理列表(user_id)
        _轮换状态[user_id] = {
            'index': 0,
            'proxy_list': [p['proxy_str'] for p in proxies],
            'mode': 代理轮换模式
        }
    return _轮换状态[user_id]

def 获取下一个代理(user_id):
    state = 获取代理轮换状态(user_id)
    if not state['proxy_list']:
        return None
    if state['mode'] == 'round_robin':
        proxy = state['proxy_list'][state['index'] % len(state['proxy_list'])]
        state['index'] = (state['index'] + 1) % len(state['proxy_list'])
        return proxy
    else:
        return random.choice(state['proxy_list'])

async def 导入代理列表(user_id, proxy_text):
    """导入代理列表，支持 ip:port 或 ip:port:user:pass 格式，每行一个"""
    lines = proxy_text.strip().split('\n')
    success = 0
    failed = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        proxy = 标准化代理(line)
        if proxy:
            if db.添加代理(user_id, proxy):
                success += 1
            else:
                failed += 1
        else:
            failed += 1
    # 清除轮换缓存
    if user_id in _轮换状态:
        del _轮换状态[user_id]
    return success, failed

async def 导入代理文件(user_id, file_path):
    """从文件导入代理列表"""
    if not os.path.exists(file_path):
        return 0, 0, "FILE_NOT_FOUND"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        success, failed = await 导入代理列表(user_id, content)
        return success, failed, None
    except Exception as e:
        return 0, 0, str(e)

async def 批量检测代理(user_id):
    """批量检测代理存活状态"""
    proxies = db.获取代理列表(user_id)
    if not proxies:
        return "没有代理可检测"
    results = []
    alive = 0
    dead = 0
    for p in proxies:
        is_alive = await 检测代理存活(p['proxy_str'])
        if is_alive:
            alive += 1
            db.更新代理状态(p['id'], 'active', 0)
            results.append(f"✅ {p['proxy_str'][:50]}... 存活")
        else:
            dead += 1
            new_fail = p['fail_count'] + 1
            if new_fail >= 代理最大失败:
                db.更新代理状态(p['id'], 'dead', new_fail)
            else:
                db.更新代理状态(p['id'], 'active', new_fail)
            results.append(f"❌ {p['proxy_str'][:50]}... 失败({new_fail}/{代理最大失败})")
    summary = f"代理检测完成: 存活 {alive}, 失败 {dead}, 总计 {alive + dead}"
    return summary + "\n" + "\n".join(results[:20])

def 获取代理统计(user_id):
    """获取代理统计信息"""
    proxies = db.获取代理列表(user_id)
    total = len(proxies)
    active = sum(1 for p in proxies if p['fail_count'] == 0)
    warn = sum(1 for p in proxies if 0 < p['fail_count'] < 代理最大失败)
    dead = sum(1 for p in proxies if p['fail_count'] >= 代理最大失败)
    return {
        'total': total,
        'active': active,
        'warn': warn,
        'dead': dead
    }

def 清空代理(user_id):
    """清空所有代理"""
    proxies = db.获取代理列表(user_id)
    for p in proxies:
        db.删除代理(p['id'], user_id)
    if user_id in _轮换状态:
        del _轮换状态[user_id]
    return len(proxies)

def 设置轮换模式(user_id, mode):
    """设置代理轮换模式: random / round_robin"""
    global _轮换状态
    if mode not in ('random', 'round_robin'):
        return False
    if user_id in _轮换状态:
        _轮换状态[user_id]['mode'] = mode
    return True