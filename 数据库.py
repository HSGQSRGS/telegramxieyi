"""数据库模块 - 协议工具箱
作者: Lion
"""
import sqlite3
import json
from datetime import datetime
from 配置 import 数据库路径, 日志

def 获取数据库():
    conn = sqlite3.connect(数据库路径)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def 初始化数据库():
    conn = 获取数据库()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS 用户 (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_vip INTEGER DEFAULT 0,
            vip_expiry TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 账号 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            session_path TEXT NOT NULL,
            session_string TEXT,
            api_id INTEGER NOT NULL,
            api_hash TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            user_tg_id INTEGER,
            bio TEXT,
            birthday TEXT,
            device_model TEXT,
            system_version TEXT,
            app_version TEXT,
            system_lang_code TEXT DEFAULT 'en',
            lang_code TEXT DEFAULT 'en',
            lang_pack TEXT DEFAULT 'tdesktop',
            premium INTEGER DEFAULT 0,
            premium_expiry TEXT,
            reg_date TEXT,
            status TEXT DEFAULT 'active',
            twofa_password TEXT,
            twofa_hint TEXT,
            recovery_email TEXT,
            proxy_id INTEGER,
            ip TEXT,
            country TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_check TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id),
            FOREIGN KEY (proxy_id) REFERENCES 代理(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 任务 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            target TEXT,
            message TEXT,
            media_path TEXT,
            total_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 代理 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            proxy_str TEXT NOT NULL UNIQUE,
            proxy_type TEXT DEFAULT 'socks5',
            fail_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 设置 (
            user_id INTEGER PRIMARY KEY,
            monitor_code INTEGER DEFAULT 1,
            consume_code INTEGER DEFAULT 1,
            auto_kill INTEGER DEFAULT 0,
            guardian_active INTEGER DEFAULT 0,
            sovereign_active INTEGER DEFAULT 0,
            sovereign_since TEXT,
            whitelist_devices TEXT DEFAULT '[]',
            monitor_keywords TEXT DEFAULT '[]',
            monitor_forward_target TEXT DEFAULT '',
            monitor_auto_reply TEXT DEFAULT '{}',
            monitor_active INTEGER DEFAULT 0,
            guardian_consume_bot TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    try:
        c.execute("ALTER TABLE 设置 ADD COLUMN monitor_active INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE 设置 ADD COLUMN guardian_consume_bot TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS 频道 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER,
            title TEXT,
            username TEXT,
            access_hash INTEGER,
            account_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 守护日志 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS 举报任务 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target TEXT NOT NULL,
            reason TEXT NOT NULL,
            msg TEXT,
            total_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES 用户(user_id)
        )
    ''')
    conn.commit()
    conn.close()
    日志.info("数据库初始化完成")

def 注册用户(user_id, username=None, first_name=None, last_name=None):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO 用户 (user_id, username, first_name, last_name, joined_at, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            last_active=excluded.last_active
    ''', (user_id, username, first_name, last_name, now, now))
    conn.commit()
    conn.close()

def 获取用户账号(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 账号 WHERE user_id = ? ORDER BY added_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 获取账号数量(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM 账号 WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["count"] if row else 0

def 按手机号查账号(phone, user_id=None):
    conn = 获取数据库()
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM 账号 WHERE phone = ? AND user_id = ?", (phone, user_id))
    else:
        c.execute("SELECT * FROM 账号 WHERE phone = ?", (phone,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def 按ID查账号(account_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 账号 WHERE id = ?", (account_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def 保存账号(user_id, phone, session_path, api_id, api_hash, first_name=None,
             last_name=None, username=None, user_tg_id=None, device_model=None,
             system_version=None, app_version=None, premium=0, premium_expiry=None,
             twofa_password=None, twofa_hint=None, recovery_email=None,
             session_string=None, bio=None, birthday=None, reg_date=None,
             system_lang_code='en', lang_code='en', lang_pack='tdesktop',
             ip=None, country=None, proxy_id=None):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = 按手机号查账号(phone, user_id)
    if existing:
        c.execute('''
            UPDATE 账号 SET
                session_path=?, session_string=?, api_id=?, api_hash=?,
                first_name=?, last_name=?, username=?, user_tg_id=?,
                device_model=?, system_version=?, app_version=?,
                system_lang_code=?, lang_code=?, lang_pack=?,
                premium=?, premium_expiry=?, twofa_password=?,
                twofa_hint=?, recovery_email=?, bio=?, birthday=?,
                reg_date=?, ip=?, country=?, proxy_id=?,
                status='active', last_check=?
            WHERE phone=? AND user_id=?
        ''', (session_path, session_string, api_id, api_hash,
              first_name, last_name, username, user_tg_id,
              device_model, system_version, app_version,
              system_lang_code, lang_code, lang_pack,
              premium, premium_expiry, twofa_password,
              twofa_hint, recovery_email, bio, birthday,
              reg_date, ip, country, proxy_id,
              now, phone, user_id))
        conn.commit()
        conn.close()
        return existing['id']
    c.execute('''
        INSERT INTO 账号 (user_id, phone, session_path, session_string,
            api_id, api_hash, first_name, last_name, username, user_tg_id,
            device_model, system_version, app_version, system_lang_code,
            lang_code, lang_pack, premium, premium_expiry,
            twofa_password, twofa_hint, recovery_email, bio, birthday,
            reg_date, ip, country, proxy_id, added_at, last_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, phone, session_path, session_string, api_id, api_hash,
          first_name, last_name, username, user_tg_id,
          device_model, system_version, app_version, system_lang_code,
          lang_code, lang_pack, premium, premium_expiry,
          twofa_password, twofa_hint, recovery_email, bio, birthday,
          reg_date, ip, country, proxy_id, now, now))
    conn.commit()
    account_id = c.lastrowid
    conn.close()
    return account_id

def 更新账号状态(phone, user_id, status='inactive'):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("UPDATE 账号 SET status = ?, last_check = ? WHERE phone = ? AND user_id = ?",
              (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone, user_id))
    conn.commit()
    conn.close()

def 更新账号字段(account_id, field, value):
    valid = ['first_name', 'last_name', 'username', 'bio', 'birthday', 'twofa_password',
             'twofa_hint', 'recovery_email', 'device_model', 'premium', 'premium_expiry',
             'status', 'session_string', 'session_path', 'ip', 'country', 'proxy_id', 'reg_date',
             'lang_code', 'lang_pack', 'system_lang_code']
    if field not in valid:
        return
    conn = 获取数据库()
    c = conn.cursor()
    c.execute(f"UPDATE 账号 SET {field} = ? WHERE id = ?", (value, account_id))
    conn.commit()
    conn.close()

def 删除账号(account_id, user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("DELETE FROM 账号 WHERE id = ? AND user_id = ?", (account_id, user_id))
    conn.commit()
    conn.close()

def 获取全部账号():
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 账号 WHERE status = 'active' ORDER BY added_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 获取用户活跃账号(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 账号 WHERE user_id = ? AND status = 'active' ORDER BY added_at DESC",
              (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 保存任务(user_id, task_type, target=None, message=None, media_path=None,
              total_count=0, status='pending'):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO 任务 (user_id, task_type, target, message, media_path,
            total_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, task_type, target, message, media_path, total_count, status, now))
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return task_id

def 更新任务(task_id, success_count=0, fail_count=0, status=None):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status:
        c.execute('''
            UPDATE 任务 SET success_count = ?, fail_count = ?, status = ?, completed_at = ?
            WHERE id = ?
        ''', (success_count, fail_count, status, now, task_id))
    else:
        c.execute('''
            UPDATE 任务 SET success_count = ?, fail_count = ? WHERE id = ?
        ''', (success_count, fail_count, task_id))
    conn.commit()
    conn.close()

def 获取用户任务(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 任务 WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 获取用户设置(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 设置 WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO 设置 (user_id) VALUES (?)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM 设置 WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def 更新用户设置(user_id, field, value):
    valid = ['monitor_code', 'consume_code', 'auto_kill', 'guardian_active',
             'sovereign_active', 'sovereign_since', 'whitelist_devices',
             'monitor_keywords', 'monitor_forward_target', 'monitor_auto_reply',
             'monitor_active', 'guardian_consume_bot']
    if field not in valid:
        return
    conn = 获取数据库()
    c = conn.cursor()
    c.execute(f"UPDATE 设置 SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def 添加代理(user_id, proxy_str):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        c.execute("INSERT INTO 代理 (user_id, proxy_str, added_at) VALUES (?, ?, ?)",
                  (user_id, proxy_str, now))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def 获取代理列表(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 代理 WHERE user_id = ? AND status = 'active'", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 更新代理状态(proxy_id, status='active', fail_count=0):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("UPDATE 代理 SET status = ?, fail_count = ? WHERE id = ?",
              (status, fail_count, proxy_id))
    conn.commit()
    conn.close()

def 删除代理(proxy_id, user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("DELETE FROM 代理 WHERE id = ? AND user_id = ?", (proxy_id, user_id))
    conn.commit()
    conn.close()

def 添加守护日志(user_id, phone, event_type, event_data=None):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO 守护日志 (user_id, phone, event_type, event_data, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, phone, event_type, event_data, now))
    conn.commit()
    conn.close()

def 获取守护日志(user_id, phone=None, limit=50):
    conn = 获取数据库()
    c = conn.cursor()
    if phone:
        c.execute("SELECT * FROM 守护日志 WHERE user_id = ? AND phone = ? ORDER BY created_at DESC LIMIT ?",
                  (user_id, phone, limit))
    else:
        c.execute("SELECT * FROM 守护日志 WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                  (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 保存举报任务(user_id, target, reason, msg=None, total_count=0, status='pending'):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO 举报任务 (user_id, target, reason, msg, total_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, target, reason, msg, total_count, status, now))
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return task_id

def 更新举报任务(task_id, success_count=0, fail_count=0, status=None):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status:
        c.execute('''
            UPDATE 举报任务 SET success_count = ?, fail_count = ?, status = ?, completed_at = ?
            WHERE id = ?
        ''', (success_count, fail_count, status, now, task_id))
    else:
        c.execute('''
            UPDATE 举报任务 SET success_count = ?, fail_count = ? WHERE id = ?
        ''', (success_count, fail_count, task_id))
    conn.commit()
    conn.close()

def 获取举报任务(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 举报任务 WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 添加频道(user_id, channel_id, title, username, access_hash, account_phone):
    conn = 获取数据库()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO 频道 (user_id, channel_id, title, username, access_hash, account_phone, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, channel_id, title, username, access_hash, account_phone, now))
    conn.commit()
    conn.close()

def 获取用户频道(user_id):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 频道 WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def 设置VIP(user_id, is_vip=1, expiry=None):
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("UPDATE 用户 SET is_vip = ?, vip_expiry = ? WHERE user_id = ?",
              (is_vip, expiry, user_id))
    conn.commit()
    conn.close()

def 获取全部用户():
    conn = 获取数据库()
    c = conn.cursor()
    c.execute("SELECT * FROM 用户 ORDER BY joined_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

初始化数据库()