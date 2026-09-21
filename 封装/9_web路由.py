"""Web 路由 — 协议工具箱
作者: Lion

合并自 GAFBot /luyou.py
基于 Flask 的 Web 路由，可作为验证码/API 接收端
"""

import os
import json
from typing import Optional

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False

try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False

from 配置 import 日志, 默认端口


# ============================================================
# 配置
# ============================================================
def 获取_web_配置():
    return {
        'server_ip': os.environ.get('SERVER_IP', '127.0.0.1'),
        'api_port': int(os.environ.get('API_PORT', 默认端口 + 5)),
        'dm': os.environ.get('DM', ''),
    }


# ============================================================
# Flask 版本
# ============================================================
_验证码缓存 = {}
_API缓存 = {}


def 创建flask应用():
    """创建 Flask Web 路由（接收验证码 + API 中转）"""
    if not FLASK_AVAILABLE:
        raise RuntimeError("Flask 未安装")

    app = Flask(__name__)

    @app.route('/')
    def index():
        cfg = 获取_web_配置()
        return (
            f"<h1>协议工具箱 Web API</h1>"
            f"<p>服务器: {cfg['server_ip']}:{cfg['api_port']}</p>"
            f"<p>作者: Lion</p>"
            f"<ul>"
            f"<li>POST /getcode?id=&lt;id&gt; - 获取验证码</li>"
            f"<li>POST /push - 推送通知</li>"
            f"<li>GET /health - 健康检查</li>"
            f"</ul>"
        )

    @app.route('/getcode', methods=['GET', 'POST'])
    def get_code():
        """获取指定 id 的最新验证码"""
        code_id = (request.args.get('id') or
                   (request.json or {}).get('id') or '')
        if not code_id:
            return jsonify({'error': 'missing id'}), 400
        code = _验证码缓存.get(code_id)
        if not code:
            return jsonify({'error': 'no code yet'}), 404
        return jsonify({'id': code_id, 'code': code})

    @app.route('/push', methods=['POST'])
    def push():
        """推送验证码（内部接口）"""
        data = request.json or {}
        code_id = data.get('id', '')
        code = data.get('code', '')
        if not code_id or not code:
            return jsonify({'error': 'missing fields'}), 400
        _验证码缓存[code_id] = code
        日志.info(f"[push] 收到验证码 {code_id} -> {code}")
        return jsonify({'ok': True})

    @app.route('/health')
    def health():
        return jsonify({'ok': True, 'author': 'Lion'})

    @app.route('/codes', methods=['GET'])
    def list_codes():
        """列出所有已存验证码（管理用）"""
        return jsonify(_验证码缓存)

    return app


def 启动flask(host: str = '0.0.0.0', port: Optional[int] = None):
    """启动 Flask（阻塞式）"""
    cfg = 获取_web_配置()
    port = port or cfg['api_port']
    app = 创建flask应用()
    日志.info(f"[web] Flask 启动 {host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


# ============================================================
# FastAPI 版本（异步）
# ============================================================
def 创建fastapi应用():
    """创建 FastAPI Web 路由"""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI 未安装")

    app = FastAPI(title="协议工具箱 API", version="LION-1.0")

    @app.get('/')
    async def index():
        cfg = 获取_web_配置()
        return {
            'name': '协议工具箱 Web API',
            'author': 'Lion',
            'server': f"{cfg['server_ip']}:{cfg['api_port']}",
            'endpoints': ['/getcode', '/push', '/codes', '/health'],
        }

    @app.get('/getcode')
    async def get_code(id: str = ''):
        if not id:
            raise HTTPException(400, 'missing id')
        code = _验证码缓存.get(id)
        if not code:
            raise HTTPException(404, 'no code yet')
        return {'id': id, 'code': code}

    @app.post('/push')
    async def push(request: Request):
        data = await request.json()
        code_id = data.get('id', '')
        code = data.get('code', '')
        if not code_id or not code:
            raise HTTPException(400, 'missing fields')
        _验证码缓存[code_id] = code
        return {'ok': True}

    @app.get('/codes')
    async def list_codes():
        return _验证码缓存

    @app.get('/health')
    async def health():
        return {'ok': True, 'author': 'Lion'}

    return app


def 启动fastapi(host: str = '0.0.0.0', port: Optional[int] = None):
    """启动 FastAPI（阻塞式）"""
    cfg = 获取_web_配置()
    port = port or cfg['api_port']
    try:
        import uvicorn
    except ImportError:
        raise RuntimeError("uvicorn 未安装")
    app = 创建fastapi应用()
    日志.info(f"[web] FastAPI 启动 {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level='info')


def 自动启动():
    """根据可用框架自动选择"""
    if FASTAPI_AVAILABLE:
        return 启动fastapi
    if FLASK_AVAILABLE:
        return 启动flask
    return None


# 公开 API
公开API = [
    '创建flask应用', '启动flask', '创建fastapi应用', '启动fastapi', '自动启动',
    '获取_web_配置',
]
