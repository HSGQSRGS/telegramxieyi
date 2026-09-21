"""代理抓取与测试 — 协议工具箱
作者: Lion

合并自封禁机器人 /bot/fetcher.py + /bot/tester.py
11 个源并发抓取 + 代理连通性测试
"""

import asyncio
import random
import re
import socket
import json
import time
from typing import Set, List, Dict, Optional, Callable

try:
    import aiohttp
    from bs4 import BeautifulSoup
    AIOHTTP_AVAILABLE = True
except Exception:
    AIOHTTP_AVAILABLE = False

try:
    import socks
    SOCKS_AVAILABLE = True
except Exception:
    SOCKS_AVAILABLE = False

from urllib.parse import urljoin

from 配置 import 日志


TIMEOUT = 10
MAX_CONCURRENT = 20

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]

IP_PORT_RE = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$')


def _random_headers(extra: dict = None) -> dict:
    h = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    if extra:
        h.update(extra)
    return h


def _extract_table_proxies(html: str) -> Set[str]:
    """从 HTML 表格抽取 IP:PORT"""
    found = set()
    if not AIOHTTP_AVAILABLE:
        return found
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2:
                for i in range(len(cells) - 1):
                    ip = cells[i].get_text(strip=True)
                    port = cells[i + 1].get_text(strip=True)
                    if IP_PORT_RE.match(f'{ip}:{port}'):
                        found.add(f'{ip}:{port}')
    except Exception:
        pass
    return found


# ── 11 个源 ──────────────────────────────────────────

async def _fetch_tomcat1235(session, raw: Set[str], progress=None):
    try:
        async with session.get('https://tomcat1235.nyc.mn/proxy_list',
                               headers=_random_headers(), timeout=TIMEOUT) as resp:
            if resp.status == 200:
                for p in _extract_table_proxies(await resp.text()):
                    raw.add(p)
    except Exception:
        pass


async def _fetch_ip3366(session, raw: Set[str], progress=None):
    cookies = {'HMACCOUNT': 'C9710B4AD1BF8729', 'http_waf_cookie': 'cached'}
    base = 'http://www.ip3366.net/'
    try:
        async with session.get(base, headers=_random_headers({'Referer': 'https://www.baidu.com/'}),
                               cookies=cookies, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return
            m = re.search(r'共\s*(\d+)\s*页', await resp.text())
            total = int(m.group(1)) if m else 20
    except Exception:
        return
    for page in range(1, total + 1):
        try:
            url = base if page == 1 else f'{base}?page={page}'
            async with session.get(url, headers=_random_headers(), cookies=cookies,
                                   timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    for p in _extract_table_proxies(await resp.text()):
                        raw.add(p)
        except Exception:
            continue
        await asyncio.sleep(0.1)


async def _fetch_kxdaili(session, raw: Set[str], progress=None):
    base = 'http://www.kxdaili.com/dailiip/2/'
    for page in range(1, 51):
        try:
            async with session.get(urljoin(base, f'{page}.html'),
                                   headers=_random_headers(), timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    if page > 3:
                        break
                    continue
                proxies = _extract_table_proxies(await resp.text())
                if not proxies:
                    break
                for p in proxies:
                    raw.add(p)
        except Exception:
            continue
        await asyncio.sleep(0.1)


async def _fetch_proxyfreeonly(session, raw: Set[str], progress=None):
    try:
        async with session.get(
            'https://proxyfreeonly.com/api/free-proxy-list?limit=10000&page=1&sortBy=lastChecked&sortType=desc',
            headers=_random_headers(), timeout=TIMEOUT
        ) as resp:
            if resp.status == 200:
                for item in await resp.json():
                    ip = item.get('ip', '')
                    port = item.get('port', '')
                    if ip and port and IP_PORT_RE.match(f'{ip}:{port}'):
                        raw.add(f'{ip}:{port}')
    except Exception:
        pass


async def _fetch_freevpnnode(session, raw: Set[str], progress=None):
    async def _one_page(p):
        try:
            async with session.get(
                f'https://cn.freevpnnode.com/free-proxy?page={p}',
                headers=_random_headers(), timeout=TIMEOUT
            ) as resp:
                if resp.status == 200:
                    for proxy in _extract_table_proxies(await resp.text()):
                        raw.add(proxy)
        except Exception:
            pass

    total = 632
    pages = list(range(1, total + 1))
    batch_size = MAX_CONCURRENT
    for batch_idx, batch in enumerate(
        (pages[i:i + batch_size] for i in range(0, len(pages), batch_size)), 1
    ):
        await asyncio.gather(*[_one_page(p) for p in batch])
        await asyncio.sleep(0.1)


async def _fetch_proxymist(session, raw: Set[str], progress=None):
    urls = [
        'https://proxymist.com/zh/protocols/http/',
        'https://proxymist.com/zh/protocols/socks4/',
        'https://proxymist.com/zh/protocols/socks5/',
        'https://proxymist.com/zh/anonymity/elite/',
        'https://proxymist.com/zh/anonymity/anonymous/',
    ]
    for url in urls:
        try:
            async with session.get(url, headers=_random_headers(), timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    for proxy in _extract_table_proxies(await resp.text()):
                        raw.add(proxy)
        except Exception:
            pass


async def _fetch_proxylister(session, raw: Set[str], progress=None):
    urls = [
        'https://proxylister.com/zh/protocols/http/',
        'https://proxylister.com/zh/protocols/socks4/',
        'https://proxylister.com/zh/protocols/socks5/',
        'https://proxylister.com/zh/anonymity/elite/',
        'https://proxylister.com/zh/anonymity/anonymous/',
    ]
    for url in urls:
        try:
            async with session.get(url, headers=_random_headers(), timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    for proxy in _extract_table_proxies(await resp.text()):
                        raw.add(proxy)
        except Exception:
            pass


async def _fetch_proxyscdn(session, raw: Set[str], progress=None):
    base = 'https://proxy.scdn.io/get_proxies.php'
    try:
        params = {'protocol': '', 'country': '', 'per_page': 100, 'page': 1}
        async with session.get(base, params=params, headers=_random_headers(),
                               timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return
            data = await resp.json()
            total = data.get('totalPages', 1)
            for p in _extract_table_proxies(data.get('table_html', '')):
                raw.add(p)
    except Exception:
        return
    for page in range(2, total + 1):
        try:
            params['page'] = page
            async with session.get(base, params=params, timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for p in _extract_table_proxies(data.get('table_html', '')):
                        raw.add(p)
        except Exception:
            continue
        await asyncio.sleep(0.05)


async def _fetch_omegaproxy(session, raw: Set[str], progress=None):
    url = 'https://www.omegaproxy.com/web_v1/free-proxy/list'
    try:
        params = {'language': 'zh-hans', 'page_size': 100, 'page': 1}
        async with session.get(url, params=params, headers=_random_headers(),
                               timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return
            data = await resp.json()
            if data.get('code') != 200:
                return
            total = data['data']['page_count']
    except Exception:
        return
    for page in range(1, total + 1):
        try:
            params['page'] = page
            async with session.get(url, params=params, timeout=TIMEOUT) as resp:
                d = await resp.json()
                if d.get('code') == 200:
                    for p in d['data']['list']:
                        raw.add(f"{p['ip']}:{p['port']}")
        except Exception:
            continue
        await asyncio.sleep(0.05)


async def _fetch_proxyshare(session, raw: Set[str], progress=None):
    url = 'https://www.proxyshare.com/web_v1/free-proxy/list'
    try:
        params = {'language': 'zh-hans', 'page_size': 100, 'page': 1}
        async with session.get(url, params=params, headers=_random_headers(),
                               timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return
            data = await resp.json()
            if data.get('code') != 200:
                return
            total = data['data']['page_count']
    except Exception:
        return
    for page in range(1, total + 1):
        try:
            params['page'] = page
            async with session.get(url, params=params, timeout=TIMEOUT) as resp:
                d = await resp.json()
                if d.get('code') == 200:
                    for p in d['data']['list']:
                        raw.add(f"{p['ip']}:{p['port']}")
        except Exception:
            continue
        await asyncio.sleep(0.05)


async def _fetch_jiliuip(session, raw: Set[str], progress=None):
    try:
        async with session.get('https://www.jiliuip.com/free/page-1',
                               headers=_random_headers(), timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return
            html = await resp.text()
            m = re.search(r"let totalCount = '(\d+)';", html)
            total = (int(m.group(1)) + 11) // 12 if m else 1
    except Exception:
        return
    for page in range(1, total + 1):
        try:
            async with session.get(f'https://www.jiliuip.com/free/page-{page}',
                                   headers=_random_headers(), timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    m = re.search(r'const fpsList = (\[.*?\]);', html, re.DOTALL)
                    if m:
                        for item in json.loads(m.group(1)):
                            ip, port = item.get('ip'), item.get('port')
                            if ip and port:
                                raw.add(f'{ip}:{port}')
        except Exception:
            pass
        await asyncio.sleep(0.1)


FETCHERS = [
    _fetch_tomcat1235,
    _fetch_ip3366,
    _fetch_kxdaili,
    _fetch_proxyfreeonly,
    _fetch_freevpnnode,
    _fetch_proxymist,
    _fetch_proxylister,
    _fetch_proxyscdn,
    _fetch_omegaproxy,
    _fetch_proxyshare,
    _fetch_jiliuip,
]

SOURCE_NAMES = [f.__name__.replace('_fetch_', '') for f in FETCHERS]


# ============================================================
# 主入口：抓取所有源
# ============================================================
async def 抓取全部代理(进度回调: Optional[Callable] = None) -> Set[str]:
    """从 11 个源并发抓取代理"""
    if not AIOHTTP_AVAILABLE:
        日志.warning('[fetcher] aiohttp 不可用，返回空集')
        return set()
    raw: Set[str] = set()

    def _make_progress(name: str):
        def _cb(*_):
            if 进度回调:
                try:
                    进度回调(name, len(raw))
                except Exception:
                    pass
        return _cb

    connector = aiohttp.TCPConnector(limit=50, limit_per_host=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [f(session, raw, _make_progress(n)) for f, n in zip(FETCHERS, SOURCE_NAMES)]
        await asyncio.gather(*tasks, return_exceptions=True)
    return raw


# ============================================================
# 连通性测试
# ============================================================
TG_DC_IPS = [
    '149.154.167.50',   # DC1
    '149.154.167.51',   # DC2
    '149.154.175.100',  # DC3
    '149.154.175.50',   # DC5
]
TG_PORT = 443
TEST_TIMEOUT = 8
MAX_CONCURRENT_TEST = 50


def _test_one_sync(host: str, port: int, target_ip: str, target_port: int) -> bool:
    """同步单代理测试（在线程池执行）"""
    if not SOCKS_AVAILABLE:
        return False
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, host, port)
        s.settimeout(TEST_TIMEOUT)
        s.connect((target_ip, target_port))
        s.close()
        return True
    except Exception:
        return False


async def 测试单代理(ip: str, port: int) -> bool:
    """测试一个 SOCKS5 代理能否到达任意 Telegram DC"""
    loop = asyncio.get_event_loop()
    for dc_ip in TG_DC_IPS:
        try:
            ok = await loop.run_in_executor(
                None, _test_one_sync, ip, port, dc_ip, TG_PORT
            )
            if ok:
                return True
        except Exception:
            continue
    return False


async def 过滤可用代理(raw_proxies: Set[str], 进度回调=None,
                     并发: int = MAX_CONCURRENT_TEST) -> List[Dict]:
    """测试所有代理，保留能到 Telegram 的"""
    proxy_list = []
    for entry in raw_proxies:
        parts = entry.split(':')
        if len(parts) == 2 and parts[1].isdigit():
            proxy_list.append((parts[0], int(parts[1])))

    if not proxy_list:
        return []

    total = len(proxy_list)
    working: List[Dict] = []
    semaphore = asyncio.Semaphore(并发)
    tested = [0]

    async def _test_one(ip, port):
        async with semaphore:
            ok = await 测试单代理(ip, port)
            tested[0] += 1
            if ok:
                working.append({'type': 'socks5', 'host': ip, 'port': port})
            if 进度回调:
                try:
                    await 进度回调(tested[0], total, len(working))
                except Exception:
                    pass

    tasks = [_test_one(ip, port) for ip, port in proxy_list]
    await asyncio.gather(*tasks, return_exceptions=True)
    return working


# ============================================================
# 一站式：刷新代理池
# ============================================================
async def 刷新代理池(进度回调=None) -> Dict:
    """抓取 + 测试 + 去重，返回可用代理列表"""
    if 进度回调:
        try:
            await 进度回调('fetch', 0)
        except Exception:
            pass
    raw = await 抓取全部代理()
    测试中 = [None]

    async def _cb(t, total, working):
        if 进度回调:
            try:
                await 进度回调('test', int(t * 100 / max(total, 1)), working)
            except Exception:
                pass

    working = await 过滤可用代理(raw, 进度回调=_cb)
    if 进度回调:
        try:
            await 进度回调('done', len(working))
        except Exception:
            pass
    return {'fetched': len(raw), 'working': working}


# ============================================================
# 保存到文件（兼容封禁机器人 all.txt 格式）
# ============================================================
def 保存到文本(代理列表: List[Dict], 文件路径: str = 'all.txt') -> str:
    """保存代理列表到文本文件"""
    import os
    try:
        with open(文件路径, 'w', encoding='utf-8') as f:
            f.write(f"# 代理IP池 | 生成: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 可用: {len(代理列表)}\n\n")
            for p in 代理列表:
                f.write(f"{p['host']}:{p['port']}\n")
        return os.path.abspath(文件路径)
    except Exception as e:
        日志.error(f"[fetcher] 保存失败: {e}")
        return ''


# 公开 API
公开API = [
    '抓取全部代理', '测试单代理', '过滤可用代理', '刷新代理池', '保存到文本',
    'SOURCE_NAMES',
]
