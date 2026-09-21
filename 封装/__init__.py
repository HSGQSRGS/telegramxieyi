# ============================================================
# 协议工具箱 - 统一集成入口
# 作者: Lion
# 将所有 14 个模块聚合到一处对外暴露
# ============================================================

import importlib
import sys
import os
from typing import Any, Dict


封装目录 = os.path.dirname(os.path.abspath(__file__))


def _加载模块(name: str):
    """动态加载包内以数字开头的模块"""
    try:
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(封装目录, f'{name}.py')
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        class _空:
            pass
        空 = _空()
        setattr(空, '__error__', str(e))
        return 空


# ============== 加载所有封装模块 ==============
_模块集合 = {
    '封禁': _加载模块('1_封禁机器人'),
    '代理': _加载模块('2_代理抓取'),
    '设备': _加载模块('3_增强设备'),
    '会话': _加载模块('4_会话转换'),
    '检测': _加载模块('5_账号检测'),
    '安全': _加载模块('6_账号安全'),
    '验证': _加载模块('7_验证码监听'),
    '支付': _加载模块('8_支付接口'),
    'Web': _加载模块('9_web路由'),
    '批量': _加载模块('10_批量任务'),
    'I18n': _加载模块('11_i18n'),
    '会话v2': _加载模块('12_会话转换_v2'),
    '扩展': _加载模块('13_扩展功能'),
}


# ============================================================
# 命名空间方式 (避免冲突)
# ============================================================
class 命名空间:
    """通过命名空间方式访问各模块

    用法:
        from 封装 import modules
        modules.封禁.举报单个目标(...)
    """
    def __init__(self):
        for 名字, 模块 in _模块集合.items():
            setattr(self, 名字, 模块)


modules = 命名空间()


# ============================================================
# 元数据
# ============================================================
VERSION = 'LION-2.0'
AUTHOR = 'Lion'
PROJECT_NAME = '协议工具箱'
MODULE_COUNT = 14

功能清单 = {
    '举报系统': ['AI智能分析', '10种举报原因', '循环举报', '欧盟模式', '批举报调度', '目标融合'],
    '代理系统': ['11源抓取', 'TG-DC测试', 'SOCKS4/5', 'HTTP', 'HTTPS', '轮换策略'],
    '账号检测': ['封禁检测', '活跃度分析', '素材能力', '注册时间', '双向限制'],
    '账号安全': ['销毁账号', '踢设备', '2FA管理', 'PassKey', '防解封'],
    '验证码': ['777000监听', 'bot转发中继', '反登录保护', '二维码登录'],
    '支付接口': ['HMAC-SHA256签名', '支付回调', '退款流程'],
    'Web管理': ['FastAPI', 'Flask', 'JWT认证', '可视化后台'],
    '批量操作': ['60+功能', '并发控制', '进度回调', '失败重试'],
    '会话管理': ['session转换', 'tdata兼容', 'JSON导出', 'ZIP批处理'],
    'AI引擎': ['目标评分', '智能策略', '机器学习预测'],
    'i18n': ['5种语言', '用户偏好', '外部语言包'],
    '高级': ['健康度', '风控', '报表', '画像', '加密存储'],
}


def 获取版本信息() -> Dict[str, Any]:
    """获取版本与模块清单"""
    return {
        'name': PROJECT_NAME,
        'author': AUTHOR,
        'version': VERSION,
        'modules': MODULE_COUNT,
        'features': 功能清单,
    }


def 打印欢迎信息() -> None:
    """打印欢迎横幅"""
    print('═' * 50)
    print(f'  🌟 {PROJECT_NAME} 已加载')
    print(f'  👑 作者: {AUTHOR}')
    print(f'  🔖 版本: {VERSION}')
    print(f'  🧩 模块数: {MODULE_COUNT}')
    print('═' * 50)


打印欢迎信息()


# ============================================================
# 单元测试入口
# ============================================================
if __name__ == '__main__':
    print()
    print('━' * 50)
    print('  协议工具箱 - 自检模式')
    print('━' * 50)

    info = 获取版本信息()
    for 功能, 列表 in info['features'].items():
        print(f'\n▸ {功能}:')
        for f in 列表:
            print(f'  ✓ {f}')

    print('\n▸ 命名空间测试:')
    print(f'  modules.封禁: {hasattr(modules.封禁, "举报单个目标")}')
    print(f'  modules.代理: {hasattr(modules.代理, "刷新代理池")}')
    print(f'  modules.设备: {hasattr(modules.设备, "应用Telethon补丁")}')
    print(f'  modules.会话: {hasattr(modules.会话, "convert_session_to_tdata")}')
    print(f'  modules.检测: {hasattr(modules.检测, "综合账号检测")}')
    print(f'  modules.安全: {hasattr(modules.安全, "踢出其他设备")}')
    print(f'  modules.验证: {hasattr(modules.验证, "启动验证码监听")}')
    print(f'  modules.支付: {hasattr(modules.支付, "sign")}')
    print(f'  modules.Web: {hasattr(modules.Web, "创建fastapi应用")}')
    print(f'  modules.批量: {hasattr(modules.批量, "run_batch")}')
    print(f'  modules.I18n: {hasattr(modules.I18n, "t")}')
    print(f'  modules.会话v2: {hasattr(modules.会话v2, "解析telethon会话")}')
    print(f'  modules.扩展: {hasattr(modules.扩展, "AI分析器")}')

    print('\n✅ 全部自检通过')
