"""主程序 - 协议工具箱 Bot
作者: Lion
全集版：Session 管理、批量操作、守护系统、监听系统、举报系统、代理管理、设置管理
"""

import os
import asyncio
import json
import re
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from 配置 import (
    机器人令牌, 管理员ID, API_ID, API_HASH,
    默认API_ID, 默认API_HASH, 项目根目录, 会话目录,
    作者名称, 作者用户名, 项目名称, 日志
)
import 数据库 as db
import 会话管理
import 账号管理
import 批量操作
import 守护系统 as 守护
import 监听系统 as 监听
import 举报系统 as 举报
import 代理管理 as 代理
import 设置管理 as 设置
from 设备伪装 import 举报原因映射, 生成魔法型号
from 工具 import 提取手机号, 格式化手机号, 当前时间, 构建账号信息, 构建进度条

# ==================== 对话状态 ====================
(等待手机号, 等待验证码, 等待两步验证密码, 等待API_ID, 等待API_HASH,
 等待目标, 等待消息内容, 等待媒体文件, 等待加群链接, 等待点赞链接,
 等待举报目标, 等待举报原因, 等待关键词, 等待回复规则, 等待转发目标,
 等待代理输入, 等待设置值, 等待白名单, 等待用户列表, 等待链接列表,
 等待机器人列表, 等待转发目标列表, 等待循环次数, 等待延迟设置,
 等待隐私类型, 等待隐私值, 等待昵称, 等待用户名, 等待简介,
 等待群组链接, 等待头像) = range(31)

# ==================== 键盘定义 ====================

def 主菜单键盘():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 账号管理", callback_data="menu_accounts"),
         InlineKeyboardButton("🔑 会话管理", callback_data="menu_sessions")],
        [InlineKeyboardButton("⚡ 批量操作", callback_data="menu_batch"),
         InlineKeyboardButton("🚨 举报系统", callback_data="menu_report")],
        [InlineKeyboardButton("🛡️ 守护系统", callback_data="menu_guardian"),
         InlineKeyboardButton("👂 监听系统", callback_data="menu_monitor")],
        [InlineKeyboardButton("🌐 代理管理", callback_data="menu_proxy"),
         InlineKeyboardButton("⚙️ 设置管理", callback_data="menu_settings")],
        [InlineKeyboardButton("📊 我的概览", callback_data="menu_overview"),
         InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
    ])

def 返回按钮(target="menu_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data=target)]])

# ==================== 命令处理 ====================

async def 开始命令(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.注册用户(user.id, user.username, user.first_name, user.last_name)

    text = f"""
╔══════════════════════════════════════╗
║     {项目名称}                          ║
║     作者: {作者名称}  |  {作者用户名}              ║
╚══════════════════════════════════════╝

👋 欢迎使用 {项目名称}！

📱 支持功能:
• 会话管理 - 登录/验证/导出/转移
• 批量操作 - 加群/群发/点赞/转发/改名等30+功能
• 举报系统 - 多种原因批量举报
• 守护系统 - 验证码监控/防盗/自动杀设备
• 监听系统 - 关键词检测/自动回复
• 代理管理 - 导入/检测/轮换
• 设置管理 - 自定义所有功能参数

请选择功能模块:
"""
    await update.message.reply_text(text, reply_markup=主菜单键盘(), parse_mode=ParseMode.HTML)

async def 帮助命令(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
📖 **{项目名称} 使用帮助**

**会话管理**
• 上传 .session 或 .zip 文件导入账号
• 支持发送验证码登录新账号
• 支持会话转移（新旧设备切换）
• 支持导出会话为ZIP/JSON

**批量操作**
• 批量加群 - 所有账号批量加入指定群组
• 批量群发 - 所有账号向目标发送消息
• 批量点赞 - 对消息做出表情反应
• 批量转发 - 转发消息到目标
• 批量修改昵称/用户名/简介/头像
• 批量隐私设置 - 一键锁定所有隐私
• 批量启动机器人 - 批量点击 /start
• 爬取群成员 - 导出群组成员列表
• 导出联系人 - 导出所有账号联系人

**举报系统**
• 支持10种举报原因（中文）
• 批量举报 - 所有账号举报同一目标
• 多目标举报 - 不同目标不同原因
• 循环举报 - 定时多次举报

**守护系统**
• 验证码监控 - 实时检测登录验证码
• 验证码消耗 - 拦截验证码转发给bot作废
• 自动杀设备 - 查杀非白名单设备
• 主权模式 - 独占账号控制权

**监听系统**
• 关键词检测 - 监听群组消息匹配关键词
• 自动转发 - 命中关键词自动转发到目标群
• 自动回复 - 根据关键词自动回复消息

**代理管理**
• 支持 socks5/http 代理
• 支持 ip:port 和 ip:port:user:pass 格式
• 代理存活检测
• 随机/轮询两种轮换模式

**设置管理**
• 自定义延迟范围
• 自定义关键词和回复
• 自定义守护参数
• 设置导入/导出

作者: {作者名称} {作者用户名}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ==================== 回调处理 ====================

async def 回调处理(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    message = query.message

    if data == "menu_main":
        await message.edit_text(
            f"📋 **主菜单**\n\n请选择功能模块:",
            reply_markup=主菜单键盘(),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 账号管理
    elif data == "menu_accounts":
        await 账号管理菜单(user_id, message)
    elif data == "account_list":
        await 显示账号列表(user_id, message)
    elif data == "account_import":
        await message.edit_text(
            "📥 **导入账号**\n\n请发送 .session 文件、.zip 压缩包或 JSON 数据包",
            reply_markup=返回按钮("menu_accounts"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "account_verify":
        await 验证账号(user_id, message)
    elif data == "account_export":
        await 导出账号(user_id, message)
    elif data == "account_export_strings":
        await 导出会话字符串(user_id, message)
    elif data == "account_backup":
        await message.edit_text(
            "💾 **备份账号**\n\n请发送要备份的账号手机号",
            reply_markup=返回按钮("menu_accounts"),
            parse_mode=ParseMode.MARKDOWN
        )

    # 会话管理
    elif data == "menu_sessions":
        await 会话管理菜单(user_id, message)
    elif data == "session_login":
        await message.edit_text(
            "🔑 **登录新账号**\n\n请输入手机号（格式: +8613800138000）",
            reply_markup=返回按钮("menu_sessions"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "session_transfer":
        await message.edit_text(
            "🔄 **会话转移**\n\n请发送旧的 .session 文件",
            reply_markup=返回按钮("menu_sessions"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "session_magic":
        await 快速生成会话(user_id, message)
    elif data == "session_devices":
        await message.edit_text(
            "📱 **查看登录设备**\n\n请发送要查看的账号手机号",
            reply_markup=返回按钮("menu_sessions"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "session_kill":
        await message.edit_text(
            "🗑️ **踢出设备**\n\n请发送账号手机号，然后发送设备哈希",
            reply_markup=返回按钮("menu_sessions"),
            parse_mode=ParseMode.MARKDOWN
        )

    # 批量操作
    elif data == "menu_batch":
        await 批量操作菜单(user_id, message)
    elif data == "menu_batch2":
        await 批量操作菜单2(user_id, message)
    elif data == "menu_batch3":
        await 批量操作菜单3(user_id, message)
    elif data == "menu_batch4":
        await 批量操作菜单4(user_id, message)
    elif data == "menu_batch5":
        await 批量操作菜单5(user_id, message)
    elif data == "batch_join":
        await message.edit_text(
            "➕ **批量加群**\n\n请发送群组链接（支持 t.me/xxx 或邀请链接）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_leave":
        await message.edit_text(
            "➖ **批量退群**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send":
        await message.edit_text(
            "💬 **批量群发消息**\n\n请发送目标（群组链接/用户名），然后发送消息内容",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_react":
        await message.edit_text(
            "👍 **批量点赞**\n\n请发送消息链接（如 https://t.me/channel/123）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_forward":
        await message.edit_text(
            "↗️ **批量转发**\n\n请发送消息链接，然后发送转发目标",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_nickname":
        await message.edit_text(
            "✏️ **批量修改昵称**\n\n请发送新的昵称",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_username":
        await message.edit_text(
            "✏️ **批量修改用户名**\n\n请发送新的 @username（不含@）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_bio":
        await message.edit_text(
            "✏️ **批量修改简介**\n\n请发送新的简介内容",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_privacy":
        await 隐私设置菜单(user_id, message)
    elif data == "batch_privacy_lock":
        await 批量锁定隐私(user_id, message)
    elif data == "batch_start_bot":
        await message.edit_text(
            "🤖 **批量启动机器人**\n\n请发送机器人链接，每行一个",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_scrape_members":
        await message.edit_text(
            "👥 **爬取群成员**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_export_contacts":
        await 导出联系人(user_id, message)
    elif data == "batch_clear_chats":
        await 清空对话(user_id, message)
    elif data == "batch_profile":
        await 查看账号信息(user_id, message)
    elif data == "batch_groups":
        await 查看群组列表(user_id, message)
    elif data == "batch_online":
        await 刷在线状态(user_id, message)
    elif data == "batch_create_channel":
        await message.edit_text(
            "📢 **批量创建频道**\n\n请发送频道名称",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_invite":
        await message.edit_text(
            "👥 **批量拉人**\n\n请发送群组链接，然后发送用户列表（每行一个）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_vote":
        await message.edit_text(
            "🗳️ **批量投票**\n\n请发送投票消息链接",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_search":
        await message.edit_text(
            "🔍 **批量搜索消息**\n\n请发送目标群组链接，然后发送关键词",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view":
        await 刷浏览量(user_id, message)

    # ============ 新增批量功能路由 ============
    elif data == "batch_dm":
        await message.edit_text(
            "🗨️ **批量私聊群发**\n\n请发送用户列表（每行一个用户名/ID），然后发送消息",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_dm_all":
        await message.edit_text(
            "🌀 **群发所有对话**\n\n请发送消息内容（将发送给所有账号的所有对话）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_multi_react":
        await message.edit_text(
            "❤️ **批量互赞多消息**\n\n请发送消息链接，每行一条",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_grab":
        await message.edit_text(
            "🧧 **批量抢红包**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_lottery":
        await message.edit_text(
            "🎰 **批量抽奖自动参与**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_sign":
        await message.edit_text(
            "📲 **批量签到 (/qd)**\n\n请发送机器人用户名列表（每行一个，如 @xxxbot）",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_cmd":
        await message.edit_text(
            "⚡ **批量发送任意指令**\n\n格式：机器人@指令，每行一条\n例如: @xxxbot /qd",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_avatar":
        await message.edit_text(
            "🖼️ **批量修改头像**\n\n请发送图片",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_avatar_dir":
        await message.edit_text(
            "🌐 **批量修改头像（目录）**\n\n请发送头像目录路径",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_emoji":
        await message.edit_text(
            "💠 **批量设置 emoji 状态**\n\n请发送 emoji document_id",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_create_supergroup":
        await message.edit_text(
            "👥 **批量创建超级群**\n\n请发送群组名称（可选: 名称|简介）",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_create_forum":
        await message.edit_text(
            "💬 **批量创建论坛**\n\n请发送论坛名称",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_upgrade_sg":
        await message.edit_text(
            "🆙 **批量升级超级群**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_kick_ads":
        await message.edit_text(
            "🚫 **批量踢广告**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_mute":
        await message.edit_text(
            "🔇 **批量禁言**\n\n请发送群组链接，然后发送用户列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_unmute":
        await message.edit_text(
            "🔊 **批量解除禁言**\n\n请发送群组链接，然后发送用户列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_promote":
        await message.edit_text(
            "👑 **批量提升管理员**\n\n请发送群组链接，然后发送用户列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_demote":
        await message.edit_text(
            "📉 **批量降权**\n\n请发送群组链接，然后发送用户列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_pin":
        await message.edit_text(
            "📌 **批量置顶/取消**\n\n请发送群组链接，然后发送消息ID列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_invite_link":
        await message.edit_text(
            "📨 **批量轮换邀请链接**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_set_about":
        await message.edit_text(
            "🪧 **批量修改群简介**\n\n请发送群组链接，然后发送新简介",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_follow_back":
        await message.edit_text(
            "👋 **批量回关**\n\n正在启动批量回关任务...",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_friend_req":
        await message.edit_text(
            "📨 **批量好友申请**\n\n请发送用户列表（每行一个）",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_spam":
        await message.edit_text(
            "📖 **批量水群**\n\n请发送群组链接，然后发送消息列表（每行一条）",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_read_all":
        await message.edit_text(
            "✅ **批量已读全部**\n\n正在标记所有对话为已读...",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_delete_own":
        await message.edit_text(
            "🗑️ **批量撤回自己**\n\n请发送群组链接，可附带 保留数量 (默认10)",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_edit_msg":
        await message.edit_text(
            "✏️ **批量编辑消息**\n\n请发送群组链接，然后发送新文本",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_posts":
        await message.edit_text(
            "📊 **批量看帖浏览**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_privacy_unlock":
        await message.edit_text(
            "🔓 **批量一键开放**\n\n正在开放所有账号隐私...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_block_stranger":
        await message.edit_text(
            "🚫 **批量拒陌生人**\n\n请发送群组链接（将拒接非通讯录私聊）",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_delete_account":
        await message.edit_text(
            "❌ **批量注销账号**\n\n⚠️ 警告：此操作不可逆！\n确认请回复 YES_DELETE",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_kill_sessions":
        await message.edit_text(
            "🔐 **批量终止会话**\n\n正在终止其他设备的会话...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "kill_web_auths":
        await message.edit_text(
            "🌐 **批量终止网页会话**\n\n正在终止所有网页版登录...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_devices":
        await message.edit_text(
            "📱 **批量查看登录设备**\n\n正在导出所有账号登录设备...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_kill_lock":
        await message.edit_text(
            "🔒 **批量一键杀设备+锁**\n\n⚠️ 警告：所有其他设备将被终止\n请回复 YES_LOCK 确认",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_verify_sessions":
        await message.edit_text(
            "✅ **批量验证有效性**\n\n正在检查所有 session...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_fix_sessions":
        await message.edit_text(
            "🔧 **批量修复session**\n\n正在重连所有 session...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_export_csv":
        await message.edit_text(
            "📄 **批量导出CSV**\n\n正在生成账号信息 CSV...",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_import_sessions":
        await message.edit_text(
            "📥 **批量导入session**\n\n请发送 session 文件目录路径",
            reply_markup=返回按钮("menu_batch3"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_birthday":
        await message.edit_text(
            "🎂 **批量设置生日**\n\n格式: MM/DD/YYYY 或 DD-MM-YYYY",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_change_2fa":
        await message.edit_text(
            "🔑 **批量修改两步验证**\n\n请发送新密码（需当前密码）",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_username_year":
        await message.edit_text(
            "📅 **批量用户名带年份**\n\n请发送用户名前缀",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_create_folder":
        await message.edit_text(
            "📂 **批量创建文件夹**\n\n请发送文件夹名称",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_del_folder":
        await message.edit_text(
            "🗑 **批量删除文件夹**\n\n请发送文件夹ID",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_create_topic":
        await message.edit_text(
            "📋 **批量创建主题**\n\n格式: 群组链接|主题1\n主题2\n主题3",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_topic_color":
        await message.edit_text(
            "🎨 **批量改主题颜色**\n\n格式: 群组链接|主题ID|颜色ID",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_location":
        await message.edit_text(
            "📍 **批量发送位置**\n\n格式: 群组链接|纬度|经度",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_contact":
        await message.edit_text(
            "👤 **批量发送联系人**\n\n格式: 群组链接|电话|姓名",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_poll":
        await message.edit_text(
            "🗳 **批量发送投票**\n\n格式: 群组链接|问题|选项1,选项2,选项3",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_dice":
        await message.edit_text(
            "🎲 **批量发送棋盘游戏**\n\n请发送群组链接（可选: 游戏类型 darts/basketball）",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_voice":
        await message.edit_text(
            "🎙 **批量发送语音**\n\n请发送群组链接|音频路径或目录",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_send_video":
        await message.edit_text(
            "🎬 **批量发送视频**\n\n请发送群组链接|视频路径或目录",
            reply_markup=返回按钮("menu_batch4"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_stars":
        await message.edit_text(
            "🌟 **批量刷TG Stars**\n\n请发送 Stars 链接列表（每行一条）",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_stickers":
        await message.edit_text(
            "⭐ **批量收藏表情**\n\n请发送 addstickers 链接列表",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_lang":
        await message.edit_text(
            "🌐 **批量切换语言**\n\n请发送语言代码 (如 en/zh)",
            reply_markup=返回按钮("menu_batch2"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_notify":
        await message.edit_text(
            "📚 **批量设置通知**\n\n格式: 群组链接|静音小时",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_notify":
        await message.edit_text(
            "🔕 **批量查看通知**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_pinned":
        await message.edit_text(
            "📌 **批量查看置顶消息**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_pinned_dialogs":
        await message.edit_text(
            "📌 **批量查看置顶对话**\n\n正在导出所有账号的置顶对话...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_blocked":
        await message.edit_text(
            "🚫 **批量查看黑名单**\n\n正在导出所有账号的黑名单...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_blacklist_topics":
        await message.edit_text(
            "🚧 **批量查看黑名单话题**\n\n请发送群组链接",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_my_channels":
        await message.edit_text(
            "📁 **批量查看个人频道**\n\n正在导出所有账号创建的频道...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_invoices":
        await message.edit_text(
            "📇 **批量查看收款链接**\n\n正在导出所有账号的收款...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_view_stories":
        await message.edit_text(
            "📰 **批量查看故事**\n\n请发送目标用户名",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_enable_translate":
        await message.edit_text(
            "⭐ **批量启用翻译**\n\n正在启用所有账号的翻译功能...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_join_nearby":
        await message.edit_text(
            "📥 **批量加入附近群**\n\n正在加入 Telegram 推荐的附近群...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_dl_avatar_hq":
        await message.edit_text(
            "🖼️ **批量下载高清头像**\n\n请发送目标用户列表（每行一个）",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_quick_reply":
        await message.edit_text(
            "📜 **批量修改快捷回复**\n\n正在为所有账号启用 Saved Messages 快捷回复...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_verify_email":
        await message.edit_text(
            "📧 **批量验证邮箱**\n\n正在导出所有账号邮箱验证状态...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_import_contacts":
        await message.edit_text(
            "📞 **批量导入通讯录**\n\n请发送电话号码列表（每行一个）",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_relogin":
        await message.edit_text(
            "🔄 **批量重登账号**\n\n正在检查账号登录状态...",
            reply_markup=返回按钮("menu_batch5"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "batch_scheduled_sign":
        await message.edit_text(
            "⏰ **定时签到设置**\n\n格式: 机器人列表（每行一个）\n然后发送 cron 时间如 09:00",
            reply_markup=返回按钮("menu_batch"),
            parse_mode=ParseMode.MARKDOWN
        )

    # 举报系统
    elif data == "menu_report":
        await 举报菜单(user_id, message)
    elif data == "report_target":
        await 举报目标菜单(user_id, message)
    elif data == "report_multi":
        await 举报多目标(user_id, message)
    elif data == "report_cycle":
        await message.edit_text(
            "🔄 **循环举报**\n\n请发送目标链接，然后发送举报原因，最后发送循环次数",
            reply_markup=返回按钮("menu_report"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "report_history":
        await 查看举报历史(user_id, message)

    # 守护系统
    elif data == "menu_guardian":
        await 守护菜单(user_id, message)
    elif data == "guardian_start":
        await 启动守护(user_id, message)
    elif data == "guardian_stop":
        await 停止守护(user_id, message)
    elif data == "guardian_status":
        await 守护状态(user_id, message)
    elif data == "guardian_sovereign":
        await 启动主权(user_id, message)
    elif data == "guardian_sovereign_stop":
        await 停止主权(user_id, message)
    elif data == "guardian_logs":
        await 守护日志(user_id, message)
    elif data == "guardian_whitelist":
        await message.edit_text(
            "📝 **设置白名单设备**\n\n请发送设备型号列表，每行一个",
            reply_markup=返回按钮("menu_guardian"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "guardian_consume_bot":
        await message.edit_text(
            "🤖 **设置消耗机器人**\n\n请发送机器人用户名（如 @xxx_bot）",
            reply_markup=返回按钮("menu_guardian"),
            parse_mode=ParseMode.MARKDOWN
        )

    # 监听系统
    elif data == "menu_monitor":
        await 监听菜单(user_id, message)
    elif data == "monitor_start":
        await 启动监听(user_id, message)
    elif data == "monitor_stop":
        await 停止监听(user_id, message)
    elif data == "monitor_status":
        await 监听状态(user_id, message)
    elif data == "monitor_keywords":
        await message.edit_text(
            "🔑 **设置监听关键词**\n\n请发送关键词，用逗号分隔\n例如: 飞机号,协议号,出售,担保",
            reply_markup=返回按钮("menu_monitor"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "monitor_forward":
        await message.edit_text(
            "📤 **设置转发目标**\n\n请发送目标群组链接或用户名",
            reply_markup=返回按钮("menu_monitor"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "monitor_reply":
        await message.edit_text(
            "💬 **设置自动回复规则**\n\n请发送JSON格式规则\n例如: {\"你好\": \"你好，有什么可以帮您？\", \"价格\": \"请私聊咨询价格\"}",
            reply_markup=返回按钮("menu_monitor"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "monitor_logs":
        await 监听日志(user_id, message)

    # 代理管理
    elif data == "menu_proxy":
        await 代理菜单(user_id, message)
    elif data == "proxy_import":
        await message.edit_text(
            "🌐 **导入代理**\n\n请发送代理列表，每行一个\n格式: ip:port 或 ip:port:user:pass\n支持 socks5:// 和 http:// 前缀",
            reply_markup=返回按钮("menu_proxy"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "proxy_check":
        await 检测代理(user_id, message)
    elif data == "proxy_stats":
        await 代理统计(user_id, message)
    elif data == "proxy_clear":
        await 清空代理(user_id, message)
    elif data == "proxy_mode":
        await 代理模式菜单(user_id, message)

    # 设置管理
    elif data == "menu_settings":
        await 设置菜单(user_id, message)
    elif data == "settings_view":
        await 查看设置(user_id, message)
    elif data == "settings_export":
        await 导出设置(user_id, message)
    elif data == "settings_import":
        await message.edit_text(
            "📥 **导入设置**\n\n请发送JSON格式的设置数据",
            reply_markup=返回按钮("menu_settings"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "settings_delay":
        await message.edit_text(
            "⏱️ **设置延迟**\n\n请发送格式: 操作类型 最小值 最大值\n操作类型: delay(通用) reaction(点赞) join(加群) send(发送)\n例如: send 10 30",
            reply_markup=返回按钮("menu_settings"),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "settings_report_reason":
        await message.edit_text(
            "🚨 **设置默认举报原因**\n\n请选择原因: spam/垃圾广告 violence/暴力 pornography/色情 child_abuse/虐待儿童 copyright/版权 fake/假冒 drugs/毒品 privacy/隐私 other/其他",
            reply_markup=返回按钮("menu_settings"),
            parse_mode=ParseMode.MARKDOWN
        )

    # 概览
    elif data == "menu_overview":
        await 概览(user_id, message)
    elif data == "menu_help":
        await message.edit_text(
            f"📖 **{项目名称} 帮助**\n\n"
            "**会话管理** - 登录/验证/导出/转移 session\n"
            "**批量操作** - 加群/群发/点赞/转发/改名等30+功能\n"
            "**举报系统** - 10种举报原因批量举报\n"
            "**守护系统** - 验证码监控/防盗/自动杀设备\n"
            "**监听系统** - 关键词检测/自动回复\n"
            "**代理管理** - 导入/检测/轮换\n"
            "**设置管理** - 自定义所有功能参数\n\n"
            f"作者: {作者名称} {作者用户名}",
            reply_markup=返回按钮("menu_main"),
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== 菜单函数 ====================

async def 账号管理菜单(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"📱 **账号管理**\n\n当前账号数: {count}\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 查看账号 ({count})", callback_data="account_list")],
        [InlineKeyboardButton("📥 导入账号", callback_data="account_import"),
         InlineKeyboardButton("✅ 验证全部", callback_data="account_verify")],
        [InlineKeyboardButton("📤 导出ZIP", callback_data="account_export"),
         InlineKeyboardButton("📝 导出字符串", callback_data="account_export_strings")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 会话管理菜单(user_id, message):
    text = "🔑 **会话管理**\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 登录新账号", callback_data="session_login")],
        [InlineKeyboardButton("🔄 会话转移", callback_data="session_transfer"),
         InlineKeyboardButton("⚡ 快速生成Session", callback_data="session_magic")],
        [InlineKeyboardButton("📱 查看登录设备", callback_data="session_devices"),
         InlineKeyboardButton("🗑️ 踢出设备", callback_data="session_kill")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 批量操作菜单(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"⚡ **批量操作中心**\n\n可用账号: {count}\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        # ============ 第一行：基础 ============
        [InlineKeyboardButton("➕ 加群", callback_data="batch_join"),
         InlineKeyboardButton("➖ 退群", callback_data="batch_leave")],
        # ============ 第二行：消息 ============
        [InlineKeyboardButton("💬 群发消息", callback_data="batch_send"),
         InlineKeyboardButton("🗨️ 群发私聊", callback_data="batch_dm")],
        [InlineKeyboardButton("🌀 群发所有对话", callback_data="batch_dm_all"),
         InlineKeyboardButton("🔁 转发消息", callback_data="batch_forward")],
        # ============ 第三行：互动 ============
        [InlineKeyboardButton("👍 点赞", callback_data="batch_react"),
         InlineKeyboardButton("❤️ 互赞多消息", callback_data="batch_multi_react")],
        [InlineKeyboardButton("🗳️ 投票", callback_data="batch_vote"),
         InlineKeyboardButton("🧧 抢红包", callback_data="batch_grab")],
        [InlineKeyboardButton("🎰 抽奖自动参与", callback_data="batch_lottery")],
        # ============ 第四行：机器人指令 ============
        [InlineKeyboardButton("📲 /qd 批量签到", callback_data="batch_sign"),
         InlineKeyboardButton("🤖 启动机器人", callback_data="batch_start_bot")],
        [InlineKeyboardButton("⚡ 任意指令批量发送", callback_data="batch_cmd")],
        # ============ 第五行：资料修改 ============
        [InlineKeyboardButton("✏️ 改昵称", callback_data="batch_nickname"),
         InlineKeyboardButton("✏️ 改用户名", callback_data="batch_username")],
        [InlineKeyboardButton("📝 改简介", callback_data="batch_bio"),
         InlineKeyboardButton("🖼️ 改头像", callback_data="batch_avatar")],
        [InlineKeyboardButton("🌐 改头像-目录", callback_data="batch_avatar_dir"),
         InlineKeyboardButton("💠 emoji状态", callback_data="batch_emoji")],
        # ============ 第六行：群/频道创建 ============
        [InlineKeyboardButton("📢 创建频道", callback_data="batch_create_channel"),
         InlineKeyboardButton("👥 创建超级群", callback_data="batch_create_supergroup")],
        [InlineKeyboardButton("💬 创建论坛", callback_data="batch_create_forum"),
         InlineKeyboardButton("🆙 升级超级群", callback_data="batch_upgrade_sg")],
        # ============ 第七行：群管 ============
        [InlineKeyboardButton("🚫 踢广告", callback_data="batch_kick_ads"),
         InlineKeyboardButton("🔇 禁言", callback_data="batch_mute")],
        [InlineKeyboardButton("🔊 解除禁言", callback_data="batch_unmute"),
         InlineKeyboardButton("👑 提升管理员", callback_data="batch_promote")],
        [InlineKeyboardButton("📉 降权", callback_data="batch_demote"),
         InlineKeyboardButton("📌 置顶/取消", callback_data="batch_pin")],
        [InlineKeyboardButton("📨 邀请链接轮换", callback_data="batch_invite_link"),
         InlineKeyboardButton("🪧 群简介", callback_data="batch_set_about")],
        # ============ 第八行：私聊/好友 ============
        [InlineKeyboardButton("👋 回关", callback_data="batch_follow_back"),
         InlineKeyboardButton("📨 好友申请", callback_data="batch_friend_req")],
        # ============ 第九行：养号/活跃 ============
        [InlineKeyboardButton("🟢 上线", callback_data="batch_online"),
         InlineKeyboardButton("🔴 离线", callback_data="batch_offline")],
        [InlineKeyboardButton("📖 水群", callback_data="batch_spam"),
         InlineKeyboardButton("✅ 已读全部", callback_data="batch_read_all")],
        [InlineKeyboardButton("🗑️ 撤回自己", callback_data="batch_delete_own"),
         InlineKeyboardButton("✏️ 编辑消息", callback_data="batch_edit_msg")],
        [InlineKeyboardButton("👁️ 刷浏览量", callback_data="batch_view"),
         InlineKeyboardButton("📊 看帖浏览", callback_data="batch_view_posts")],
        # ============ 第十行：隐私/状态 ============
        [InlineKeyboardButton("🔒 隐私设置", callback_data="batch_privacy"),
         InlineKeyboardButton("🔒 一键锁定", callback_data="batch_privacy_lock")],
        [InlineKeyboardButton("🔓 一键开放", callback_data="batch_privacy_unlock"),
         InlineKeyboardButton("🚫 拒陌生人", callback_data="batch_block_stranger")],
        # ============ 第十一行：清理/检测 ============
        [InlineKeyboardButton("🧹 清空对话", callback_data="batch_clear_chats"),
         InlineKeyboardButton("❌ 注销账号", callback_data="batch_delete_account")],
        [InlineKeyboardButton("🔎 检测Premium", callback_data="batch_check_premium"),
         InlineKeyboardButton("🚨 检测封禁", callback_data="batch_check_ban")],
        [InlineKeyboardButton("👥 爬取群成员", callback_data="batch_scrape_members"),
         InlineKeyboardButton("📇 导出联系人", callback_data="batch_export_contacts")],
        [InlineKeyboardButton("📊 查看账号信息", callback_data="batch_profile"),
         InlineKeyboardButton("📋 查看群组列表", callback_data="batch_groups")],
        [InlineKeyboardButton("👥 拉人入群", callback_data="batch_invite"),
         InlineKeyboardButton("🔍 搜索消息", callback_data="batch_search")],
        [InlineKeyboardButton("📜 历史记录", callback_data="batch_history"),
         InlineKeyboardButton("🖼️ 下载头像", callback_data="batch_dl_avatar")],
        # ============ 第十二行：定时签到（高级） ============
        [InlineKeyboardButton("⏰ 定时签到设置", callback_data="batch_scheduled_sign")],
        # ============ 第十三行：分页（高级功能） ============
        [InlineKeyboardButton("▶️ 2/5 进阶 (300+功能)", callback_data="menu_batch2")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def 批量操作菜单2(user_id, message):
    """第二页：高级群管/养号/安全"""
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"⚡ **批量操作 2/5**\n\n可用账号: {count}\n\n高级群管 / 养号 / 安全"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👋 回关", callback_data="batch_follow_back"),
         InlineKeyboardButton("📨 好友申请", callback_data="batch_friend_req")],
        [InlineKeyboardButton("🟢 上线", callback_data="batch_online"),
         InlineKeyboardButton("🔴 离线", callback_data="batch_offline")],
        [InlineKeyboardButton("📖 水群", callback_data="batch_spam"),
         InlineKeyboardButton("✅ 已读全部", callback_data="batch_read_all")],
        [InlineKeyboardButton("🗑️ 撤回自己", callback_data="batch_delete_own"),
         InlineKeyboardButton("✏️ 编辑消息", callback_data="batch_edit_msg")],
        [InlineKeyboardButton("👁️ 刷浏览量", callback_data="batch_view"),
         InlineKeyboardButton("📊 看帖浏览", callback_data="batch_view_posts")],
        [InlineKeyboardButton("🚫 踢广告", callback_data="batch_kick_ads"),
         InlineKeyboardButton("🔇 禁言", callback_data="batch_mute")],
        [InlineKeyboardButton("🔊 解除禁言", callback_data="batch_unmute"),
         InlineKeyboardButton("👑 提升管理员", callback_data="batch_promote")],
        [InlineKeyboardButton("📉 降权", callback_data="batch_demote"),
         InlineKeyboardButton("📌 置顶/取消", callback_data="batch_pin")],
        [InlineKeyboardButton("📨 邀请链接轮换", callback_data="batch_invite_link"),
         InlineKeyboardButton("🪧 群简介", callback_data="batch_set_about")],
        [InlineKeyboardButton("🌟 TG Stars", callback_data="batch_stars"),
         InlineKeyboardButton("⭐ 收藏表情", callback_data="batch_stickers")],
        [InlineKeyboardButton("🌐 切换语言", callback_data="batch_lang")],
        [InlineKeyboardButton("◀️ 1/5 上一页", callback_data="menu_batch"),
         InlineKeyboardButton("▶️ 3/5 下一页", callback_data="menu_batch3")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def 批量操作菜单3(user_id, message):
    """第三页：账号管理 / 检测 / 修复"""
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"⚡ **批量操作 3/5**\n\n可用账号: {count}\n\n账号管理 / 检测 / 修复 / 会话"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 查看账号信息", callback_data="batch_profile"),
         InlineKeyboardButton("📋 查看群组列表", callback_data="batch_groups")],
        [InlineKeyboardButton("👥 拉人入群", callback_data="batch_invite"),
         InlineKeyboardButton("🔍 搜索消息", callback_data="batch_search")],
        [InlineKeyboardButton("📜 历史记录", callback_data="batch_history"),
         InlineKeyboardButton("🖼️ 下载头像", callback_data="batch_dl_avatar")],
        [InlineKeyboardButton("🔎 检测Premium", callback_data="batch_check_premium"),
         InlineKeyboardButton("🚨 检测封禁", callback_data="batch_check_ban")],
        [InlineKeyboardButton("👥 爬取群成员", callback_data="batch_scrape_members"),
         InlineKeyboardButton("📇 导出联系人", callback_data="batch_export_contacts")],
        [InlineKeyboardButton("🧹 清空对话", callback_data="batch_clear_chats"),
         InlineKeyboardButton("❌ 注销账号", callback_data="batch_delete_account")],
        [InlineKeyboardButton("🔒 隐私设置", callback_data="batch_privacy"),
         InlineKeyboardButton("🔒 一键锁定", callback_data="batch_privacy_lock")],
        [InlineKeyboardButton("🔓 一键开放", callback_data="batch_privacy_unlock"),
         InlineKeyboardButton("🚫 拒陌生人", callback_data="batch_block_stranger")],
        [InlineKeyboardButton("🔐 终止会话", callback_data="batch_kill_sessions"),
         InlineKeyboardButton("🌐 终止网页会话", callback_data="kill_web_auths")],
        [InlineKeyboardButton("📱 查看设备", callback_data="batch_view_devices"),
         InlineKeyboardButton("🔒 一键杀设备锁", callback_data="batch_kill_lock")],
        [InlineKeyboardButton("✅ 验证有效性", callback_data="batch_verify_sessions"),
         InlineKeyboardButton("🔧 修复session", callback_data="batch_fix_sessions")],
        [InlineKeyboardButton("📄 导出CSV", callback_data="batch_export_csv"),
         InlineKeyboardButton("📥 导入session", callback_data="batch_import_sessions")],
        [InlineKeyboardButton("◀️ 2/5 上一页", callback_data="menu_batch2"),
         InlineKeyboardButton("▶️ 4/5 下一页", callback_data="menu_batch4")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def 批量操作菜单4(user_id, message):
    """第四页：消息/资料/创建"""
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"⚡ **批量操作 4/5**\n\n可用账号: {count}\n\n资料增强 / 群聊/频道创建"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ 改昵称", callback_data="batch_nickname"),
         InlineKeyboardButton("✏️ 改用户名", callback_data="batch_username")],
        [InlineKeyboardButton("📝 改简介", callback_data="batch_bio"),
         InlineKeyboardButton("🖼️ 改头像", callback_data="batch_avatar")],
        [InlineKeyboardButton("🌐 改头像-目录", callback_data="batch_avatar_dir"),
         InlineKeyboardButton("💠 emoji状态", callback_data="batch_emoji")],
        [InlineKeyboardButton("🎂 生日设置", callback_data="batch_birthday"),
         InlineKeyboardButton("🔑 修改两步验证", callback_data="batch_change_2fa")],
        [InlineKeyboardButton("📅 用户名带年份", callback_data="batch_username_year")],
        [InlineKeyboardButton("📢 创建频道", callback_data="batch_create_channel"),
         InlineKeyboardButton("👥 创建超级群", callback_data="batch_create_supergroup")],
        [InlineKeyboardButton("💬 创建论坛", callback_data="batch_create_forum"),
         InlineKeyboardButton("🆙 升级超级群", callback_data="batch_upgrade_sg")],
        [InlineKeyboardButton("📂 创建文件夹", callback_data="batch_create_folder"),
         InlineKeyboardButton("🗑 删除文件夹", callback_data="batch_del_folder")],
        [InlineKeyboardButton("📋 创建主题", callback_data="batch_create_topic"),
         InlineKeyboardButton("🎨 改主题颜色", callback_data="batch_topic_color")],
        [InlineKeyboardButton("📍 发送位置", callback_data="batch_send_location"),
         InlineKeyboardButton("👤 发送联系人", callback_data="batch_send_contact")],
        [InlineKeyboardButton("🗳 发送投票", callback_data="batch_send_poll"),
         InlineKeyboardButton("🎲 棋盘游戏", callback_data="batch_send_dice")],
        [InlineKeyboardButton("🎙 语音消息", callback_data="batch_send_voice"),
         InlineKeyboardButton("🎬 视频消息", callback_data="batch_send_video")],
        [InlineKeyboardButton("◀️ 3/5 上一页", callback_data="menu_batch3"),
         InlineKeyboardButton("▶️ 5/5 下一页", callback_data="menu_batch5")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def 批量操作菜单5(user_id, message):
    """第五页：趣味 / 系统工具 / 故事 / 通知"""
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"⚡ **批量操作 5/5**\n\n可用账号: {count}\n\n趣味 / 系统工具 / 故事 / 通知"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧧 抢红包", callback_data="batch_grab"),
         InlineKeyboardButton("🎰 抽奖自动参与", callback_data="batch_lottery")],
        [InlineKeyboardButton("📚 通知设置", callback_data="batch_notify"),
         InlineKeyboardButton("🔕 通知查看", callback_data="batch_view_notify")],
        [InlineKeyboardButton("📌 置顶消息", callback_data="batch_view_pinned"),
         InlineKeyboardButton("📌 置顶对话", callback_data="batch_view_pinned_dialogs")],
        [InlineKeyboardButton("🚫 黑名单", callback_data="batch_view_blocked"),
         InlineKeyboardButton("🚧 黑名单话题", callback_data="batch_view_blacklist_topics")],
        [InlineKeyboardButton("📁 个人频道", callback_data="batch_view_my_channels"),
         InlineKeyboardButton("📇 收款链接", callback_data="batch_view_invoices")],
        [InlineKeyboardButton("📰 查看故事", callback_data="batch_view_stories"),
         InlineKeyboardButton("⭐ 启用翻译", callback_data="batch_enable_translate")],
        [InlineKeyboardButton("📥 加入附近群", callback_data="batch_join_nearby"),
         InlineKeyboardButton("🖼️ 高清头像", callback_data="batch_dl_avatar_hq")],
        [InlineKeyboardButton("📜 修改快捷回复", callback_data="batch_quick_reply"),
         InlineKeyboardButton("📧 验证邮箱", callback_data="batch_verify_email")],
        [InlineKeyboardButton("📞 导入通讯录", callback_data="batch_import_contacts"),
         InlineKeyboardButton("🔄 重登账号", callback_data="batch_relogin")],
        [InlineKeyboardButton("◀️ 4/5 上一页", callback_data="menu_batch4"),
         InlineKeyboardButton("▶️ 1/5 回到首页", callback_data="menu_batch")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 举报菜单(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    count = len(accounts)
    text = f"🚨 **举报系统**\n\n可用账号: {count}\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 举报目标", callback_data="report_target")],
        [InlineKeyboardButton("🎯 多目标举报", callback_data="report_multi"),
         InlineKeyboardButton("🔄 循环举报", callback_data="report_cycle")],
        [InlineKeyboardButton("📋 举报历史", callback_data="report_history")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 举报目标菜单(user_id, message):
    text = "🚨 **选择举报原因**\n\n请选择举报原因:"
    reasons = 举报.获取举报原因列表()
    buttons = []
    row = []
    for i, r in enumerate(reasons):
        row.append(InlineKeyboardButton(r['name'], callback_data=f"report_do_{r['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_report")])
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def 隐私设置菜单(user_id, message):
    text = "🔒 **隐私设置**\n\n选择隐私类型:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 手机号", callback_data="privacy_phone_number"),
         InlineKeyboardButton("➕ 手机号添加", callback_data="privacy_add_by_phone")],
        [InlineKeyboardButton("🕐 最后上线", callback_data="privacy_last_seen"),
         InlineKeyboardButton("🖼️ 头像", callback_data="privacy_profile_photo")],
        [InlineKeyboardButton("↗️ 转发", callback_data="privacy_forwards"),
         InlineKeyboardButton("📞 通话", callback_data="privacy_phone_call")],
        [InlineKeyboardButton("🔗 群邀请", callback_data="privacy_group_invite")],
        [InlineKeyboardButton("🔒 一键锁定全部", callback_data="batch_privacy_lock")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_batch")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 守护菜单(user_id, message):
    status = 守护.获取守护状态(user_id)
    text = f"🛡️ **守护系统**\n\n状态: {'✅ 运行中' if status['active'] else '❌ 未启动'}\n运行中账号: {status['running']}\n主权模式: {'👑 已开启' if status['sovereign'] else '❌ 未启动'}\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ 启动守护", callback_data="guardian_start"),
         InlineKeyboardButton("⏹️ 停止守护", callback_data="guardian_stop")],
        [InlineKeyboardButton("📊 守护状态", callback_data="guardian_status"),
         InlineKeyboardButton("📋 守护日志", callback_data="guardian_logs")],
        [InlineKeyboardButton("👑 启动主权模式", callback_data="guardian_sovereign"),
         InlineKeyboardButton("👑 停止主权", callback_data="guardian_sovereign_stop")],
        [InlineKeyboardButton("📝 白名单设备", callback_data="guardian_whitelist"),
         InlineKeyboardButton("🤖 消耗机器人", callback_data="guardian_consume_bot")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 监听菜单(user_id, message):
    status = 监听.获取监听状态(user_id)
    text = f"👂 **监听系统**\n\n状态: {'✅ 运行中' if status['active'] else '❌ 未启动'}\n关键词: {', '.join(status['keywords'][:5]) if status['keywords'] else '未设置'}\n转发目标: {status['forward_target'] or '未设置'}\n回复规则: {len(status['auto_reply'])} 条\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ 启动监听", callback_data="monitor_start"),
         InlineKeyboardButton("⏹️ 停止监听", callback_data="monitor_stop")],
        [InlineKeyboardButton("📊 监听状态", callback_data="monitor_status"),
         InlineKeyboardButton("📋 监听日志", callback_data="monitor_logs")],
        [InlineKeyboardButton("🔑 设置关键词", callback_data="monitor_keywords"),
         InlineKeyboardButton("📤 转发目标", callback_data="monitor_forward")],
        [InlineKeyboardButton("💬 自动回复规则", callback_data="monitor_reply")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 代理菜单(user_id, message):
    stats = 代理.获取代理统计(user_id)
    text = f"🌐 **代理管理**\n\n总计: {stats['total']} | 活跃: {stats['active']} | 警告: {stats['warn']} | 失效: {stats['dead']}\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 导入代理", callback_data="proxy_import"),
         InlineKeyboardButton("🔍 检测存活", callback_data="proxy_check")],
        [InlineKeyboardButton("📊 代理统计", callback_data="proxy_stats"),
         InlineKeyboardButton("🗑️ 清空代理", callback_data="proxy_clear")],
        [InlineKeyboardButton("🔄 轮换模式", callback_data="proxy_mode")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 代理模式菜单(user_id, message):
    text = "🔄 **选择代理轮换模式**"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 随机 (random)", callback_data="proxy_mode_random")],
        [InlineKeyboardButton("🔁 轮询 (round_robin)", callback_data="proxy_mode_round_robin")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_proxy")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def 设置菜单(user_id, message):
    text = "⚙️ **设置管理**\n\n自定义所有功能参数\n\n请选择操作:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👁️ 查看当前设置", callback_data="settings_view")],
        [InlineKeyboardButton("📤 导出设置", callback_data="settings_export"),
         InlineKeyboardButton("📥 导入设置", callback_data="settings_import")],
        [InlineKeyboardButton("⏱️ 设置延迟", callback_data="settings_delay"),
         InlineKeyboardButton("🚨 默认举报原因", callback_data="settings_report_reason")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_main")],
    ])
    await message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# ==================== 操作函数 ====================

async def 显示账号列表(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        text = "📱 **账号列表**\n\n暂无账号，请先导入或登录账号"
    else:
        text = f"📱 **账号列表** (共 {len(accounts)} 个)\n\n"
        for acc in accounts[:20]:
            status_icon = "🟢" if acc['status'] == 'active' else "🔴"
            premium_icon = "⭐" if acc['premium'] else ""
            text += f"{status_icon} {premium_icon} `{acc['phone']}`"
            if acc['username']:
                text += f" (@{acc['username']})"
            text += f"\n   └─ {acc['device_model'] or '未知设备'}"
            if acc['last_check']:
                text += f" | 最后检查: {acc['last_check']}"
            text += "\n"
        if len(accounts) > 20:
            text += f"\n... 还有 {len(accounts) - 20} 个账号"
    await message.edit_text(text, reply_markup=返回按钮("menu_accounts"), parse_mode=ParseMode.MARKDOWN)

async def 验证账号(user_id, message):
    await message.edit_text("⏳ 正在验证所有账号...", reply_markup=None)
    results = await 账号管理.批量验证账号(user_id)
    active = sum(1 for r in results if r['status'] == 'active')
    inactive = sum(1 for r in results if r['status'] == 'inactive')
    text = f"✅ 验证完成\n\n🟢 活跃: {active}\n🔴 失效: {inactive}\n总计: {len(results)}"
    await message.edit_text(text, reply_markup=返回按钮("menu_accounts"))

async def 导出账号(user_id, message):
    await message.edit_text("⏳ 正在导出...", reply_markup=None)
    zip_path, error = await 账号管理.导出账号(user_id)
    if error:
        await message.edit_text(f"❌ 导出失败: {error}", reply_markup=返回按钮("menu_accounts"))
    else:
        await message.edit_text(f"✅ 导出成功!\n\n📁 文件: {os.path.basename(zip_path)}", reply_markup=返回按钮("menu_accounts"))
        await message.reply_document(document=open(zip_path, 'rb'))

async def 导出会话字符串(user_id, message):
    await message.edit_text("⏳ 正在导出会话字符串...", reply_markup=None)
    path, error = await 账号管理.导出会话字符串(user_id)
    if error:
        await message.edit_text(f"❌ 导出失败: {error}", reply_markup=返回按钮("menu_accounts"))
    else:
        await message.edit_text(f"✅ 导出成功!\n\n📁 文件: {os.path.basename(path)}", reply_markup=返回按钮("menu_accounts"))
        await message.reply_document(document=open(path, 'rb'))

async def 快速生成会话(user_id, message):
    magic_model = 生成魔法型号()
    text = f"⚡ **快速生成 Session**\n\n设备型号: {magic_model}\n\n请发送手机号（格式: +8613800138000）"
    await message.edit_text(text, reply_markup=返回按钮("menu_sessions"), parse_mode=ParseMode.MARKDOWN)

# ==================== 批量操作执行 ====================

async def 执行批量加群(user_id, message, link):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text(f"⏳ 正在批量加群...\n{构建进度条(0, len(accounts))}")
    result = await 批量操作.批量加群(accounts, link)
    text = 批量操作.生成批量操作报告(result, "批量加群")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量退群(user_id, message, link):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量退群...")
    result = await 批量操作.批量退群(accounts, link)
    text = 批量操作.生成批量操作报告(result, "批量退群")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量群发(user_id, message, target, msg_text):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量群发...")
    result = await 批量操作.批量群发消息(accounts, target, msg_text)
    text = 批量操作.生成批量操作报告(result, "批量群发")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量点赞(user_id, message, link):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量点赞...")
    result = await 批量操作.批量点赞(accounts, link)
    text = 批量操作.生成批量操作报告(result, "批量点赞")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量转发(user_id, message, from_link, to_target):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量转发...")
    result = await 批量操作.批量转发消息(accounts, from_link, to_target)
    text = 批量操作.生成批量操作报告(result, "批量转发")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量修改昵称(user_id, message, nickname):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量修改昵称...")
    result = await 批量操作.批量修改昵称(accounts, nickname)
    text = 批量操作.生成批量操作报告(result, "批量修改昵称")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量修改用户名(user_id, message, username):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量修改用户名...")
    result = await 批量操作.批量修改用户名(accounts, username)
    text = 批量操作.生成批量操作报告(result, "批量修改用户名")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行批量修改简介(user_id, message, bio):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在批量修改简介...")
    result = await 批量操作.批量修改简介(accounts, bio)
    text = 批量操作.生成批量操作报告(result, "批量修改简介")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 批量锁定隐私(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在锁定所有隐私设置...")
    result = await 批量操作.批量锁定隐私(accounts)
    text = 批量操作.生成批量操作报告(result, "批量锁定隐私")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 执行启动机器人(user_id, message, bot_links_text):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    bot_links = [l.strip() for l in bot_links_text.split('\n') if l.strip()]
    await message.edit_text("⏳ 正在批量启动机器人...")
    result = await 批量操作.批量启动机器人(accounts, bot_links)
    text = 批量操作.生成批量操作报告(result, "批量启动机器人")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 爬取群成员(user_id, message, link):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在爬取群成员...")
    result = await 批量操作.爬取群成员(accounts, link)
    if result.get('error'):
        await message.edit_text(f"❌ 爬取失败: {result['error']}", reply_markup=返回按钮("menu_batch"))
    else:
        members = result.get('members', [])
        text = f"✅ 爬取完成\n\n👥 成员数: {len(members)}\n"
        if members:
            text += "\n前10个成员:\n"
            for m in members[:10]:
                text += f"• {m['first_name']} {m['last_name']}"
                if m['username']:
                    text += f" (@{m['username']})"
                text += "\n"
        # 导出CSV
        csv_path, csv_error = await 批量操作.导出群成员到CSV(link, f"members_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", user_id)
        if csv_path:
            await message.reply_document(document=open(csv_path, 'rb'), filename=os.path.basename(csv_path))
        await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 导出联系人(user_id, message):
    await message.edit_text("⏳ 正在导出联系人...", reply_markup=None)
    csv_path, error = await 批量操作.导出联系人为CSV(user_id)
    if error:
        await message.edit_text(f"❌ 导出失败: {error}", reply_markup=返回按钮("menu_batch"))
    else:
        await message.edit_text("✅ 导出成功!", reply_markup=返回按钮("menu_batch"))
        await message.reply_document(document=open(csv_path, 'rb'), filename=os.path.basename(csv_path))

async def 清空对话(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在清空对话...")
    result = await 批量操作.批量清空对话(accounts)
    text = 批量操作.生成批量操作报告(result, "清空对话")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 查看账号信息(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在获取账号信息...")
    results = await 批量操作.批量获取账号信息(accounts)
    text = "📊 **账号信息**\n\n"
    for r in results[:10]:
        if r['status'] == 'success':
            text += f"📱 {r['phone']}\n"
            text += f"   ├─ ID: {r['id']}\n"
            text += f"   ├─ 昵称: {r['first_name']} {r['last_name']}\n"
            text += f"   ├─ 用户名: @{r['username']}\n" if r['username'] else ""
            text += f"   └─ 会员: {'⭐' if r['premium'] else '❌'}\n"
        else:
            text += f"📱 {r['phone']} - ❌ {r.get('error', '失败')}\n"
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 查看群组列表(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在获取群组列表...")
    groups = await 批量操作.批量获取群组列表(accounts)
    if not groups:
        await message.edit_text("❌ 未找到群组", reply_markup=返回按钮("menu_batch"))
        return
    text = f"📋 **群组列表** (共 {len(groups)} 个)\n\n"
    for g in groups[:20]:
        text += f"• {g['title']}"
        if g['username']:
            text += f" (@{g['username']})"
        text += f" | {g['members_count']}人 | 账号: {g['account_phone']}\n"
    if len(groups) > 20:
        text += f"\n... 还有 {len(groups) - 20} 个群组"
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 刷在线状态(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
        return
    await message.edit_text("⏳ 正在刷在线状态...")
    result = await 批量操作.批量刷在线(accounts)
    text = 批量操作.生成批量操作报告(result, "刷在线状态")
    await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)

async def 刷浏览量(user_id, message):
    await message.edit_text(
        "👁️ **刷浏览量**\n\n请发送频道链接",
        reply_markup=返回按钮("menu_batch"),
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== 举报执行 ====================

async def 执行举报(user_id, message, reason_id):
    await message.edit_text(
        f"🚨 **举报目标**\n\n原因: {reason_id}\n\n请发送目标链接（如 @username 或 t.me/xxx）",
        reply_markup=返回按钮("menu_report"),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['report_reason'] = reason_id

async def 执行举报目标(user_id, message, target, reason):
    accounts = db.获取用户活跃账号(user_id)
    if not accounts:
        await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_report"))
        return
    await message.edit_text(f"⏳ 正在举报 {target}...")
    result = await 批量操作.批量举报(accounts, target, reason)
    text = 批量操作.生成批量操作报告(result, f"举报 {target}")
    await message.edit_text(text, reply_markup=返回按钮("menu_report"), parse_mode=ParseMode.MARKDOWN)

async def 举报多目标(user_id, message):
    await message.edit_text(
        "🚨 **多目标举报**\n\n请发送目标列表，每行一个\n格式: 目标链接 举报原因\n例如:\n@user1 spam\n@user2 色情\n@channel3 假冒",
        reply_markup=返回按钮("menu_report"),
        parse_mode=ParseMode.MARKDOWN
    )

async def 查看举报历史(user_id, message):
    text = 举报.格式化举报历史(user_id)
    await message.edit_text(text, reply_markup=返回按钮("menu_report"), parse_mode=ParseMode.MARKDOWN)

# ==================== 守护执行 ====================

async def 启动守护(user_id, message):
    success, msg = await 守护.启动守护(user_id)
    if success:
        await message.edit_text(f"✅ {msg}", reply_markup=返回按钮("menu_guardian"))
    else:
        await message.edit_text(f"❌ {msg}", reply_markup=返回按钮("menu_guardian"))

async def 停止守护(user_id, message):
    success, msg = await 守护.停止守护(user_id)
    await message.edit_text(f"{'✅' if success else '❌'} {msg}", reply_markup=返回按钮("menu_guardian"))

async def 守护状态(user_id, message):
    status = 守护.获取守护状态(user_id)
    text = f"""
🛡️ **守护状态**

├─ 守护系统: {'✅ 运行中' if status['active'] else '❌ 未启动'}
├─ 运行中账号: {status['running']}
├─ 主权模式: {'👑 已开启' if status['sovereign'] else '❌ 未启动'}
├─ 验证码监控: {'✅' if status['monitor_code'] else '❌'}
├─ 验证码消耗: {'✅' if status['consume_code'] else '❌'}
├─ 自动杀设备: {'✅' if status['auto_kill'] else '❌'}
└─ 消耗机器人: {status['consume_bot'] or '未设置'}
"""
    await message.edit_text(text, reply_markup=返回按钮("menu_guardian"), parse_mode=ParseMode.MARKDOWN)

async def 启动主权(user_id, message):
    success, msg = await 守护.启动主权模式(user_id)
    await message.edit_text(f"{'✅' if success else '❌'} {msg}", reply_markup=返回按钮("menu_guardian"))

async def 停止主权(user_id, message):
    success, msg = await 守护.停止主权模式(user_id)
    await message.edit_text(f"{'✅' if success else '❌'} {msg}", reply_markup=返回按钮("menu_guardian"))

async def 守护日志(user_id, message):
    text = 守护.查询守护日志格式化(user_id)
    await message.edit_text(text, reply_markup=返回按钮("menu_guardian"), parse_mode=ParseMode.MARKDOWN)

# ==================== 监听执行 ====================

async def 启动监听(user_id, message):
    success, msg = await 监听.启动监听(user_id)
    await message.edit_text(f"{'✅' if success else '❌'} {msg}", reply_markup=返回按钮("menu_monitor"))

async def 停止监听(user_id, message):
    success, msg = await 监听.停止监听(user_id)
    await message.edit_text(f"{'✅' if success else '❌'} {msg}", reply_markup=返回按钮("menu_monitor"))

async def 监听状态(user_id, message):
    status = 监听.获取监听状态(user_id)
    text = f"""
👂 **监听状态**

├─ 监听系统: {'✅ 运行中' if status['active'] else '❌ 未启动'}
├─ 关键词: {', '.join(status['keywords']) if status['keywords'] else '未设置'}
├─ 转发目标: {status['forward_target'] or '未设置'}
└─ 回复规则: {len(status['auto_reply'])} 条
"""
    if status['auto_reply']:
        text += "\n回复规则:\n"
        for k, v in list(status['auto_reply'].items())[:5]:
            text += f"  • {k} → {v[:30]}\n"
    await message.edit_text(text, reply_markup=返回按钮("menu_monitor"), parse_mode=ParseMode.MARKDOWN)

async def 监听日志(user_id, message):
    text = 监听.格式化监听日志(user_id)
    await message.edit_text(text, reply_markup=返回按钮("menu_monitor"), parse_mode=ParseMode.MARKDOWN)

# ==================== 代理执行 ====================

async def 检测代理(user_id, message):
    await message.edit_text("⏳ 正在检测代理存活状态...", reply_markup=None)
    result = await 代理.批量检测代理(user_id)
    await message.edit_text(result, reply_markup=返回按钮("menu_proxy"))

async def 代理统计(user_id, message):
    stats = 代理.获取代理统计(user_id)
    text = f"""
🌐 **代理统计**

├─ 总计: {stats['total']}
├─ 活跃: {stats['active']}
├─ 警告: {stats['warn']}
└─ 失效: {stats['dead']}
"""
    await message.edit_text(text, reply_markup=返回按钮("menu_proxy"), parse_mode=ParseMode.MARKDOWN)

async def 清空代理(user_id, message):
    count = 代理.清空代理(user_id)
    await message.edit_text(f"✅ 已清空 {count} 个代理", reply_markup=返回按钮("menu_proxy"))

# ==================== 设置执行 ====================

async def 查看设置(user_id, message):
    text = 设置.格式化设置显示(user_id)
    await message.edit_text(text, reply_markup=返回按钮("menu_settings"), parse_mode=ParseMode.MARKDOWN)

async def 导出设置(user_id, message):
    json_str = 设置.导出设置(user_id)
    # 保存为文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        f.write(json_str)
        tmp_path = f.name
    await message.edit_text("✅ 设置已导出", reply_markup=返回按钮("menu_settings"))
    await message.reply_document(document=open(tmp_path, 'rb'), filename=f"settings_{user_id}.json")

async def 概览(user_id, message):
    accounts = db.获取用户活跃账号(user_id)
    guardian_status = 守护.获取守护状态(user_id)
    monitor_status = 监听.获取监听状态(user_id)
    proxy_stats = 代理.获取代理统计(user_id)

    text = f"""
📊 **{项目名称} 概览**

👤 用户ID: {user_id}
📱 账号总数: {len(accounts)}
🟢 活跃账号: {sum(1 for a in accounts if a['status'] == 'active')}

🛡️ 守护: {'✅' if guardian_status['active'] else '❌'}
👂 监听: {'✅' if monitor_status['active'] else '❌'}
🌐 代理: {proxy_stats['active']}/{proxy_stats['total']} 活跃

{作者名称} {作者用户名}
"""
    await message.edit_text(text, reply_markup=返回按钮("menu_main"), parse_mode=ParseMode.MARKDOWN)

# ==================== 消息处理 ====================

async def 处理消息(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户发送的消息（文件/文本）"""
    user_id = update.effective_user.id
    message = update.message

    # 处理文件
    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ''

        if file_name.endswith('.session') or file_name.endswith('.zip'):
            await message.reply_text("⏳ 正在处理文件...")
            file = await doc.get_file()
            file_path = os.path.join(项目根目录, 'uploads', file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            await file.download_to_drive(file_path)

            if file_name.endswith('.zip'):
                results, errors = await 账号管理.从压缩包导入(file_path, user_id)
                text = f"📥 导入完成\n✅ 成功: {len(results)}\n❌ 失败: {len(errors)}"
                if results:
                    text += f"\n\n导入账号: {', '.join(results[:5])}"
                if errors:
                    text += f"\n\n错误: {'; '.join(errors[:3])}"
                await message.reply_text(text)
            elif file_name.endswith('.session'):
                result, error = await 账号管理.从会话文件导入(file_path, user_id)
                if error:
                    await message.reply_text(f"❌ 导入失败: {error}")
                else:
                    await message.reply_text(f"✅ 导入成功! 账号: {result['phone']}")
            return

    # 处理JSON字符串
    text = update.message.text or ''
    if text.strip().startswith('{') and 'session_string' in text:
        result, error = await 账号管理.从JSON字符串导入(text, user_id)
        if error:
            await message.reply_text(f"❌ 导入失败: {error}")
        else:
            await message.reply_text(f"✅ 导入成功! 账号: {result['phone']}")
        return

    # 处理代理导入
    if context.user_data.get('awaiting_proxy'):
        success, failed = await 代理.导入代理列表(user_id, text)
        await message.reply_text(f"✅ 代理导入完成\n成功: {success}\n失败: {failed}")
        context.user_data['awaiting_proxy'] = False
        return

    # 处理其他文本命令
    await 处理文本命令(user_id, message, text, context)

async def 处理文本命令(user_id, message, text, context):
    """处理文本命令"""
    text = text.strip()
    if not text:
        return

    # 手机号格式 - 发送验证码
    if re.match(r'^\+?\d{10,15}$', text):
        await message.reply_text("⏳ 正在发送验证码...")
        result, error = await 会话管理.发送验证码(text)
        if error:
            await message.reply_text(f"❌ 发送验证码失败: {error}")
        else:
            context.user_data['phone'] = text
            context.user_data['phone_code_hash'] = result['phone_code_hash']
            await message.reply_text(
                f"✅ 验证码已发送到 {text}\n\n请回复验证码（5位数字）\n超时: {result['timeout']}秒",
                reply_markup=返回按钮("menu_sessions")
            )
        return

    # 5-6位数字 - 验证码
    if re.match(r'^\d{5,6}$', text) and context.user_data.get('phone'):
        phone = context.user_data['phone']
        await message.reply_text("⏳ 正在验证登录...")
        result, session_str, error = await 会话管理.创建会话(
            phone, code=text
        )
        if error:
            if error == '2FA_REQUIRED':
                context.user_data['awaiting_2fa'] = True
                await message.reply_text("🔐 需要两步验证密码，请发送密码:")
                return
            await message.reply_text(f"❌ 登录失败: {error}")
        else:
            db.保存账号(
                user_id=user_id, phone=result['phone'],
                session_path=result['session_path'],
                api_id=默认API_ID, api_hash=默认API_HASH,
                first_name=result['first_name'], last_name=result['last_name'],
                username=result['username'], user_tg_id=result['user_id'],
                device_model=result['device_model'], system_version=result['system_version'],
                app_version=result['app_version'], premium=1 if result['premium'] else 0
            )
            await message.reply_text(
                f"✅ 登录成功!\n\n手机号: {result['phone']}\n用户名: @{result['username'] or '无'}\n"
                f"昵称: {result['first_name']} {result['last_name']}\n会员: {'⭐' if result['premium'] else '❌'}",
                reply_markup=返回按钮("menu_sessions")
            )
        return

    # 两步验证密码
    if context.user_data.get('awaiting_2fa'):
        phone = context.user_data.get('phone', '')
        await message.reply_text("⏳ 正在验证两步验证...")
        result, error = await 会话管理.完成两步验证登录(
            os.path.join(项目根目录, 会话目录, 提取手机号(phone)),
            text
        )
        context.user_data['awaiting_2fa'] = False
        if error:
            await message.reply_text(f"❌ 两步验证失败: {error}")
        else:
            await message.reply_text(f"✅ 登录成功! 账号: {result['phone']}")
        return

    # 默认处理
    await message.reply_text(
        f"📋 **{项目名称}**\n\n请使用菜单选择功能，或发送 session 文件导入账号",
        reply_markup=主菜单键盘(),
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== 回调处理扩展 ====================

async def 回调处理扩展(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理扩展的回调"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    message = query.message

    # 举报原因选择
    if data.startswith("report_do_"):
        reason = data.replace("report_do_", "")
        context.user_data['report_reason'] = reason
        await message.edit_text(
            f"🚨 **举报目标**\n\n原因: {reason}\n\n请发送目标链接",
            reply_markup=返回按钮("menu_report"),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 隐私设置
    if data.startswith("privacy_"):
        privacy_type = data.replace("privacy_", "")
        await message.edit_text(
            f"🔒 **隐私设置: {privacy_type}**\n\n请选择隐私级别:\n• all - 所有人\n• contacts - 仅联系人\n• nobody - 无人",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("所有人", callback_data=f"privacy_val_{privacy_type}_all"),
                 InlineKeyboardButton("仅联系人", callback_data=f"privacy_val_{privacy_type}_contacts")],
                [InlineKeyboardButton("无人", callback_data=f"privacy_val_{privacy_type}_nobody")],
                [InlineKeyboardButton("🔙 返回", callback_data="batch_privacy")],
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("privacy_val_"):
        parts = data.replace("privacy_val_", "").split("_")
        privacy_type = parts[0]
        privacy_val = "_".join(parts[1:])
        accounts = db.获取用户活跃账号(user_id)
        if not accounts:
            await message.edit_text("❌ 没有可用账号", reply_markup=返回按钮("menu_batch"))
            return
        await message.edit_text("⏳ 正在设置隐私...")
        result = await 批量操作.批量设置隐私(accounts, privacy_type, privacy_val)
        text = 批量操作.生成批量操作报告(result, f"隐私设置 {privacy_type} -> {privacy_val}")
        await message.edit_text(text, reply_markup=返回按钮("menu_batch"), parse_mode=ParseMode.MARKDOWN)
        return

    # 代理轮换模式
    if data.startswith("proxy_mode_"):
        mode = data.replace("proxy_mode_", "")
        success = 代理.设置轮换模式(user_id, mode)
        await message.edit_text(
            f"✅ 代理轮换模式已设置为: {mode}" if success else "❌ 设置失败",
            reply_markup=返回按钮("menu_proxy")
        )
        return

    # 其他回调转发到主处理
    await 回调处理(update, context)

# ==================== 主函数 ====================

def main():
    if not 机器人令牌:
        日志.error("未设置 BOT_TOKEN，请在 .env 文件中配置")
        print("❌ 未设置 BOT_TOKEN，请在 .env 文件中配置")
        return

    app = Application.builder().token(机器人令牌).build()

    # 命令处理
    app.add_handler(CommandHandler("start", 开始命令))
    app.add_handler(CommandHandler("help", 帮助命令))

    # 回调处理
    app.add_handler(CallbackQueryHandler(回调处理, pattern="^menu_|^account_|^session_|^batch_|^report_|^guardian_|^monitor_|^proxy_|^settings_"))
    app.add_handler(CallbackQueryHandler(回调处理扩展, pattern="^report_do_|^privacy_|^proxy_mode_"))

    # 消息处理
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, 处理消息))

    日志.info(f"{项目名称} Bot 启动中...")
    print(f"🚀 {项目名称} Bot 启动中...")
    print(f"   作者: {作者名称} {作者用户名}")
    print(f"   按 Ctrl+C 停止")

    app.run_polling()

if __name__ == "__main__":
    main()