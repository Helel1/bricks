# -*- coding: utf-8 -*-
# @Time    : 2023-12-29 10:03
# @Author  : Kem
# @Desc    : 管理工具（命令行入口适配器）
#
# 职责概述：
# 1) 解析 CLI 参数并统一封装为 Argv（见 bricks/client/__init__.py: Argv）
# 2) 通过 adapters（适配器表）按 form 路由到具体处理函数（默认 run_task）
# 3) 支持 base64 参数模式，便于远程调用时避免转义/空格问题
import base64
import sys
from typing import Callable, List, Union
from urllib import parse

from bricks.client import Argv
from bricks.client.runner import BaseRunner
from bricks.utils import pandora


@pandora.with_metaclass(singleton=True, autonomous=("install",))
class Manager:
    """
    CLI 管理器：单例 + 适配器路由

    - with_metaclass(singleton=True)：保证进程内唯一实例，避免重复初始化。
    - autonomous=("install",)：若存在 install 钩子会在实例化时自动调用（此处未使用）。
    - adapters：form → 处理函数 的映射，默认注册 "run_task"。
    """

    def __init__(self):
        # 适配器路由表，可通过 register_adapter 动态扩展
        self.adapters = {"run_task": self.run_task}

    @staticmethod
    def _parse(argvs: list) -> Argv:
        """
        解析命令行参数并构造 Argv 对象

        用法（与 Argv.get_parser 一致）：
          python manager.py <filename> <form> \
            -m/--main <main入口> \
            -a/--args key=value        # 可多次
            -extra/--extra key=value    # 可多次
            -workdir/--workdir <目录>   # 同时注入 sys.path 并切换 cwd
            -env/--env KEY=VALUE        # 可多次，且立即设置为环境变量
            -rpc/--rpc key=value        # 可多次（用于 RPC 启动配置）

        特殊：当仅传 1 个参数且以 base64:// 开头时，会先解码为真实参数串。
        """

        def _2dict(obj):
            """将 [-a/-extra/-env/-rpc] 多次传入的键值对合并为字典，并做类型猜测。"""
            kw = {}
            # iterable(obj) 统一 None/单值/多值为可迭代，随后用 & 连接后 parse_qsl 解析为 (k, v) 列表
            for key, value in parse.parse_qsl("&".join(pandora.iterable(obj))):
                # guess：将字符串尽可能转换为 int/float/bool/json 等 Python 类型
                kw[key] = pandora.guess(value)
            return kw

        # 支持 base64://<encoded> 形式传参，便于跨进程/网络传输
        if len(argvs) == 2 and argvs[1].startswith("base64://"):
            en_argv = argvs[1][9:]
            de_argvs = base64.b64decode(en_argv.encode()).decode().split(" ")
            argvs = [argvs[0], *de_argvs]

        # 统一复用 Argv 的解析器，确保 CLI 行为一致
        parser = Argv.get_parser()
        argv = parser.parse_args(argvs)

        # 汇总解析结果到 Argv 数据类
        return Argv(
            filename=argv.filename,
            form=argv.form,
            main=argv.main,
            args=_2dict(argv.args),
            extra=_2dict(argv.extra),
            env={**_2dict(argv.env), "workdir": argv.workdir},
            rpc=_2dict(argv.rpc),
            workdir=argv.workdir,
        )

    def run(self, argv: Union[str, List[str]] = None):
        """
        运行

        :param argv: 命令行参数, 不传的时候取 sys.argv
        :return:
        """
        # 拼接参数来源：默认取 sys.argv，若外部传入字符串/列表则扩展之
        argvs = [*sys.argv]
        # 调试输出：可保留或按需关闭
        print(f"manage 的入参{argvs}")
        if isinstance(argv, str):
            argvs.extend(argv.split(" "))
        else:
            argvs.extend(pandora.iterable(argv))
        print(f"manage 的解析之后的参数{argvs}")
        argv = self._parse(argvs)
        self.run_adapter(argv)

    def register_adapter(self, form: str, action: Callable):
        """注册一个适配器（命令类别 → 处理函数）。"""
        self.adapters[form] = action

    def run_adapter(self, argv: Argv):
        """根据 argv.form 路由至对应适配器并执行。"""
        form: str = argv.form
        assert form in self.adapters, f"form 未注册: {form}"
        adapter = self.adapters[form]
        print(f"适配器：{self.adapters}")
        return adapter(argv)

    @staticmethod
    def run_task(argv: Argv):
        """默认适配器：委托 BaseRunner 运行任务或以 RPC 模式启动。"""
        runner = BaseRunner()
        return runner.run_task(argv)
