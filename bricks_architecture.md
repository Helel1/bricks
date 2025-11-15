# Bricks 项目架构与调度器解析

> 基于代码库（如 `bricks/core/genesis.py`、`bricks/core/dispatch.py`、`bricks/utils/scheduler.py` 等）与官方文档页面梳理的总结，重点关注调度器。

## 1. 项目骨架速览

- **核心层**：`Chaos/Pangu` 抽象（`bricks/core/genesis.py`）提供生命周期钩子、事件织入与 `Dispatcher` 初始化，`Context/Flow`（`bricks/core/context.py`）承担上下文管理与流程分支，`EventManager`（`bricks/core/events.py`）负责事件注册与触发。
- **执行与并发**：`Dispatcher`/`Worker`/`Task`（`bricks/core/dispatch.py`）构成可伸缩线程池，既能提交同步任务，也能激活异步协程，支持 worker 暂停、唤醒与取消。
- **蜘蛛家族**：`bricks/spider/air.py`、`form.py`、`template.py` 提供代码式、流程配置式与模板化开发体验；`Context` 内置 request/response/seeds/task_queue 等对象，使业务逻辑像积木一样组合。
- **基础设施**：`lib/queues`（本地/Redis/Smart）、`lib/request|response|items|proxies`、`db/*` 数据适配、`downloader/*` 多种请求实现、`plugins/*` 提供请求前后扩展、`client/*` 实现 CLI+RPC。
- **状态与全局变量**：`bricks/state.py` 中 `G/T` 维护全局/线程变量，`const` 定义了完整的生命周期事件常量，贯穿整个框架。

## 2. 运行流程（以 Air Spider 为例）

1. **入口**：通过 `manager.py` → `bricks/client/manage.py` 解析 CLI 参数，交由 `BaseRunner` 执行本地函数或启动 RPC 服务。
2. **实例化**：Spider 通过 `MetaClass` 自动执行 `_when_*` 装饰器与 `install()`，注册默认事件（如错误捕获）。
3. **任务准备**：`TaskQueue`（本地或 Redis）放入 seeds，`Flow` 维护待执行链路；`dispatcher` 根据 `concurrency` 创建 worker。
4. **消费循环**：`Pangu.on_consume` 反复 `produce()` context，依次执行 `context.next` 中的解析/下载/管道函数；遇到 `branch/submit/background` 时可把新任务再次丢给 `Dispatcher`。
5. **事件驱动**：在 `const.BEFORE_* / AFTER_* / ON_*` 节点插入插件，例如 `plugins.on_request.Before.set_proxy`、`After.bypass` 等，实现零侵入的扩展。
6. **收尾**：成功/失败通过 `Context.success/failure` 更新队列，`before_close` 触发清理事件，`Dispatcher` 在任务耗尽后回收 worker。

## 3. 调度器深度剖析

### 3.1 线程级调度（Dispatcher）

- **资源池**：初始化时将 `max_workers` 个标识放入 `_remain_workers`，按需创建 `Worker`，空闲时自动退出并归还额度。
- **同步/异步共存**：`Task.is_async` 判断函数类型，`submit_task` 将同步任务塞入 `_TaskQueue`，异步任务则交给 `active_task`，后者在专用 event loop 中 `ensure_future`。
- **控制与取消**：`Semaphore` `_running_tasks/_active_tasks` 限制并发，`cancel_task` 可在任务仍在队列时直接移除，否则强制停止对应 worker；`pause_worker`/`awake_worker` 支持人工干预。

### 3.2 时间级调度（Scheduler）

- **Trigger 抽象**：`BaseTrigger` 支持 `cron/interval/date` 三类，并提供 `begin/until`、多种执行模式（忽略/不忽略任务耗时、后台线程执行）与异常策略。
- **表达式解析**：`CronTrigger` 支持 `L`、区间、步长、`N#A`（第几周）等高级语法；`IntervalTrigger` 使用 `seconds=5&hours=2` 的 query 语法；`DateTrigger` 在命中一次后自动取消。
- **运行循环**：`Scheduler.run` 按 `should_run` 过滤、排序触发器并执行 `job.run()`，`wait()` 依据下一次运行时间睡眠，最大等待 10 秒并重检。
- **Spider 集成**：`Chaos.launch` 允许开发者传入 `scheduler` dict（含 `form/exprs` 等），内部创建 `Scheduler` 并在触发时调用 `self.run(task_name, …)`，从而把任意 Spider 任务转换为定时任务。

### 3.3 调度互联

1. 时间调度层（`Scheduler`）决定 **何时** 启动任务。
2. 工作线程层（`Dispatcher`）决定 **如何** 并发消费任务。
3. `TaskQueue` 保证任务可跨线程/跨进程共享，配合 RPC 可以进一步扩展到多机。

## 4. 关键模块与学习建议

| 模块 | 作用 | 入门提示 |
| --- | --- | --- |
| `bricks/spider/air.py` | 代码式 Spider，展示 `Context`、`submit/branch`、重试/信号处理 | 先跑 `example`，再尝试自定义插件 |
| `bricks/lib/queues` | 本地/Redis/Smart 队列，提供 `Item` 指纹、`py2str` 等工具 | 理解 `queue_name` 命名与 `qtypes`（current/temp/failure） |
| `bricks/downloader/*` | 多种请求实现（curl-cffi、requests、playwright 等），统一封装异常与请求体解析 | 自定义下载器时只需实现 `fetch`，其余逻辑由装饰器兜底 |
| `bricks/plugins/on_request.py` | 请求前后插件：代理、UA、响应校验、条件脚本 | 使用 `@on_request.before`/`after` 快速扩展 |
| `bricks/client/runner.py` | CLI 与 RPC 入口，支持 HTTP/gRPC/WebSocket | 通过 `rpc` 参数即可把 Spider API 化 |

## 5. 风险与优化建议（批判性审视）

1. **时间调度无持久化**：`Scheduler` 所有任务驻留内存，进程重启即失；也缺乏分布式竞争。建议引入 Redis/SQLite 记录 `_next_fire_time` 或直接使用 APScheduler/Celery Beat 等成熟方案。
2. **`launch()` 重复创建调度器**：每次调用都 `Scheduler().run()` 阻塞，难以在单进程中维护多个定时任务。可将调度器提升为 Spider 成员，通过 `start()` 在后台常驻。
3. **工作线程缩容滞后**：`adjust_workers` 只会根据待办数扩容，闲时全靠 worker 自行退出，若 `max_workers` 大可能造成线程频繁创建/销毁。可增加基于队列长度/CPU 的平滑缩容逻辑。
4. **任务级重试策略分散**：异常只在 `Worker` 内部 `set_exception` 并触发 `context.Error` 事件，默认需要 Spider 自行抛 `signals.Retry`。建议提供统一的重试/退避配置接口减少样板代码。
5. **官方文档缺少调度细节**：Nextra 页面目前只有特性概述，学员仍需阅读源码。可补充「调度 FAQ」与 demo（例如 `Scheduler.get_fire_times()` 验证 cron），降低学习门槛。

## 6. 建议的学习路径

1. **跑通示例**：使用 `python manager.py run_task -m example.xxx` 启动 demo；观察 `Dispatcher` 日志与事件触发顺序。
2. **练习调度**：在 REPL 中调用 `Scheduler.get_fire_times()` 验证 cron/interval 表达式，再用 `Chaos.launch` 将同样的配置投入实际 Spider。
3. **自定义插件**：仿照 `plugins/on_request.py` 编写 before/after 插件（如指标上报、动态 header）。
4. **扩展队列/下载器**：若需要分布式，可优先尝试 Redis 队列；若要接入企业代理，可继承 `AbstractDownloader` 或 `BaseProxy`。
5. **规划调度演进**：根据业务规模决定是否接入外部调度平台，并评估任务持久化、分布式抢占、错过补偿等需求。

> 如需进一步拆解 `TaskQueue`、`Form` 爬虫配置或编写调度 Demo，可在此基础上继续扩展。

## 7. 命令执行链路（CLI → Runner → Spider）

以命令 `python manager.py run_task -m example/spider/air.py --workdir /Users/zhouzhixin/ai/bricks` 为例：

1. 入口与参数采集
   - 调用 `Manager().run()` 收集 `sys.argv` 并打印调试信息（`bricks/client/manage.py:1`）。
   - 未使用 base64 传参则跳过解码分支。
2. 解析成 Argv
   - `Manager._parse()` → `Argv.get_parser()` 构造解析器并解析位置/选项参数（`bricks/client/__init__.py:1`）。
   - `--workdir` 触发 `set_work_dir`：将目录插入 `sys.path` 并 `os.chdir` 到该目录。
   - 组装 `Argv` 数据类（含 `filename/form/main/args/extra/env/rpc/workdir`）。
3. 适配器路由
   - `Manager.run_adapter()` 读取 `argv.form=run_task`，调用 `Manager.run_task()`（`bricks/client/manage.py:1`）。
4. Runner 执行
   - `BaseRunner.run_task(argv)`：若无 `rpc` 参数则走本地模式 `run_local(argv)`（`bricks/client/runner.py:1`）。
   - `run_local()` 检测 `main` 为文件路径：`exec('example/spider/air.py', {"__name__": "__main__", **args, **extra})`。
5. Spider 启动
   - `example/spider/air.py` 在 `__main__` 分支中构建 `MySpider` 并 `spider.run()`。
   - 元类织入事件/拦截器，`Pangu` 初始化 `Dispatcher`，随后进入 `on_consume` 主循环，按事件驱动完成请求/解析/队列/存储的流水线（`bricks/core/genesis.py:1`、`bricks/core/dispatch.py:1`）。
6. 可观测点
   - `--workdir` 会影响当前工作目录与模块导入路径；`-env` 会在解析阶段写入 `os.environ`；`manage.py` 会输出两行调试打印。

## 8. Chaos 运行流程与事件织入

以 `Chaos`/`Pangu` 为基类的 Spider，在调用 `run()` 时会经过一层元类织入的统一流程：

1. 元类实例化阶段（`MetaClass.__call__`）
   - 创建实例后遍历所有方法：
     - 对 `_when_xxx` 形式的方法（如 `_when_run`、`_when_before_start`、`_when_before_close`），自动用它们去包装对应原方法 `xxx`；
     - 对带有 `__event__` 属性的方法，自动调用 `instance.use(*func.__event__)` 完成事件注册（交给 `EventManager`）。
   - 若实例实现了 `install()`，在拦截器和事件注册完成后自动调用一次（`Pangu.install` 默认注册错误捕获事件）。

2. `run()` 调用链
   - 原始 `Chaos.run()` 在实例化后会被 `_when_run` 替换为 wrapper：

     ```text
     spider.run(...) 实际执行顺序：
       1) before_start()
       2) 原始 run(...) 逻辑（例如 run_all）
       3) before_close()
     ```

3. `before_start` / `before_close` 的事件织入
   - `before_start` 被 `_when_before_start` 包装，执行顺序：

     ```text
     make_context(form=BEFORE_START)
       -> EventManager.invoke(context)   # 触发所有注册到 BEFORE_START 的事件处理函数
       -> 原始 before_start()            # 默认是 pass，用户可重写
     ```

   - `before_close` 被 `_when_before_close` 包装，执行顺序：

     ```text
     make_context(form=BEFORE_CLOSE)
       -> EventManager.invoke(context)   # 触发所有注册到 BEFORE_CLOSE 的事件处理函数
       -> 原始 before_close()
     ```

4. 整体调用时序总结

   ```text
   spider = MySpider()
   spider.run()
     -> _when_run 包装后的 wrapper
        -> before_start()
           -> _when_before_start wrapper
              -> make_context(BEFORE_START)
              -> EventManager.invoke(BEFORE_START)  # 调用所有 BEFORE_START 插件
              -> 原始 before_start()
        -> 原始 run(...) 业务逻辑
        -> before_close()
           -> _when_before_close wrapper
              -> make_context(BEFORE_CLOSE)
              -> EventManager.invoke(BEFORE_CLOSE)  # 调用所有 BEFORE_CLOSE 插件
              -> 原始 before_close()
   ```

   因此：
   - `MetaClass` 负责在实例化阶段“织入”拦截器和事件注册；
   - `_when_*` 系列方法定义了统一的前后逻辑（生命周期钩子 + 事件触发）；
   - 你在 Spider 上只需：
     - 重写 `before_start/before_close` 或 `run_xxx`，即可挂载生命周期逻辑；
     - 使用事件装饰器（给方法加 `__event__`）即可将插件自动注册到对应阶段。
