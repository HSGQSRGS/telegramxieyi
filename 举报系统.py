"""
举报系统模块 - 协议工具箱
作者: Lion
支持多种举报原因：虐待儿童、版权、虚假、毒品、色情、垃圾广告、暴力等
"""

import asyncio
import json
from datetime import datetime
from telethon import errors
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake,
    InputReportReasonIllegalDrugs, InputReportReasonPersonalDetails,
    InputReportReasonOther, InputReportReasonGeoIrrelevant,
    InputPeerUser, InputPeerChannel, InputPeerChat
)
from 配置 import 最小延迟, 最大延迟, 并发限制, 日志
import 数据库 as db
from 会话管理 import 获取账号客户端
from 设备伪装 import 举报原因映射
from 工具 import 当前时间, 构建进度条

# 举报原因映射（支持中文）
_举报原因映射 = {
    'spam': InputReportReasonSpam(),
    '垃圾广告': InputReportReasonSpam(),
    '垃圾': InputReportReasonSpam(),
    '广告': InputReportReasonSpam(),
    'violence': InputReportReasonViolence(),
    '暴力': InputReportReasonViolence(),
    '暴力内容': InputReportReasonViolence(),
    'pornography': InputReportReasonPornography(),
    '色情': InputReportReasonPornography(),
    '色情内容': InputReportReasonPornography(),
    'child_abuse': InputReportReasonChildAbuse(),
    '虐待儿童': InputReportReasonChildAbuse(),
    '儿童': InputReportReasonChildAbuse(),
    'copyright': InputReportReasonCopyright(),
    '版权': InputReportReasonCopyright(),
    '侵犯版权': InputReportReasonCopyright(),
    'fake': InputReportReasonFake(),
    '假冒': InputReportReasonFake(),
    '假冒身份': InputReportReasonFake(),
    '虚假': InputReportReasonFake(),
    'illegal_drugs': InputReportReasonIllegalDrugs(),
    '毒品': InputReportReasonIllegalDrugs(),
    '非法毒品': InputReportReasonIllegalDrugs(),
    'personal_details': InputReportReasonPersonalDetails(),
    '隐私': InputReportReasonPersonalDetails(),
    '泄露隐私': InputReportReasonPersonalDetails(),
    '人肉': InputReportReasonPersonalDetails(),
    'other': InputReportReasonOther(),
    '其他': InputReportReasonOther(),
    '其他原因': InputReportReasonOther(),
    'geo': InputReportReasonGeoIrrelevant(),
    '地理位置': InputReportReasonGeoIrrelevant(),
    '位置': InputReportReasonGeoIrrelevant(),
}

def 获取举报原因列表():
    """获取所有可用的举报原因"""
    return [
        {'id': 'spam', 'name': '垃圾广告', 'desc': '发送垃圾广告信息'},
        {'id': 'violence', 'name': '暴力内容', 'desc': '发布暴力相关内容'},
        {'id': 'pornography', 'name': '色情内容', 'desc': '发布色情内容'},
        {'id': 'child_abuse', 'name': '虐待儿童', 'desc': '涉及虐待儿童内容'},
        {'id': 'copyright', 'name': '侵犯版权', 'desc': '侵犯他人版权'},
        {'id': 'fake', 'name': '假冒身份', 'desc': '假冒他人身份'},
        {'id': 'illegal_drugs', 'name': '非法毒品', 'desc': '涉及非法毒品'},
        {'id': 'personal_details', 'name': '泄露隐私', 'desc': '泄露他人隐私信息'},
        {'id': 'other', 'name': '其他原因', 'desc': '其他违规原因'},
        {'id': 'geo', 'name': '地理位置', 'desc': '不当地理位置信息'},
    ]

def _解析举报原因(原因):
    """解析举报原因，支持中文和英文"""
    if 原因 in _举报原因映射:
        return _举报原因映射[原因]
    return InputReportReasonOther()

async def 举报单个目标(account, 目标, 原因='spam', 消息ID=None):
    """单个账号举报目标"""
    client = await 获取账号客户端(account)
    if not client:
        return False, "CLIENT_FAILED"

    try:
        reason_obj = _解析举报原因(原因)
        entity = await client.get_entity(目标)

        if 消息ID:
            await client(ReportRequest(
                peer=entity,
                id=[int(消息ID)],
                reason=reason_obj,
                message=""
            ))
        else:
            await client(ReportRequest(
                peer=entity,
                id=[],
                reason=reason_obj,
                message=""
            ))

        return True, None
    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        try:
            reason_obj = _解析举报原因(原因)
            entity = await client.get_entity(目标)
            await client(ReportRequest(
                peer=entity,
                id=[int(消息ID)] if 消息ID else [],
                reason=reason_obj,
                message=""
            ))
            return True, None
        except Exception as e2:
            return False, str(e2)
    except Exception as e:
        return False, str(e)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

async def 批量举报(user_id, 目标, 原因='spam', 消息ID=None, 进度回调=None):
    """
    批量举报目标
    使用用户所有活跃账号对目标进行举报
    """
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return {'success': 0, 'fail': 0, 'error': 'NO_ACCOUNTS', 'details': []}

    task_id = db.保存举报任务(
        user_id=user_id,
        target=目标,
        reason=原因,
        msg=str(消息ID) if 消息ID else None,
        total_count=len(accounts),
        status='running'
    )

    results = {'success': 0, 'fail': 0, 'task_id': task_id, 'details': []}

    import random
    from 配置 import 最小延迟, 最大延迟

    for i, acc in enumerate(accounts):
        success, error = await 举报单个目标(acc, 目标, 原因, 消息ID)
        if success:
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'target': 目标, 'reason': 原因
            })
        else:
            results['fail'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'fail', 'error': error or 'UNKNOWN',
                'target': 目标, 'reason': 原因
            })

        if 进度回调:
            await 进度回调(i + 1, len(accounts))

        if i < len(accounts) - 1:
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))

    db.更新举报任务(task_id, results['success'], results['fail'], 'completed')
    return results

async def 批量举报多目标(user_id, 目标列表, 进度回调=None):
    """
    批量举报多个目标
    目标列表格式: [{'target': '@username', 'reason': 'spam', 'msg': '123'}, ...]
    """
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return {'success': 0, 'fail': 0, 'error': 'NO_ACCOUNTS', 'details': []}

    total_reports = 0
    results = {'success': 0, 'fail': 0, 'details': []}

    import random
    from 配置 import 最小延迟, 最大延迟

    for target_info in 目标列表:
        if isinstance(target_info, str):
            target = target_info
            reason = 'spam'
            msg_id = None
        else:
            target = target_info.get('target', '')
            reason = target_info.get('reason', 'spam')
            msg_id = target_info.get('msg', None)

        if not target:
            continue

        for i, acc in enumerate(accounts):
            success, error = await 举报单个目标(acc, target, reason, msg_id)
            if success:
                results['success'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'status': 'success',
                    'target': target, 'reason': reason
                })
            else:
                results['fail'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'status': 'fail',
                    'error': error or 'UNKNOWN', 'target': target, 'reason': reason
                })

            total_reports += 1
            if 进度回调:
                await 进度回调(total_reports, len(目标列表) * len(accounts))

            if i < len(accounts) - 1:
                await asyncio.sleep(random.uniform(最小延迟, 最大延迟))

    return results

async def 循环举报(user_id, 目标, 原因='spam', 循环次数=3, 间隔秒=60, 进度回调=None):
    """循环举报目标（多次举报）"""
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return {'success': 0, 'fail': 0, 'error': 'NO_ACCOUNTS', 'details': []}

    results = {'success': 0, 'fail': 0, 'cycles': 0, 'details': []}

    for cycle in range(循环次数):
        cycle_results = await 批量举报(user_id, 目标, 原因, None, 进度回调)
        results['success'] += cycle_results['success']
        results['fail'] += cycle_results['fail']
        results['details'].extend(cycle_results.get('details', []))
        results['cycles'] = cycle + 1

        if cycle < 循环次数 - 1:
            await asyncio.sleep(间隔秒)

    return results

def 获取举报历史(user_id):
    """获取举报任务历史"""
    return db.获取举报任务(user_id)

def 格式化举报结果(结果):
    """格式化举报结果为可读文本"""
    if 结果.get('error'):
        return f"❌ 举报失败: {结果['error']}"

    total = 结果['success'] + 结果['fail']
    text = "📊 举报结果:\n"
    text += f"├─ ✅ 成功: {结果['success']}\n"
    text += f"├─ ❌ 失败: {结果['fail']}\n"
    if 结果.get('cycles'):
        text += f"├─ 🔄 循环: {结果['cycles']} 次\n"
    text += f"└─ 📊 总计: {total}"

    details = 结果.get('details', [])[:10]
    if details:
        text += "\n\n📋 详情:"
        for d in details:
            p = d.get('phone', 'N/A')
            s = d.get('status', '')
            t = d.get('target', '')
            r = d.get('reason', '')
            err = d.get('error', '')
            icon = "✅" if s == 'success' else "❌"
            line = f"\n{icon} {p} → {t} ({r})"
            if err:
                line += f" - {err[:50]}"
            text += line

    return text

def 格式化举报历史(user_id):
    """格式化举报历史"""
    tasks = 获取举报历史(user_id)
    if not tasks:
        return "暂无举报记录"

    text = "📋 举报历史:\n"
    for task in tasks[:20]:
        icon = "✅" if task['status'] == 'completed' else "🔄" if task['status'] == 'running' else "⏳"
        text += f"\n{icon} {task['created_at']} | {task['target']}"
        text += f"\n   原因: {task['reason']} | 成功: {task['success_count']} | 失败: {task['fail_count']}"
        text += f"\n   状态: {task['status']}"

    return text