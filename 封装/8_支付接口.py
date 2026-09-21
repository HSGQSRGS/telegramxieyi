"""支付接口 — 协议工具箱
作者: Lion

合并自 GAFBot /pay.py + /okpay_sign.py
支持 HMAC-SHA256 签名 + 验证
"""

import hashlib
import hmac
import secrets
import time
import uuid
from typing import Dict, Optional
from urllib.parse import urlencode

from 配置 import 日志


# ============================================================
# 签名工具（合并自 okpay_sign.py）
# ============================================================
def _flatten(data: dict, prefix: str = '') -> Dict[str, str]:
    """递归扁平化嵌套字典为 {key.str: value}"""
    result = {}
    for k, v in data.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    result.update(_flatten(item, f'{key}.{i}'))
                else:
                    result[f'{key}.{i}'] = str(item)
        else:
            result[key] = str(v)
    return result


def build_base(params: dict) -> str:
    """生成签名底串（按 key 排序）"""
    flat = _flatten(params)
    pairs = sorted(flat.items())
    return '&'.join(f'{k}={v}' for k, v in pairs if v not in ('', None))


def sign(params: dict, token: str) -> str:
    """HMAC-SHA256 签名"""
    base = build_base(params)
    return hmac.new(
        token.encode('utf-8'),
        base.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest().upper()


def signed_request(params: dict, shop_id: str, token: str,
                   endpoint: Optional[str] = None) -> Dict:
    """自动添加 id / timestamp / nonce / sign"""
    payload = dict(params)
    payload['id'] = payload.get('id') or uuid.uuid4().hex[:24]
    payload['shop_id'] = shop_id
    payload['timestamp'] = payload.get('timestamp') or str(int(time.time()))
    payload['nonce'] = payload.get('nonce') or secrets.token_hex(8)
    payload['sign'] = sign(payload, token)
    if endpoint:
        payload['endpoint'] = endpoint
    return payload


def verify(payload: dict, token: str) -> bool:
    """验证 payload 中的 sign"""
    try:
        given = payload.pop('sign', None) if 'sign' in payload else None
        if not given:
            return False
        expected = sign(payload, token)
        return hmac.compare_digest(given.upper(), expected.upper())
    except Exception:
        return False


# ============================================================
# 内置支付封装
# ============================================================
class 支付客户端:
    """统一的支付 API 客户端"""

    def __init__(self, shop_id: str, token: str, base_url: str = 'https://pay.example.com'):
        self.shop_id = shop_id
        self.token = token
        self.base_url = base_url.rstrip('/')

    def _call(self, action: str, payload: dict, timeout: int = 15) -> Dict:
        """同步 POST（不阻塞）"""
        import requests
        signed = signed_request({**payload, 'action': action}, self.shop_id, self.token)
        try:
            r = requests.post(f'{self.base_url}/api', json=signed, timeout=timeout)
            return r.json()
        except Exception as e:
            return {'error': str(e)[:100]}

    def 创建订单(self, 金额: float, 商品名: str, 买家id: str,
              回调url: Optional[str] = None) -> Dict:
        return self._call('create_order', {
            'amount': 金额,
            'subject': 商品名,
            'buyer_id': 买家id,
            'notify_url': 回调url or '',
        })

    def 查询订单(self, 订单id: str) -> Dict:
        return self._call('query_order', {'order_id': 订单id})

    def 退款(self, 订单id: str, 金额: Optional[float] = None,
           原因: str = '') -> Dict:
        return self._call('refund', {
            'order_id': 订单id,
            'amount': 金额 or 0,
            'reason': 原因,
        })


# ============================================================
# 异步版本
# ============================================================
class 异步支付客户端:
    """支付 API 异步客户端"""

    def __init__(self, shop_id: str, token: str, base_url: str = 'https://pay.example.com'):
        self.shop_id = shop_id
        self.token = token
        self.base_url = base_url.rstrip('/')

    async def _call(self, action: str, payload: dict, timeout: int = 15) -> Dict:
        """异步 POST"""
        try:
            import aiohttp
        except ImportError:
            return {'error': 'aiohttp 未安装'}
        signed = signed_request({**payload, 'action': action}, self.shop_id, self.token)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/api',
                    json=signed,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as r:
                    return await r.json()
        except Exception as e:
            return {'error': str(e)[:100]}

    async def 创建订单(self, 金额: float, 商品名: str, 买家id: str,
                   回调url: Optional[str] = None) -> Dict:
        return await self._call('create_order', {
            'amount': 金额,
            'subject': 商品名,
            'buyer_id': 买家id,
            'notify_url': 回调url or '',
        })

    async def 查询订单(self, 订单id: str) -> Dict:
        return await self._call('query_order', {'order_id': 订单id})


# 公开 API
公开API = [
    'sign', 'verify', 'build_base', 'signed_request',
    '支付客户端', '异步支付客户端',
]
