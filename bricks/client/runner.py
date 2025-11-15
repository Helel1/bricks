# -*- coding: utf-8 -*-
# @Time    : 2023-12-29 11:11
# @Author  : Kem
# @Desc    : 运行器
#
# 职责：
# - BaseRunner：根据 Argv 决定以“本地执行”还是“RPC 模式”运行任务；
# - RpcProxy：将本地运行逻辑包装成可通过 HTTP/gRPC/WebSocket 等方式调用的 RPC 服务。
import os
import signal
import sys
import threading
import time
from concurrent.futures import Future
from typing import Callable, Any

from loguru import logger

from bricks.client import Argv
from bricks.rpc.common import MODE, serve
from bricks.utils import pandora


class RpcProxy:
    """RPC 代理对象

    - 对外暴露一个“服务对象”（自身或绑定的 object），由 bricks.rpc.common.serve 负责监听端口；
    - 内置 stop/reload 等管理方法，并提供 add_background_task 工具启动后台任务；
    - 可通过 register_adapter 注册额外适配方法，丰富 RPC 调用接口。
    """

    def __init__(self, main: Callable, *args, **kwargs):
        # main: 当 RPC 服务启动成功后要执行的主逻辑（通常是 BaseRunner.run_local）
        self.object = None  # 实际被代理的业务对象（可通过 bind 绑定）
        self.main = main
        self.args = args
        self.kwargs = kwargs
        self.adapters = {}  # form/name -> callable，自定义适配方法表

    @classmethod
    def stop(cls, delay=1):
        """异步停止当前进程：delay 秒后发送 SIGTERM。

        常用于通过 RPC 调用远程停止服务。
        """
        fu = cls.add_background_task(
            lambda: os.kill(os.getpid(), signal.SIGTERM), delay=delay
        )
        return f"即将在 {delay} 秒后停止程序, 后台任务: {fu}"

    @classmethod
    def reload(cls, python: str = None, delay=1):
        """异步重启当前进程。

        - 优先使用 os.execv 实现原地重启；
        - 若失败则使用 os.spawnv 新建进程并退出当前进程。
        """
        python = python or sys.executable

        def main():
            try:
                os.execv(python, [python] + sys.argv)
            except OSError:
                os.spawnv(os.P_NOWAIT, python, [python] + sys.argv)
                sys.exit(0)

        fu = cls.add_background_task(main, delay=delay)
        return f"即将在 {delay} 秒后停止程序, 后台任务: {fu}"

    @staticmethod
    def add_background_task(func, args: list = None, kwargs: dict = None, delay=1, daemon=False):
        """以后台任务形式执行函数，并返回一个 Future 用于跟踪结果。

        :param func: 要执行的函数
        :param args: 位置参数
        :param kwargs: 关键字参数
        :param delay: 延迟执行的秒数
        :param daemon: 是否以守护线程运行（delay>0 时生效）
        """
        future = Future()
        args = args or []
        kwargs = kwargs or {}

        def main():
            try:
                delay and time.sleep(delay)
                ret = func(*args, **kwargs)
            except BaseException as exc:
                if future.set_running_or_notify_cancel():
                    future.set_exception(exc)
                raise
            else:
                future.set_result(ret)

        if delay:
            t = threading.Thread(target=main, daemon=daemon)
            t.start()
        else:
            main()

        return future

    def bind(self, obj):
        """绑定真实业务对象，将其方法暴露给 RPC 调用。"""
        self.object = obj
        return self

    def __getattr__(self, name):
        """属性访问代理逻辑：优先返回 adapters 中注册的方法，否则代理到绑定对象。"""
        if name in self.adapters:
            return self.adapters[name]
        else:
            return getattr(self.object, name)

    def start(self, mode: MODE = "http", concurrency: int = 10, ident: Any = 0, **kwargs):
        """启动 RPC 服务。

        :param mode: RPC 模式，如 http/grpc 等
        :param concurrency: 并发度，由 serve 实现决定含义
        :param ident: 标识/端口信息，由具体 RPC 实现解释
        """
        serve(self, mode=mode, concurrency=concurrency, ident=ident, on_server_started=self.on_server_started, **kwargs)

    def on_server_started(self, ident: Any):
        """RPC 服务启动后的回调：打印日志并在后台线程中执行 main。"""
        logger.debug(f'[RPC] 服务启动成功, 监听端口: {ident}')
        threading.Thread(target=lambda: self.main(*self.args, **self.kwargs), daemon=True).start()

    def register_adapter(self, form: str, action: Callable):
        """注册一个适配器方法，使其可以通过 RPC 名称调用。"""
        self.adapters[form] = action


class BaseRunner:
    def __init__(self):
        # 记录任务开始/结束时间，便于统计运行耗时（当前仅初始化）
        self.st_utime = time.time()
        self.et_utime = time.time()

    @staticmethod
    def run_local(argv: Argv):
        """本地运行任务。

        根据 argv.main 的形式判断：
        - 若为文件路径：读取脚本并以 __main__ 环境 exec；
        - 若为可导入对象路径：动态加载并调用函数。
        """
        main: str = argv.main
        if os.path.sep in main or os.path.exists(main):
            # main 看起来像路径，或对应文件存在 → 视为脚本文件
            with open(argv.main) as f:
                # 以 __name__ == "__main__" 执行脚本，并注入 args/extra 为全局变量
                exec(f.read(), {"__name__": "__main__", **argv.args, **argv.extra})
                return None
        else:
            # 否则视为可导入对象路径（例如 "pkg.mod:func"），按函数方式调用
            func: Callable = pandora.load_objects(main)
            return pandora.invoke(func=func, kwargs=argv.args, namespace=argv.extra)

    def run_task(self, argv: Argv):
        """
        运行任务

        :param argv: 由 Manager/Argv 构造的参数对象
        :return: 本地执行时返回函数结果；RPC 模式下返回 None
        """

        assert argv.main, "main 参数不能为空"

        # bind rpc
        rpc_options: dict = argv.rpc or {}

        if rpc_options:
            # 若配置了 rpc 参数，则以 RPC 模式启动：
            # 1) 创建 RpcProxy 绑定 run_local 作为主逻辑
            # 2) 将 proxy 注入 extra 中，便于任务内部感知/操作 RPC
            # 3) 调用 proxy.start(**rpc_options) 启动 RPC 服务
            proxy = RpcProxy(self.run_local, argv)
            argv.extra.update({"rpc": proxy})
            proxy.start(**rpc_options)
            return None

        else:
            # 默认走本地执行逻辑
            return self.run_local(argv)
