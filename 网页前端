"""Web 管理后台 - 协议工具箱
作者: Lion
FastAPI + JWT 鉴权，提供账号 / 守护 / 监听 / 举报 / 代理 / 设置 全模块只读视图与基础管理
"""
import sys
import time
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Form, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
import uvicorn

# 加入项目根目录
根 = Path(__file__).parent.parent
sys.path.insert(0, str(根))

import 数据库 as db
import 配置
from 配置 import (
    后台地址, 后台端口, 后台用户名, 后台密码, 后台密钥,
    项目名称, 作者名称,
)

logger = logging.getLogger("Web后台")

静态目录 = Path(__file__).parent / "网页前端" / "静态资源"
模板目录 = Path(__file__).parent / "网页前端"
静态目录.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=f"{项目名称} · 管理后台", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(静态目录)), name="static")

SECRET_KEY = 后台密钥
ALGO = "HS256"
TOKEN_NAME = "adm_token"


def 简单哈希(原文: str) -> str:
    """SHA256 加盐哈希"""
    import hashlib
    盐 = "协议工具箱-Lion"
    return hashlib.sha256(f"{盐}-{原文}".encode()).hexdigest()


def 校验密码(原文: str) -> bool:
    """校验后台密码"""
    return 简单哈希(原文) == 简单哈希(后台密码)


def 创建JWT(payload: dict, 过期秒: int = 86400 * 7) -> str:
    p = payload.copy()
    p["exp"] = time.time() + 过期秒
    return jwt.encode(p, SECRET_KEY, algorithm=ALGO)


def 解析JWT(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None


async def 当前用户(request: Request, 令牌: Optional[str] = Cookie(None)) -> dict:
    if not 令牌:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            令牌 = auth[7:]
    if not 令牌:
        raise HTTPException(status_code=401, detail="未登录")
    p = 解析JWT(令牌)
    if not p:
        raise HTTPException(status_code=401, detail="令牌无效")
    return p


# ===================== 页面 =====================
@app.get("/", response_class=HTMLResponse)
async def 首页(请求: Request):
    return RedirectResponse("/登录" if not 请求.cookies.get(TOKEN_NAME) else "/控制台")


@app.get("/登录", response_class=HTMLResponse)
async def 登录页(请求: Request):
    html = (模板目录 / "登录.html").read_text(encoding="utf-8")
    html = html.replace("{{ 标题 }}", f"{项目名称} · 登录")
    html = html.replace("{{ 项目名 }}", 项目名称)
    return HTMLResponse(html)


@app.post("/登录")
async def 提交登录(用户: str = Form(...), 密码: str = Form(...)):
    if 用户 != 后台用户名 or not 校验密码(密码):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = 创建JWT({"sub": 用户, "role": "admin"})
    resp = JSONResponse({"ok": True})
    resp.set_cookie(TOKEN_NAME, token, max_age=86400 * 7, httponly=True)
    return resp


@app.get("/登出")
async def 登出():
    resp = RedirectResponse("/登录")
    resp.delete_cookie(TOKEN_NAME)
    return resp


@app.get("/控制台", response_class=HTMLResponse)
async def 控制台页(请求: Request, 用户: dict = Depends(当前用户)):
    html = (模板目录 / "控制台.html").read_text(encoding="utf-8")
    html = html.replace("{{ 标题 }}", f"{项目名称} · 控制台")
    html = html.replace("{{ 项目名 }}", 项目名称)
    return HTMLResponse(html)


# ===================== API =====================
@app.get("/api/统计")
async def 统计接口(_: dict = Depends(当前用户)):
    """全局统计数字"""
    conn = db.获取数据库()
    c = conn.cursor()
    out = {}
    for k, t in [("用户数", "用户"), ("账号数", "账号"), ("任务数", "任务"),
                 ("代理数", "代理"), ("守护日志", "守护日志"), ("举报任务", "举报任务"),
                 ("频道数", "频道")]:
        try:
            c.execute(f"SELECT COUNT(*) AS c FROM {t}")
            out[k] = c.fetchone()["c"]
        except Exception:
            out[k] = 0
    conn.close()
    return out


@app.get("/api/账号")
async def 账号列表(用户ID: Optional[int] = None, 数量: int = 50, _user: dict = Depends(当前用户)):
    """账号列表"""
    conn = db.获取数据库()
    c = conn.cursor()
    if 用户ID:
        c.execute("SELECT id,user_id,phone,first_name,last_name,username,status,premium,added_at FROM 账号 WHERE user_id=? ORDER BY added_at DESC LIMIT ?", (用户ID, 数量))
    else:
        c.execute("SELECT id,user_id,phone,first_name,last_name,username,status,premium,added_at FROM 账号 ORDER BY added_at DESC LIMIT ?", (数量,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/任务")
async def 任务列表(_user: dict = Depends(当前用户)):
    """任务列表"""
    conn = db.获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 任务 ORDER BY created_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/守护日志")
async def 守护日志API(数量: int = 100, _user: dict = Depends(当前用户)):
    """守护日志"""
    conn = db.获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 守护日志 ORDER BY created_at DESC LIMIT ?", (数量,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/代理")
async def 代理列表(_user: dict = Depends(当前用户)):
    """代理列表"""
    conn = db.获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 代理 ORDER BY added_at DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/举报任务")
async def 举报任务列表(_user: dict = Depends(当前用户)):
    """举报任务列表"""
    conn = db.获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 举报任务 ORDER BY created_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/设置/{用户ID}")
async def 查看设置(用户ID: int, _user: dict = Depends(当前用户)):
    """查看某用户设置"""
    return db.获取用户设置(用户ID)


def 启动():
    """启动 Web 后台"""
    db.初始化数据库()
    print(f"🌐 {项目名称} · Web 后台启动中...")
    print(f"   地址: http://{后台地址}:{后台端口}")
    print(f"   账号: {后台用户名} / {后台密码}")
    uvicorn.run(app, host=后台地址, port=后台端口, log_level="info")


if __name__ == "__main__":
    启动()
