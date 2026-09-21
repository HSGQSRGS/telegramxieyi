# ============================================================
# 协议工具箱 - 多语言 i18n 模块
# 作者: Lion
# 支持: 简体中文 / English / Русский / العربية / Español
# ============================================================

from typing import Dict, Any, Optional
import json
import os
import locale


# 默认语言配置（用户可在设置中切换）
SUPPORTED_LANGS = ['zh-CN', 'en', 'ru', 'ar', 'es']
DEFAULT_LANG = 'zh-CN'
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')

# 内存中的语言包缓存
_LOCALE_CACHE: Dict[str, Dict[str, str]] = {}


# ============================================================
# 语言资源加载
# ============================================================
def 加载语言包(语言代码: str) -> Dict[str, str]:
    """加载指定语言的语言包（带缓存）"""
    if 语言代码 in _LOCALE_CACHE:
        return _LOCALE_CACHE[语言代码]

    # 默认内嵌语言包（避免文件依赖）
    默认包 = {
        # 通用
        'main_menu': '🌟 协议工具箱 / Protocol Toolbox 🌟',
        'author': '👑 作者: Lion',
        'version': '🔖 版本: LION-2.0',
        'loading': '⏳ 加载中...',
        'success': '✅ 操作成功',
        'failed': '❌ 操作失败',
        'confirm': '⚠️ 确认执行此操作？',
        'cancelled': '🚫 已取消',

        # 举报系统
        'report_start': '🚨 启动举报引擎',
        'report_target': '🎯 举报目标',
        'report_reason': '📝 举报原因',
        'report_ai_analyze': '🤖 AI 正在分析目标...',
        'report_dispatch': '📡 调度举报账号中...',
        'report_complete': '🎉 举报完成',

        # 代理系统
        'proxy_fetching': '🌐 正在抓取代理...',
        'proxy_testing': '🔬 正在测试代理连通性...',
        'proxy_working': '✨ 可用代理',

        # 账号系统
        'account_banned': '🔴 账号已封禁',
        'account_alive': '🟢 账号正常',
        'account_login_protect': '🛡️ 反登录保护已启动',

        # 批量
        'batch_start': '⚡ 批量任务启动',
        'batch_progress': '📊 进度',
        'batch_complete': '🎊 批量任务完成',

        # 菜单项
        'menu_report': '🚨 举报中心',
        'menu_proxy': '🌐 代理系统',
        'menu_account': '👤 账号管理',
        'menu_batch': '⚡ 批量操作',
        'menu_session': '🔑 会话转换',
        'menu_security': '🔒 账号安全',
        'menu_verification': '📱 验证码监听',
        'menu_payment': '💳 支付接口',
        'menu_panel': '🖥️ 管理后台',
        'menu_settings': '⚙️ 设置',
    }

    # 尝试加载外部语言包（如果有）
    pack_path = os.path.join(LOCALES_DIR, f'{语言代码}.json')
    if os.path.exists(pack_path):
        try:
            with open(pack_path, 'r', encoding='utf-8') as f:
                外部包 = json.load(f)
                默认包.update(外部包)
        except Exception:
            pass

    _LOCALE_CACHE[语言代码] = 默认包
    return 默认包


# ============================================================
# 翻译函数
# ============================================================
def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """翻译函数（支持占位符替换）

    用法:
        t('menu_report', 'zh-CN')
        t('welcome', 'en', name='Lion')
    """
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG

    pack = 加载语言包(lang)
    text = pack.get(key, key)

    # 占位符替换（安全方式）
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def 获取用户语言(user_id: int) -> str:
    """获取用户语言偏好（默认从主程序设置中获取，否则用中文）"""
    try:
        from 配置 import 获取用户语言 as _获取
        lang = _获取(user_id)
        if lang in SUPPORTED_LANGS:
            return lang
    except Exception:
        pass
    return DEFAULT_LANG


def 设置用户语言(user_id: int, lang: str) -> bool:
    """保存用户语言偏好"""
    if lang not in SUPPORTED_LANGS:
        return False
    try:
        from 配置 import 设置用户语言 as _设置
        return _设置(user_id, lang)
    except Exception:
        return False


# ============================================================
# 语言切换器 (Inline Keyboard)
# ============================================================
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def 构造语言键盘(callback_prefix: str = 'lang_') -> InlineKeyboardMarkup:
    """构造语言切换内联键盘"""
    按钮 = []
    语言配置 = [
        ('zh-CN', '🇨🇳 简体中文'),
        ('en', '🇺🇸 English'),
        ('ru', '🇷🇺 Русский'),
        ('ar', '🇸🇦 العربية'),
        ('es', '🇪🇸 Español'),
    ]
    for 代码, 名称 in 语言配置:
        按钮.append([InlineKeyboardButton(名称, callback_data=f'{callback_prefix}{代码}')])
    return InlineKeyboardMarkup(按钮)


def 处理语言选择(callback_data: str, callback_prefix: str = 'lang_') -> Optional[str]:
    """解析 callback_data 返回语言代码"""
    if callback_data.startswith(callback_prefix):
        code = callback_data[len(callback_prefix):]
        if code in SUPPORTED_LANGS:
            return code
    return None


# ============================================================
# 装饰器：自动按用户语言翻译
# ============================================================
def 按语言翻译(func):
    """装饰器：自动按用户语言翻译函数返回值

    用法:
        @按语言翻译
        async def 菜单文本(user_id):
            return t('main_menu')
    """
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if isinstance(result, str):
            # 从 kwargs 或 args 提取 user_id
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            lang = 获取用户语言(user_id) if user_id else DEFAULT_LANG
            return t(result, lang)
        return result
    return wrapper


# ============================================================
# 智能翻译（回退到中文）
# ============================================================
def t_safe(key: str, lang: str = DEFAULT_LANG) -> str:
    """安全翻译（缺失时回退到中文，再缺失回退到 key）"""
    if lang != DEFAULT_LANG:
        text = t(key, lang)
        # 如果非中文下没找到，尝试用中文
        if text == key:
            text = t(key, DEFAULT_LANG)
            if text == key:
                # 都没找到，返回 key
                return key
        return text
    return t(key, DEFAULT_LANG)


# ============================================================
# 工具方法
# ============================================================
def 获取所有支持语言() -> list:
    """返回支持的语言代码列表"""
    return SUPPORTED_LANGS.copy()


def 验证语言代码(代码: str) -> bool:
    """验证语言代码是否支持"""
    return 代码 in SUPPORTED_LANGS


def 清空缓存():
    """清空语言包缓存"""
    global _LOCALE_CACHE
    _LOCALE_CACHE = {}
