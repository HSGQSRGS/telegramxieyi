"""并发启动 - 协议工具箱
同时启动机器人 + Web 后台
作者: Lion
"""
import sys
import threading
import time
from pathlib import Path

根 = Path(__file__).parent
sys.path.insert(0, str(根))

import 配置
from 配置 import 项目名称, 作者名称, 后台地址, 后台端口, 后台用户名, 后台密码


def 启动机器人():
    """启动机器人主程序"""
    import 主程序
    主程序.main()


def 启动后台():
    """启动 Web 后台"""
    from 管理后台.web后台 import 启动
    启动()


def main():
    """主入口"""
    print("=" * 60)
    print(f"  {项目名称} · 作者 {作者名称}")
    print(f"  批量 / 守护 / 监听 / 举报 / 代理 / 会话 全集版")
    print("=" * 60)

    import 数据库
    数据库.初始化数据库()
    print("✅ 数据库初始化完成")

    # 后台线程
    t = threading.Thread(target=启动后台, daemon=True)
    t.start()
    print(f"✅ Web 后台已启动：http://{后台地址}:{后台端口}")
    print(f"   默认账号：{后台用户名} / {后台密码}")

    time.sleep(2)

    print("✅ 机器人启动中...")
    print(f"   项目：{项目名称}")
    print(f"   作者：{作者名称}")
    print(f"   按 Ctrl+C 停止")
    启动机器人()


if __name__ == "__main__":
    main()