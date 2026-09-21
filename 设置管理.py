"""
设置管理模块 - 协议工具箱
作者: Lion
可自定义的设置管理：
- 监听设置（关键词、回复、转发目标）
- 守护设置（验证码监控、自动杀设备、主权模式）
- 举报设置（默认举报原因）
- 代理设置（轮换模式）
- 延迟设置（各操作延迟范围）
- 隐私设置
"""

import json
import 数据库 as db
from 配置 import (
    最小延迟, 最大延迟, 最小反应延迟, 最大反应延迟,
    最小加群延迟, 最大加群延迟, 最小发送延迟, 最大发送延迟,
    代理轮换模式, 日志
)

# ==================== 获取当前设置 ====================

def 获取全部设置(user_id):
    """获取用户全部设置（合并数据库和默认值）"""
    settings = db.获取用户设置(user_id)
    if not settings:
        return _默认设置()

    result = _默认设置()
    result.update({
        'monitor_code': bool(settings.get('monitor_code', 1)),
        'consume_code': bool(settings.get('consume_code', 1)),
        'auto_kill': bool(settings.get('auto_kill', 0)),
        'guardian_active': bool(settings.get('guardian_active', 0)),
        'sovereign_active': bool(settings.get('sovereign_active', 0)),
        'sovereign_since': settings.get('sovereign_since', ''),
        'monitor_active': bool(settings.get('monitor_active', 0)),
        'monitor_forward_target': settings.get('monitor_forward_target', ''),
        'guardian_consume_bot': settings.get('guardian_consume_bot', ''),
    })

    # 解析 JSON 字段
    try:
        result['monitor_keywords'] = json.loads(settings.get('monitor_keywords', '[]'))
    except Exception:
        result['monitor_keywords'] = []

    try:
        result['monitor_auto_reply'] = json.loads(settings.get('monitor_auto_reply', '{}'))
    except Exception:
        result['monitor_auto_reply'] = {}

    try:
        result['whitelist_devices'] = json.loads(settings.get('whitelist_devices', '[]'))
    except Exception:
        result['whitelist_devices'] = []

    return result

def _默认设置():
    """默认设置"""
    return {
        'monitor_code': True,
        'consume_code': True,
        'auto_kill': False,
        'guardian_active': False,
        'sovereign_active': False,
        'sovereign_since': '',
        'monitor_active': False,
        'monitor_forward_target': '',
        'guardian_consume_bot': '',
        'monitor_keywords': ['飞机号', '协议号', '出售', '担保', '收号', '出号'],
        'monitor_auto_reply': {},
        'whitelist_devices': [],
        'delay_min': 最小延迟,
        'delay_max': 最大延迟,
        'reaction_delay_min': 最小反应延迟,
        'reaction_delay_max': 最大反应延迟,
        'join_delay_min': 最小加群延迟,
        'join_delay_max': 最大加群延迟,
        'send_delay_min': 最小发送延迟,
        'send_delay_max': 最大发送延迟,
        'proxy_rotation_mode': 代理轮换模式,
        'default_report_reason': 'spam',
    }

# ==================== 监听设置 ====================

async def 设置监听关键词(user_id, 关键词列表):
    """设置监听关键词"""
    if isinstance(关键词列表, str):
        关键词列表 = [k.strip() for k in 关键词列表.split(',') if k.strip()]
    db.更新用户设置(user_id, 'monitor_keywords', json.dumps(关键词列表, ensure_ascii=False))
    return True, f"关键词已更新（{len(关键词列表)} 个）"

async def 设置监听转发目标(user_id, 目标):
    """设置转发目标群组"""
    db.更新用户设置(user_id, 'monitor_forward_target', 目标)
    return True, f"转发目标已设置为: {目标}"

async def 设置自动回复规则(user_id, 回复规则):
    """
    设置自动回复规则
    格式: {"关键词1": "回复内容1", "关键词2": "回复内容2"}
    """
    if isinstance(回复规则, str):
        try:
            回复规则 = json.loads(回复规则)
        except Exception:
            return False, "JSON格式错误"
    db.更新用户设置(user_id, 'monitor_auto_reply', json.dumps(回复规则, ensure_ascii=False))
    return True, f"回复规则已设置（{len(回复规则)} 条）"

# ==================== 守护设置 ====================

async def 设置验证码监控(user_id, 启用=True):
    """设置是否监控验证码"""
    db.更新用户设置(user_id, 'monitor_code', 1 if 启用 else 0)
    return True, f"验证码监控: {'已开启' if 启用 else '已关闭'}"

async def 设置验证码消耗(user_id, 启用=True):
    """设置是否自动消耗验证码"""
    db.更新用户设置(user_id, 'consume_code', 1 if 启用 else 0)
    return True, f"验证码消耗: {'已开启' if 启用 else '已关闭'}"

async def 设置自动杀设备(user_id, 启用=True):
    """设置是否自动查杀非白名单设备"""
    db.更新用户设置(user_id, 'auto_kill', 1 if 启用 else 0)
    return True, f"自动杀设备: {'已开启' if 启用 else '已关闭'}"

async def 设置消耗机器人(user_id, 机器人用户名):
    """设置验证码消耗转发机器人"""
    db.更新用户设置(user_id, 'guardian_consume_bot', 机器人用户名)
    return True, f"消耗机器人已设置为: {机器人用户名}"

async def 设置白名单设备(user_id, 设备列表):
    """设置设备白名单"""
    db.更新用户设置(user_id, 'whitelist_devices', json.dumps(设备列表, ensure_ascii=False))
    return True, f"白名单已更新（{len(设备列表)} 个设备）"

# ==================== 延迟设置 ====================

async def 设置操作延迟(user_id, 操作类型, 最小值, 最大值):
    """设置各类操作的延迟范围"""
    valid_types = ['delay', 'reaction', 'join', 'send']
    if 操作类型 not in valid_types:
        return False, "无效的操作类型"

    field_map = {
        'delay': ('delay_min', 'delay_max'),
        'reaction': ('reaction_delay_min', 'reaction_delay_max'),
        'join': ('join_delay_min', 'join_delay_max'),
        'send': ('send_delay_min', 'send_delay_max'),
    }

    min_field, max_field = field_map[操作类型]
    db.更新用户设置(user_id, min_field, str(最小值))
    db.更新用户设置(user_id, max_field, str(最大值))

    return True, f"{操作类型} 延迟: {最小值}-{最大值} 秒"

# ==================== 举报设置 ====================

async def 设置默认举报原因(user_id, 原因):
    """设置默认举报原因"""
    valid_reasons = ['spam', 'violence', 'pornography', 'child_abuse', 'copyright',
                     'fake', 'illegal_drugs', 'personal_details', 'other', 'geo',
                     '垃圾广告', '暴力', '色情', '虐待儿童', '版权', '假冒', '毒品', '隐私', '其他']
    if 原因 not in valid_reasons:
        return False, f"无效的举报原因，可选: {', '.join(valid_reasons)}"
    db.更新用户设置(user_id, 'default_report_reason', 原因)
    return True, f"默认举报原因已设置为: {原因}"

# ==================== 代理设置 ====================

async def 设置代理轮换模式(user_id, 模式):
    """设置代理轮换模式"""
    if 模式 not in ('random', 'round_robin'):
        return False, "模式只支持 random 或 round_robin"
    db.更新用户设置(user_id, 'proxy_rotation_mode', 模式)
    from 代理管理 import 设置轮换模式
    设置轮换模式(user_id, 模式)
    return True, f"代理轮换模式: {模式}"

# ==================== 设置导出/导入 ====================

def 导出设置(user_id):
    """导出用户设置为JSON"""
    settings = 获取全部设置(user_id)
    return json.dumps(settings, ensure_ascii=False, indent=2)

async def 导入设置(user_id, 设置JSON):
    """从JSON导入设置"""
    try:
        if isinstance(设置JSON, str):
            settings = json.loads(设置JSON)
        else:
            settings = 设置JSON
    except Exception:
        return False, "JSON格式错误"

    field_map = {
        'monitor_code': 'monitor_code',
        'consume_code': 'consume_code',
        'auto_kill': 'auto_kill',
        'guardian_active': 'guardian_active',
        'sovereign_active': 'sovereign_active',
        'monitor_active': 'monitor_active',
        'monitor_forward_target': 'monitor_forward_target',
        'guardian_consume_bot': 'guardian_consume_bot',
    }

    for key, db_field in field_map.items():
        if key in settings:
            val = settings[key]
            if isinstance(val, bool):
                val = 1 if val else 0
            db.更新用户设置(user_id, db_field, val)

    json_fields = {
        'monitor_keywords': 'monitor_keywords',
        'monitor_auto_reply': 'monitor_auto_reply',
        'whitelist_devices': 'whitelist_devices',
    }

    for key, db_field in json_fields.items():
        if key in settings:
            db.更新用户设置(user_id, db_field, json.dumps(settings[key], ensure_ascii=False))

    return True, "设置导入成功"

# ==================== 格式化设置显示 ====================

def 格式化设置显示(user_id):
    """格式化显示当前设置"""
    settings = 获取全部设置(user_id)

    text = "⚙️ **当前设置**\n\n"

    # 守护设置
    text += "🛡️ **守护设置**\n"
    text += f"├─ 验证码监控: {'✅ 开启' if settings['monitor_code'] else '❌ 关闭'}\n"
    text += f"├─ 验证码消耗: {'✅ 开启' if settings['consume_code'] else '❌ 关闭'}\n"
    text += f"├─ 自动杀设备: {'✅ 开启' if settings['auto_kill'] else '❌ 关闭'}\n"
    text += f"├─ 守护状态: {'✅ 运行中' if settings['guardian_active'] else '❌ 未启动'}\n"
    text += f"├─ 主权模式: {'👑 已开启' if settings['sovereign_active'] else '❌ 未启动'}\n"
    text += f"└─ 消耗机器人: {settings['guardian_consume_bot'] or '未设置'}\n"

    # 监听设置
    text += "\n👂 **监听设置**\n"
    text += f"├─ 监听状态: {'✅ 运行中' if settings['monitor_active'] else '❌ 未启动'}\n"
    text += f"├─ 关键词: {', '.join(settings['monitor_keywords']) if settings['monitor_keywords'] else '未设置'}\n"
    text += f"├─ 转发目标: {settings['monitor_forward_target'] or '未设置'}\n"
    auto_reply = settings['monitor_auto_reply']
    text += f"└─ 回复规则: {len(auto_reply)} 条\n"
    if auto_reply:
        for k, v in list(auto_reply.items())[:5]:
            text += f"      {k} → {v[:30]}\n"

    # 延迟设置
    text += "\n⏱️ **延迟设置**\n"
    text += f"├─ 通用延迟: {settings['delay_min']}-{settings['delay_max']}秒\n"
    text += f"├─ 点赞延迟: {settings['reaction_delay_min']}-{settings['reaction_delay_max']}秒\n"
    text += f"├─ 加群延迟: {settings['join_delay_min']}-{settings['join_delay_max']}秒\n"
    text += f"└─ 发送延迟: {settings['send_delay_min']}-{settings['send_delay_max']}秒\n"

    # 代理设置
    text += "\n🌐 **代理设置**\n"
    text += f"└─ 轮换模式: {settings['proxy_rotation_mode']}\n"

    # 举报设置
    text += "\n🚨 **举报设置**\n"
    text += f"└─ 默认原因: {settings['default_report_reason']}\n"

    return text