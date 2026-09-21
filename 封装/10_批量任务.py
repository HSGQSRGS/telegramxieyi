"""批量任务引擎 + 隐私批量设置 — 协议工具箱
作者: Lion

合并自 GAFBot:
- task_engine.py  BatchTask 通用任务执行器
- yinsi.py        隐私设置（手机号/最近在线/转发/头像可见性）
"""

import asyncio
import json
import os
import zipfile
from datetime import datetime
from typing import Optional, List, Callable, Awaitable, Dict, Any

from 配置 import 日志
import 数据库 as db


# ============================================================
# 批量任务引擎 (合并自 task_engine.py)
# ============================================================
class BatchTask:
    """通用并发批量任务执行器"""

    def __init__(self, 用户id: int, 任务名: str, 并发: int = 5, 超时: int = 3600):
        self.user_id = 用户id
        self.name = 任务名
        self.semaphore = asyncio.Semaphore(并发)
        self.stop_event = asyncio.Event()
        self.timeout_event = asyncio.Event()
        self.results = {'success': [], 'fail': []}
        self.progress = {'done': 0, 'total': 0}
        self.status_msg = None
        self.stop_callback = None
        self._watchdog_task = None
        self.created_at = datetime.now()

    async def start_watchdog(self, on_timeout: Callable):
        """启动超时看门狗"""
        async def _wd():
            try:
                # 默认 1 小时超时
                await asyncio.sleep(3600)
                self.stop_event.set()
                self.timeout_event.set()
                try:
                    await on_timeout()
                except Exception:
                    pass
            except asyncio.CancelledError:
                pass
        self._watchdog_task = asyncio.create_task(_wd())

    def cancel_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

    def request_stop(self):
        self.stop_event.set()


活跃任务 = {}  # user_id -> BatchTask


def 获取活跃任务(user_id: int) -> Optional[BatchTask]:
    return 活跃任务.get(user_id)


def 设置活跃任务(user_id: int, task: BatchTask):
    活跃任务[user_id] = task


def 清除活跃任务(user_id: int):
    if user_id in 活跃任务:
        del 活跃任务[user_id]


async def run_batch(items: List[Any],
                  process_one: Callable[[Any], Awaitable[Dict]],
                  on_progress: Optional[Callable] = None,
                  progress_text_fn: Optional[Callable] = None,
                  stop_event: Optional[asyncio.Event] = None,
                  并发: int = 5,
                  timeout: int = 3600) -> Dict:
    """通用并发执行器

    参数:
        items: 待处理项列表
        process_one: 单项处理函数 (item) -> {success: bool, ...}
        on_progress: 每完成一项回调 (done, total, success, fail)
        progress_text_fn: 返回当前进度的文本
        stop_event: 主动停止事件
        并发: 同时进行的协程数
    """
    results = {'success': [], 'fail': [], 'cancelled': []}
    semaphore = asyncio.Semaphore(并发)
    total = len(items)
    done = [0]
    success_c = [0]
    fail_c = [0]

    async def _worker(item, idx):
        async with semaphore:
            if stop_event and stop_event.is_set():
                results['cancelled'].append(idx)
                return
            try:
                r = await process_one(item)
                if r.get('success'):
                    results['success'].append({'index': idx, **r})
                    success_c[0] += 1
                else:
                    results['fail'].append({'index': idx, **r})
                    fail_c[0] += 1
            except Exception as e:
                results['fail'].append({'index': idx, 'error': str(e)[:100]})
                fail_c[0] += 1
            done[0] += 1
            if on_progress:
                try:
                    await on_progress(done[0], total, success_c[0], fail_c[0])
                except Exception:
                    pass

    tasks = [_worker(item, i) for i, item in enumerate(items)]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results


async def 打包分类结果(results: Dict, 输出路径: str = 'results.zip') -> str:
    """将 success / fail 分类打包到 zip"""
    try:
        with zipfile.ZipFile(输出路径, 'w', zipfile.ZIP_DEFLATED) as z:
            for cat in ['success', 'fail', 'cancelled']:
                items = results.get(cat, [])
                if isinstance(items, list):
                    for i, r in enumerate(items):
                        try:
                            z.writestr(f'{cat}/{i}.json', json.dumps(r, ensure_ascii=False, indent=2))
                        except Exception:
                            pass
        return os.path.abspath(输出路径)
    except Exception as e:
        日志.error(f"[task] 打包失败: {e}")
        return ''


# ============================================================
# 隐私设置 (合并自 yinsi.py)
# ============================================================
隐私项映射 = {
    'phone':           ('隐私: 手机号可见性',     'phone'),
    'last_seen':       ('隐私: 在线状态可见性',   'lastSeen'),
    'forward':         ('隐私: 转发消息来源',     'forwards'),
    'profile_photo':   ('隐私: 头像可见性',       'profilePhotos'),
    'bio':             ('隐私: 简介可见性',       'bio'),
    'call':            ('隐私: 通话许可',         'calls'),
    'group_call':      ('隐私: 群组通话',         'groupCalls'),
    'messages':        ('隐私: 私信许可',         'messages'),
    'invite':          ('隐私: 邀请到群',         'invite'),
    'voice_video':     ('隐私: 语音/视频通话',    'voiceVideo'),
}

隐私范围映射 = {
    'everyone':    '所有人',
    'contacts':    '仅联系人',
    'nobody':      '谁都不行',
    'non_contacts': '非联系人',
}

隐私key导入映射 = {
    'phone':         'InputPrivacyKeyPhoneNumber',
    'last_seen':     'InputPrivacyKeyStatusTimestamp',
    'forward':       'InputPrivacyKeyForwards',
    'profile_photo': 'InputPrivacyKeyProfilePhotos',
    'bio':           'InputPrivacyKeyAbout',
    'call':          'InputPrivacyKeyPhoneCallSettings',
    'group_call':    'InputPrivacyKeyPhoneCallP2P',
    'messages':      'InputPrivacyKeyMessages',
    'invite':        'InputPrivacyKeyChatInvite',
    'voice_video':   'InputPrivacyKeyVoiceVideoCalls',
}

隐私范围类映射 = {
    'everyone':     'InputPrivacyValueAllowAll',
    'contacts':     'InputPrivacyValueAllowContacts',
    'nobody':       'InputPrivacyValueDisallowAll',
    'non_contacts': 'InputPrivacyValueDisallowContacts',
}


async def 应用隐私设置(client, 项目: str, 范围: str) -> bool:
    """应用一项隐私设置"""
    try:
        from telethon.tl.functions.account import SetPrivacyRequest
        from telethon import tl

        key_cls = getattr(tl, 隐私key导入映射.get(项目))
        rule_cls = getattr(tl, 隐私范围类映射.get(范围))

        rule = rule_cls()
        rules = [rule]

        await client(SetPrivacyRequest(key=key_cls(), rules=rules))
        return True
    except Exception as e:
        日志.error(f"[yinsi] {项目}={范围} 失败: {e}")
        return False


async def 批量设置隐私(accounts: List[dict], 项目: str, 范围: str,
                    进度回调=None) -> Dict:
    """对多个账号批量设置同一项隐私"""
    from 会话管理 import 获取账号客户端
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            ok = await 应用隐私设置(client, 项目, 范围)
            if ok:
                results['success'] += 1
                results['details'].append({'phone': acc.get('phone'), 'status': 'set'})
            else:
                results['fail'] += 1
                results['details'].append({'phone': acc.get('phone'), 'status': 'fail'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(0.5)
    return results


async def 批量一键锁定(accounts: List[dict], 进度回调=None) -> Dict:
    """对一组账号隐藏所有隐私 → 锁定"""
    results_by_field = {}
    for 项目 in ['phone', 'last_seen', 'forward', 'profile_photo', 'voice_video']:
        r = await 批量设置隐私(accounts, 项目, 'nobody', 进度回调)
        results_by_field[项目] = r
    return results_by_field


async def 批量一键开放(accounts: List[dict], 进度回调=None) -> Dict:
    """对一组账号开放所有隐私"""
    results_by_field = {}
    for 项目 in ['phone', 'last_seen', 'forward', 'profile_photo', 'voice_video']:
        r = await 批量设置隐私(accounts, 项目, 'everyone', 进度回调)
        results_by_field[项目] = r
    return results_by_field


# ============================================================
# 公开 API
# ============================================================
公开API = [
    'BatchTask', 'run_batch', '打包分类结果',
    '获取活跃任务', '设置活跃任务', '清除活跃任务',
    '应用隐私设置', '批量设置隐私', '批量一键锁定', '批量一键开放',
    '隐私项映射', '隐私范围映射',
]
