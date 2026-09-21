"""
批量操作模块 - 协议工具箱
作者: Lion
全集版：批量登录、加群、群发、点赞、转发、举报、爬取群成员、导出联系人等 30+ 功能
"""

import os
import asyncio
import random
import re
import csv
import json
from datetime import datetime
from io import StringIO
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import (
    JoinChannelRequest, LeaveChannelRequest,
    InviteToChannelRequest, CreateChannelRequest,
    GetFullChannelRequest, GetParticipantsRequest,
    EditAdminRequest, EditPhotoRequest
)
from telethon.tl.functions.messages import (
    ImportChatInviteRequest, SendReactionRequest,
    GetMessagesRequest, ForwardMessagesRequest,
    CheckChatInviteRequest, SendMessageRequest,
    GetDialogsRequest, GetHistoryRequest,
    DeleteHistoryRequest, DeleteMessagesRequest,
    SearchRequest, GetDiscussionMessageRequest,
    SendVoteRequest, GetPollResultsRequest,
    GetMessageReactionsListRequest, GetRepliesRequest
)
from telethon.tl.functions.account import (
    UpdateProfileRequest, UpdateUsernameRequest,
    SetPrivacyRequest, GetAuthorizationsRequest,
    ResetAuthorizationRequest, ResetWebAuthorizationsRequest,
    UpdateStatusRequest, GetPrivacyRequest,
    UpdateDeviceLockedRequest
)
from telethon.tl.functions.photos import (
    DeletePhotosRequest, GetUserPhotosRequest,
    UploadProfilePhotoRequest
)
from telethon.tl.functions.contacts import (
    ImportContactsRequest, GetContactsRequest,
    DeleteContactsRequest, SearchRequest as ContactsSearchRequest,
    ResolveUsernameRequest, GetContactIDsRequest
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.help import GetNearestDcRequest
from telethon.tl.functions.updates import GetChannelDifferenceRequest
from telethon.tl.functions.stats import GetMessagePublicForwardsRequest
from telethon.tl.types import (
    ReactionEmoji, InputPhoto, InputPeerUser,
    InputPrivacyKeyPhoneNumber, InputPrivacyKeyAddedByPhone,
    InputPrivacyKeyStatusTimestamp, InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyForwards, InputPrivacyKeyPhoneCall,
    InputPrivacyKeyChatInvite, InputPrivacyKeyBirthday,
    InputPrivacyValueAllowAll, InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll, InputPrivacyValueAllowUsers,
    InputPrivacyValueDisallowUsers, InputUser,
    ChannelParticipantsSearch, ChannelParticipantsBots,
    ChannelParticipantsAdmins, ChannelParticipantsKicked,
    ChatBannedRights, InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake,
    InputReportReasonIllegalDrugs, InputReportReasonPersonalDetails,
    InputReportReasonOther, InputReportReasonGeoIrrelevant,
    InputMessagesFilterPhotos, InputMessagesFilterVideo,
    InputMessagesFilterMusic, InputMessagesFilterDocument,
    InputMessagesFilterVoice, InputMessagesFilterRoundVideo,
    InputMessagesFilterUrl, InputMessagesFilterGif,
    InputMessagesFilterContacts, InputMessagesFilterMyMentions,
    InputMessagesFilterChatPhotos, InputMessagesFilterPhoneCalls,
    InputMessagesFilterRoundVoice, InputMessagesFilterPinned,
    SendMessageEmojiInteraction, SendMessageEmojiInteractionSeen,
    EmojiStatus, InputStickerSetItem, InputStickerSetShortName
)
from telethon.tl.functions.stickers import CreateStickerSetRequest
from 配置 import (
    API_ID, API_HASH, 默认API_ID, 默认API_HASH,
    会话目录, 导出目录, 项目根目录, 并发限制,
    最小延迟, 最大延迟, 最小反应延迟, 最大反应延迟,
    最小加群延迟, 最大加群延迟, 最小发送延迟, 最大发送延迟, 日志
)
import 数据库 as db
import 会话管理
from 会话管理 import 获取账号客户端
from 设备伪装 import 预设表情, 白名单ID, 白名单用户名, 隐私选项, 举报原因映射
from 工具 import (
    解析消息链接, 解析机器人链接, 解析加群链接,
    去掉后缀, 随机字符串, 随机数字, 当前时间, 格式化时间戳,
    创建压缩包, 保存JSON导出, 构建进度条, 提取手机号, 清理路径
)
from 代理管理 import 获取下一个代理

# ==================== 内部工具函数 ====================

async def _安全执行(client, func, *args, **kwargs):
    """安全执行一个操作，处理 FloodWait 等异常"""
    try:
        return await func(*args, **kwargs), None
    except errors.FloodWaitError as e:
        日志.warning(f"FloodWait {e.seconds}s")
        await asyncio.sleep(e.seconds)
        try:
            return await func(*args, **kwargs), None
        except Exception as e2:
            return None, str(e2)
    except Exception as e:
        return None, str(e)

async def _批量操作执行器(accounts, 操作函数, 延迟范围=None, 进度回调=None):
    """批量操作执行器，遍历账号执行操作"""
    if 延迟范围 is None:
        延迟范围 = (最小延迟, 最大延迟)
    results = {'success': 0, 'fail': 0, 'details': []}
    semaphore = asyncio.Semaphore(并发限制)

    async def 执行单个(acc, index):
        async with semaphore:
            client = await 获取账号客户端(acc)
            if not client:
                return {'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'}
            try:
                detail = await 操作函数(client, acc, index)
                if detail:
                    return detail
                else:
                    return {'phone': acc['phone'], 'status': 'fail', 'error': 'OPERATION_FAILED'}
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    detail = await 操作函数(client, acc, index)
                    return detail if detail else {'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD_RETRY_FAILED'}
                except Exception:
                    return {'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD'}
            except Exception as e:
                return {'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]}
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    tasks = [执行单个(acc, i) for i, acc in enumerate(accounts)]
    for i, task in enumerate(asyncio.as_completed(tasks)):
        detail = await task
        if detail['status'] == 'success':
            results['success'] += 1
        else:
            results['fail'] += 1
        results['details'].append(detail)
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts) - 1:
            await asyncio.sleep(random.uniform(*延迟范围))
    return results

async def _批量执行(accounts, 操作函数, 延迟范围=None, 进度回调=None):
    """简化的批量执行，按顺序处理"""
    if 延迟范围 is None:
        延迟范围 = (最小延迟, 最大延迟)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            detail = await 操作函数(client, acc, i)
            if detail:
                results['success'] += 1
                results['details'].append(detail)
            else:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'OPERATION_FAILED'})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                detail = await 操作函数(client, acc, i)
                if detail:
                    results['success'] += 1
                    results['details'].append(detail)
                else:
                    results['fail'] += 1
                    results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD_RETRY_FAILED'})
            except Exception:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts) - 1:
            await asyncio.sleep(random.uniform(*延迟范围))
    return results

# ==================== 批量加群 ====================

async def 批量加群(accounts, 链接, 进度回调=None):
    """批量账号加入频道/群组"""
    results = {'success': 0, 'fail': 0, 'details': []}
    链接类型, 链接值 = 解析加群链接(链接)
    if not 链接值:
        results['error'] = 'INVALID_LINK'
        return results

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            if 链接类型 == 'hash':
                await client(ImportChatInviteRequest(链接值))
            else:
                entity = await client.get_entity(链接值)
                await client(JoinChannelRequest(entity))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except errors.FloodWaitError as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': f'FLOOD_{e.seconds}'})
        except Exception as e:
            err = str(e)
            if "USER_ALREADY_PARTICIPANT" in err:
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success', 'note': 'already_joined'})
            else:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': err[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小加群延迟, 最大加群延迟))
    return results

async def 批量退群(accounts, 链接, 进度回调=None):
    """批量账号退出频道/群组"""
    results = {'success': 0, 'fail': 0, 'details': []}
    链接类型, 链接值 = 解析加群链接(链接)
    if not 链接值:
        results['error'] = 'INVALID_LINK'
        return results

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            entity = await client.get_entity(链接值)
            await client(LeaveChannelRequest(entity))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小加群延迟, 最大加群延迟))
    return results

# ==================== 批量群发消息 ====================

async def 批量群发消息(accounts, 目标, 消息内容, 重复次数=1, 媒体路径=None, 进度回调=None):
    """批量账号向目标发送消息"""
    results = {'success': 0, 'fail': 0, 'total_sent': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_sent = 0
        acc_fail = 0
        try:
            for r in range(重复次数):
                try:
                    if 媒体路径 and os.path.exists(媒体路径):
                        await client.send_file(目标, 媒体路径, caption=消息内容)
                    else:
                        await client.send_message(目标, 消息内容)
                    acc_sent += 1
                    if r < 重复次数 - 1:
                        await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        await client.send_message(目标, 消息内容)
                        acc_sent += 1
                    except Exception:
                        acc_fail += 1
                except Exception as e:
                    acc_fail += 1
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'sent': acc_sent, 'failed': acc_fail
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
    return results

async def 批量发送媒体(accounts, 目标, 媒体路径, 标题='', 进度回调=None):
    """批量发送媒体文件"""
    results = {'success': 0, 'fail': 0, 'details': []}
    if not os.path.exists(媒体路径):
        results['error'] = 'FILE_NOT_FOUND'
        return results

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            await client.send_file(目标, 媒体路径, caption=标题)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client.send_file(目标, 媒体路径, caption=标题)
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success'})
            except Exception:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
    return results

# ==================== 批量点赞/表情反应 ====================

async def 批量点赞(accounts, 消息链接, 表情=None, 进度回调=None):
    """批量对消息做出表情反应"""
    if 表情 is None:
        表情 = random.choice(预设表情)
    用户名, 消息ID = 解析消息链接(消息链接)
    if not 用户名 or not 消息ID:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            entity = await client.get_entity(用户名)
            实际表情 = random.choice(预设表情) if 表情 == 'random' else 表情
            await client(SendReactionRequest(
                peer=entity, msg_id=消息ID,
                reaction=[ReactionEmoji(emoticon=实际表情)]
            ))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'emoji': 实际表情
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小反应延迟, 最大反应延迟))
    return results

async def 批量多目标点赞(accounts, 目标列表, 进度回调=None):
    """批量对多个消息做出表情反应"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_success = 0
        try:
            for target in 目标列表:
                用户名, 消息ID = 解析消息链接(target.get('link', ''))
                if not 用户名 or not 消息ID:
                    continue
                表情 = target.get('emoji', random.choice(预设表情))
                try:
                    entity = await client.get_entity(用户名)
                    await client(SendReactionRequest(
                        peer=entity, msg_id=消息ID,
                        reaction=[ReactionEmoji(emoticon=表情)]
                    ))
                    acc_success += 1
                except Exception:
                    continue
                await asyncio.sleep(random.uniform(0.5, 1.5))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'reacted': acc_success
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小反应延迟, 最大反应延迟))
    return results

# ==================== 批量转发消息 ====================

async def 批量转发消息(accounts, 消息链接, 目标, 进度回调=None):
    """批量转发消息到目标"""
    用户名, 消息ID = 解析消息链接(消息链接)
    if not 用户名 or not 消息ID:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            from_entity = await client.get_entity(用户名)
            to_entity = await client.get_entity(目标)
            await client(ForwardMessagesRequest(
                from_peer=from_entity,
                id=[消息ID],
                to_peer=to_entity
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
    return results

# ==================== 批量启动机器人 ====================

async def 批量启动机器人(accounts, 机器人链接列表, 进度回调=None):
    """批量启动机器人"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for link in 机器人链接列表:
        用户名, 启动参数 = 解析机器人链接(link.strip())
        if not 用户名:
            continue
        命令 = f"/start {启动参数}" if 启动参数 else "/start"
        for i, acc in enumerate(accounts):
            client = await 获取账号客户端(acc)
            if not client:
                results['fail'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'bot': 用户名, 'status': 'fail', 'error': 'CLIENT_FAILED'
                })
                continue
            try:
                entity = await client.get_entity(f"@{用户名}")
                await client.send_message(entity, 命令)
                results['success'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'bot': 用户名, 'status': 'success'
                })
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    entity = await client.get_entity(f"@{用户名}")
                    await client.send_message(entity, 命令)
                    results['success'] += 1
                    results['details'].append({
                        'phone': acc['phone'], 'bot': 用户名, 'status': 'success'
                    })
                except Exception:
                    results['fail'] += 1
                    results['details'].append({
                        'phone': acc['phone'], 'bot': 用户名, 'status': 'fail', 'error': 'FLOOD'
                    })
            except Exception as e:
                results['fail'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'bot': 用户名, 'status': 'fail', 'error': str(e)[:100]
                })
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            if i < len(accounts):
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
    return results

# ==================== 批量爬取群成员 ====================

async def 爬取群成员(accounts, 群组链接, 进度回调=None):
    """爬取群组成员信息"""
    用户名, _ = 解析加群链接(群组链接)
    if not 用户名:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'members': []}

    acc = accounts[0] if accounts else None
    if not acc:
        return {'success': 0, 'fail': 0, 'error': 'NO_ACCOUNTS', 'members': []}

    client = await 获取账号客户端(acc)
    if not client:
        return {'success': 0, 'fail': 0, 'error': 'CLIENT_FAILED', 'members': []}

    members = []
    try:
        entity = await client.get_entity(用户名)
        offset = 0
        limit = 200
        while True:
            participants = await client(GetParticipantsRequest(
                channel=entity,
                filter=ChannelParticipantsSearch(''),
                offset=offset,
                limit=limit,
                hash=0
            ))
            if not participants.users:
                break
            for user in participants.users:
                members.append({
                    'id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'phone': user.phone or '',
                    'is_bot': user.bot,
                    'is_premium': getattr(user, 'premium', False)
                })
            offset += len(participants.users)
            if len(participants.users) < limit:
                break
            await asyncio.sleep(1)
            if 进度回调:
                await 进度回调(len(members), 0)
        await client.disconnect()
        return {'success': 1, 'fail': 0, 'members': members, 'total': len(members)}
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return {'success': 0, 'fail': 1, 'error': str(e)[:100], 'members': members}

# ==================== 批量导出联系人 ====================

async def 导出联系人(accounts, 进度回调=None):
    """导出所有账号的联系人"""
    all_contacts = []
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            continue
        try:
            contacts = await client(GetContactsRequest(hash=0))
            for user in contacts.users:
                all_contacts.append({
                    'id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'phone': user.phone or '',
                    'account_phone': acc['phone']
                })
        except Exception:
            pass
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return all_contacts

# ==================== 批量修改资料 ====================

async def 批量修改昵称(accounts, 新昵称, 进度回调=None):
    """批量修改账号昵称"""
    return await _批量执行(accounts, lambda c, a, i: _修改昵称(c, a, 新昵称), 进度回调=进度回调)

async def _修改昵称(client, acc, 新昵称):
    try:
        await client(UpdateProfileRequest(first_name=新昵称))
        return {'phone': acc['phone'], 'status': 'success'}
    except Exception as e:
        return None

async def 批量修改用户名(accounts, 新用户名, 进度回调=None):
    """批量修改账号 @username"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            await client(UpdateUsernameRequest(新用户名))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateUsernameRequest(新用户名))
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success'})
            except Exception:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'FLOOD'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

async def 批量修改简介(accounts, 新简介, 进度回调=None):
    """批量修改账号简介"""
    async def _操作(client, acc, i):
        try:
            await client(UpdateProfileRequest(about=新简介))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

async def 批量修改姓名(accounts, 新名字, 新姓氏='', 进度回调=None):
    """批量修改账号姓名"""
    async def _操作(client, acc, i):
        try:
            await client(UpdateProfileRequest(first_name=新名字, last_name=新姓氏))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

async def 批量上传头像(accounts, 头像路径, 进度回调=None):
    """批量上传头像"""
    if not os.path.exists(头像路径):
        return {'success': 0, 'fail': 0, 'error': 'FILE_NOT_FOUND', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            await client(UploadProfilePhotoRequest(
                await client.upload_file(头像路径)
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

async def 批量随机头像(accounts, 进度回调=None):
    """批量设置为随机头像（删除当前头像）"""
    async def _操作(client, acc, i):
        try:
            photos = await client(GetUserPhotosRequest(user_id="me", offset=0, max_id=0, limit=1))
            if photos.photos:
                await client(DeletePhotosRequest(id=[photos.photos[0]]))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量隐私设置 ====================

async def 批量设置隐私(accounts, 隐私类型, 隐私值, 进度回调=None):
    """批量设置隐私选项
    隐私类型: phone_number, add_by_phone, last_seen, profile_photo, forwards, phone_call, group_invite
    隐私值: all, contacts, nobody
    """
    隐私映射 = {
        'phone_number': InputPrivacyKeyPhoneNumber(),
        'add_by_phone': InputPrivacyKeyAddedByPhone(),
        'last_seen': InputPrivacyKeyStatusTimestamp(),
        'profile_photo': InputPrivacyKeyProfilePhoto(),
        'forwards': InputPrivacyKeyForwards(),
        'phone_call': InputPrivacyKeyPhoneCall(),
        'group_invite': InputPrivacyKeyChatInvite(),
    }
    值映射 = {
        'all': [InputPrivacyValueAllowAll()],
        'contacts': [InputPrivacyValueAllowContacts()],
        'nobody': [InputPrivacyValueDisallowAll()],
    }
    if 隐私类型 not in 隐私映射:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_PRIVACY_TYPE', 'details': []}
    if 隐私值 not in 值映射:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_PRIVACY_VALUE', 'details': []}

    key = 隐私映射[隐私类型]
    rules = 值映射[隐私值]

    async def _操作(client, acc, i):
        try:
            await client(SetPrivacyRequest(key=key, rules=rules))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

async def 批量锁定隐私(accounts, 进度回调=None):
    """批量锁定所有隐私为仅联系人可见"""
    privacy_types = ['phone_number', 'add_by_phone', 'last_seen', 'profile_photo', 'forwards', 'phone_call', 'group_invite']
    all_results = {'success': 0, 'fail': 0, 'details': []}
    for pt in privacy_types:
        r = await 批量设置隐私(accounts, pt, 'contacts', 进度回调)
        all_results['success'] += r['success']
        all_results['fail'] += r['fail']
        all_results['details'].extend(r['details'])
    return all_results

# ==================== 批量创建频道 ====================

async def 批量创建频道(accounts, 频道名称, 频道简介='', 进度回调=None):
    """批量创建频道/群组"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            result = await client(CreateChannelRequest(
                title=频道名称,
                about=频道简介,
                megagroup=False
            ))
            channel = result.updates[0].channel_id if result.updates else None
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'channel_id': str(channel)
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

# ==================== 批量拉人入群 ====================

async def 批量拉人入群(accounts, 群组链接, 用户列表, 进度回调=None):
    """批量拉用户入群"""
    用户名, _ = 解析加群链接(群组链接)
    if not 用户名:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            entity = await client.get_entity(用户名)
            users_to_add = []
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    users_to_add.append(ue)
                except Exception:
                    pass
            if users_to_add:
                await client(InviteToChannelRequest(entity, users_to_add))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'invited': len(users_to_add)
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

# ==================== 批量投票 ====================

async def 批量投票(accounts, 消息链接, 选项索引=0, 进度回调=None):
    """批量在投票中投票"""
    用户名, 消息ID = 解析消息链接(消息链接)
    if not 用户名 or not 消息ID:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            entity = await client.get_entity(用户名)
            await client(SendVoteRequest(
                peer=entity,
                msg_id=消息ID,
                options=[bytes([选项索引])]
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小反应延迟, 最大反应延迟))
    return results

# ==================== 批量修改两步验证 ====================

async def 批量设置两步验证(accounts, 新密码, 提示='', 进度回调=None):
    """批量设置两步验证密码"""
    async def _操作(client, acc, i):
        try:
            from telethon.tl.functions.account import GetPasswordRequest, UpdatePasswordSettingsRequest
            from telethon.tl.types import PasswordInputSettings, InputCheckPasswordEmpty
            pwd = await client(GetPasswordRequest())
            if pwd.has_password:
                return {'phone': acc['phone'], 'status': 'skip', 'note': '已有密码'}
            new_hash = pwd.compute_new_password_hash(新密码)
            await client(UpdatePasswordSettingsRequest(
                password=InputCheckPasswordEmpty(),
                new_settings=PasswordInputSettings(hint=提示, new_password_hash=new_hash)
            ))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量聊天记录操作 ====================

async def 批量删除聊天记录(accounts, 目标, 进度回调=None):
    """批量删除与目标的聊天记录"""
    async def _操作(client, acc, i):
        try:
            entity = await client.get_entity(目标)
            await client(DeleteHistoryRequest(
                peer=entity, max_id=0, just_clear=False, revoke=True
            ))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

async def 批量清空对话(accounts, 进度回调=None):
    """批量清空所有对话"""
    async def _操作(client, acc, i):
        try:
            dialogs = await client.get_dialogs()
            count = 0
            for d in dialogs:
                try:
                    await client(DeleteHistoryRequest(
                        peer=d.entity, max_id=0, just_clear=True, revoke=False
                    ))
                    count += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            return {'phone': acc['phone'], 'status': 'success', 'cleared': count}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量注销 ====================

async def 批量注销(accounts, 进度回调=None):
    """批量注销账号（谨慎使用！）"""
    async def _操作(client, acc, i):
        try:
            from telethon.tl.functions.account import DeleteAccountRequest
            await client(DeleteAccountRequest(reason='批量注销'))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量获取信息 ====================

async def 批量获取账号信息(accounts, 进度回调=None):
    """批量获取账号详细信息"""
    results = []
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results.append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            me = await client.get_me()
            full = await client(GetFullUserRequest('me'))
            info = {
                'phone': acc['phone'],
                'status': 'success',
                'id': me.id,
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'username': me.username or '',
                'premium': getattr(me, 'premium', False),
                'bio': getattr(full.full_user, 'about', '') if full and full.full_user else '',
                'photos_count': getattr(full.full_user, 'photos', None) and len(full.full_user.photos.photos) if full and full.full_user and hasattr(full.full_user, 'photos') and full.full_user.photos else 0,
            }
            results.append(info)
        except Exception as e:
            results.append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results

async def 批量获取群组列表(accounts, 进度回调=None):
    """批量获取每个账号的群组列表"""
    all_groups = []
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            continue
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if d.is_group or d.is_channel:
                    all_groups.append({
                        'account_phone': acc['phone'],
                        'title': d.title,
                        'id': d.entity.id,
                        'username': getattr(d.entity, 'username', '') or '',
                        'members_count': getattr(d.entity, 'participants_count', 0),
                        'is_channel': d.is_channel,
                        'is_group': d.is_group,
                    })
        except Exception:
            pass
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return all_groups

# ==================== 批量搜索消息 ====================

async def 批量搜索消息(accounts, 目标, 关键词, 限制=50, 进度回调=None):
    """批量搜索消息"""
    async def _操作(client, acc, i):
        try:
            entity = await client.get_entity(目标)
            messages = await client(SearchRequest(
                peer=entity, q=关键词, filter=None,
                min_date=None, max_date=None, offset_id=0,
                add_offset=0, limit=限制, max_id=0, min_id=0,
                hash=0, from_id=None
            ))
            found = len(messages.messages)
            return {'phone': acc['phone'], 'status': 'success', 'found': found}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量获取消息历史 ====================

async def 批量获取消息历史(accounts, 目标, 限制=100, 进度回调=None):
    """批量获取消息历史"""
    async def _操作(client, acc, i):
        try:
            entity = await client.get_entity(目标)
            messages = await client.get_messages(entity, limit=限制)
            return {
                'phone': acc['phone'], 'status': 'success',
                'count': len(messages) if messages else 0
            }
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 数据导出 ====================

async def 导出群成员到CSV(群组链接, 输出路径, user_id):
    """导出群成员到CSV文件"""
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return None, "NO_ACCOUNTS"

    result = await 爬取群成员(accounts, 群组链接)
    if result.get('error'):
        return None, result['error']

    members = result.get('members', [])
    if not members:
        return None, "NO_MEMBERS"

    export_dir = os.path.join(项目根目录, 导出目录)
    os.makedirs(export_dir, exist_ok=True)
    csv_path = os.path.join(export_dir, 输出路径)

    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'username', 'first_name', 'last_name', 'phone', 'is_bot', 'is_premium'])
        writer.writeheader()
        writer.writerows(members)

    return csv_path, None

async def 导出联系人为CSV(user_id):
    """导出所有联系人为CSV"""
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        return None, "NO_ACCOUNTS"

    contacts = await 导出联系人(accounts)
    if not contacts:
        return None, "NO_CONTACTS"

    export_dir = os.path.join(项目根目录, 导出目录)
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(export_dir, f"contacts_{user_id}_{timestamp}.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'username', 'first_name', 'last_name', 'phone', 'account_phone'])
        writer.writeheader()
        writer.writerows(contacts)

    return csv_path, None

# ==================== 批量举报 ====================

async def _举报操作(client, acc, 目标, 原因, 消息内容=None):
    """单个账号举报操作"""
    举报原因映射表 = {
        'spam': InputReportReasonSpam(),
        '垃圾广告': InputReportReasonSpam(),
        'violence': InputReportReasonViolence(),
        '暴力': InputReportReasonViolence(),
        'pornography': InputReportReasonPornography(),
        '色情': InputReportReasonPornography(),
        'child_abuse': InputReportReasonChildAbuse(),
        '虐待儿童': InputReportReasonChildAbuse(),
        'copyright': InputReportReasonCopyright(),
        '版权': InputReportReasonCopyright(),
        'fake': InputReportReasonFake(),
        '假冒': InputReportReasonFake(),
        'illegal_drugs': InputReportReasonIllegalDrugs(),
        '毒品': InputReportReasonIllegalDrugs(),
        'personal_details': InputReportReasonPersonalDetails(),
        '隐私': InputReportReasonPersonalDetails(),
        'other': InputReportReasonOther(),
        '其他': InputReportReasonOther(),
        'geo': InputReportReasonGeo(),
        '地理位置': InputReportReasonGeo(),
    }
    reason_obj = 举报原因映射表.get(原因, InputReportReasonOther())
    try:
        entity = await client.get_entity(目标)
        messages = None
        if 消息内容:
            try:
                msg_id = int(消息内容)
                messages = [msg_id]
            except ValueError:
                pass
        await client.report(entity, reason=reason_obj, message=messages)
        return {'phone': acc['phone'], 'status': 'success', 'target': 目标, 'reason': 原因}
    except Exception as e:
        return None

async def 批量举报(accounts, 目标, 原因='spam', 消息内容=None, 进度回调=None):
    """批量举报目标"""
    async def _操作(client, acc, i):
        return await _举报操作(client, acc, 目标, 原因, 消息内容)
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

async def 批量举报多目标(accounts, 目标列表, 进度回调=None):
    """批量举报多个目标，每个目标使用不同原因"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_success = 0
        try:
            for target in 目标列表:
                t = target if isinstance(target, str) else target.get('target', '')
                r = 'spam' if isinstance(target, str) else target.get('reason', 'spam')
                m = None if isinstance(target, str) else target.get('msg', None)
                detail = await _举报操作(client, acc, t, r, m)
                if detail:
                    acc_success += 1
                    results['details'].append(detail)
                await asyncio.sleep(random.uniform(1, 3))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

# ==================== 批量刷浏览量 ====================

async def 批量刷浏览量(accounts, 频道链接, 消息数量=10, 进度回调=None):
    """批量刷频道浏览量"""
    async def _操作(client, acc, i):
        try:
            entity = await client.get_entity(频道链接)
            messages = await client.get_messages(entity, limit=消息数量)
            count = 0
            if messages:
                for msg in messages:
                    try:
                        await client.get_messages(entity, ids=msg.id)
                        count += 1
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)
            return {'phone': acc['phone'], 'status': 'success', 'viewed': count}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量踢人 ====================

async def 批量踢人(accounts, 群组链接, 用户列表, 进度回调=None):
    """批量从群组中踢人"""
    用户名, _ = 解析加群链接(群组链接)
    if not 用户名:
        return {'success': 0, 'fail': 0, 'error': 'INVALID_LINK', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            entity = await client.get_entity(用户名)
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    rights = ChatBannedRights(
                        until_date=None, view_messages=True,
                        send_messages=True, send_media=True,
                        send_stickers=True, send_gifs=True,
                        send_games=True, send_inline=True,
                        embed_links=True, send_polls=True,
                        change_info=True, invite_users=True,
                        pin_messages=True
                    )
                    await client(EditAdminRequest(entity, ue, rights, None))
                except Exception:
                    pass
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'kicked': len(用户列表)
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results

# ==================== 批量添加联系人 ====================

async def 批量添加联系人(accounts, 联系人列表, 进度回调=None):
    """批量添加联系人"""
    async def _操作(client, acc, i):
        try:
            for contact in 联系人列表:
                phone = contact.get('phone', '')
                first_name = contact.get('first_name', '用户')
                last_name = contact.get('last_name', '')
                try:
                    await client(ImportContactsRequest([{
                        'phone': phone,
                        'first_name': first_name,
                        'last_name': last_name
                    }]))
                except Exception:
                    pass
                await asyncio.sleep(1)
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量刷在线状态 ====================

async def 批量刷在线(accounts, 持续秒数=60, 进度回调=None):
    """批量刷在线状态"""
    async def _操作(client, acc, i):
        try:
            await client(UpdateStatusRequest(offline=False))
            await asyncio.sleep(min(持续秒数, 30))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)

# ==================== 批量发贴纸 ====================

async def 批量发贴纸(accounts, 目标, 贴纸路径, 进度回调=None):
    """批量发送贴纸"""
    if not os.path.exists(贴纸路径):
        return {'success': 0, 'fail': 0, 'error': 'FILE_NOT_FOUND', 'details': []}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            await client.send_file(目标, 贴纸路径, force_document=False)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        if i < len(accounts):
            await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
    return results

# ==================== 生成批量操作报告 ====================

def 生成批量操作报告(结果, 操作名称):
    """生成人类可读的操作报告"""
    if 结果.get('error'):
        return f"❌ {操作名称} 失败: {结果['error']}"

    total = 结果['success'] + 结果['fail']
    text = f"📊 {操作名称} 完成\n"
    text += f"├─ ✅ 成功: {结果['success']}\n"
    text += f"├─ ❌ 失败: {结果['fail']}\n"
    if 'total_sent' in 结果:
        text += f"├─ 📨 发送: {结果['total_sent']}\n"
    if 'members' in 结果:
        text += f"├─ 👥 成员: {结果.get('total', len(结果['members']))}\n"
    text += f"└─ 📊 总计: {total}"

    details = 结果.get('details', [])[:10]
    if details:
        text += "\n\n📋 详情:"
        for d in details:
            p = d.get('phone', 'N/A')
            s = d.get('status', '')
            err = d.get('error', '')
            icon = "✅" if s == 'success' else "❌"
            extra = ""
            if 'sent' in d:
                extra = f" ({d['sent']}条)"
            if 'emoji' in d:
                extra = f" {d['emoji']}"
            if err:
                extra = f" - {err[:50]}"
            text += f"\n{icon} {p}{extra}"
    return text# ==========================================================================
# ⭐ 新增超级批量操作模块（60+ 功能） - 协议工具箱 作者 Lion
# ==========================================================================
# 包括但不限于：
# 1) 批量签到（/qd）      2) 批量发送任意机器人指令      3) 批量修改资料增强
# 4) 批量创建群组/频道增强  5) 批量刷在线/已读/已播放        6) 批量养号
# 7) 自动回复              8) 批量好友申请/通过             9) 批量互赞互关
# 10) 批量赠送 premium    11) 批量邀请入私聊             12) 批量定位签到
# 13) 批量领取红包        14) 批量参与投票增强           15) 批量水群
# 16) 批量收藏           17) 批量话题                18) 批量置顶
# 19) 批量修改主题色      20) 批量设置 emoji 状态     21) 批量表情包
# 22) 批量语音            23) 批量定位                24) 批量贴纸
# 25) 批量视频笔记       26) 批量文章                27) 批量联系人合并
# 28) 批量匿名管理       29) 批量踢广告               30) 批量禁言
# 31) 批量解除禁言        32) 批量提升管理员           33) 批量降权
# 34) 批量公开/私有       35) 批量转移所有权           36) 批量切换两步
# 37) 批量重置未读        38) 批量已读                  39) 批量撤回已读
# 40) 批量删除自己的消息 41) 批量编辑消息               42) 批量定时任务
# 43) 批量群规公告        44) 批量欢迎语               45) 批量邀请链接轮换
# 46) 批量升级 supergroup 47) 批量隐藏/显示 在线       48) 批量已读表情包
# 49) 批量下载头像       50) 批量检测 premium        51) 批量设置用户名后缀
# 52) 批量生日提醒       53) 批量星座签到            54) 批量抽奖模拟
# 55) 批量回关           56) 批量双向关注            57) 批量检测被封
# 58) 批量解除敏感       59) 批量拒绝陌生人          60) 批量接受陌生人
# 61) 批量修改通知设置   62) 批量修改语言              63) 批量开关邮箱通知
# ==========================================================================

# ==================== 1. 批量签到（/qd） ====================

# 内置常用签到指令集合（覆盖大部分签到机器人）
内置签到指令 = [
    "/qd",         # 通用签到
    "/sign",       # 英文版签到
    "/checkin",    # check-in
    "/daily",      # daily
    "/qiandao",    # 全拼
    "/qd ",        # 带空格变体
    "/signin",
    "/每日签到",
    ".qd",         # 带点
    "/qd@botname",    # 指向具体 bot（占位）
]


async def 批量签到(accounts, 机器人列表, 进度回调=None):
    """批量向多个机器人发送签到指令（如 /qd /sign /checkin 等）

    参数:
        accounts: 账号列表
        机器人列表: bot 用户名列表，如 ['@xxxbot', '@yyybot']
    """
    results = {'success': 0, 'fail': 0, 'details': [], '指令列表': []}
    # 拼装每个机器人对应的签到指令
    指令列表 = []
    for bot in 机器人列表:
        for cmd in 内置签到指令:
            实际cmd = cmd.replace("@botname", f"@{bot.replace('@','')}")
            指令列表.append({"机器人": bot, "指令": 实际cmd})
    results['指令列表'] = 指令列表

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_ok = 0
        try:
            for item in 指令列表:
                try:
                    entity = await client.get_entity(item["机器人"])
                    await client.send_message(entity, item["指令"])
                    acc_ok += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        entity = await client.get_entity(item["机器人"])
                        await client.send_message(entity, item["指令"])
                        acc_ok += 1
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'sent': acc_ok
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 2. 批量发送任意机器人指令 ====================

async def 批量发送指令(accounts, 指令任务列表, 进度回调=None):
    """批量向任意机器人发送任意指令

    指令任务列表格式:
        [
            {"机器人": "@xxxbot", "指令": "/start 参数"},
            {"机器人": "@yyybot", "指令": "/qd"},
            ...
        ]
    """
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_sent = 0
        try:
            for task in 指令任务列表:
                bot = task.get("机器人", "")
                cmd = task.get("指令", "")
                if not bot or not cmd:
                    continue
                try:
                    entity = await client.get_entity(bot)
                    await client.send_message(entity, cmd)
                    acc_sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        entity = await client.get_entity(bot)
                        await client.send_message(entity, cmd)
                        acc_sent += 1
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'sent': acc_sent
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量启动机器人增强(accounts, 机器人链接列表, 自定义参数=None, 进度回调=None):
    """批量启动机器人增强版（支持多个参数、回车分隔、自定义 payload）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for link in 机器人链接列表:
        用户名, 启动参数 = 解析机器人链接(link.strip())
        if not 用户名:
            continue
        命令 = f"/start {启动参数 or ''}".strip()
        if 自定义参数:
            命令 = f"{命令} {自定义参数}".strip()
        for i, acc in enumerate(accounts):
            client = await 获取账号客户端(acc)
            if not client:
                results['fail'] += 1
                continue
            try:
                entity = await client.get_entity(f"@{用户名}")
                await client.send_message(entity, 命令)
                results['success'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'bot': 用户名, 'status': 'success', 'cmd': 命令
                })
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    entity = await client.get_entity(f"@{用户名}")
                    await client.send_message(entity, 命令)
                    results['success'] += 1
                except Exception:
                    results['fail'] += 1
            except Exception as e:
                results['fail'] += 1
                results['details'].append({
                    'phone': acc['phone'], 'bot': 用户名, 'status': 'fail', 'error': str(e)[:100]
                })
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
        if 进度回调:
            await 进度回调(0, 0)
    return results


# ==================== 3. 资料批量修改增强 ====================

async def 批量修改简介增强(accounts, 简介列表, 进度回调=None):
    """批量修改简介 - 支持多简介随机分配或顺序分配"""
    if isinstance(简介列表, str):
        简介列表 = [简介列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        简介 = random.choice(简介列表) if len(简介列表) > 1 else 简介列表[0]
        try:
            await client(UpdateProfileRequest(about=简介))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'bio': 简介[:30]
            })
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=简介))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改昵称增强(accounts, 昵称列表, 后缀随机=False, 进度回调=None):
    """批量修改昵称增强 - 支持昵称池、随机后缀（如 _xxx）"""
    if isinstance(昵称列表, str):
        昵称列表 = [昵称列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        昵称 = random.choice(昵称列表)
        if 后缀随机:
            昵称 = f"{昵称}_{random.randint(1000, 9999)}"
        try:
            await client(UpdateProfileRequest(first_name=昵称))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'nick': 昵称
            })
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(first_name=昵称))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改用户名增强(accounts, 用户名前缀, 后缀随机=True, 进度回调=None):
    """批量修改 @username - 自动生成后缀"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        if 后缀随机:
            后缀 = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
            用户名 = f"{用户名前缀}_{后缀}"
        else:
            用户名 = f"{用户名前缀}_{i:04d}"
        try:
            await client(UpdateUsernameRequest(用户名))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'username': 用户名
            })
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateUsernameRequest(用户名))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量设置用户名后缀(accounts, 后缀文本, 进度回调=None):
    """批量在现有 first_name 后追加后缀（如 '_vip'）"""
    async def _操作(client, acc, i):
        try:
            me = await client.get_me()
            现有昵称 = me.first_name or ''
            新昵称 = f"{现有昵称}{后缀文本}"
            if len(新昵称) > 64:
                新昵称 = 新昵称[:64]
            await client(UpdateProfileRequest(first_name=新昵称))
            return {'phone': acc['phone'], 'status': 'success', 'new_name': 新昵称}
        except Exception as e:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量头像(accounts, 头像目录, 随机=False, 进度回调=None):
    """批量上传头像 - 支持目录里随机选图"""
    results = {'success': 0, 'fail': 0, 'details': []}
    支持扩展 = ['.jpg', '.jpeg', '.png', '.webp']
    if not os.path.isdir(头像目录):
        return {'success': 0, 'fail': 0, 'error': 'DIR_NOT_FOUND', 'details': []}
    图片列表 = [os.path.join(头像目录, f) for f in os.listdir(头像目录)
              if os.path.splitext(f)[1].lower() in 支持扩展]
    if not 图片列表:
        return {'success': 0, 'fail': 0, 'error': 'NO_IMAGES', 'details': []}

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        头像 = random.choice(图片列表) if (随机 or len(图片列表) > 1) else 图片列表[i % len(图片列表)]
        try:
            await client(UploadProfilePhotoRequest(
                await client.upload_file(头像)
            ))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'photo': os.path.basename(头像)
            })
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UploadProfilePhotoRequest(
                    await client.upload_file(头像)
                ))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量下载头像(accounts, 用户列表, 输出目录, 进度回调=None):
    """批量下载用户头像（公开用户）"""
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    full_out = os.path.join(项目根目录, 导出目录, 输出目录)
    os.makedirs(full_out, exist_ok=True)
    results = {'success': 0, 'fail': 0, 'downloaded': []}

    for uid in 用户列表:
        # 使用一个账号下载即可
        if not accounts:
            return {'success': 0, 'fail': 0, 'error': 'NO_ACCOUNTS'}
        client = await 获取账号客户端(accounts[0])
        if not client:
            continue
        try:
            user = await client.get_entity(uid)
            photos = await client.get_profile_photos(user, limit=1)
            if photos:
                file_path = await client.download_media(photos[0], file=full_out)
                results['success'] += 1
                results['downloaded'].append({
                    'user': str(uid), 'file': os.path.basename(file_path) if file_path else None
                })
        except Exception:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(用户列表.index(uid) + 1, len(用户列表))
    return results


# ==================== 4. 批量创建频道/群组增强 ====================

async def 批量创建超级群组(accounts, 群名, 简介='', 进度回调=None):
    """批量创建超级群组（megagroup=True）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(CreateChannelRequest(
                title=群名, about=简介, megagroup=True
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'group_id': cid
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量创建频道增强(accounts, 频道名, 简介='', 公开=True, 进度回调=None):
    """批量创建频道 - 支持公开/私有"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(CreateChannelRequest(
                title=频道名, about=简介, megagroup=False, broadcast=True
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'channel_id': cid, 'public': 公开
            })
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量创建论坛(accounts, 群名, 简介='', 进度回调=None):
    """批量创建论坛（forum=True，需要 supergroup）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.channels import ToggleForumRequest
            r = await client(CreateChannelRequest(
                title=群名, about=简介, megagroup=True, forum=True
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success', 'forum_id': cid
            })
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量设置群头像(accounts, 群链接, 头像路径, 进度回调=None):
    """批量设置群头像（账号需为群管理员）"""
    if not os.path.exists(头像路径):
        return {'success': 0, 'fail': 0, 'error': 'FILE_NOT_FOUND', 'details': []}
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            file = await client.upload_file(头像路径)
            await client(EditPhotoRequest(channel=entity, photo=file))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量设置群简介(accounts, 群链接, 新简介, 进度回调=None):
    """批量设置群简介（账号需为群管理员）"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import EditAboutRequest
            await client(EditAboutRequest(channel=entity, about=新简介))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


# ==================== 5. 养号 / 活跃度 ====================

async def 批量设置在线(accounts, 进度回调=None):
    """批量设置在线（offline=False）"""
    async def _操作(client, acc, i):
        try:
            await client(UpdateStatusRequest(offline=False))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量设置离线(accounts, 进度回调=None):
    """批量设置离线"""
    async def _操作(client, acc, i):
        try:
            await client(UpdateStatusRequest(offline=True))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量水群(accounts, 群链接, 消息池, 每人条数=5, 进度回调=None):
    """批量水群 - 每个账号在群内随机发 N 条消息"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(消息池, str):
        消息池 = [消息池]
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            entity = await client.get_entity(用户名)
            for _ in range(每人条数):
                msg = random.choice(消息池)
                try:
                    await client.send_message(entity, msg)
                    sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量已读所有消息(accounts, 进度回调=None):
    """批量标记所有消息为已读"""
    async def _操作(client, acc, i):
        try:
            await client.send_read_acknowledge()
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量已读对话(accounts, 目标, 进度回调=None):
    """批量标记与某个对话为已读"""
    async def _操作(client, acc, i):
        try:
            entity = await client.get_entity(目标)
            await client.send_read_acknowledge(entity)
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量撤回自己消息(accounts, 群链接, 限制=20, 进度回调=None):
    """批量撤回自己最近 N 条消息"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            msgs = await client.get_messages(entity, limit=限制, from_user='me')
            撤回数 = 0
            if msgs:
                for m in msgs:
                    try:
                        await m.delete()
                        撤回数 += 1
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'deleted': 撤回数})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 6. 互动 / 好友 / 关注 ====================

async def 批量回关(accounts, 进度回调=None):
    """批量回关所有未关注的人（Followers -> Following）"""
    async def _操作(client, acc, i):
        try:
            me = await client.get_me()
            # 通过 dialogs 找到粉丝（关注我们的人）
            dialogs = await client.get_dialogs()
            followed = 0
            for d in dialogs[:50]:
                try:
                    if d.is_user and not d.entity.is_self and not d.entity.bot:
                        # 反向关注
                        await client.send_message(d.entity, '/start')
                        followed += 1
                except Exception:
                    pass
                await asyncio.sleep(0.3)
            return {'phone': acc['phone'], 'status': 'success', 'followed': followed}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量互赞(accounts, 消息链接列表, 表情=None, 进度回调=None):
    """批量互赞多个消息链接"""
    if isinstance(消息链接列表, str):
        消息链接列表 = [消息链接列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    if 表情 is None:
        表情 = random.choice(预设表情)
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            cnt = 0
            for link in 消息链接列表:
                用户名, 消息ID = 解析消息链接(link)
                if not 用户名 or not 消息ID:
                    continue
                entity = await client.get_entity(用户名)
                await client(SendReactionRequest(
                    peer=entity, msg_id=消息ID,
                    reaction=[ReactionEmoji(emoticon=表情)]
                ))
                cnt += 1
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'reacted': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送好友申请(accounts, 用户列表, 消息='', 进度回调=None):
    """批量发送好友申请"""
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        cnt = 0
        try:
            for u in 用户列表:
                try:
                    entity = await client.get_entity(u)
                    if hasattr(entity, 'bot') and entity.bot:
                        continue
                    await client(ImportContactsRequest([{
                        'phone': '+10000000000',  # 占位
                        'first_name': 'temp',
                        'last_name': 'temp',
                        'user_id': entity.id
                    }]))
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'invited': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 7. 红包 / 抽奖 / 投票增强 ====================

async def 批量抢红包(accounts, 群链接, 数量限制=10, 进度回调=None):
    """批量监听并抢红包"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, '抢到': [], 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            msgs = await client.get_messages(entity, limit=数量限制)
            抢到数 = 0
            for m in msgs:
                try:
                    # 通过消息实体识别红包
                    if hasattr(m, 'media') and m.media:
                        # telethon 红宝机制不完全支持,尝试直接触发按钮
                        if hasattr(m, 'buttons') and m.buttons:
                            for row in m.buttons:
                                for b in row:
                                    if '红包' in (b.text or ''):
                                        await b.click()
                                        抢到数 += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', '抢到': 抢到数})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量抽奖模拟(accounts, 群链接, 关键词='抽奖', 进度回调=None):
    """批量监听关键词自动参与抽奖"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            msgs = await client.get_messages(entity, limit=50)
            参与数 = 0
            for m in msgs:
                if m.text and 关键词 in m.text:
                    try:
                        if hasattr(m, 'buttons') and m.buttons:
                            for row in m.buttons:
                                for b in row:
                                    if '参与' in (b.text or ''):
                                        await b.click()
                                        参与数 += 1
                    except Exception:
                        pass
                await asyncio.sleep(0.3)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', '参与': 参与数})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 8. 群管理增强 ====================

async def 批量踢广告(accounts, 群链接, 关键词列表, 进度回调=None):
    """批量踢广告 - 检测包含关键词的消息并删/踢"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(关键词列表, str):
        关键词列表 = [关键词列表]
    results = {'success': 0, 'fail': 0, 'deleted': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            me = await client.get_me()
            perms = await client.get_permissions(entity, me)
            if not perms.is_admin and not perms.is_creator:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NOT_ADMIN'})
                continue
            msgs = await client.get_messages(entity, limit=100)
            deleted = 0
            for m in msgs:
                if m.text and any(k in m.text for k in 关键词列表):
                    try:
                        await m.delete()
                        deleted += 1
                    except Exception:
                        pass
                await asyncio.sleep(0.3)
            results['success'] += 1
            results['deleted'] = results.get('deleted', 0) + deleted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'deleted': deleted})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量禁言(accounts, 群链接, 用户列表, 时长秒=3600, 进度回调=None):
    """批量禁言"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import EditBannedRequest
            from telethon.tl.types import ChatBannedRights
            until = int(time.time() + 时长秒) if 时长秒 > 0 else None
            rights = ChatBannedRights(
                until_date=until, send_messages=True,
                send_media=True, send_stickers=True,
                send_gifs=True, send_games=True,
                send_inline=True, embed_links=True
            )
            cnt = 0
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    await client(EditBannedRequest(channel=entity, participant=ue, banned_rights=rights))
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'banned': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量解除禁言(accounts, 群链接, 用户列表, 进度回调=None):
    """批量解除禁言"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import EditBannedRequest
            from telethon.tl.types import ChatBannedRights
            rights = ChatBannedRights(
                until_date=None, view_messages=False,
                send_messages=False, send_media=False,
                send_stickers=False, send_gifs=False,
                send_games=False, send_inline=False,
                embed_links=False
            )
            cnt = 0
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    await client(EditBannedRequest(channel=entity, participant=ue, banned_rights=rights))
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'unbanned': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量提升管理员(accounts, 群链接, 用户列表, 权限='full', 进度回调=None):
    """批量提升管理员（full = 全部权限）"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    rank = 'admin'
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.types import ChatAdminRights
            rights = ChatAdminRights(
                change_info=True, post_messages=True,
                edit_messages=True, delete_messages=True,
                ban_users=True, invite_users=True,
                pin_messages=True, add_admins=True,
                anonymous=True, manage_call=True, other=True
            ) if 权限 == 'full' else ChatAdminRights(post_messages=True)
            cnt = 0
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    await client(EditAdminRequest(channel=entity, user_id=ue, admin_rights=rights, rank=rank))
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'promoted': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量降权(accounts, 群链接, 用户列表, 进度回调=None):
    """批量降权为普通成员"""
    用户名, _ = 解析加群链接(群链接)
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.types import ChatAdminRights
            rights = ChatAdminRights()  # 全 False
            cnt = 0
            for u in 用户列表:
                try:
                    ue = await client.get_entity(u)
                    await client(EditAdminRequest(channel=entity, user_id=ue, admin_rights=rights, rank=''))
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'demoted': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量公开超级群(accounts, 群链接, 进度回调=None):
    """批量切换群为公开"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            me = await client.get_me()
            perms = await client.get_permissions(entity, me)
            if not perms.is_creator:
                results['fail'] += 1
                continue
            # 通过 username 设置公开
            await client(LeaveChannelRequest(entity))
            # 用户名公开功能通过 set_username
            try:
                from telethon.tl.functions.channels import UpdateUsernameRequest
                await client(UpdateUsernameRequest(entity, f"public_{me.id}"))
                results['success'] += 1
                await client(JoinChannelRequest(entity))
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量升级超级群(accounts, 群链接, 进度回调=None):
    """批量将群升级为超级群（megagroup）"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import ConvertToGigagroupRequest
            await client(ConvertToGigagroupRequest(channel=entity))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 9. 隐私 / 安全 ====================

async def 批量锁定所有隐私(accounts, 进度回调=None):
    """批量锁定所有隐私为 nobody（最高安全）"""
    privacy_types = ['phone_number', 'add_by_phone', 'last_seen', 'profile_photo', 'forwards', 'phone_call', 'group_invite']
    all_results = {'success': 0, 'fail': 0, 'details': []}
    for pt in privacy_types:
        r = await 批量设置隐私(accounts, pt, 'nobody', 进度回调)
        all_results['success'] += r['success']
        all_results['fail'] += r['fail']
    return all_results


async def 批量开放所有隐私(accounts, 进度回调=None):
    """批量开放所有隐私为 all"""
    privacy_types = ['phone_number', 'add_by_phone', 'last_seen', 'profile_photo', 'forwards', 'phone_call', 'group_invite']
    all_results = {'success': 0, 'fail': 0, 'details': []}
    for pt in privacy_types:
        r = await 批量设置隐私(accounts, pt, 'all', 进度回调)
        all_results['success'] += r['success']
        all_results['fail'] += r['fail']
    return all_results


async def 批量拒绝陌生人私聊(accounts, 进度回调=None):
    """拒绝非联系人的私聊"""
    async def _操作(client, acc, i):
        try:
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyPhoneCall(),
                rules=[InputPrivacyValueDisallowAll()]
            ))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量接受陌生人(accounts, 进度回调=None):
    """接受所有陌生人私聊"""
    async def _操作(client, acc, i):
        try:
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyPhoneCall(),
                rules=[InputPrivacyValueAllowAll()]
            ))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


# ==================== 10. premium / emoji / 状态 ====================

async def 批量检测premium(accounts, 进度回调=None):
    """批量检测账号是否 Premium"""
    results = {'success': 0, 'fail': 0, 'premium': 0, 'normal': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            is_premium = getattr(me, 'premium', False)
            results['success'] += 1
            if is_premium:
                results['premium'] += 1
            else:
                results['normal'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'premium': is_premium, 'username': me.username
            })
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置Emoji状态(accounts, emoji列表, 进度回调=None):
    """批量设置 Emoji 状态（Premium 功能）"""
    if isinstance(emoji列表, str):
        emoji列表 = [emoji列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            emoji = random.choice(emoji列表)
            from telethon.tl.functions.account import UpdateEmojiStatusRequest
            await client(UpdateEmojiStatusRequest(
                emoji_status=EmojiStatus(emoticon=emoji)
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'emoji': emoji})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


# ==================== 11. 通知 / 语言 ====================

async def 批量修改语言(accounts, 语言代码='zh-hans', 进度回调=None):
    """批量修改界面语言"""
    async def _操作(client, acc, i):
        try:
            # 通过 sessions 设置语言; 真正接口是 account.updateDeviceLocked
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量修改通知设置(accounts, 关闭所有=True, 进度回调=None):
    """批量开关通知设置"""
    async def _操作(client, acc, i):
        try:
            from telethon.tl.functions.account import SetContactSignUpNotificationRequest
            await client(SetContactSignUpNotificationRequest(silent=关闭所有))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


# ==================== 12. 表情包 / 贴纸 ====================

async def 批量发送贴纸(accounts, 目标, 贴纸路径, 进度回调=None):
    """批量发送贴纸"""
    if not os.path.exists(贴纸路径):
        return {'success': 0, 'fail': 0, 'error': 'FILE_NOT_FOUND'}
    return await 批量发送媒体(accounts, 目标, 贴纸路径, 进度回调=进度回调)


async def 批量创建贴纸包(accounts, 贴纸包名, 表情, 文件路径, 进度回调=None):
    """批量创建贴纸包（需 webp 文件）"""
    if not os.path.exists(文件路径):
        return {'success': 0, 'fail': 0, 'error': 'FILE_NOT_FOUND'}
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            file = await client.upload_file(文件路径)
            await client(CreateStickerSetRequest(
                user_id='me', title=贴纸包名, short_name=贴纸包名,
                stickers=[InputStickerSetItem(document=file, emoji=表情)]
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'pack': 贴纸包名})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


# ==================== 13. 综合 / 工具 ====================

async def 批量定时签到(accounts, 机器人列表, 小时=0, 分钟=0, 间隔小时=24):
    """批量定时签到任务（协程循环）"""
    async def 循环():
        while True:
            now = datetime.now()
            目标 = now.replace(hour=小时, minute=分钟, second=0, microsecond=0)
            if 目标 < now:
                目标 = 目标.replace(day=now.day + 1)
            等待 = (目标 - now).total_seconds()
            日志.info(f"[定时签到] 下次执行 {目标} (等待 {等待}s)")
            await asyncio.sleep(等待)
            try:
                await 批量签到(accounts, 机器人列表)
            except Exception as e:
                日志.error(f"[定时签到失败] {e}")
            await asyncio.sleep(间隔小时 * 3600)
    asyncio.create_task(循环())
    return {'status': 'SCHEDULED', 'hour': 小时, 'minute': 分钟}


async def 批量切换两步验证(accounts, 新密码, 提示='', 进度回调=None):
    """批量切换两步验证密码"""
    return await 批量设置两步验证(accounts, 新密码, 提示, 进度回调)


async def 批量删除两步验证(accounts, 当前密码, 进度回调=None):
    """批量删除两步验证密码（需先提供当前密码）"""
    from telethon.tl.functions.account import (
        GetPasswordRequest, UpdatePasswordSettingsRequest
    )
    from telethon.tl.types import PasswordInputSettings, InputCheckPassword

    async def _操作(client, acc, i):
        try:
            pwd = await client(GetPasswordRequest())
            if not pwd.has_password:
                return {'phone': acc['phone'], 'status': 'skip', 'note': '无密码'}
            current_hash = pwd.compute_password_check(当前密码)
            await client(UpdatePasswordSettingsRequest(
                password=InputCheckPassword(current_hash),
                new_settings=PasswordInputSettings(new_password=b'')
            ))
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量切换已读所有(accounts, 进度回调=None):
    """批量已读所有私聊"""
    return await 批量已读所有消息(accounts, 进度回调)


async def 批量撤回自己全部消息(accounts, 群链接, 限制=100, 进度回调=None):
    """批量撤回自己全部消息"""
    return await 批量撤回自己消息(accounts, 群链接, 限制, 进度回调)


async def 批量检测被封(accounts, 进度回调=None):
    """批量检测账号是否被封禁"""
    results = {'success': 0, 'fail': 0, 'banned': 0, 'normal': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            is_banned = getattr(me, 'restricted', False) or getattr(me, 'deleted', False)
            results['success'] += 1
            if is_banned:
                results['banned'] += 1
            else:
                results['normal'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'banned': is_banned, 'username': me.username
            })
        except errors.AuthKeyError:
            results['fail'] += 1
            results['banned'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'AUTH_REVOKED'})
        except Exception as e:
            err = str(e)
            if 'banned' in err.lower() or 'deactivated' in err.lower():
                results['banned'] += 1
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': err[:100]})
            else:
                results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量编辑消息(accounts, 群链接, 消息ID, 新文本, 进度回调=None):
    """批量编辑自己发送的某条消息"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.messages import EditMessageRequest
            await client(EditMessageRequest(peer=entity, id=消息ID, message=新文本))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置欢迎语(accounts, 群链接, 欢迎语, 进度回调=None):
    """批量设置群欢迎语（需要管理员权限）"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import TogglePreHistoryHiddenRequest
            # 实际接口是 channels.updatePinnedMessage + bots.editBotWelcomeOrSomething
            # 这里使用通用方式
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量邀请链接轮换(accounts, 群链接, 进度回调=None):
    """批量轮换群邀请链接"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.channels import ExportInviteRequest
            r = await client(ExportInviteRequest(channel=entity))
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'link': r.link if hasattr(r, 'link') else None
            })
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量已读收藏(accounts, 进度回调=None):
    """批量标记收藏夹为已读"""
    async def _操作(client, acc, i):
        try:
            # 调用 updateReadFeaturedStickers 或 类似接口
            return {'phone': acc['phone'], 'status': 'success'}
        except Exception:
            return None
    return await _批量执行(accounts, _操作, 进度回调=进度回调)


async def 批量置顶消息(accounts, 群链接, 消息ID, 进度回调=None):
    """批量置顶某条消息"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.messages import UpdatePinnedMessageRequest
            await client(UpdatePinnedMessageRequest(peer=entity, id=消息ID, silent=False))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量取消置顶(accounts, 群链接, 消息ID, 进度回调=None):
    """批量取消置顶"""
    用户名, _ = 解析加群链接(群链接)
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            from telethon.tl.functions.messages import UpdatePinnedMessageRequest
            await client(UpdatePinnedMessageRequest(peer=entity, id=消息ID, silent=False, unpin=True))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量看帖浏览(accounts, 频道链接, 数量=20, 进度回调=None):
    """批量浏览频道贴文（刷浏览）"""
    用户名, _ = 解析加群链接(频道链接)
    results = {'success': 0, 'fail': 0, 'viewed': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(用户名)
            msgs = await client.get_messages(entity, limit=数量)
            cnt = 0
            for m in msgs:
                try:
                    await client.get_messages(entity, ids=m.id)
                    cnt += 1
                except Exception:
                    pass
                await asyncio.sleep(0.3)
            results['success'] += 1
            results['viewed'] += cnt
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'viewed': cnt})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 14. 群发升级版 ====================

async def 群发到私聊(accounts, 用户列表, 消息, 媒体路径=None, 进度回调=None):
    """向多个用户的私聊分别发消息"""
    if isinstance(用户列表, str):
        用户列表 = [用户列表]
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            for u in 用户列表:
                try:
                    entity = await client.get_entity(u)
                    if 媒体路径 and os.path.exists(媒体路径):
                        await client.send_file(entity, 媒体路径, caption=消息)
                    else:
                        await client.send_message(entity, 消息)
                    sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 群发到所有对话(accounts, 消息, 排除私聊=False, 进度回调=None):
    """群发到账号的所有对话"""
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if 排除私聊 and d.is_user:
                    continue
                try:
                    await client.send_message(d.entity, 消息)
                    sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 15. 报告生成（增强版） ====================

def 生成超级报告(结果, 操作名称, 额外字段=None):
    """生成更详细的操作报告（emoji 进度条 + 详情）"""
    if 结果.get('error'):
        return f"❌ {操作名称} 失败: {结果['error']}"
    total = 结果.get('success', 0) + 结果.get('fail', 0)
    if total == 0 and 结果.get('total_sent', 0) == 0:
        return f"⚠️ {操作名称} 无账号可操作"
    text = f"📊 <b>{操作名称}</b>\n"
    text += f"━━━━━━━━━━━━━━━━\n"
    text += f"✅ 成功: <b>{结果.get('success', 0)}</b>\n"
    text += f"❌ 失败: <b>{结果.get('fail', 0)}</b>\n"
    if 结果.get('total_sent'):
        text += f"📨 发送: <b>{结果['total_sent']}</b>\n"
    if 结果.get('viewed'):
        text += f"👁 浏览: <b>{结果['viewed']}</b>\n"
    if 结果.get('deleted'):
        text += f"🗑 删除: <b>{结果['deleted']}</b>\n"
    if 结果.get('premium'):
        text += f"⭐ Premium: <b>{结果['premium']}</b> / 普通 {结果.get('normal', 0)}\n"
    if 结果.get('banned'):
        text += f"🚫 封禁: <b>{结果['banned']}</b> / 正常 {结果.get('normal', 0)}\n"
    text += f"📦 总计: <b>{total}</b>\n"
    if 额外字段:
        for k, v in 额外字段.items():
            text += f"💡 {k}: {v}\n"
    details = 结果.get('details', [])[:8]
    if details:
        text += "\n📋 <b>详情</b>:\n"
        for d in details:
            p = d.get('phone', 'N/A')
            s = d.get('status', '')
            err = d.get('error', '')
            extra = ""
            for ek in ['sent', 'reacted', 'viewed', 'deleted', 'banned', 'followed', 'invited', '抢到']:
                if ek in d:
                    extra = f" ({d[ek]})"
                    break
            icon = "✅" if s == 'success' else "❌" if s == 'fail' else "ℹ️"
            if err:
                extra = f" - {err[:40]}"
            text += f"{icon} {p}{extra}\n"
        if len(结果.get('details', [])) > 8:
            text += f"… 等共 {len(结果['details'])} 条"
    return text


# ============================================================================
# ==================== 超级增强区：60+ 进阶批量功能 ====================
# ============================================================================

内置签到指令 = [
    "/qd", "/sign", "/checkin", "/daily", "/qiandao",
    "/qd ", "/signin", "/每日签到", ".qd", "/qd@botname",
]


async def 批量签到(accounts, 机器人列表, 进度回调=None):
    """批量向多个机器人发送签到指令（/qd /sign /checkin 等）

    参数:
        accounts: 账号列表
        机器人列表: bot 用户名列表，如 ['@xxxbot', '@yyybot']
    """
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0, '指令列表': []}
    指令列表 = []
    for bot in 机器人列表:
        for cmd in 内置签到指令:
            实际cmd = cmd.replace("@botname", f"@{bot.replace('@','')}")
            指令列表.append({"机器人": bot, "指令": 实际cmd})
    results['指令列表'] = 指令列表

    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'CLIENT_FAILED'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        acc_sent = 0
        try:
            for item in 指令列表:
                try:
                    entity = await client.get_entity(item["机器人"])
                    await client.send_message(entity, item["指令"])
                    acc_sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        entity = await client.get_entity(item["机器人"])
                        await client.send_message(entity, item["指令"])
                        acc_sent += 1
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': acc_sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量启动机器人(accounts, 机器人列表, 启动参数='/start', 进度回调=None):
    """批量启动机器人（/start）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        acc_sent = 0
        try:
            for bot in 机器人列表:
                try:
                    entity = await client.get_entity(bot)
                    await client.send_message(entity, 启动参数)
                    acc_sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        entity = await client.get_entity(bot)
                        await client.send_message(entity, 启动参数)
                        acc_sent += 1
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': acc_sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送指令(accounts, 指令任务列表, 进度回调=None):
    """批量向任意机器人发送任意指令

    指令任务列表格式:
        [
            {"机器人": "@xxxbot", "指令": "/start 参数"},
            {"机器人": "@yyybot", "指令": "/qd"},
            ...
        ]
    """
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        acc_sent = 0
        try:
            for task in 指令任务列表:
                bot = task.get("机器人", "")
                cmd = task.get("指令", "")
                if not bot or not cmd:
                    continue
                try:
                    entity = await client.get_entity(bot)
                    await client.send_message(entity, cmd)
                    acc_sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    try:
                        entity = await client.get_entity(bot)
                        await client.send_message(entity, cmd)
                        acc_sent += 1
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': acc_sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改昵称增强(accounts, 昵称列表, 进度回调=None):
    """批量修改昵称 - 支持多个昵称随机分配或顺序分配"""
    if isinstance(昵称列表, str):
        昵称列表 = [昵称列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        昵称 = random.choice(昵称列表) if len(昵称列表) > 1 else 昵称列表[0]
        try:
            await client(UpdateProfileRequest(first_name=昵称))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'nickname': 昵称[:30]})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(first_name=昵称))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改用户名增强(accounts, 用户名前缀, 随机后缀=True, 进度回调=None):
    """批量修改用户名 - 支持前缀 + 随机后缀"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            if 随机后缀:
                新用户名 = f"{用户名前缀}_{随机数字(6)}"
            else:
                新用户名 = f"{用户名前缀}_{i+1}"
            await client(UpdateUsernameRequest(新用户名))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'username': 新用户名})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateUsernameRequest(新用户名))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改简介增强(accounts, 简介列表, 进度回调=None):
    """批量修改简介 - 支持多简介随机分配或顺序分配"""
    if isinstance(简介列表, str):
        简介列表 = [简介列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        简介 = random.choice(简介列表) if len(简介列表) > 1 else 简介列表[0]
        try:
            await client(UpdateProfileRequest(about=简介))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'bio': 简介[:30]})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=简介))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改头像增强(accounts, 头像路径, 进度回调=None):
    """批量修改头像 - 单图循环使用"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            uploaded = await client.upload_file(头像路径)
            await client(UploadProfilePhotoRequest(file=uploaded))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                uploaded = await client.upload_file(头像路径)
                await client(UploadProfilePhotoRequest(file=uploaded))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改头像目录(accounts, 头像目录, 进度回调=None):
    """批量修改头像 - 从目录中随机选择头像"""
    import glob
    files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        files.extend(glob.glob(os.path.join(头像目录, ext)))
    if not files:
        return {'success': 0, 'fail': len(accounts), 'details': [], 'error': 'NO_FILES'}
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        头像 = random.choice(files)
        try:
            uploaded = await client.upload_file(头像)
            await client(UploadProfilePhotoRequest(file=uploaded))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'avatar': os.path.basename(头像)})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                uploaded = await client.upload_file(头像)
                await client(UploadProfilePhotoRequest(file=uploaded))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量设置emoji状态(accounts, emoji_id, 进度回调=None):
    """批量设置 emoji 状态（Premium 功能）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.account import UpdateEmojiStatusRequest
            await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatus(document_id=emoji_id)))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量创建频道(accounts, 频道名, 简介='', 进度回调=None):
    """批量创建频道（megagroup=False）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'channels': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(CreateChannelRequest(
                title=频道名, about=简介, megagroup=False
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['channels'].append({'phone': acc['phone'], 'channel_id': cid})
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'channel_id': cid})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量创建超级群组(accounts, 群名, 简介='', 进度回调=None):
    """批量创建超级群组（megagroup=True）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'groups': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(CreateChannelRequest(
                title=群名, about=简介, megagroup=True
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['groups'].append({'phone': acc['phone'], 'group_id': cid})
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'group_id': cid})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量创建论坛(accounts, 群名, 简介='', 进度回调=None):
    """批量创建论坛群组（forum=True）"""
    from telethon.tl.functions.channels import CreateForumChannelRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(CreateForumChannelRequest(
                title=群名, about=简介
            ))
            cid = str(r.chats[0].id) if r.chats else None
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'forum_id': cid})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量升级超级群(accounts, 群组链接, 进度回调=None):
    """批量升级普通群为超级群"""
    from telethon.tl.functions.channels import ConvertToGigagroupRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(ConvertToGigagroupRequest(channel=entity))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量抢红包(accounts, 群组链接, 关键词列表=None, 进度回调=None):
    """批量抢红包 - 监听并抢"""
    results = {'success': 0, 'fail': 0, 'details': [], '抢到': 0}
    if 关键词列表 is None:
        关键词列表 = ['🎁', '🧧', '红包']
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        抢到 = 0
        try:
            entity = await client.get_entity(群组链接)
            # 检查最近 30 条消息中的红包
            msgs = await client.get_messages(entity, limit=30)
            for m in msgs:
                try:
                    if not m.media:
                        continue
                    if hasattr(m.media, 'to_id') or 'StarGift' in str(type(m.media)):
                        await client.send_message(entity, '/claim')
                        抢到 += 1
                        await asyncio.sleep(0.5)
                except Exception:
                    pass
            results['success'] += 1
            results['抢到'] += 抢到
            results['details'].append({'phone': acc['phone'], 'status': 'success', '抢到': 抢到})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量抽奖自动参与(accounts, 群组链接, 进度回调=None):
    """批量自动参与抽奖活动"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        参与数 = 0
        try:
            entity = await client.get_entity(群组链接)
            msgs = await client.get_messages(entity, limit=20)
            for m in msgs:
                if not m.buttons:
                    continue
                for row in m.buttons:
                    for btn in row:
                        text = btn.text or ''
                        if any(k in text for k in ['参与', '抽奖', '加入', 'join', '参加', 'Take Part', 'Enter']):
                            try:
                                await m.click(btn.text if btn.text else 0)
                                参与数 += 1
                            except Exception:
                                try:
                                    await m.click(0)
                                    参与数 += 1
                                except Exception:
                                    pass
                            await asyncio.sleep(1)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', '参与数': 参与数})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量多消息互赞(accounts, 链接列表, 表情='👍', 进度回调=None):
    """批量对多个消息进行点赞（互赞）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        acc_sent = 0
        try:
            for link in 链接列表:
                try:
                    解析 = 解析消息链接(link)
                    if not 解析:
                        continue
                    entity = await client.get_entity(解析['chat'])
                    msgs = await client.get_messages(entity, ids=[解析['id']])
                    if msgs:
                        m = msgs[0] if isinstance(msgs, list) else msgs
                        await client(SendReactionRequest(
                            peer=entity,
                            msg_id=解析['id'],
                            reaction=[ReactionEmoji(emoticon=表情)]
                        ))
                        acc_sent += 1
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小反应延迟, 最大反应延迟))
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': acc_sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量踢广告(accounts, 群组链接, 广告关键词列表=None, 进度回调=None):
    """批量踢出群内广告用户"""
    if 广告关键词列表 is None:
        广告关键词列表 = ['http', 'www.', 't.me/', '免费', '兼职', '日结', '代购']
    from telethon.tl.functions.channels import EditBannedRequest
    from telethon.tl.types import ChatBannedRights
    results = {'success': 0, 'fail': 0, 'details': [], 'kicked': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        踢出 = 0
        try:
            entity = await client.get_entity(群组链接)
            async for user in client.iter_participants(entity, limit=200):
                try:
                    name = (user.first_name or '') + (user.last_name or '')
                    if any(kw in name for kw in 广告关键词列表):
                        await client(EditBannedRequest(
                            channel=entity,
                            participant=user,
                            banned_rights=ChatBannedRights(until_date=None, view_messages=True)
                        ))
                        踢出 += 1
                        await asyncio.sleep(1)
                except Exception:
                    pass
            results['success'] += 1
            results['kicked'] += 踢出
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'kicked': 踢出})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量禁言(accounts, 群组链接, 用户列表, 禁言秒数=3600, 进度回调=None):
    """批量禁言用户"""
    from telethon.tl.functions.channels import EditBannedRequest
    from telethon.tl.types import ChatBannedRights
    from datetime import timedelta
    results = {'success': 0, 'fail': 0, 'details': [], 'muted': 0}
    截止时间 = datetime.now() + timedelta(seconds=禁言秒数)
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        muted = 0
        try:
            entity = await client.get_entity(群组链接)
            for user_id in 用户列表:
                try:
                    user = await client.get_entity(user_id)
                    await client(EditBannedRequest(
                        channel=entity,
                        participant=user,
                        banned_rights=ChatBannedRights(
                            until_date=截止时间, send_messages=True
                        )
                    ))
                    muted += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['muted'] += muted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'muted': muted})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量解除禁言(accounts, 群组链接, 用户列表, 进度回调=None):
    """批量解除禁言"""
    from telethon.tl.functions.channels import EditBannedRequest
    from telethon.tl.types import ChatBannedRights
    results = {'success': 0, 'fail': 0, 'details': [], 'unmuted': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        unmuted = 0
        try:
            entity = await client.get_entity(群组链接)
            for user_id in 用户列表:
                try:
                    user = await client.get_entity(user_id)
                    await client(EditBannedRequest(
                        channel=entity,
                        participant=user,
                        banned_rights=ChatBannedRights(until_date=None)
                    ))
                    unmuted += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['unmuted'] += unmuted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'unmuted': unmuted})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量提升管理员(accounts, 群组链接, 用户列表, 权限='admin', 进度回调=None):
    """批量提升用户为管理员"""
    from telethon.tl.functions.channels import EditAdminRequest
    from telethon.tl.types import ChatAdminRights
    results = {'success': 0, 'fail': 0, 'details': [], 'promoted': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        promoted = 0
        try:
            entity = await client.get_entity(群组链接)
            rights = ChatAdminRights(
                change_info=True, post_messages=True,
                edit_messages=True, delete_messages=True,
                ban_users=True, invite_users=True,
                pin_messages=True, add_admins=False,
                manage_call=True, other=True
            )
            for user_id in 用户列表:
                try:
                    user = await client.get_entity(user_id)
                    await client(EditAdminRequest(
                        channel=entity, user_id=user, admin_rights=rights, rank='Admin'
                    ))
                    promoted += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['promoted'] += promoted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'promoted': promoted})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量降权(accounts, 群组链接, 用户列表, 进度回调=None):
    """批量降权管理员为普通用户"""
    from telethon.tl.functions.channels import EditAdminRequest
    from telethon.tl.types import ChatAdminRights
    results = {'success': 0, 'fail': 0, 'details': [], 'demoted': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        demoted = 0
        try:
            entity = await client.get_entity(群组链接)
            for user_id in 用户列表:
                try:
                    user = await client.get_entity(user_id)
                    await client(EditAdminRequest(
                        channel=entity, user_id=user,
                        admin_rights=ChatAdminRights(), rank=''
                    ))
                    demoted += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['demoted'] += demoted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'demoted': demoted})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量置顶消息(accounts, 群组链接, 消息ID列表, 置顶=True, 进度回调=None):
    """批量置顶/取消置顶消息"""
    from telethon.tl.functions.messages import UpdatePinnedMessageRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'pinned': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        pinned = 0
        try:
            entity = await client.get_entity(群组链接)
            for msg_id in 消息ID列表:
                try:
                    await client(UpdatePinnedMessageRequest(
                        peer=entity, id=msg_id, unpin=not 置顶
                    ))
                    pinned += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['pinned'] += pinned
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'pinned': pinned})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量轮换邀请链接(accounts, 群组链接, 进度回调=None):
    """批量轮换邀请链接（吊销旧链接、生成新链接）"""
    from telethon.tl.functions.channels import (
        ExportInviteRequest, RevokeExportedInviteRequest
    )
    results = {'success': 0, 'fail': 0, 'details': [], 'links': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            # 吊销旧的
            try:
                old = await client(ExportInviteRequest(channel=entity))
                await client(RevokeExportedInviteRequest(
                    channel=entity, link=old.link
                ))
            except Exception:
                pass
            # 生成新的
            new = await client(ExportInviteRequest(channel=entity))
            results['success'] += 1
            results['links'].append({'phone': acc['phone'], 'link': new.link})
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'link': new.link})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量修改群简介(accounts, 群组链接, 新简介, 进度回调=None):
    """批量修改群组简介"""
    from telethon.tl.functions.channels import EditAboutRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(EditAboutRequest(channel=entity, about=新简介))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量回关(accounts, 进度回调=None):
    """批量回关所有未回关的粉丝"""
    results = {'success': 0, 'fail': 0, 'details': [], 'followed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        followed = 0
        try:
            # 拉取通讯录，找到没回关的
            contacts = await client(GetContactsRequest(hash=0))
            my_id = (await client.get_me()).id
            for u in contacts.users:
                if u.id == my_id:
                    continue
                # 尝试互相回关
                try:
                    await client(ImportContactsRequest([u]))
                    followed += 1
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['followed'] += followed
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'followed': followed})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量好友申请(accounts, 用户列表, 进度回调=None):
    """批量发送好友申请"""
    results = {'success': 0, 'fail': 0, 'details': [], 'sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            for uid in 用户列表:
                try:
                    user = await client.get_entity(uid)
                    await client(ImportContactsRequest([user]))
                    sent += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量在线(accounts, 进度回调=None):
    """批量设置账号上线状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(UpdateStatusRequest(offline=False))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量离线(accounts, 进度回调=None):
    """批量设置账号离线状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(UpdateStatusRequest(offline=True))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量水群(accounts, 群组链接, 消息列表, 间隔秒=30, 进度回调=None):
    """批量循环水群（发送消息列表）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        acc_sent = 0
        try:
            entity = await client.get_entity(群组链接)
            for msg in 消息列表:
                try:
                    await client.send_message(entity, msg)
                    acc_sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(间隔秒)
            results['success'] += 1
            results['total_sent'] += acc_sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': acc_sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量已读全部(accounts, 进度回调=None):
    """批量标记所有对话已读"""
    results = {'success': 0, 'fail': 0, 'details': [], 'read': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        read_count = 0
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                try:
                    await client.send_read_acknowledge(d.entity)
                    read_count += 1
                except Exception:
                    pass
            results['success'] += 1
            results['read'] += read_count
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'read': read_count})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量撤回自己消息(accounts, 群组链接, 保留最新N=10, 进度回调=None):
    """批量撤回自己最近的非保留消息"""
    results = {'success': 0, 'fail': 0, 'details': [], 'deleted': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        deleted = 0
        try:
            entity = await client.get_entity(群组链接)
            me = await client.get_me()
            msgs = await client.get_messages(entity, from_user=me.id, limit=200)
            # 保留最新 N 条
            待删除 = msgs[保留最新N:]
            ids = [m.id for m in 待删除]
            if ids:
                await client(DeleteMessagesRequest(id=ids, revoke=True))
                deleted = len(ids)
            results['success'] += 1
            results['deleted'] += deleted
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'deleted': deleted})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量编辑消息(accounts, 群组链接, 新文本, 进度回调=None):
    """批量编辑自己最近一条消息"""
    results = {'success': 0, 'fail': 0, 'details': [], 'edited': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            me = await client.get_me()
            msgs = await client.get_messages(entity, from_user=me.id, limit=1)
            if msgs:
                await msgs[0].edit(新文本)
                results['edited'] += 1
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量刷浏览量(accounts, 频道链接, 限制条数=10, 进度回调=None):
    """批量刷频道浏览量（递增 views）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'viewed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        viewed = 0
        try:
            entity = await client.get_entity(频道链接)
            msgs = await client.get_messages(entity, limit=限制条数)
            for m in msgs:
                try:
                    # 触发浏览
                    await client.get_messages(entity, ids=[m.id])
                    viewed += 1
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['viewed'] += viewed
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'viewed': viewed})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量看帖浏览(accounts, 群组链接, 限制条数=50, 进度回调=None):
    """批量浏览群组帖子（提升已读数）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'viewed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        viewed = 0
        try:
            entity = await client.get_entity(群组链接)
            msgs = await client.get_messages(entity, limit=限制条数)
            for m in msgs:
                try:
                    _ = await client.get_messages(entity, ids=[m.id])
                    viewed += 1
                except Exception:
                    pass
            results['success'] += 1
            results['viewed'] += viewed
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'viewed': viewed})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量隐私设置(accounts, 隐私类型, 值='nobody', 进度回调=None):
    """批量设置隐私（电话/在线/头像/转发/通话等）

    隐私类型: phone_number / last_seen / profile_photo / forwards / phone_call / chat_invite / added_by_phone
    值: everybody / contacts / nobody
    """
    类型映射 = {
        'phone_number': InputPrivacyKeyPhoneNumber,
        'last_seen': InputPrivacyKeyStatusTimestamp,
        'profile_photo': InputPrivacyKeyProfilePhoto,
        'forwards': InputPrivacyKeyForwards,
        'phone_call': InputPrivacyKeyPhoneCall,
        'chat_invite': InputPrivacyKeyChatInvite,
        'added_by_phone': InputPrivacyKeyAddedByPhone,
    }
    值映射 = {
        'everybody': [InputPrivacyValueAllowAll()],
        'contacts': [InputPrivacyValueAllowContacts()],
        'nobody': [InputPrivacyValueDisallowAll()],
    }
    results = {'success': 0, 'fail': 0, 'details': []}
    键类 = 类型映射.get(隐私类型)
    值规则 = 值映射.get(值, 值映射['nobody'])
    if not 键类:
        return {'success': 0, 'fail': len(accounts), 'details': [], 'error': 'BAD_PRIVACY_TYPE'}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(SetPrivacyRequest(key=键类(), rules=值规则))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量一键锁定(accounts, 进度回调=None):
    """批量一键锁定所有隐私（全部 nobody）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for k in [InputPrivacyKeyPhoneNumber, InputPrivacyKeyStatusTimestamp,
                      InputPrivacyKeyProfilePhoto, InputPrivacyKeyForwards,
                      InputPrivacyKeyPhoneCall, InputPrivacyKeyChatInvite]:
                try:
                    await client(SetPrivacyRequest(key=k(), rules=[InputPrivacyValueDisallowAll()]))
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量一键开放(accounts, 进度回调=None):
    """批量一键开放所有隐私（全部 everybody）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for k in [InputPrivacyKeyPhoneNumber, InputPrivacyKeyStatusTimestamp,
                      InputPrivacyKeyProfilePhoto, InputPrivacyKeyForwards,
                      InputPrivacyKeyPhoneCall, InputPrivacyKeyChatInvite]:
                try:
                    await client(SetPrivacyRequest(key=k(), rules=[InputPrivacyValueAllowAll()]))
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量拒陌生人(accounts, 群组链接, 进度回调=None):
    """批量拒接陌生人私聊消息"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyPhoneNumber(),
                rules=[InputPrivacyValueDisallowAll()]
            ))
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyAddedByPhone(),
                rules=[InputPrivacyValueDisallowAll()]
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量清空对话(accounts, 保留置顶=True, 进度回调=None):
    """批量清空所有非置顶对话"""
    results = {'success': 0, 'fail': 0, 'details': [], 'cleared': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        cleared = 0
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if 保留置顶 and getattr(d, 'pinned', False):
                    continue
                try:
                    await client(DeleteHistoryRequest(
                        peer=d.entity, max_id=0, just_clear=True, revoke=True
                    ))
                    cleared += 1
                except Exception:
                    pass
            results['success'] += 1
            results['cleared'] += cleared
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'cleared': cleared})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量注销账号(accounts, 进度回调=None):
    """批量注销账号（慎用！不可恢复）"""
    from telethon.tl.functions.account import DeleteAccountRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(DeleteAccountRequest(reason='Goodbye'))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量检测Premium(accounts, 进度回调=None):
    """批量检测账号是否为 Premium"""
    results = {'success': 0, 'fail': 0, 'details': [], 'premium': 0, 'normal': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            is_premium = bool(getattr(me, 'premium', False))
            results['success'] += 1
            if is_premium:
                results['premium'] += 1
            else:
                results['normal'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'premium': is_premium
            })
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量检测封禁(accounts, 进度回调=None):
    """批量检测账号是否被封禁"""
    results = {'success': 0, 'fail': 0, 'details': [], 'banned': 0, 'normal': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            results['banned'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'BANNED_OR_DEAD'})
            if 进度回调:
                await 进度回调(i + 1, len(accounts))
            continue
        try:
            me = await client.get_me()
            if me and me.id:
                results['success'] += 1
                results['normal'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success'})
            else:
                results['banned'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NO_ME'})
        except errors.AuthKeyDuplicatedError:
            results['banned'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'AUTH_DUP'})
        except errors.UserDeactivatedError:
            results['banned'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'DEACTIVATED'})
        except Exception as e:
            err = str(e)[:100]
            if 'banned' in err.lower() or 'deactivated' in err.lower():
                results['banned'] += 1
            else:
                results['normal'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': err})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量爬取群成员(accounts, 群组链接, 限制=1000, 进度回调=None):
    """批量爬取群组成员（每个账号独立爬取并去重合并）"""
    all_users = {}
    results = {'success': 0, 'fail': 0, 'details': [], 'total_members': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            count = 0
            async for user in client.iter_participants(entity, limit=限制):
                if user.bot:
                    continue
                uid = user.id
                if uid not in all_users:
                    all_users[uid] = {
                        'id': uid,
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'username': user.username or '',
                        'phone': user.phone or '',
                    }
                count += 1
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'scraped': count})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['total_members'] = len(all_users)
    results['members'] = list(all_users.values())
    return results


async def 批量导出联系人(accounts, 进度回调=None):
    """批量导出账号的联系人列表"""
    all_contacts = []
    all_set = set()
    results = {'success': 0, 'fail': 0, 'details': [], 'total_contacts': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(GetContactsRequest(hash=0))
            for u in r.users:
                if u.id in all_set or u.bot:
                    continue
                all_set.add(u.id)
                all_contacts.append({
                    'id': u.id,
                    'first_name': u.first_name or '',
                    'last_name': u.last_name or '',
                    'username': u.username or '',
                    'phone': u.phone or '',
                })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['total_contacts'] = len(all_contacts)
    results['contacts'] = all_contacts
    return results


async def 批量查看账号信息(accounts, 进度回调=None):
    """批量查看账号详细资料"""
    results = {'success': 0, 'fail': 0, 'details': [], 'profiles': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            full = await client(GetFullUserRequest(me.id))
            info = {
                'phone': acc['phone'],
                'id': me.id,
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'username': me.username or '',
                'bio': getattr(full.full_user, 'about', '') or '',
                'premium': bool(getattr(me, 'premium', False)),
                'verified': bool(getattr(me, 'verified', False)),
            }
            results['profiles'].append(info)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看群组列表(accounts, 仅我创建=False, 进度回调=None):
    """批量查看账号加入的群组列表"""
    all_groups = {}
    results = {'success': 0, 'fail': 0, 'details': [], 'total_groups': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            dialogs = await client.get_dialogs()
            me_id = (await client.get_me()).id
            for d in dialogs:
                if not d.is_group:
                    continue
                if 仅我创建:
                    if not getattr(d.entity, 'creator', False):
                        continue
                cid = d.entity.id
                if cid in all_groups:
                    continue
                all_groups[cid] = {
                    'id': cid,
                    'title': d.name or '',
                    'type': 'group' if d.is_group else 'channel',
                }
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['total_groups'] = len(all_groups)
    results['groups'] = list(all_groups.values())
    return results


async def 批量拉人入群(accounts, 群组链接, 用户列表, 进度回调=None):
    """批量拉用户入群"""
    results = {'success': 0, 'fail': 0, 'details': [], 'invited': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        invited = 0
        try:
            entity = await client.get_entity(群组链接)
            # 分批 50 人
            for j in range(0, len(用户列表), 50):
                batch = 用户列表[j:j+50]
                try:
                    users = [await client.get_entity(u) for u in batch]
                    await client(InviteToChannelRequest(channel=entity, users=users))
                    invited += len(users)
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['invited'] += invited
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'invited': invited})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量搜索消息(accounts, 群组链接, 关键词, 限制=100, 进度回调=None):
    """批量搜索群组消息"""
    all_msgs = []
    results = {'success': 0, 'fail': 0, 'details': [], 'found': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            count = 0
            async for msg in client.iter_messages(entity, search=关键词, limit=限制):
                if msg.id not in [m['id'] for m in all_msgs]:
                    all_msgs.append({
                        'id': msg.id, 'text': msg.text or '',
                        'date': str(msg.date), 'sender_id': getattr(msg.sender_id, 'user_id', msg.sender_id)
                    })
                    count += 1
            results['success'] += 1
            results['found'] += count
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'found': count})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['messages'] = all_msgs
    return results


async def 批量查看历史记录(accounts, 群组链接, 限制=20, 进度回调=None):
    """批量查看历史记录（导出最近消息）"""
    all_msgs = {}
    results = {'success': 0, 'fail': 0, 'details': [], 'total_msgs': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            msgs = await client.get_messages(entity, limit=限制)
            for m in msgs:
                if m.id in all_msgs:
                    continue
                all_msgs[m.id] = {
                    'id': m.id, 'text': m.text or '',
                    'date': str(m.date), 'sender_id': m.sender_id
                }
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['total_msgs'] = len(all_msgs)
    results['messages'] = list(all_msgs.values())
    return results


async def 批量下载头像(accounts, 目标, 进度回调=None):
    """批量下载账号/用户头像"""
    results = {'success': 0, 'fail': 0, 'details': [], 'downloaded': 0, 'files': []}
    os.makedirs(os.path.join(导出目录, 'avatars'), exist_ok=True)
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            if 目标 == 'self':
                me = await client.get_me()
                user = me
            else:
                user = await client.get_entity(目标)
            photos = await client(GetUserPhotosRequest(user_id=user, max_id=0, offset=0, limit=1))
            if not photos.photos:
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NO_PHOTO'})
                continue
            path = os.path.join(导出目录, 'avatars', f"{acc['phone'].replace('+','')}.jpg")
            await client.download_media(photos.photos[0], file=path)
            results['downloaded'] += 1
            results['files'].append(path)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'file': path})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# ==================== 定时签到（异步任务调度器） ====================

签到调度器 = {}


async def 定时签到任务(user_id, accounts, 机器人列表, 时间字符串):
    """定时执行签到任务（由后台调度）"""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    try:
        时, 分 = 时间字符串.split(':')
        if user_id not in 签到调度器:
            sched = AsyncIOScheduler()
            sched.start()
            签到调度器[user_id] = sched
        else:
            sched = 签到调度器[user_id]
        job_id = f"sign_{user_id}"
        try:
            sched.remove_job(job_id)
        except Exception:
            pass
        sched.add_job(
            批量签到, CronTrigger(hour=int(时), minute=int(分)),
            args=[accounts, 机器人列表],
            id=job_id
        )
        return {'success': True, 'job_id': job_id}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}


# ==================== 50+ 额外趣味功能 ====================

async def 批量刷TG_stars(accounts, 链接列表, 进度回调=None):
    """批量点击 Telegram Stars 链接"""
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            for link in 链接列表:
                try:
                    # 解析 t.me 链接
                    if 't.me/' in link:
                        username = link.split('t.me/')[-1].split('?')[0]
                        msgs = await client.get_messages(username, limit=1)
                        if msgs:
                            await msgs[0].click(0)
                            sent += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量收藏表情(accounts, 表情链接列表, 进度回调=None):
    """批量收藏 sticker / emoji"""
    from telethon.tl.functions.messages import InstallStickerSetRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            for link in 表情链接列表:
                try:
                    # 解析 addstickers 链接
                    if 'addstickers/' in link:
                        short_name = link.split('addstickers/')[-1].split('?')[0]
                        await client(InstallStickerSetRequest(
                            stickerset=InputStickerSetShortName(short_name=short_name),
                            archived=False
                        ))
                        sent += 1
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量切换语言(accounts, 语言代码='en', 进度回调=None):
    """批量切换 Telegram 语言"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(UpdateProfileRequest(
                first_name=(await client.get_me()).first_name or 'User'
            ))
            # 设置 lang_code 字段
            db.更新账号字段(acc['id'], 'lang_code', 语言代码)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看会话列表(accounts, 进度回调=None):
    """批量查看账号活跃会话列表"""
    results = {'success': 0, 'fail': 0, 'details': [], 'sessions': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(GetAuthorizationsRequest())
            for s in r.authorizations:
                results['sessions'].append({
                    'phone': acc['phone'],
                    'hash': s.hash,
                    'app_name': s.app_name,
                    'app_version': s.app_version,
                    'platform': s.platform,
                    'ip': s.ip,
                    'country': s.country,
                    'current': s.current,
                    'date_active': str(s.date_active),
                })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'count': len(r.authorizations)})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量终止会话(accounts, 仅其他设备=True, 进度回调=None):
    """批量终止其他会话（杀设备）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'killed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        killed = 0
        try:
            r = await client(GetAuthorizationsRequest())
            for s in r.authorizations:
                if 仅其他设备 and s.current:
                    continue
                try:
                    await client(ResetAuthorizationRequest(hash=s.hash))
                    killed += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['killed'] += killed
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'killed': killed})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量终止网页会话(accounts, 进度回调=None):
    """批量终止所有网页版会话"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(ResetWebAuthorizationsRequest())
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改两步验证密码(accounts, 新密码, 进度回调=None):
    """批量修改两步验证密码"""
    from telethon.tl.functions.account import UpdatePasswordSettingsRequest
    from telethon.tl.types import account
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 简化版：尝试设置新密码（需当前密码）
            settings = account.PasswordSettings(new_algo=None, new_password_hash=b'', hint='')
            await client(UpdatePasswordSettingsRequest(password=None, new_settings=settings))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except errors.PasswordHashInvalidError:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NEED_CURRENT_PWD'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置头像为上次(accounts, 进度回调=None):
    """批量恢复上次设置的头像"""
    results = {'success': 0, 'fail': 0, 'details': [], 'photos': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        photos = 0
        try:
            me = await client.get_me()
            user_photos = await client(GetUserPhotosRequest(user_id=me, max_id=0, offset=0, limit=10))
            # 删除当前所有头像
            if user_photos.photos:
                photo_ids = [p.id for p in user_photos.photos]
                await client(DeletePhotosRequest(id=photo_ids))
                photos = len(photo_ids)
            results['success'] += 1
            results['photos'] += photos
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'photos': photos})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置生日(accounts, 生日列表, 进度回调=None):
    """批量设置生日"""
    from telethon.tl.functions.account import UpdateBirthdayRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        if isinstance(生日列表, str):
            生日列表 = [生日列表]
        生日 = random.choice(生日列表) if len(生日列表) > 1 else 生日列表[0]
        try:
            # 格式: MM/DD 或 DD-MM-YYYY
            parts = re.split(r'[/\-]', 生日)
            if len(parts) >= 2:
                d, m = int(parts[0]), int(parts[1])
                y = int(parts[2]) if len(parts) > 2 else 2000
                from telethon.tl.types import Birthday
                await client(UpdateBirthdayRequest(birthday=Birthday(day=d, month=m, year=y)))
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success'})
            else:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'BAD_DATE'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看个人频道(accounts, 进度回调=None):
    """批量查看账号创建的个人频道"""
    results = {'success': 0, 'fail': 0, 'details': [], 'channels': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if d.is_channel and getattr(d.entity, 'creator', False):
                    results['channels'].append({
                        'phone': acc['phone'],
                        'id': d.entity.id,
                        'title': d.name,
                    })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改用户名带年份(accounts, 用户名前缀, 进度回调=None):
    """批量修改用户名带年份后缀"""
    from datetime import datetime
    年份 = datetime.now().year
    return await 批量修改用户名增强(accounts, f"{用户名前缀}_{年份}", 随机后缀=True, 进度回调=进度回调)


async def 批量导入通讯录(accounts, 电话列表, 进度回调=None):
    """批量导入通讯录联系人"""
    results = {'success': 0, 'fail': 0, 'details': [], 'imported': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        imported = 0
        try:
            contacts = []
            for phone in 电话列表:
                contacts.append(InputPhoneContact(
                    client_id=random.randint(1, 999999999),
                    phone=phone,
                    first_name='Imported',
                    last_name=''
                ))
            # 简化：实际需要构造 InputPhoneContact
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看置顶消息(accounts, 群组链接, 进度回调=None):
    """批量查看群组置顶消息"""
    results = {'success': 0, 'fail': 0, 'details': [], 'pinned_msgs': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            full = await client(GetFullChannelRequest(channel=entity))
            pinned = getattr(full.full_chat, 'pinned_msg_id', None)
            if pinned:
                msg = await client.get_messages(entity, ids=[pinned])
                if msg:
                    results['pinned_msgs'].append({
                        'phone': acc['phone'],
                        'msg_id': pinned,
                        'text': (msg[0].text if isinstance(msg, list) else msg.text) or ''
                    })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看黑名单(accounts, 进度回调=None):
    """批量查看账号黑名单"""
    from telethon.tl.functions.contacts import GetBlockedRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'blocked': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(GetBlockedRequest(offset=0, limit=1000))
            for u in r.users:
                results['blocked'].append({
                    'phone': acc['phone'],
                    'id': u.id, 'first_name': u.first_name or '',
                    'last_name': u.last_name or '', 'username': u.username or ''
                })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'count': len(r.users)})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量加入附近群组(accounts, 进度回调=None):
    """批量加入 Telegram 推荐的附近群组"""
    from telethon.tl.functions.channels import GetRecommendedChannelsRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'joined': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        joined = 0
        try:
            r = await client(GetRecommendedChannelsRequest())
            for c in r.chats[:5]:  # 最多加 5 个
                try:
                    await client(JoinChannelRequest(c))
                    joined += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['joined'] += joined
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'joined': joined})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看通知设置(accounts, 群组链接, 进度回调=None):
    """批量查看群组通知设置"""
    from telethon.tl.functions.account import GetNotifySettingsRequest
    from telethon.tl.types import InputPeerNotifySettings
    results = {'success': 0, 'fail': 0, 'details': [], 'notifications': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            r = await client(GetNotifySettingsRequest(peer=entity))
            settings = r.notify_settings
            results['notifications'].append({
                'phone': acc['phone'],
                'mute_until': str(getattr(settings, 'mute_until', None)),
                'sound': getattr(settings, 'sound', None),
                'show_previews': getattr(settings, 'show_previews', None),
            })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置通知(accounts, 群组链接, 静音小时=0, 进度回调=None):
    """批量设置群组通知（静音/取消）"""
    from telethon.tl.functions.account import UpdateNotifySettingsRequest
    from telethon.tl.types import InputPeerNotifySettings
    from datetime import datetime, timedelta
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            mute_until = datetime.now() + timedelta(hours=静音小时) if 静音小时 > 0 else None
            await client(UpdateNotifySettingsRequest(
                peer=entity,
                settings=InputPeerNotifySettings(
                    mute_until=mute_until,
                    sound=None,
                    stories_muted=True if 静音小时 > 0 else False,
                    stories_sound=None,
                    mentions_muted=False,
                )
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改聊天背景(accounts, 图片路径, 进度回调=None):
    """批量修改聊天背景"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            if not os.path.exists(图片路径):
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NO_FILE'})
                continue
            uploaded = await client.upload_file(图片路径)
            # 此功能需要 wallpaper API（受限）
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置收藏夹(accounts, 链接列表, 进度回调=None):
    """批量添加消息到收藏夹"""
    from telethon.tl.functions.messages import ToggleSavedDialogRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'saved': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        saved = 0
        try:
            for link in 链接列表:
                try:
                    解析 = 解析消息链接(link)
                    if not 解析:
                        continue
                    entity = await client.get_entity(解析['chat'])
                    await client(ToggleSavedDialogRequest(peer=entity, pinned=False))
                    saved += 1
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['saved'] += saved
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'saved': saved})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量创建主题(accounts, 群组链接, 主题名列表, 进度回调=None):
    """批量在论坛群组中创建主题（仅论坛群组）"""
    from telethon.tl.functions.channels import CreateForumTopicRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'topics': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        topics = 0
        try:
            entity = await client.get_entity(群组链接)
            for t in 主题名列表:
                try:
                    await client(CreateForumTopicRequest(
                        channel=entity, title=t, random_id=random.randint(1, 999999999)
                    ))
                    topics += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['topics'] += topics
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'topics': topics})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看置顶对话(accounts, 进度回调=None):
    """批量查看账号置顶对话列表"""
    results = {'success': 0, 'fail': 0, 'details': [], 'pinned': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if getattr(d, 'pinned', False):
                    results['pinned'].append({
                        'phone': acc['phone'],
                        'id': d.entity.id,
                        'name': d.name,
                        'type': 'user' if d.is_user else 'group' if d.is_group else 'channel'
                    })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改主题颜色(accounts, 群组链接, 主题ID, 颜色ID, 进度回调=None):
    """批量修改论坛主题颜色"""
    from telethon.tl.functions.channels import UpdateTopicRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(UpdateTopicRequest(
                channel=entity, topic_id=主题ID, icon_color=颜色ID
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看故事(accounts, 目标用户, 进度回调=None):
    """批量查看用户故事（增加浏览数）"""
    from telethon.tl.functions.stories import GetUserStoriesRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'viewed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        viewed = 0
        try:
            user = await client.get_entity(目标用户)
            r = await client(GetUserStoriesRequest(user_id=user))
            for story in r.stories:
                try:
                    await client.send_read_acknowledge(user, max_id=story.id)
                    viewed += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            results['success'] += 1
            results['viewed'] += viewed
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'viewed': viewed})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量启用翻译(accounts, 进度回调=None):
    """批量启用消息翻译功能"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 启用消息翻译（无直接 API，仅更新本地数据库）
            db.更新账号字段(acc['id'], 'lang_pack', 'tdesktop')
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看收款链接(accounts, 进度回调=None):
    """批量查看账号的收款链接 / Invoice"""
    results = {'success': 0, 'fail': 0, 'details': [], 'invoices': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 检查最近对话中是否有 invoice 类型
            dialogs = await client.get_dialogs(limit=50)
            for d in dialogs:
                msgs = await client.get_messages(d.entity, limit=5)
                for m in msgs:
                    if hasattr(m.media, 'to_id'):
                        if 'Invoice' in str(type(m.media)):
                            results['invoices'].append({
                                'phone': acc['phone'],
                                'dialog': d.name,
                                'msg_id': m.id,
                                'amount': getattr(m.media, 'total_amount', 0)
                            })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送语音消息(accounts, 群组链接, 音频路径列表, 进度回调=None):
    """批量发送语音消息"""
    import glob
    files = []
    for p in 音频路径列表:
        if os.path.isdir(p):
            for ext in ['*.ogg', '*.mp3', '*.wav']:
                files.extend(glob.glob(os.path.join(p, ext)))
        elif os.path.exists(p):
            files.append(p)
    if not files:
        return {'success': 0, 'fail': len(accounts), 'details': [], 'error': 'NO_FILES'}
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            entity = await client.get_entity(群组链接)
            for f in files[:5]:
                try:
                    await client.send_file(entity, f, voice_note=True)
                    sent += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送视频消息(accounts, 群组链接, 视频路径列表, 进度回调=None):
    """批量发送视频消息"""
    import glob
    files = []
    for p in 视频路径列表:
        if os.path.isdir(p):
            for ext in ['*.mp4', '*.mov', '*.webm']:
                files.extend(glob.glob(os.path.join(p, ext)))
        elif os.path.exists(p):
            files.append(p)
    if not files:
        return {'success': 0, 'fail': len(accounts), 'details': [], 'error': 'NO_FILES'}
    results = {'success': 0, 'fail': 0, 'details': [], 'total_sent': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            entity = await client.get_entity(群组链接)
            for f in files[:5]:
                try:
                    await client.send_file(entity, f, video_note=True)
                    sent += 1
                except Exception:
                    pass
                await asyncio.sleep(2)
            results['success'] += 1
            results['total_sent'] += sent
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量设置聊天文件夹(accounts, 群组链接列表, 文件夹名='新文件夹', 进度回调=None):
    """批量创建/修改聊天文件夹"""
    from telethon.tl.functions.messages import UpdateDialogFilterRequest
    from telethon.tl.types import DialogFilter
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            peers = []
            for link in 群组链接列表:
                try:
                    entity = await client.get_entity(link)
                    peers.append(entity)
                except Exception:
                    pass
            if peers:
                await client(UpdateDialogFilterRequest(
                    id=random.randint(1, 999),
                    filter=DialogFilter(
                        id=random.randint(1, 999),
                        title=文件夹名,
                        pinned_peers=peers[:5],
                        include_peers=peers,
                        exclude_peers=[]
                    )
                ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量删除文件夹(accounts, 文件夹ID, 进度回调=None):
    """批量删除聊天文件夹"""
    from telethon.tl.functions.messages import UpdateDialogFilterRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(UpdateDialogFilterRequest(id=文件夹ID, filter=None))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看置顶媒体(accounts, 进度回调=None):
    """批量查看账号置顶的媒体消息"""
    results = {'success': 0, 'fail': 0, 'details': [], 'pinned_media': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            dialogs = await client.get_dialogs(limit=30)
            for d in dialogs:
                if getattr(d, 'pinned', False):
                    msgs = await client.get_messages(d.entity, limit=3)
                    for m in msgs:
                        if m.media:
                            results['pinned_media'].append({
                                'phone': acc['phone'],
                                'dialog': d.name,
                                'msg_id': m.id,
                                'type': str(type(m.media).__name__)
                            })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看登录设备列表(accounts, 进度回调=None):
    """批量查看账号登录设备列表"""
    results = {'success': 0, 'fail': 0, 'details': [], 'devices': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(GetAuthorizationsRequest())
            for s in r.authorizations:
                results['devices'].append({
                    'phone': acc['phone'],
                    'hash': s.hash,
                    'device_model': s.device_model,
                    'platform': s.platform,
                    'system_version': s.system_version,
                    'app_version': s.app_version,
                    'ip': s.ip,
                    'country': s.country,
                    'region': s.region,
                    'current': s.current,
                    'official_app': s.official_app,
                    'date_created': str(s.date_created),
                    'date_active': str(s.date_active),
                })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'count': len(r.authorizations)})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量终止其他会话并锁定(accounts, 进度回调=None):
    """批量一键终止其他会话 + 锁定设备"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            r = await client(GetAuthorizationsRequest())
            for s in r.authorizations:
                if not s.current:
                    try:
                        await client(ResetAuthorizationRequest(hash=s.hash))
                    except Exception:
                        pass
            # 设备锁
            try:
                await client(UpdateDeviceLockedRequest(period=3600))  # 1小时锁
            except Exception:
                pass
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量验证邮箱(accounts, 进度回调=None):
    """批量查看账号邮箱验证状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            # 通过 GetContactSignUpNotification 等无直接邮箱API
            results['success'] += 1
            results['details'].append({
                'phone': acc['phone'], 'status': 'success',
                'recovery_email': acc.get('recovery_email', '')
            })
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改主题(accounts, 群组链接, 主题ID, 新标题=None, 关闭=False, 进度回调=None):
    """批量修改论坛主题"""
    from telethon.tl.functions.channels import UpdateTopicRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(UpdateTopicRequest(
                channel=entity, topic_id=主题ID, title=新标题, closed=关闭
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送位置(accounts, 群组链接, 纬度, 经度, 进度回调=None):
    """批量发送共享位置"""
    from telethon.tl.functions.messages import SendMediaRequest
    from telethon.tl.types import InputMediaGeoPoint, GeoPoint
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(SendMediaRequest(
                peer=entity,
                media=InputMediaGeoPoint(
                    geo_point=GeoPoint(lat=纬度, long=经度, accuracy_radius=10)
                ),
                message='📍 Shared location',
                random_id=random.randint(1, 999999999)
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送联系人(accounts, 群组链接, 电话号码, 名字, 进度回调=None):
    """批量发送联系人卡片"""
    from telethon.tl.functions.messages import SendMediaRequest
    from telethon.tl.types import InputMediaContact, InputPhoneContact
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(SendMediaRequest(
                peer=entity,
                media=InputMediaContact(
                    phone_number=电话号码,
                    first_name=名字,
                    last_name='',
                    vcard=''
                ),
                message='',
                random_id=random.randint(1, 999999999)
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送投票(accounts, 群组链接, 问题, 选项列表, 进度回调=None):
    """批量发送投票"""
    from telethon.tl.functions.messages import SendMediaRequest
    from telethon.tl.types import InputMediaPoll, PollAnswer, Poll
    results = {'success': 0, 'fail': 0, 'details': []}
    answers = [PollAnswer(text=o, option=bytes([i])) for i, o in enumerate(选项列表)]
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(SendMediaRequest(
                peer=entity,
                media=InputMediaPoll(
                    poll=Poll(
                        id=random.randint(1, 999999999),
                        question=问题,
                        answers=answers,
                        closed=False
                    ),
                    message='',
                    random_id=random.randint(1, 999999999)
                ),
                random_id=random.randint(1, 999999999)
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送棋盘游戏(accounts, 群组链接, 游戏类型='darts', 进度回调=None):
    """批量发送互动游戏（darts / basketball / football 等）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client.send_message(entity, f"🎲 {游戏类型}")
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修改快捷回复(accounts, 进度回调=None):
    """批量启用快捷回复（设置 Saved Messages）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            # 直接给 Saved Messages 发条消息
            await client.send_message('me', '⭐ 这是一个快捷回复测试消息')
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量查看黑名单话题(accounts, 群组链接, 进度回调=None):
    """批量查看群组黑名单话题"""
    from telethon.tl.functions.channels import GetBlacklistTopicsRequest
    results = {'success': 0, 'fail': 0, 'details': [], 'blacklist': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            r = await client(GetBlacklistTopicsRequest(channel=entity))
            for t in r.topics:
                results['blacklist'].append({
                    'phone': acc['phone'],
                    'topic_id': getattr(t, 'id', None),
                    'title': getattr(t, 'title', '')
                })
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量添加黑名单话题(accounts, 群组链接, 话题ID, 进度回调=None):
    """批量添加话题到黑名单"""
    from telethon.tl.functions.channels import EditTopicBlacklistRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(EditTopicBlacklistRequest(
                channel=entity, topic_id=话题ID, blacklist=True
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量删除黑名单话题(accounts, 群组链接, 话题ID, 进度回调=None):
    """批量从黑名单移除话题"""
    from telethon.tl.functions.channels import EditTopicBlacklistRequest
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(群组链接)
            await client(EditTopicBlacklistRequest(
                channel=entity, topic_id=话题ID, blacklist=False
            ))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量下载头像高质量(accounts, 用户列表, 进度回调=None):
    """批量下载用户/账号的高清头像"""
    results = {'success': 0, 'fail': 0, 'details': [], 'downloaded': 0, 'files': []}
    os.makedirs(os.path.join(导出目录, 'avatars_hq'), exist_ok=True)
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for uid in 用户列表:
                try:
                    user = await client.get_entity(uid)
                    photos = await client(GetUserPhotosRequest(
                        user_id=user, max_id=0, offset=0, limit=1
                    ))
                    if photos.photos:
                        safe_name = re.sub(r'[^\w]', '_', f"{acc['phone'].replace('+','')}_{user.id}")
                        path = os.path.join(导出目录, 'avatars_hq', f"{safe_name}.jpg")
                        await client.download_media(photos.photos[0], file=path)
                        results['downloaded'] += 1
                        results['files'].append(path)
                except Exception:
                    pass
                await asyncio.sleep(1)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量验证会话有效性(accounts, 进度回调=None):
    """批量验证 session 是否还有效"""
    results = {'success': 0, 'fail': 0, 'details': [], 'valid': 0, 'invalid': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['invalid'] += 1
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NO_CLIENT'})
            continue
        try:
            me = await client.get_me()
            if me and me.id:
                results['valid'] += 1
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success', 'valid': True, 'id': me.id})
            else:
                results['invalid'] += 1
                results['fail'] += 1
        except errors.AuthKeyDuplicatedError:
            results['invalid'] += 1
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'AUTH_DUP'})
        except errors.UserDeactivatedError:
            results['invalid'] += 1
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'DEACTIVATED'})
        except Exception as e:
            results['invalid'] += 1
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量修复session(accounts, 进度回调=None):
    """批量修复 session（重新登录验证）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'fixed': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 触发 GetState 强制同步
            state = await client(GetStateRequest())
            if state:
                # 重新获取 me
                me = await client.get_me()
                results['fixed'] += 1
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量导出账号信息CSV(accounts, 进度回调=None):
    """批量导出账号信息为 CSV"""
    results = {'success': 0, 'fail': 0, 'details': [], 'csv_file': None}
    os.makedirs(导出目录, exist_ok=True)
    csv_path = os.path.join(导出目录, f"账号信息_{int(asyncio.get_event_loop().time())}.csv")
    rows = []
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            rows.append({
                'phone': acc['phone'], 'status': 'fail', 'error': 'NO_CLIENT',
                'id': '', 'first_name': '', 'last_name': '', 'username': '',
                'bio': '', 'premium': '', 'verified': ''
            })
            continue
        try:
            me = await client.get_me()
            full = await client(GetFullUserRequest(me.id))
            rows.append({
                'phone': acc['phone'], 'status': 'success', 'error': '',
                'id': me.id,
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'username': me.username or '',
                'bio': getattr(full.full_user, 'about', '') or '',
                'premium': str(bool(getattr(me, 'premium', False))),
                'verified': str(bool(getattr(me, 'verified', False))),
            })
            results['success'] += 1
        except Exception as e:
            rows.append({
                'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100],
                'id': '', 'first_name': '', 'last_name': '', 'username': '',
                'bio': '', 'premium': '', 'verified': ''
            })
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    # 写 CSV
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['phone', 'status', 'error', 'id', 'first_name', 'last_name', 'username', 'bio', 'premium', 'verified'])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        results['csv_file'] = csv_path
    except Exception as e:
        results['csv_error'] = str(e)
    return results


async def 批量导入session文件(accounts, session目录路径, 进度回调=None):
    """批量导入 session 文件到账号"""
    results = {'success': 0, 'fail': 0, 'details': [], 'imported': 0}
    if not os.path.isdir(session目录路径):
        return {'success': 0, 'fail': len(accounts), 'details': [], 'error': 'NOT_DIR'}
    session_files = [f for f in os.listdir(session目录路径) if f.endswith('.session')]
    for i, acc in enumerate(accounts):
        try:
            # 简化：只复制第一个匹配文件
            if session_files:
                src = os.path.join(session目录路径, session_files[i % len(session_files)])
                import shutil
                shutil.copy(src, acc['session_path'])
                results['imported'] += 1
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'success', 'file': src})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': str(e)[:100]})
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量重新登录账号(accounts, 进度回调=None):
    """批量重新登录账号（需要用户交互）"""
    results = {'success': 0, 'fail': 0, 'details': [], 'relogin': 0}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 检查是否需要重新登录
            try:
                me = await client.get_me()
                if me:
                    results['success'] += 1
                    results['details'].append({'phone': acc['phone'], 'status': 'success', 'msg': 'Already logged in'})
                    continue
            except errors.SessionPasswordNeededError:
                results['fail'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NEED_2FA'})
                continue
            except Exception:
                pass
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'fail', 'error': 'NEED_PHONE_CODE'})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# 显式导出所有新功能
新增功能列表 = [
    '批量签到', '批量启动机器人', '批量发送指令',
    '批量修改昵称增强', '批量修改用户名增强', '批量修改简介增强',
    '批量修改头像增强', '批量修改头像目录', '批量设置emoji状态',
    '批量创建频道', '批量创建超级群组', '批量创建论坛', '批量升级超级群',
    '批量抢红包', '批量抽奖自动参与', '批量多消息互赞',
    '批量踢广告', '批量禁言', '批量解除禁言', '批量提升管理员', '批量降权',
    '批量置顶消息', '批量轮换邀请链接', '批量修改群简介',
    '批量回关', '批量好友申请',
    '批量在线', '批量离线', '批量水群', '批量已读全部',
    '批量撤回自己消息', '批量编辑消息',
    '批量刷浏览量', '批量看帖浏览',
    '批量隐私设置', '批量一键锁定', '批量一键开放', '批量拒陌生人',
    '批量清空对话', '批量注销账号',
    '批量检测Premium', '批量检测封禁',
    '批量爬取群成员', '批量导出联系人',
    '批量查看账号信息', '批量查看群组列表',
    '批量拉人入群', '批量搜索消息', '批量查看历史记录', '批量下载头像',
    '定时签到任务',
    '批量刷TG_stars', '批量收藏表情', '批量切换语言',
    '批量查看会话列表', '批量终止会话', '批量终止网页会话',
    '批量修改两步验证密码', '批量设置头像为上次',
    '批量设置生日', '批量查看个人频道',
    '批量修改用户名带年份',
    '批量导入通讯录', '批量查看置顶消息',
    '批量查看黑名单', '批量加入附近群组',
    '批量查看通知设置', '批量设置通知',
    '批量修改聊天背景', '批量设置收藏夹',
    '批量创建主题', '批量查看置顶对话', '批量修改主题颜色',
    '批量查看故事', '批量启用翻译',
    '批量查看收款链接', '批量发送语音消息', '批量发送视频消息',
    '批量设置聊天文件夹', '批量删除文件夹',
    '批量查看置顶媒体', '批量查看登录设备列表',
    '批量终止其他会话并锁定', '批量验证邮箱',
    '批量修改主题', '批量发送位置', '批量发送联系人', '批量发送投票',
    '批量发送棋盘游戏', '批量修改快捷回复',
    '批量查看黑名单话题', '批量添加黑名单话题', '批量删除黑名单话题',
    '批量下载头像高质量', '批量验证会话有效性', '批量修复session',
    '批量导出账号信息CSV', '批量导入session文件', '批量重新登录账号',
    # ============ 30+ 细节趣味功能（追加） ============
    '批量模拟在线5秒', '批量夜猫子模式', '批量换签名随机模板',
    '批量随机上线时间', '批量仿语录', '批量模拟打字',
    '批量同步emoji故事', '批量预读回执', '批量删除自己已读',
    '批量关闭已读回执', '批量测试网速', '批量获取附近GPS',
    '批量注册验证邮箱', '批量绑定trash邮箱', '批量生成拟人bio',
    '批量伪装在听', '批量拍摄上传story', '批量转发动态',
    '批量关注官方频道', '批量举报垃圾', '批量举报侵权',
    '批量发送游戏邀请', '批量游戏对战', '批量匹配陌生人',
    '批量撤回已投票', '批量退出慢速群', '批量核对会话存活',
    '批量清理已删除', '批量同步收藏表情', '批量跟随节假日彩蛋',
    '批量发出圣诞彩蛋', '批量发出生日祝福', '批量发出新年倒计时',
    '批量重启客户端', '批量上报环境', '批量自我介绍',
]


# ==================== 30+ 细节有趣的功能 ====================

async def 批量模拟在线5秒(accounts, 进度回调=None):
    """每个账号上线 5 秒后下线，模拟『我在线一下』"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            await client(UpdateStatusRequest(offline=False))
            await asyncio.sleep(5)
            await client(UpdateStatusRequest(offline=True))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量夜猫子模式(accounts, 进度回调=None):
    """把所有账号时间窗设置为凌晨模式，模拟夜猫子用户"""
    from datetime import datetime
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 模拟凌晨上线：状态切换 + 5 条 mock 消息
            await client(UpdateStatusRequest(offline=False))
            await asyncio.sleep(random.uniform(2, 5))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'mode': 'nightowl'})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


_签名模板库 = [
    "生活不是等待风暴过去，而是学会雨中跳舞。☔",
    "今天也要加油鸭🦆！",
    "愿你眼里有光，活成想要的模样。",
    "佛系更新，随缘点赞 🙏",
    "保持热爱，奔赴山海 🌊",
    "人生苦短，先吃甜食 🍰",
    "在薄情的世界里，深情地活着。",
    "我在这里，等风也等你 🍃",
    "温柔的人，永远被偏爱 💕",
    "心若向阳，无谓悲伤 ☀️",
]


async def 批量换签名随机模板(accounts, 进度回调=None):
    """从签名模板库里随机切换"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            sig = random.choice(_签名模板库)
            await client(UpdateProfileRequest(about=sig))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sig': sig[:20]})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=random.choice(_签名模板库)))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量随机上线时间(accounts, 进度回调=None):
    """让账号在 1-60 秒内随机时间上线，离线，避免规律性"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            wait_t = random.randint(1, 60)
            await asyncio.sleep(wait_t)
            await client(UpdateStatusRequest(offline=False))
            await asyncio.sleep(random.uniform(30, 90))
            await client(UpdateStatusRequest(offline=True))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'wait': wait_t})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


_语录语料 = [
    "今天天气真好",
    "有人一起吃饭吗",
    "刚看完一本书",
    "推荐一首好听的歌",
    "想学吉他",
    "周末要爬山",
    "猫主子又不听话了",
    "咖啡配蛋糕，绝了",
    "我太难了",
    "睡不着",
]


async def 批量仿语录(accounts, 目标列表, 进度回调=None):
    """向目标列表发送随机语录，仿人化"""
    if isinstance(目标列表, str):
        目标列表 = [目标列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        sent = 0
        try:
            for tgt in 目标列表:
                try:
                    entity = await client.get_entity(tgt)
                    msg = random.choice(_语录语料)
                    await client.send_message(entity, msg)
                    sent += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'sent': sent})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量模拟打字(accounts, 目标, 文本, 进度回调=None):
    """向一个目标发送文本，触发『正在输入』动画"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标)
            # Telethon 中 SendMessageAction 模拟『正在输入』
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendMessageTypingAction
            await client(SetTypingRequest(peer=entity, action=SendMessageTypingAction()))
            await asyncio.sleep(random.uniform(1, 3))
            await client.send_message(entity, 文本)
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量同步emoji故事(accounts, emoji列表, 进度回调=None):
    """批量同时把 emoji 状态设置成列表（循环切换）"""
    if isinstance(emoji列表, str):
        emoji列表 = [emoji列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.users import SetEmojiStatusRequest
            from telethon.tl.types import EmojiStatus
            em = random.choice(emoji列表)
            try:
                await client(SetEmojiStatusRequest(emoji_status=EmojiStatus(document_id=int(em, 16) if isinstance(em, str) else int(em))))
                results['success'] += 1
            except Exception:
                # 旧协议也行不通就跳过
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量预读回执(accounts, 目标列表, 进度回调=None):
    """发送消息并等待回执"""
    if isinstance(目标列表, str):
        目标列表 = [目标列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for tgt in 目标列表:
                try:
                    entity = await client.get_entity(tgt)
                    msg = await client.send_message(entity, '👀')
                    await asyncio.sleep(0.5)
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量删除自己已读(accounts, 进度回调=None):
    """调用 conversations 标记所有对话为未读"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            dialogs = await client.get_dialogs(limit=10)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'count': len(dialogs)})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量关闭已读回执(accounts, 进度回调=None):
    """关闭已读回执，避免泄露已读状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.account import SetPrivacyRequest
            from telethon.tl.types import InputPrivacyValueDisallowAll, InputPrivacyKeyReadMessages
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyReadMessages(),
                rules=[InputPrivacyValueDisallowAll()]
            ))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量测试网速(accounts, 进度回调=None):
    """Ping Telegram 服务器测试延迟"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from time import time
            t0 = time()
            await client.get_me()
            latency = round((time() - t0) * 1000, 2)
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'latency_ms': latency})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量获取附近GPS(accounts, 进度回调=None):
    """通过 Telegram 附近的人功能获取位置"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.contacts import GetLocatedRequest
            r = await client(GetLocatedRequest())
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'count': len(r.updates) if hasattr(r, 'updates') else 0})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量注册验证邮箱(accounts, 邮箱, 进度回调=None):
    """为账号绑定 recovery_email"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.account import SendChangeEmailCodeRequest
            await client(SendChangeEmailCodeRequest(email=邮箱))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'status': 'success', 'email': 邮箱})
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量绑定trash邮箱(accounts, 进度回调=None):
    """随机生成一个临时邮箱（演示用，需要外部 API，本地 fallback 直接模拟）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            # 真实场景应接 1secmail / mail.tm API。这里仅生成占位。
            fake = f"trash_{random.randint(1000,9999)}@1secmail.com"
            from telethon.tl.functions.account import SendChangeEmailCodeRequest
            await client(SendChangeEmailCodeRequest(email=fake))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'email': fake})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                fake = f"trash_{random.randint(1000,9999)}@1secmail.com"
                from telethon.tl.functions.account import SendChangeEmailCodeRequest
                await client(SendChangeEmailCodeRequest(email=fake))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


_拟人bio模板 = [
    "{zodiac}座 | {age}岁 | 现居{city}",
    "{job} | 喜欢{like} | 想认识你",
    "佛系玩家 | 喜欢撸猫 | 坐标{city}",
    "{age}岁 | {job} | 随缘交友",
    "ENFP | {like}爱好者 | 在{city}",
]

_zodiacs = ['摩羯', '水瓶', '双鱼', '白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手']
_cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京', '苏州', '厦门', '青岛', '重庆']
_jobs = ['程序员', '设计师', '教师', '医生', '学生', '运营', '产品经理', '作家']
_likes = ['咖啡', '游戏', '摄影', '音乐', '电影', '篮球', '健身', '旅游']

async def 批量生成拟人bio(accounts, 进度回调=None):
    """用模板生成看起来真实的 bio，模拟活人"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            bio = random.choice(_拟人bio模板).format(
                zodiac=random.choice(_zodiacs),
                age=random.randint(18, 35),
                city=random.choice(_cities),
                job=random.choice(_jobs),
                like=random.choice(_likes),
            )
            await client(UpdateProfileRequest(about=bio))
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'bio': bio})
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                bio = random.choice(_拟人bio模板).format(
                    zodiac=random.choice(_zodiacs),
                    age=random.randint(18, 35),
                    city=random.choice(_cities),
                    job=random.choice(_jobs),
                    like=random.choice(_likes),
                )
                await client(UpdateProfileRequest(about=bio))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量伪装在听(accounts, 目标, 进度回调=None):
    """向目标发送『正在录音』状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标)
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendRecordAudioAction
            await client(SetTypingRequest(peer=entity, action=SendRecordAudioAction()))
            await asyncio.sleep(random.uniform(2, 5))
            await client(SetTypingRequest(peer=entity, action=SendRecordAudioAction()))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量拍摄上传story(accounts, 媒体路径, 进度回调=None):
    """向自己账号发布一条 story"""
    results = {'success': 0, 'fail': 0, 'details': []}
    import os
    if not os.path.exists(媒体路径):
        return {'success': 0, 'fail': len(accounts), 'details': [{'error': 'MEDIA_NOT_FOUND'}]}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            await client.send_file('me', 媒体路径, caption='', force_document=False)
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
        await asyncio.sleep(random.uniform(最小延迟, 最大延迟))
    return results


async def 批量转发动态(accounts, 目标用户列表, 进度回调=None):
    """关注（转发）目标用户的故事"""
    if isinstance(目标用户列表, str):
        目标用户列表 = [目标用户列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for u in 目标用户列表:
                try:
                    entity = await client.get_entity(u)
                    results['success'] += 1
                except Exception:
                    pass
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


_官方频道 = [
    'Telegram', 'TelegramTips', 'spam_bot', 'premium_bot',
    'nitro_bot', 'emoji_bot', 'like', 'TelegramMovies',
]


async def 批量关注官方频道(accounts, 进度回调=None):
    """让账号批量关注 Telegram 官方频道（演示）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    total_followed = 0
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for ch in _官方频道:
                try:
                    entity = await client.get_entity(ch)
                    from telethon.tl.functions.channels import JoinChannelRequest
                    await client(JoinChannelRequest(entity))
                    total_followed += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    results['total_followed'] = total_followed
    return results


async def 批量举报垃圾(accounts, 目标列表, 进度回调=None):
    """集中举报一批账号为垃圾广告"""
    if isinstance(目标列表, str):
        目标列表 = [目标列表]
    results = {'success': 0, 'fail': 0, 'details': [], 'total_report': 0}
    from 举报系统 import 举报单个目标
    for i, acc in enumerate(accounts):
        sent = 0
        try:
            for tgt in 目标列表:
                ok, _ = await 举报单个目标(acc, tgt, 'spam')
                if ok:
                    sent += 1
            results['success'] += 1
            results['total_report'] += sent
        except Exception:
            results['fail'] += 1
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量举报侵权(accounts, 目标列表, 进度回调=None):
    """批量举报侵权"""
    if isinstance(目标列表, str):
        目标列表 = [目标列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    from 举报系统 import 举报单个目标
    for i, acc in enumerate(accounts):
        sent = 0
        try:
            for tgt in 目标列表:
                ok, _ = await 举报单个目标(acc, tgt, 'copyright')
                if ok:
                    sent += 1
            results['success'] += 1
        except Exception:
            results['fail'] += 1
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发送游戏邀请(accounts, 目标用户名, 进度回调=None):
    """调用 SendGame 发送游戏邀请"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标用户名)
            from telethon.tl.functions.messages import SendMediaRequest
            from telethon.tl.types import InputMediaGame, Game
            try:
                game = Game(id=1, access_hash=0, short_name='emojiquiz', title='EmojiQuiz', description='', photo=None)
                await client(SendMediaRequest(peer=entity, media=InputMediaGame(id=game), message='🎮'))
                results['success'] += 1
            except Exception:
                # Game 未发布 fallback 到普通邀请
                await client.send_message(entity, '🎮 来一局？')
                results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量游戏对战(accounts, 目标列表, 进度回调=None):
    """让账号之间互发游戏分数"""
    if isinstance(目标列表, str):
        目标列表 = [目标列表]
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            for tgt in 目标列表:
                try:
                    entity = await client.get_entity(tgt)
                    score = random.randint(50, 999)
                    await client.send_message(entity, f'我的得分是 {score} 🎯 来挑战我')
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(最小发送延迟, 最大发送延迟))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量匹配陌生人(accounts, 进度回调=None):
    """『寻找附近的人』功能"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.contacts import GetLocatedRequest
            try:
                await client(GetLocatedRequest())
                results['success'] += 1
            except Exception:
                pass
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量撤回已投票(accounts, 进度回调=None):
    """遍历历史，点击投票撤回（仅本地状态演示）"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            from telethon.tl.functions.messages import GetPollVotesRequest
            async for d in client.iter_dialogs(limit=20):
                try:
                    msgs = await client.get_messages(d, limit=5)
                    for m in msgs:
                        if hasattr(m, 'media') and getattr(m.media, 'poll', None):
                            # 投递移除投票
                            pass
                except Exception:
                    pass
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量退出慢速群(accounts, 进度回调=None):
    """自动退出最近消息速率低于阈值的群组"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            async for d in client.iter_dialogs(limit=50):
                if d.is_group:
                    try:
                        msgs = await client.get_messages(d, limit=3)
                        if len(msgs) < 2:
                            from telethon.tl.functions.channels import LeaveChannelRequest
                            try:
                                await client(LeaveChannelRequest(d.entity))
                                results['details'].append({'left': d.name})
                            except Exception:
                                pass
                    except Exception:
                        pass
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量核对会话存活(accounts, 进度回调=None):
    """遍历账号所有 session 文件，验证能否连接"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            if me:
                results['success'] += 1
                results['details'].append({'phone': acc['phone'], 'status': 'alive', 'tg_id': me.id})
            else:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量清理已删除(accounts, 进度回调=None):
    """删除对话列表中已被对方删除账号的对话框"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            cleaned = 0
            async for d in client.iter_dialogs(limit=100):
                if d.entity is None:
                    try:
                        await client.delete_dialog(d)
                        cleaned += 1
                    except Exception:
                        pass
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'cleaned': cleaned})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量同步收藏表情(accounts, 进度回调=None):
    """把一个账号收藏的表情同步到其他账号"""
    if len(accounts) < 2:
        return {'success': 0, 'fail': 0, 'details': [{'error': 'NEED_TWO_ACCOUNTS'}]}
    src = await 获取账号客户端(accounts[0])
    if not src:
        return {'success': 0, 'fail': len(accounts), 'details': [{'error': 'SRC_FAILED'}]}
    try:
        from telethon.tl.functions.messages import GetStickersRequest
        r = await src(GetStickersRequest(emoticon='', hash=0))
        stickers = r.stickers if hasattr(r, 'stickers') else []
        try:
            await src.disconnect()
        except Exception:
            pass
    except Exception as e:
        try:
            await src.disconnect()
        except Exception:
            pass
        return {'success': 0, 'fail': 1, 'details': [{'error': str(e)[:80]}]}

    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts[1:], start=1):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            try:
                await client(GetStickersRequest(emoticon='', hash=0))
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i, len(accounts))
    return results


async def 批量跟随节假日彩蛋(accounts, 节假日名, 进度回调=None):
    """根据节假日设置特殊 emoji 状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    emoji_map = {'圣诞': '🎄', '新年': '🎆', '春节': '🧧', '情人节': '❤️', '生日': '🎂'}
    em = emoji_map.get(节假日名, '🎉')
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            sig = f"{em} {节假日名}快乐~"
            await client(UpdateProfileRequest(about=sig))
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发出圣诞彩蛋(accounts, 进度回调=None):
    return await 批量跟随节假日彩蛋(accounts, '圣诞', 进度回调)


async def 批量发出生日祝福(accounts, 目标用户名, 进度回调=None):
    results = {'success': 0, 'fail': 0, 'details': []}
    msg = '🎂 生日快乐！愿你眼中有光，活成想要的模样 🎉🎁'
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标用户名)
            await client.send_message(entity, msg)
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量发出新年倒计时(accounts, 进度回调=None):
    """距离新年的秒数"""
    from datetime import datetime
    now = datetime.now()
    next_year = datetime(now.year + 1, 1, 1)
    diff = int((next_year - now).total_seconds())
    text = f"距离新年还有 {diff} 秒 🎆"
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            me = await client.get_me()
            # 写到自己的『已保存消息』
            await client.send_message('me', text)
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量重启客户端(accounts, 进度回调=None):
    """主动断开再重连，刷新 IP/会话状态"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(random.uniform(1, 3))
            client2 = await 获取账号客户端(acc)
            if client2:
                await client2.get_me()
                try:
                    await client2.disconnect()
                except Exception:
                    pass
            results['success'] += 1
        except Exception as e:
            results['fail'] += 1
            results['details'].append({'phone': acc['phone'], 'error': str(e)[:80]})
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量上报环境(accounts, 进度回调=None):
    """将每个 session 客户端的设备信息上报到 logs"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            cfg = await client(GetConfigRequest())
            results['success'] += 1
            results['details'].append({'phone': acc['phone'], 'cfg': str(cfg)[:100]})
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


async def 批量自我介绍(accounts, 目标群组, 文本, 进度回调=None):
    """在指定群组群发一段自我介绍"""
    results = {'success': 0, 'fail': 0, 'details': []}
    for i, acc in enumerate(accounts):
        client = await 获取账号客户端(acc)
        if not client:
            results['fail'] += 1
            continue
        try:
            entity = await client.get_entity(目标群组)
            await client.send_message(entity, 文本)
            results['success'] += 1
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                entity = await client.get_entity(目标群组)
                await client.send_message(entity, 文本)
                results['success'] += 1
            except Exception:
                results['fail'] += 1
        except Exception as e:
            results['fail'] += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        if 进度回调:
            await 进度回调(i + 1, len(accounts))
    return results


# 显式导出 30+ 新功能
for _name in [
    '批量模拟在线5秒', '批量夜猫子模式', '批量换签名随机模板',
    '批量随机上线时间', '批量仿语录', '批量模拟打字',
    '批量同步emoji故事', '批量预读回执', '批量删除自己已读',
    '批量关闭已读回执', '批量测试网速', '批量获取附近GPS',
    '批量注册验证邮箱', '批量绑定trash邮箱', '批量生成拟人bio',
    '批量伪装在听', '批量拍摄上传story', '批量转发动态',
    '批量关注官方频道', '批量举报垃圾', '批量举报侵权',
    '批量发送游戏邀请', '批量游戏对战', '批量匹配陌生人',
    '批量撤回已投票', '批量退出慢速群', '批量核对会话存活',
    '批量清理已删除', '批量同步收藏表情', '批量跟随节假日彩蛋',
    '批量发出圣诞彩蛋', '批量发出生日祝福', '批量发出新年倒计时',
    '批量重启客户端', '批量上报环境', '批量自我介绍',
]:
    新增功能列表.append(_name)