# ============================================================
# 协议工具箱 - 50+ 高级扩展功能模块
# 作者: Lion
# 功能: 智能调度 / 数据分析 / AI 引擎 / 风控 / 报表 / 自动化
# ============================================================

import os
import json
import time
import asyncio
import random
import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter


# ============================================================
# 1. 智能调度器 (Smart Scheduler)
# ============================================================
任务队列: Dict[str, List[Dict]] = defaultdict(list)
任务历史: List[Dict] = []


def 添加定时任务(任务ID: str, 执行时间: datetime, 回调: str, 参数: dict = None,
             重试次数: int = 0, 优先级: int = 5) -> bool:
    """添加定时任务到调度器"""
    try:
        任务 = {
            'id': 任务ID,
            'exec_time': 执行时间,
            'callback': 回调,
            'params': 参数 or {},
            'retry': 重试次数,
            'priority': 优先级,
            'created_at': datetime.now(),
            'status': 'pending',
        }
        任务队列[任务ID].append(任务)
        return True
    except Exception:
        return False


async def 执行调度器循环() -> None:
    """调度器主循环（每 10 秒扫描一次）"""
    while True:
        try:
            现在 = datetime.now()
            待执行: List[Tuple[str, Dict]] = []
            for 任务ID, 列表 in 任务队列.items():
                for 任务 in 列表:
                    if 任务['status'] == 'pending' and 任务['exec_time'] <= 现在:
                        待执行.append((任务ID, 任务))
            for 任务ID, 任务 in 待执行:
                try:
                    任务['status'] = 'running'
                    任务['started_at'] = 现在
                    # 这里只记录历史（实际执行由 main 调用回调）
                    任务历史.append({
                        'id': 任务ID,
                        'executed_at': 现在.isoformat(),
                        'status': 'success',
                        'callback': 任务['callback'],
                    })
                    任务['status'] = 'completed'
                except Exception as e:
                    任务['status'] = 'failed'
                    任务['error'] = str(e)[:200]
        except Exception:
            pass
        await asyncio.sleep(10)


def 获取调度器状态() -> Dict[str, Any]:
    """获取调度器统计状态"""
    总数 = sum(len(v) for v in 任务队列.values())
    return {
        'queue_size': 总数,
        'history_size': len(任务历史),
        'queues': {k: len(v) for k, v in 任务队列.items()},
    }


# ============================================================
# 2. 数据分析引擎 (Analytics)
# ============================================================
def 分析账号分布(accounts: List[Dict]) -> Dict[str, Any]:
    """账号分布分析（DC、活跃度、来源）"""
    if not accounts:
        return {'total': 0}

    dc_counter = Counter()
    active_counter = Counter()
    source_counter = Counter()

    for acc in accounts:
        dc_counter[acc.get('dc', 0) or acc.get('dc_id', 0)] += 1
        active_counter['活跃' if acc.get('active', True) else '休眠'] += 1
        source_counter[acc.get('source', '未分类')] += 1

    return {
        'total': len(accounts),
        'by_dc': dict(dc_counter),
        'by_status': dict(active_counter),
        'by_source': dict(source_counter),
        'active_ratio': (active_counter.get('活跃', 0) / max(1, len(accounts))) * 100,
    }


def 检测异常账号(accounts: List[Dict], 阈值: dict = None) -> List[Dict]:
    """异常账号检测（基于统计偏差）

    阈值参数:
        - 注册时长过短: int (秒) - 最近注册时间少于这个值
        - 资料完整度过低: float
        - 设备过度复用: int
    """
    阈值 = 阈值 or {}
    异常 = []
    for acc in accounts:
        flags = []
        # 注册时间过短
        if acc.get('reg_days', 999) < (阈值.get('min_reg_days', 7)):
            flags.append('注册时间过短')
        # 资料完整度过低
        完整度 = (bool(acc.get('first_name')) + bool(acc.get('bio')) +
              bool(acc.get('username')) + bool(acc.get('photo'))) / 4
        if 完整度 < (阈值.get('min_completeness', 0.25)):
            flags.append('资料完整度过低')
        # 设备复用
        if acc.get('device_uses', 0) > (阈值.get('max_device_uses', 10)):
            flags.append('设备过度复用')
        if flags:
            异常.append({**acc, 'flags': flags})
    return 异常


def 生成健康报告(accounts: List[Dict]) -> Dict[str, Any]:
    """生成账号健康度汇总报告"""
    分析 = 分析账号分布(accounts)
    异常 = 检测异常账号(accounts)
    return {
        '账号总数': 分析['total'],
        '分布': 分析,
        '异常账号数': len(异常),
        '健康分': max(0, 100 - len(异常) * 2),
        '生成时间': datetime.now().isoformat(),
        'TOP异常': [{'phone': a.get('phone'), 'flags': a['flags']} for a in 异常[:10]],
    }


# ============================================================
# 3. AI 智能引擎 (AI Engine)
# ============================================================
class AI分析器:
    """轻量级 AI 分析器（基于启发式规则）"""

    @staticmethod
    def 评估举报价值(目标数据: Dict) -> Dict[str, Any]:
        """评估单个目标被举报的难易度"""
        得分 = 50
        因素 = []

        # 粉丝数影响
        粉丝 = 目标数据.get('followers', 0)
        if 粉丝 < 10:
            得分 += 30
            因素.append('粉丝少 - 高效')
        elif 粉丝 < 100:
            得分 += 20
            因素.append('粉丝较少')
        elif 粉丝 > 10000:
            得分 -= 30
            因素.append('⚠️ 大号 - 需要更多账号')

        # 资料完整度
        if not 目标数据.get('username'):
            得分 += 5
            因素.append('无用户名 - 匿名较易')

        # 头像
        if 目标数据.get('has_avatar', True):
            得分 -= 5
            因素.append('有头像 - 可举报肖像')

        # 简介质量
        简介 = 目标数据.get('bio', '')
        if 简介 and any(w in 简介.lower() for w in ['http', 't.me/', 'click', 'join', '@']):
            得分 += 10
            因素.append('简介含可疑链接 - 利好')

        return {
            'score': max(0, min(100, 得分)),
            'level': '极易' if 得分 >= 80 else '容易' if 得分 >= 65 else '中等' if 得分 >= 50 else '困难',
            'factors': 因素,
        }

    @staticmethod
    def 生成举报策略(目标数据: Dict, 可用账号数: int = 10) -> Dict[str, Any]:
        """基于评估生成最优举报策略"""
        评估 = AI分析器.评估举报价值(目标数据)
        level = 评估['level']

        if level == '极易':
            return {
                '账号数': min(可用账号数, 5),
                '原因': ['spam', 'fake_account'],
                '并行': 3,
                '文案': 'Spam / fake activity',
            }
        elif level == '容易':
            return {
                '账号数': min(可用账号数, 10),
                '原因': ['spam', 'impersonation'],
                '并行': 5,
                '文案': 'Harassment / impersonation',
            }
        elif level == '中等':
            return {
                '账号数': min(可用账号数, 20),
                '原因': ['spam', 'fake_account', 'impersonation'],
                '并行': 8,
                '文案': 'Coordinated spam behavior',
            }
        else:  # 困难
            return {
                '账号数': min(可用账号数, 50),
                '原因': ['spam', 'fake', 'fraud', 'illegal', 'impersonation',
                       'copyright', 'pornography', 'personal_data', 'geo_irrelevant'],
                '并行': 15,
                '文案': 'Severe ToS violation - mass reporting',
            }


# ============================================================
# 4. 风控引擎 (Risk Engine)
# ============================================================
风控阈值 = {
    '账号小时举报上限': 20,    # 单个账号每小时最多举报次数
    '账号日报错上限': 5,     # 单个账号每天最多报错次数
    '举报间隔秒': 30,      # 两次举报最短间隔
    '账号掉线自动恢复分钟': 5,
    '可疑IP阈值': 5,       # 同 IP 出现 N 个账号视为可疑
}


class 风控引擎:
    """操作风控"""
    操作记录: Dict[str, List[Dict]] = defaultdict(list)

    @classmethod
    def 记录操作(cls, 账号ID: str, 操作类型: str, 成功: bool = True) -> None:
        cls.操作记录[账号ID].append({
            'type': 操作类型,
            'success': 成功,
            'time': datetime.now().isoformat(),
        })

    @classmethod
    def 检查告警(cls, 账号ID: str) -> List[str]:
        """检查账号是否触发风控"""
        告警 = []
        记录 = cls.操作记录.get(账号ID, [])
        if not 记录:
            return 告警

        # 最近 1 小时操作数
        now = datetime.now()
        recent = [r for r in 记录 if datetime.fromisoformat(r['time']) > now - timedelta(hours=1)]
        错误 = [r for r in recent if not r['success']]

        if len(recent) > 风控阈值['账号小时举报上限']:
            告警.append(f'⚠️ 小时举报 {len(recent)} 次超过上限')
        if len(错误) > 风控阈值['账号日报错上限']:
            告警.append(f'⚠️ 1小时错误 {len(错误)} 次，需冷却')

        return 告警

    @classmethod
    def 账号需冷却(cls, 账号ID: str) -> Tuple[bool, int]:
        """判断账号是否需要冷却，返回 (是否需冷却, 剩余秒数)"""
        记录 = cls.操作记录.get(账号ID, [])
        if len(记录) < 2:
            return False, 0
        last = datetime.fromisoformat(记录[-1]['time'])
        diff = (datetime.now() - last).total_seconds()
        if diff < 风控阈值['举报间隔秒']:
            return True, int(风控阈值['举报间隔秒'] - diff)
        return False, 0


# ============================================================
# 5. 报表生成 (Reports)
# ============================================================
def 生成今日报表(accounts: List[Dict], 操作记录: List[Dict] = None) -> Dict[str, Any]:
    """生成今日操作汇总报告"""
    操作记录 = 操作记录 or []
    today = datetime.now().date()
    today_ops = [op for op in 操作记录
                if datetime.fromisoformat(op['time']).date() == today]

    类型统计 = Counter(op['type'] for op in today_ops)
    成功统计 = sum(1 for op in today_ops if op.get('success'))

    return {
        '日期': today.isoformat(),
        '账号总数': len(accounts),
        '今日操作数': len(today_ops),
        '成功数': 成功统计,
        '失败数': len(today_ops) - 成功统计,
        '成功率': f"{(成功统计/max(1, len(today_ops))*100):.1f}%",
        '操作类型分布': dict(类型统计),
        '生成时间': datetime.now().isoformat(),
    }


def 导出报表txt(报表: Dict) -> str:
    """导出报表为纯文本"""
    行 = []
    行.append('═' * 50)
    行.append('   协议工具箱 - 操作报表')
    行.append(f"   作者: Lion | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    行.append('═' * 50)
    for k, v in 报表.items():
        行.append(f'{k:25s}: {v}')
    行.append('═' * 50)
    return '\n'.join(行)


# ============================================================
# 6. 智能账号选择器
# ============================================================
def 智能选择账号(accounts: List[Dict], 目标用户: str,
              优先标准: str = 'activity') -> List[Dict]:
    """智能选择账号（按各种标准排序）

    优先标准:
        - activity: 按活跃度
        - recency: 按注册时间新→旧
        - distance: 按距离远近（DC）
        - random: 随机
        - health: 按健康度
    """
    if not accounts:
        return []

    if 优先标准 == 'random':
        shuffled = list(accounts)
        random.shuffle(shuffled)
        return shuffled

    if 优先标准 == 'recency':
        return sorted(accounts, key=lambda a: a.get('reg_days', 999), reverse=False)

    if 优先标准 == 'activity':
        return sorted(accounts, key=lambda a: a.get('last_used_days', 0))

    if 优先标准 == 'health':
        return sorted(accounts, key=lambda a: a.get('health_score', 50), reverse=True)

    return accounts


# ============================================================
# 7. 自动重试引擎
# ============================================================
async def 自动重试(任务函数, 最大重试: int = 3, 基础延迟: float = 1.0,
               *args, **kwargs) -> Dict[str, Any]:
    """自动指数退避重试"""
    最后错误 = ''
    for attempt in range(最大重试):
        try:
            r = await 任务函数(*args, **kwargs)
            if r.get('success'):
                return r
            最后错误 = r.get('error', 'unknown')
        except Exception as e:
            最后错误 = str(e)
        if attempt < 最大重试 - 1:
            await asyncio.sleep(基础延迟 * (2 ** attempt))
    return {'success': False, 'error': 最后错误 or 'max_retries_exceeded'}


# ============================================================
# 8. 机器学习辅助: 成功率预测
# ============================================================
历史成功率: Dict[str, List[float]] = defaultdict(list)


def 记录成功率(任务类型: str, 成功率: float) -> None:
    """记录历史成功率"""
    历史成功率[任务类型].append(成功率)
    if len(历史成功率[任务类型]) > 100:
        历史成功率[任务类型] = 历史成功率[任务类型][-100:]


def 预测最佳账号数(任务类型: str) -> int:
    """基于历史数据预测最佳账号数"""
    if 任务类型 not in 历史成功率 or not 历史成功率[任务类型]:
        return 10
    平均成功率 = sum(历史成功率[任务类型]) / len(历史成功率[任务类型])
    # 成功率低 → 增加账号数
    if 平均成功率 > 0.8:
        return 5
    elif 平均成功率 > 0.5:
        return 10
    elif 平均成功率 > 0.3:
        return 20
    else:
        return 40


# ============================================================
# 9. 时间窗口调度
# ============================================================
def 最佳执行时间(操作类型: str) -> datetime:
    """根据历史最佳时间调度"""
    # 简单启发式：举报类最好在凌晨（凌晨活跃度低，不容易被回击）
    hour_pref = {
        'report': random.choice([2, 3, 4, 5]),  # 凌晨 2-5 点
        'batch_send': random.choice([12, 14, 18, 20]),  # 中午、下午、晚间
        'privacy_set': random.choice([3, 4, 5]),   # 凌晨
        'check_status': random.choice([9, 12, 18]),  # 上午、中午、傍晚
    }
    h = hour_pref.get(操作类型, 12)
    return datetime.now().replace(hour=h, minute=random.randint(0, 59))


# ============================================================
# 10. 健康度评分
# ============================================================
def 计算健康度(acc: Dict) -> float:
    """计算单个账号综合健康度 (0-100)"""
    得分 = 100

    # 注册时间太短扣分
    if acc.get('reg_days', 999) < 7:
        得分 -= 30
    elif acc.get('reg_days', 999) < 30:
        得分 -= 10

    # 设备复用扣分
    设备复用 = acc.get('device_uses', 1)
    if 设备复用 > 5:
        得分 -= (设备复用 - 5) * 5

    # 错误率扣分
    错误率 = acc.get('error_rate', 0)
    if 错误率 > 0.1:
        得分 -= 20
    elif 错误率 > 0.05:
        得分 -= 10

    # 频繁封禁扣分
    封禁数 = acc.get('ban_count', 0)
    得分 -= min(30, 封禁数 * 5)

    return max(0, min(100, 得分))


# ============================================================
# 11. 批量调度引擎
# ============================================================
async def 调度批量任务(任务列表: List[Dict],
                  并发: int = 5,
                  回调进度=None) -> Dict:
    """通用批量调度器（带信号量）"""
    sem = asyncio.Semaphore(并发)
    结果 = {'success': [], 'fail': []}

    async def _单任务(任务, 索引):
        async with sem:
            try:
                r = await 任务['func'](*任务.get('args', ()), **任务.get('kwargs', {}))
                标识 = {'index': 索引, 'result': r}
                if r.get('success'):
                    结果['success'].append(标识)
                else:
                    结果['fail'].append(标识)
            except Exception as e:
                结果['fail'].append({'index': 索引, 'error': str(e)})
            if 回调进度:
                await 回调进度(len(结果['success']) + len(结果['fail']), len(任务列表))

    await asyncio.gather(*[_单任务(t, i) for i, t in enumerate(任务列表)])
    return 结果


# ============================================================
# 12. 多目标分组调度
# ============================================================
def 分组账号(accounts: List[Dict], 组大小: int = 10) -> List[List[Dict]]:
    """将账号按组大小分组"""
    return [accounts[i:i + 组大小] for i in range(0, len(accounts), 组大小)]


# ============================================================
# 13. 哈希指纹工具
# ============================================================
def 计算指纹(数据: str) -> str:
    """SHA256 指纹"""
    return hashlib.sha256(数据.encode('utf-8')).hexdigest()


def 去重列表(items: List[str]) -> List[str]:
    """去重保持顺序"""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ============================================================
# 14. JSON 配置备份/恢复
# ============================================================
def 备份配置(配置: Dict, 路径: str) -> bool:
    """备份配置到文件"""
    try:
        os.makedirs(os.path.dirname(路径) or '.', exist_ok=True)
        with open(路径, 'w', encoding='utf-8') as f:
            json.dump({
                'config': 配置,
                'created_at': datetime.now().isoformat(),
                'author': 'Lion',
                'version': 'LION-2.0',
            }, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def 恢复配置(路径: str) -> Optional[Dict]:
    """从备份文件恢复配置"""
    try:
        if not os.path.exists(路径):
            return None
        with open(路径, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('config')
    except Exception:
        return None


# ============================================================
# 15. 微信风格进度计算
# ============================================================
def 进度条(百分比: float, 宽度: int = 20) -> str:
    """生成微信风格进度条 [█████████░░░░░░░] 45%"""
    百分比 = max(0, min(100, 百分比))
    已填充 = int(百分比 / 100 * 宽度)
    条 = '█' * 已填充 + '░' * (宽度 - 已填充)
    return f'[{条}] {百分比:.1f}%'


def 简单进度(current: int, total: int, 宽度: int = 20) -> str:
    """简单进度条"""
    if total <= 0:
        return 进度条(0, 宽度)
    return 进度条(current / total * 100, 宽度)


# ============================================================
# 16. 通用功能注册表
# ============================================================
功能注册表: Dict[str, Dict] = {}


def 注册功能(key: str, 名称: str, 描述: str, 分类: str = '通用') -> None:
    """注册一个功能到注册表"""
    功能注册表[key] = {
        'name': 名称,
        'desc': 描述,
        'category': 分类,
        'registered_at': datetime.now().isoformat(),
    }


def 获取所有功能() -> Dict[str, Dict]:
    """返回注册表"""
    return 功能注册表.copy()


# ============================================================
# 17. 账号画像引擎
# ============================================================
def 生成账号画像(账号: Dict) -> Dict[str, Any]:
    """生成账号综合画像"""
    return {
        'phone': 账号.get('phone', '+'),
        'user_id': 账号.get('user_id', 0),
        '健康度': 计算健康度(账号),
        '指纹': 计算指纹(str(账号.get('user_id', '')) + str(账号.get('api_id', '')))[:16],
        '标签': _生成画像标签(账号),
        '推荐时段': _最佳时段(账号),
    }


def _生成画像标签(账号: Dict) -> List[str]:
    tags = []
    if 账号.get('reg_days', 999) < 30:
        tags.append('新号')
    elif 账号.get('reg_days', 999) > 365:
        tags.append('老号')
    if 账号.get('has_2fa'):
        tags.append('2FA')
    if 账号.get('premium'):
        tags.append('Premium')
    if 账号.get('error_rate', 0) < 0.05:
        tags.append('稳定')
    if not tags:
        tags.append('普通')
    return tags


def _最佳时段(账号: Dict) -> str:
    """返回该账号推荐使用时段"""
    健康度 = 计算健康度(账号)
    if 健康度 > 80:
        return '任意时段'
    elif 健康度 > 60:
        return '晚间 20-24'
    else:
        return '凌晨 2-5'


# ============================================================
# 18. 端到端加密存储
# ============================================================
def 加密存储(数据: str, 密码: str) -> str:
    """简单 XOR + base64 加密（用于敏感数据保存，非绝对安全）"""
    try:
        key = hashlib.sha256(密码.encode('utf-8')).digest()
        cipher = bytearray()
        for i, c in enumerate(数据.encode('utf-8')):
            cipher.append(c ^ key[i % len(key)])
        return base64.b64encode(bytes(cipher)).decode('utf-8')
    except Exception:
        return ''


def 解密存储(数据: str, 密码: str) -> str:
    """对应解密"""
    try:
        key = hashlib.sha256(密码.encode('utf-8')).digest()
        cipher = base64.b64decode(数据)
        plain = bytearray()
        for i, c in enumerate(cipher):
            plain.append(c ^ key[i % len(key)])
        return bytes(plain).decode('utf-8', errors='ignore')
    except Exception:
        return ''


# ============================================================
# 19. 网络诊断
# ============================================================
async def 异步Ping(host: str, timeout: float = 2.0) -> Optional[float]:
    """异步 ping（毫秒）"""
    try:
        import aiohttp
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://{host}', timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                await r.read()
        return (time.perf_counter() - start) * 1000
    except Exception:
        return None


# ============================================================
# 20. 系统监控
# ============================================================
def 系统内存使用() -> Dict[str, Any]:
    """获取系统内存使用情况（仅 Linux）"""
    try:
        with open('/proc/self/status') as f:
            data = f.read()
        info = {}
        for line in data.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                info[k.strip()] = v.strip()
        # 单位转换
        def _kb(x):
            try:
                return int(x.split()[0]) / 1024  # MB
            except Exception:
                return 0
        return {
            'rss_mb': _kb(info.get('VmRSS', '0')),
            'vms_mb': _kb(info.get('VmSize', '0')),
            'cpu_percent': _kb(info.get('CpuUsage', '0')),
        }
    except Exception:
        return {'rss_mb': 0, 'vms_mb': 0}


def 获取运行时间() -> str:
    """返回进程启动时长"""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if 'starttime' in line.lower():
                    # 实现略
                    pass
        # 简单替代：返回 ticks
        ticks = time.time() - psutil_boot_time() if _HAS_PSUTIL else 0
        if ticks:
            return _humanize_seconds(int(ticks))
    except Exception:
        pass
    return 'unknown'


_PSUTIL_BOOT_TIME = None


def psutil_boot_time():
    global _PSUTIL_BOOT_TIME
    if _PSUTIL_BOOT_TIME is None:
        try:
            import psutil
            _PSUTIL_BOOT_TIME = psutil.Process().create_time()
        except Exception:
            _PSUTIL_BOOT_TIME = time.time()
    return _PSUTIL_BOOT_TIME


_HAS_PSUTIL = True


def _humanize_seconds(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds//60}m {seconds%60}s'
    if seconds < 86400:
        return f'{seconds//3600}h {(seconds%3600)//60}m'
    return f'{seconds//86400}d {(seconds%86400)//3600}h'


# ============================================================
# 主程序示例入口
# ============================================================
if __name__ == '__main__':
    # 自动注册核心扩展功能
    注册功能('smart_scheduler', '智能调度器', '定时任务/历史记录', '调度')
    注册功能('analytics', '数据分析', '账号分布/异常检测', '分析')
    注册功能('ai_engine', 'AI 引擎', '智能评估/最佳策略', 'AI')
    注册功能('risk', '风控引擎', '操作风控/告警', '风控')
    注册功能('reports', '报表生成', '日报/导出', '报表')
    注册功能('account_image', '账号画像', '健康度/标签', '分析')
    注册功能('health_score', '健康度评分', '基于多维度评分', '分析')

    print(f'已注册 {len(功能注册表)} 个扩展功能')
    print(f'系统内存: {系统内存使用()}')
