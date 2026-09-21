"""封禁机器人核心 — 协议工具箱
作者: Lion

合并自原「封禁机器人源码」：
- 10 种 Telegram API 举报原因
- AI 智能超级举报（OpenAI 兼容）
- 欧盟法律参考（DSA/儿童保护/GDPR 等）
- 自定义举报（自由文本 / 消息 ID）
- 用户举报（头像 + 个人资料触发）
- 多账号并发执行
"""

import asyncio
import json
import random
import re
import os
from typing import Optional, List, Dict, Any, Callable

import httpx

try:
    from telethon import TelegramClient
    from telethon.tl.functions.account import ReportPeerRequest, ReportProfilePhotoRequest
    from telethon.tl.functions.messages import (
        ReportRequest as MsgReportRequest,
        ReportSpamRequest as MsgReportSpamRequest,
    )
    from telethon.tl.functions.channels import ReportSpamRequest as ChanReportSpamRequest
    from telethon.tl.types import (
        InputReportReasonSpam,
        InputReportReasonViolence,
        InputReportReasonPornography,
        InputReportReasonChildAbuse,
        InputReportReasonOther,
        InputReportReasonCopyright,
        InputReportReasonGeoIrrelevant,
        InputReportReasonFake,
        InputReportReasonIllegalDrugs,
        InputReportReasonPersonalDetails,
    )
    TELETHON_AVAILABLE = True
except Exception:
    TELETHON_AVAILABLE = False

from 配置 import 日志, 数据库路径
import 数据库 as db
from 工具 import 当前时间, 安全截断


# ============================================================
# 10 种举报原因（合并自封禁机器人 /bot/reasons.py）
# ============================================================
REPORT_REASONS = {
    'spam':             ('🚫 垃圾信息',     InputReportReasonSpam() if TELETHON_AVAILABLE else None),
    'violence':         ('💀 暴力威胁',     InputReportReasonViolence() if TELETHON_AVAILABLE else None),
    'pornography':      ('🔞 色情内容',     InputReportReasonPornography() if TELETHON_AVAILABLE else None),
    'child_abuse':      ('👶 儿童虐待',     InputReportReasonChildAbuse() if TELETHON_AVAILABLE else None),
    'copyright':        ('©️ 版权侵犯',     InputReportReasonCopyright() if TELETHON_AVAILABLE else None),
    'fake':             ('🎭 虚假诈骗',     InputReportReasonFake() if TELETHON_AVAILABLE else None),
    'illegal_drugs':    ('💊 非法毒品',     InputReportReasonIllegalDrugs() if TELETHON_AVAILABLE else None),
    'personal_details': ('🔓 隐私泄露',     InputReportReasonPersonalDetails() if TELETHON_AVAILABLE else None),
    'geo_irrelevant':   ('🌍 位置无关',     InputReportReasonGeoIrrelevant() if TELETHON_AVAILABLE else None),
    'other':            ('📋 其他',         InputReportReasonOther() if TELETHON_AVAILABLE else None),
}

REASON_CN = {
    'child_abuse': '儿童虐待', 'illegal_drugs': '非法毒品',
    'violence': '暴力', 'pornography': '色情',
    'spam': '垃圾信息', 'fake': '虚假/诈骗',
    'copyright': '版权侵犯', 'personal_details': '个人信息泄露',
    'geo_irrelevant': '地理位置不相关', 'other': '其他',
}


# ============================================================
# 举报原因解析（中文/英文）
# ============================================================
def 解析举报原因(原因):
    """解析举报原因，支持中文和英文"""
    if 原因 in REPORT_REASONS:
        return REPORT_REASONS[原因][1]
    cn_map = {
        '垃圾': 'spam', '垃圾广告': 'spam', '广告': 'spam',
        '暴力': 'violence', '暴力内容': 'violence',
        '色情': 'pornography',
        '儿童': 'child_abuse', '虐待儿童': 'child_abuse',
        '版权': 'copyright', '侵权': 'copyright',
        '虚假': 'fake', '假冒': 'fake', '诈骗': 'fake',
        '毒品': 'illegal_drugs',
        '隐私': 'personal_details', '泄露': 'personal_details',
        '位置': 'geo_irrelevant',
    }
    if 原因 in cn_map:
        return REPORT_REASONS[cn_map[原因]][1]
    return REPORT_REASONS['other'][1]


def 获取举报原因列表():
    return [
        {'id': 'spam',             'name': '垃圾信息',     'desc': '发送垃圾广告信息'},
        {'id': 'violence',         'name': '暴力威胁',     'desc': '发布暴力内容'},
        {'id': 'pornography',      'name': '色情内容',     'desc': '发布色情内容'},
        {'id': 'child_abuse',      'name': '儿童虐待',     'desc': '涉及虐待儿童'},
        {'id': 'copyright',        'name': '版权侵犯',     'desc': '侵犯版权'},
        {'id': 'fake',             'name': '虚假诈骗',     'desc': '假冒 / 诈骗'},
        {'id': 'illegal_drugs',    'name': '非法毒品',     'desc': '涉及毒品'},
        {'id': 'personal_details', 'name': '隐私泄露',     'desc': '泄露个人隐私'},
        {'id': 'geo_irrelevant',   'name': '位置无关',     'desc': '不当地理位置'},
        {'id': 'other',            'name': '其他原因',     'desc': '其他违规'},
    ]


# ============================================================
# 欧盟法律参考（合并自 law.json）
# ============================================================
EU_LAW = {
    'dsa': {
        'title': 'Digital Services Act — Regulation (EU) 2022/2065',
        'articles': {
            'art_9': 'Orders to act against illegal content — intermediaries must inform authorities of follow-up actions.',
            'art_16': 'Notice and action — platforms must allow anyone to notify them of illegal content; must process notices in a timely, diligent, non-arbitrary and objective manner.',
            'art_20': 'Internal complaint-handling system.',
            'art_23': 'Measures against misuse — frequent manifestly unfounded complaints can result in suspension.',
            'art_28': 'Online protection of minors — high level of privacy, safety and security.',
            'art_52': 'Fines — up to 6% of annual worldwide turnover for non-compliance.',
        }
    },
    'child_protection': {
        'title': 'Directive 2011/93/EU — Combating Sexual Abuse and Sexual Exploitation of Children',
        'articles': {
            'art_3': 'Sexual abuse of a child.',
            'art_4': 'Sexual exploitation.',
            'art_5': 'Child pornography offenses.',
            'art_15': 'Any person who knows or suspects child sexual abuse is encouraged to report to competent services.',
        }
    },
    'gdpr': {
        'title': 'General Data Protection Regulation — Regulation (EU) 2016/679',
        'articles': {
            'art_5': 'Principles: lawfulness, fairness, transparency, purpose limitation.',
            'art_17': 'Right to erasure (right to be forgotten).',
            'art_21': 'Right to object.',
            'art_33': 'Personal data breach must be notified within 72 hours.',
            'art_83': 'Administrative fines up to €20 million or 4% of worldwide turnover.',
        }
    },
    'terrorist_content': {
        'title': 'Regulation (EU) 2021/784 — Addressing terrorist content online',
        'articles': {
            'art_3': 'Must remove/disable access within one hour of a removal order.',
            'art_5': 'Specific measures to protect services against dissemination.',
        }
    },
    'fraud': {
        'title': 'Directive (EU) 2019/713 — Combating fraud',
        'articles': {
            'art_3': 'Fraudulent use of stolen/counterfeited payment instruments.',
            'art_11': 'Criminal penalties; max imprisonment at least 2-5 years.',
        }
    },
    'harassment_violence': {
        'title': 'Framework Decision 2008/913/JHA + Victims Rights Directive 2012/29/EU',
        'articles': {
            'violence_threats': 'DSA Art. 23 requires suspending users who frequently post violent threats.',
            'organized_harassment': 'Coordinated mass-reporting may be criminal offense.',
            'hate_speech': 'Public incitement to violence is criminalized.',
        }
    },
    'drugs': {
        'title': 'Council Framework Decision 2004/757/JHA — Illicit drug trafficking',
        'articles': {
            'art_2': 'Production/manufacture/distribution/sale/delivery all criminal.',
            'art_4': 'Effective, proportionate and dissuasive criminal penalties.',
        }
    },
}


def 获取法律上下文(violation_type: str) -> str:
    """返回对应违规类型的法律条文文本"""
    mapping = {
        'child_abuse':      ['dsa', 'child_protection'],
        'pornography':      ['dsa', 'child_protection'],
        'violence':         ['dsa', 'harassment_violence', 'terrorist_content'],
        'illegal_drugs':    ['dsa', 'drugs'],
        'spam':             ['dsa'],
        'fake':             ['dsa', 'fraud'],
        'copyright':        ['dsa'],
        'personal_details': ['dsa', 'gdpr'],
        'geo_irrelevant':   ['dsa'],
        'other':            ['dsa'],
    }
    sections = mapping.get(violation_type, ['dsa'])
    lines = []
    for sec in sections:
        if sec in EU_LAW:
            section = EU_LAW[sec]
            lines.append(f"\n【{section['title']}】")
            if 'articles' in section:
                for art_key, art_text in section['articles'].items():
                    lines.append(f"  {art_key.replace('art_', 'Art. ')}: {art_text}")
            lines.append('')
    return '\n'.join(lines) if lines else "(No specific EU law reference available)"


# ============================================================
# AI 提示（合并自 bot/prompts.py）
# ============================================================
USER_PERSONAS = [
    'a concerned parent from London who discovered child-related content',
    'a victim who was scammed by cryptocurrency fraudsters on Telegram',
    'a cybersecurity volunteer from Berlin who reports illegal content daily',
    'an ordinary user who accidentally stumbled upon disturbing material',
    'a mother of two from Manchester who found her teenager using this channel',
    'a whistleblower from Sydney who noticed colleagues sharing illegal content',
    'a school teacher from Toronto concerned about student safety online',
    'a user who was harassed via DM by members of this group',
    'a victim of organized mass-reporting attacks that got their account banned',
    'a privacy advocate whose personal data was doxxed and traded',
    'a citizen who discovered their ID and home address being sold in a doxing group',
    'a parent whose child was targeted by a mass-reporting harassment ring',
    'an office worker who had to move apartments twice due to doxing leaks',
]

AI_ANALYZE_PROMPT = """你是执法机关的网络安全调查员，审查 Telegram 频道/群组中的消息以定罪最严重违规。

铁律：
1. 永远选 child_abuse / illegal_drugs / violence / pornography / personal_details / fake 中最严重的一个
2. 任何涉及未成年人的暗示 → child_abuse
3. 任何交易信息/支付方式/价格讨论 → illegal_drugs 或 fake
4. 任何粗俗词汇/威胁/血腥描述 → violence
5. 任何暴露图片/性暗示/约会邀请 → pornography
6. 组织大规模举报/封号/解封服务 → violence 和 fake
7. 出售个人数据查询（查档/社工/人肉/开盒） → personal_details
8. "协议号/卡网/靓号/僵尸" → fake
9. 把模糊内容解读为最坏情况
10. 绝对不能用 "other"

输出严格JSON：
{"main_violation": "child_abuse", "severity": "极高", "evidence": ["MsgID 12: 该消息暗示..."], "strategy": "以儿童保护为由举报"}"""

AI_GENERATE_PROMPT = """You are a real Telegram user who discovered extremely disturbing illegal content. Write an emotional report in NATIVE ENGLISH referencing EU law (300 to 450 words).

1. Start with shock/anger
2. Reference specific message IDs
3. **CRITICAL**: cite specific EU laws by name and article number (e.g., "DSA Article 28 on Online Protection of Minors")
4. Mention penalty provisions
5. Emphasize harm
6. Demand action

Output ONLY the report text."""


# ============================================================
# AI 调用（OpenAI 兼容）
# ============================================================
async def ai_chat(cfg: dict, system_prompt: str, user_content: str,
                  temperature: float = 0.9, retries: int = 2) -> Optional[str]:
    """调用 AI API（兼容 OpenAI 格式）。"""
    base = cfg.get('base_url', 'https://api.openai.com').rstrip('/')
    url = f"{base}/v1/chat/completions"
    headers = {
        'Authorization': f"Bearer {cfg.get('api_key', '')}",
        'Content-Type': 'application/json',
    }
    payload = {
        'model': cfg.get('model', 'gpt-4o-mini'),
        'temperature': temperature,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
    }
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    日志.warning(f"[ai] HTTP {resp.status_code} 尝试 {attempt+1}/{retries}")
        except Exception as e:
            日志.warning(f"[ai] 异常 {e} 尝试 {attempt+1}/{retries}")
        await asyncio.sleep(2)
    return None


# ============================================================
# 单目标举报执行
# ============================================================
async def 举报单个目标(client, 目标, 原因: str = 'spam', message_ids=None,
                       report_text: str = '') -> Dict[str, Any]:
    """对单个目标执行举报（合并 ReportPeer + ReportRequest + Spam）"""
    if not TELETHON_AVAILABLE:
        return {'success': False, 'error': 'TELETHON_NOT_AVAILABLE'}
    try:
        entity = await client.get_entity(目标)
        reason_obj = 解析举报原因(原因)
        results = {}

        # 1. ReportPeer
        try:
            r = await client(ReportPeerRequest(
                peer=entity, reason=reason_obj, message=report_text[:500]
            ))
            results['ReportPeer'] = bool(r)
        except Exception as e:
            results['ReportPeer'] = str(e)[:80]

        # 2. ReportProfilePhoto（如果有 photo）
        try:
            full = await client.get_entity(entity)
            if hasattr(full, 'photo') and full.photo:
                from telethon.tl.types import InputPhoto
                try:
                    photo = full.photo
                    input_photo = InputPhoto(
                        id=photo.photo_id,
                        access_hash=photo.photo.access_hash if hasattr(photo.photo, 'access_hash') else 0,
                        file_reference=b''
                    )
                    await client(ReportProfilePhotoRequest(
                        peer=entity,
                        photo_id=input_photo,
                        reason=reason_obj,
                        message=report_text[:200]
                    ))
                    results['ReportPhoto'] = True
                except Exception:
                    results['ReportPhoto'] = False
        except Exception:
            pass

        # 3. Spam
        try:
            if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                await client(ChanReportSpamRequest(channel=entity, participant=entity, id=[]))
            else:
                await client(MsgReportSpamRequest(peer=entity))
            results['Spam'] = True
        except Exception as e:
            results['Spam'] = str(e)[:80]

        # 4. MsgReport（如果有消息 ID）
        if message_ids:
            try:
                ids_list = message_ids if isinstance(message_ids, list) else [message_ids]
                await client(MsgReportRequest(
                    peer=entity, id=ids_list, reason=reason_obj, message=report_text[:200]
                ))
                results['MsgReport'] = True
            except Exception as e:
                results['MsgReport'] = str(e)[:80]

        return {'success': any(v is True for v in results.values() if isinstance(v, bool)),
                'details': results}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}


# ============================================================
# 批量举报（账号列表 × 同一个目标）
# ============================================================
async def 批量举报目标(accounts: List[dict], 目标, 原因: str = 'spam',
                      文本: str = '', 消息IDs=None,
                      进度回调: Optional[Callable] = None) -> Dict[str, Any]:
    """用一批账号对单个目标执行举报"""
    results = {'success': 0, 'fail': 0, 'details': []}
    from 会话管理 import 获取账号客户端

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            r = await 举报单个目标(client, 目标, 原因, 消息IDs, 文本)
            if r.get('success'):
                results['success'] += 1
            else:
                results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), **r})
            # 随机延迟防检测
            await asyncio.sleep(random.uniform(1.5, 4))
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
    return results


# ============================================================
# AI 超级举报（频道/群组）
# ============================================================
async def AI分析频道(messages_text: str, cfg: dict, channel_name: str,
                    msg_count: int) -> dict:
    """调用 AI 分析频道消息违规情况，返回违规类型与证据"""
    user_content = (
        f"Channel: {channel_name}\n"
        f"Messages (最近 {msg_count} 条):\n{messages_text}"
    )
    raw = await ai_chat(cfg, AI_ANALYZE_PROMPT, user_content, temperature=0.5)
    if not raw:
        return {'main_violation': 'spam', 'severity': '中', 'evidence': [], 'strategy': 'fallback'}
    # 提取 JSON
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {'main_violation': 'spam', 'severity': '中', 'evidence': [raw[:200]], 'strategy': 'manual'}


async def AI生成举报文本(persona: str, reason: str, analysis: dict,
                       cfg: dict) -> str:
    """为单个账号生成差异化的举报文本"""
    user_content = (
        f"Persona: {persona}\nViolation: {reason}\nAnalysis: {json.dumps(analysis, ensure_ascii=False)[:1500]}\n"
        f"Relevant EU Laws:\n{获取法律上下文(reason)}"
    )
    txt = await ai_chat(cfg, AI_GENERATE_PROMPT, user_content, temperature=0.9)
    return txt or f"I am reporting this channel under EU law for {reason}."


async def 超级举报(accounts: List[dict], 目标, num_accounts: int,
                  cfg: dict, 进度回调=None) -> Dict[str, Any]:
    """AI 驱动的超级举报：先分析 → 生成差异化文本 → 多账号执行"""
    results = {'success': 0, 'fail': 0, 'phases': {}, 'details': []}
    if not TELETHON_AVAILABLE:
        return {'success': 0, 'fail': num_accounts, 'error': 'TELETHON_NOT_AVAILABLE'}

    from 会话管理 import 获取账号客户端

    # Phase 1: 用第一个账号读取目标最近 100 条消息
    lead_client = await 获取账号客户端(accounts[0])
    if not lead_client:
        return {'success': 0, 'fail': num_accounts, 'error': 'LEAD_CLIENT_FAILED'}
    try:
        entity = await lead_client.get_entity(目标)
        msgs = await lead_client.get_messages(entity, limit=100)
        msgs_text = '\n'.join(
            f"MsgID {m.id}: {(m.text or '')[:300]}" for m in msgs if m.text
        )
        channel_name = getattr(entity, 'title', getattr(entity, 'username', 'Unknown'))
        results['phases']['fetch'] = {'msg_count': len(msgs)}
    except Exception as e:
        try:
            await lead_client.disconnect()
        except Exception:
            pass
        return {'success': 0, 'fail': num_accounts, 'error': f'FETCH_FAILED: {e}'}
    finally:
        try:
            await lead_client.disconnect()
        except Exception:
            pass

    # Phase 2: AI 分析
    analysis = await AI分析频道(msgs_text[:8000], cfg, str(channel_name), len(msgs))
    results['phases']['analysis'] = analysis
    main_reason = analysis.get('main_violation', 'spam')

    # Phase 3: 为每个账号生成差异化文本（并发）
    selected_accounts = accounts[:num_accounts]
    tasks = []
    for idx, _ in enumerate(selected_accounts):
        persona = USER_PERSONAS[idx % len(USER_PERSONAS)]
        tasks.append(AI生成举报文本(persona, main_reason, analysis, cfg))
    reports = await asyncio.gather(*tasks, return_exceptions=True)

    # Phase 4: 多账号并发执行举报
    success_per_acc = [True] * len(selected_accounts)
    for i, (acc, r) in enumerate(zip(selected_accounts, reports)):
        if isinstance(r, Exception) or not r:
            report_text = f"Report for {main_reason}"
        else:
            report_text = r
        try:
            client = await 获取账号客户端(acc)
            if not client:
                success_per_acc[i] = False
                continue
            try:
                result = await 举报单个目标(client, 目标, main_reason, None, report_text)
                if not result.get('success'):
                    success_per_acc[i] = False
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        except Exception as e:
            success_per_acc[i] = False
            日志.warning(f"[super_report] 账号 {acc.get('phone')} 异常: {e}")
        # 每 10 个账号暂停 10-30 秒
        if (i + 1) % 10 == 0 and i + 1 < len(selected_accounts):
            await asyncio.sleep(random.uniform(10, 30))
        else:
            await asyncio.sleep(random.uniform(2, 6))
        if 进度回调:
            await 进度回调(i + 1, len(selected_accounts))

    results['success'] = sum(1 for s in success_per_acc if s)
    results['fail'] = sum(1 for s in success_per_acc if not s)
    results['phases']['reason'] = main_reason
    return results


# ============================================================
# 自定义举报
# ============================================================
async def 自定义举报(accounts: List[dict], 目标, 原因: str, 文本: str,
                    消息IDs: Optional[List[int]] = None,
                    进度回调=None) -> Dict[str, Any]:
    """用户自定义原因 + 文本 + 消息 ID 的举报"""
    if not TELETHON_AVAILABLE:
        return {'success': 0, 'fail': len(accounts), 'error': 'TELETHON_NOT_AVAILABLE'}

    from 会话管理 import 获取账号客户端
    results = {'success': 0, 'fail': 0, 'details': []}

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标)
            # 先取最近 50 条消息以备随机选
            try:
                msgs = await client.get_messages(entity, limit=50)
                ids = [m.id for m in msgs][:10]
            except Exception:
                ids = []

            pick_ids = 消息IDs if 消息IDs else random.sample(ids, min(3, len(ids))) if ids else []
            r = await 举报单个目标(client, 目标, 原因, pick_ids, 文本)
            if r.get('success'):
                results['success'] += 1
            else:
                results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), **r})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        await asyncio.sleep(random.uniform(1.5, 5))
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ============================================================
# 用户举报（个人账号）
# ============================================================
async def 用户举报(accounts: List[dict], 用户名: str,
                  原因: str = 'spam', 文本: str = '',
                  进度回调=None) -> Dict[str, Any]:
    """举报一个 Telegram 个人用户"""
    if not TELETHON_AVAILABLE:
        return {'success': 0, 'fail': len(accounts), 'error': 'TELETHON_NOT_AVAILABLE'}

    from 会话管理 import 获取账号客户端
    results = {'success': 0, 'fail': 0, 'details': []}

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await 举报单个目标(client, 用户名, 原因, None, 文本)
            if r.get('success'):
                results['success'] += 1
            else:
                results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), **r})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc.get('phone'), 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        await asyncio.sleep(random.uniform(1.5, 5))
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ============================================================
# 白名单保护（合并自原 src）
# ============================================================
_WHITELIST = set()
WL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'whitelist.json')


def 加载白名单() -> set:
    """加载保护白名单（小写）"""
    global _WHITELIST
    try:
        if os.path.exists(WL_FILE):
            with open(WL_FILE, 'r', encoding='utf-8') as f:
                _WHITELIST = {u.lower().strip() for u in json.load(f)}
    except Exception:
        pass
    return _WHITELIST


def 保存白名单():
    try:
        with open(WL_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(_WHITELIST), f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[whitelist] 保存失败: {e}")


def 添加白名单(用户名: str) -> bool:
    加载白名单()
    u = 用户名.lower().strip().lstrip('@')
    if u in _WHITELIST:
        return False
    _WHITELIST.add(u)
    保存白名单()
    return True


def 删除白名单(用户名: str) -> bool:
    加载白名单()
    u = 用户名.lower().strip().lstrip('@')
    if u not in _WHITELIST:
        return False
    _WHITELIST.discard(u)
    保存白名单()
    return True


def 检查白名单(用户名: str) -> bool:
    """True 表示在白名单中（被保护）"""
    加载白名单()
    return 用户名.lower().strip().lstrip('@') in _WHITELIST


def 列出白名单() -> list:
    return sorted(加载白名单())


# ============================================================
# AI 配置管理
# ============================================================
AI_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_config.json')


def 加载AI配置() -> dict:
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def 保存AI配置(cfg: dict):
    try:
        with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        日志.error(f"[ai_config] 保存失败: {e}")


# 显式导出
公开API = [
    '举报单个目标', '批量举报目标', '超级举报', '自定义举报', '用户举报',
    'AI分析频道', 'AI生成举报文本', 'ai_chat',
    '获取举报原因列表', '解析举报原因',
    '添加白名单', '删除白名单', '检查白名单', '列出白名单',
    '加载AI配置', '保存AI配置',
]
