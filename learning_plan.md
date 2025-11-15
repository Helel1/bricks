# Bricks 学习计划（1 个月）

> 目标：在一个月内熟练掌握 Bricks 框架原理，能够开发或修改小型功能；默认仅使用本地队列，Redis 后续可按需补充。

## 使用说明（如何配合对话一起用）

- 进度以本文件和 `bricks_architecture.md` 为准，不依赖聊天记录回溯。
- 每次开始学习前，在提问时注明当前节点，例如：`【Day2 / genesis.py / MetaClass】`。
- 学到重要结论或图示时，优先让我帮你同步到：
  - 当天的「今日总结」（写在本文件对应 Day 下）；
  - 或 `bricks_architecture.md` 中相关章节。
- 和 Bricks 不强相关的“泛 Python / 架构”问题，可：
  - 开新对话单独问；或
  - 记录到单独的 `notes/misc.md`（如你后续创建）。
- 每次结束学习时，让我用 3–5 行总结今天内容，并写回「今日总结」，确保进度可追踪。

## 第 1 周：环境起步与整体认知

- 搭建 Python 环境并安装 `requirements.txt`；如暂未配置 Redis，则先使用本地队列运行。
- 跑通 `example` 中至少一个 Spider，记录日志（入口、事件、队列流转）。
- 精读 `README` 与 `bricks_architecture.md`，用导图梳理目录结构、生命周期事件、调度层级。
- 输出：一份“项目骨架 + 运行链路”笔记（含 CLI → Spider 流程、Context 生命周期）。

## 第 2 周：核心源码精读

- 重点阅读 `bricks/core/genesis.py`、`context.py`、`events.py`，绘制 `Flow` 调度与事件触发时序。
- 深入 `dispatcher` 与 `scheduler`：分别编写 demo 脚本，验证同步/异步任务执行、cron/interval 触发与 `get_fire_times()`。
- 记录调度 FAQ：例如 worker 伸缩、任务取消、调度模式 0/1/2/3 差异等。
- 输出：时序图 + 调度 FAQ 文档。

## 第 3 周：Spider 实战与插件

- 精读 `bricks/spider/air.py`，实现一个自定义 Spider（含请求、解析、存储或打印）。
- 对比 `form` 或 `template` Spider，体验配置式开发路径。
- 编写至少两个插件（如请求日志、指标上报、条件脚本），练习事件注册、`Context.get_context()` 与 `signals` 控制。
- 操作 TaskQueue：演练 `submit/branch/background`、成功/失败重试路径。
- 输出：“Spider 实战日志”，记录 Context 字段、插件钩子、队列操作要点。

## 第 4 周：高级主题与小功能迭代

- 深入 `lib/queues`、`downloader`、`client/runner` 等扩展点；如条件允许，临时搭建 Redis 验证分布式队列表现。
- 选择一个小功能进行实现（示例：新增调度策略参数、扩展 downloader、增强 CLI 校验或日志输出），并编写设计说明/简单测试。
- 了解 RPC (`bricks/client/runner.py`, `bricks/rpc/*`)，尝试把 Spider 暴露为 API（可选）。
- 输出：改动说明 + 回顾总结，说明如何定位源码并实施修改。

## 持续动作

- 每周末复盘，将阅读/实验心得追加到 `learning_plan.md` 或个人笔记。
- 若后续配置 Redis，在第 3~4 周追加“分布式队列”实验，重点观察任务持久化、多进程协调与性能差异。
- 关注开放问题（调度持久化、worker 缩容、重试策略等），形成后续优化 backlog。

---

## 每日任务拆分（28 天）

说明：请先在下方填写“开始日期”，然后为每一日的“日期”填写实际日期（YYYY-MM-DD）。如周末休息，可将对应日调整为“缓冲/复盘/选修”。

- 开始日期：2025-11-13（YYYY-MM-DD）

### Day 1
- 日期：2025-11-13
- 目标：完成环境搭建并跑通 1 个示例
- 任务：
  - 安装依赖与基础工具；运行 `example` 中任一 Spider，观察日志与输出
  - 记录启动链路（CLI → Runner → Spider）
- 资料：`README.md:1`、`manager.py:1`、`bricks/client/manage.py:1`、`bricks/client/runner.py:1`
- 难度：2/5；预计时长：3h
- 今日总结：
  执行链路（以 `python manager.py run_task -m example/spider/air.py --workdir /Users/zhouzhixin/ai/bricks` 为例）

  ```mermaid
  flowchart TD
    A[CLI 命令] --> B[Manager.run 收集 argv]
    B --> C[Manager._parse + Argv.get_parser]
    C -->|--workdir| C2[设置 sys.path 与 chdir]
    C --> D[构造 Argv 数据类]
    D --> E[run_adapter(form=run_task)]
    E --> F[Manager.run_task → BaseRunner.run_task]
    F -->|无 rpc| G[BaseRunner.run_local]
    G -->|main 是文件| H[exec example/spider/air.py]
    H --> I[__main__ 新建 MySpider 并 run]
    I --> J[元类织入/注册事件 + 初始化 Dispatcher]
    J --> K[on_consume 主循环：事件/下载/解析/队列/存储]
  ```

  备注：`--workdir` 会影响模块导入与相对路径；`-env` 在解析阶段直接写入 `os.environ`；`manage.py` 会输出两行调试打印便于观察参数。

  ASCII 版本（便于快速回顾）

  ```
  CLI: python manager.py run_task -m example/spider/air.py --workdir ...
      |
      v
  Manager.run()
      |
      v
  Manager._parse() -> Argv.get_parser() -> set_work_dir()
      |
      v
  Argv(filename, form=run_task, main=example/spider/air.py, ...)
      |
      v
  Manager.run_adapter(form=run_task) -> Manager.run_task()
      |
      v
  BaseRunner.run_task(argv)
      |
      v
  [无 rpc] BaseRunner.run_local(argv)
      |
      v
  exec('example/spider/air.py', {"__name__":"__main__", ...})
      |
      v
  MySpider().run()  ->  元类织入/注册事件  ->  Pangu 初始化 Dispatcher
                                      |
                                      v
                           on_consume 主循环（事件/下载/解析/队列/存储）
  ```

### Day 2
- 日期：____
- 目标：建立全局认知与目录地图
- 任务：
  - 精读 `bricks_architecture.md`，绘制目录结构与生命周期事件导图
  - 标注关键入口与扩展点
- 资料：`bricks_architecture.md:1`
- 难度：2/5；预计时长：3h
- 今日总结：
  目录速览与关键模块（简版）

  ```
  .
  ├─ manager.py                    # 顶层入口，调用 bricks/client/manage.py
  ├─ bricks/
  │  ├─ core/
  │  │  ├─ genesis.py             # Chaos/Pangu，生命周期与调度接入
  │  │  ├─ context.py             # Context/Flow，分支/回滚/后台
  │  │  ├─ events.py              # 事件注册与触发
  │  │  └─ dispatch.py            # Dispatcher/Worker/Task 线程级调度
  │  ├─ utils/
  │  │  └─ scheduler.py           # 时间级调度（cron/interval/date）
  │  ├─ spider/                   # air/form/template 三类爬虫
  │  ├─ downloader/               # 请求实现（curl-cffi/requests/...）
  │  ├─ lib/                      # queues/items/request/response/proxies 等
  │  ├─ plugins/                  # on_request 等插件（事件前后钩子）
  │  └─ client/                   # manage/runner（CLI/RPC）
  └─ example/                     # 示例（spider/downloader/rpc/...）
  ```

  要点：
  - 双层调度：时间触发（utils.scheduler）+ 工作线程（core.dispatch）
  - 事件驱动：const 定义阶段事件，plugins 通过 EventManager 注入前后钩子
  - Flow 驱动：branch/background/rollback 形成“积木式”执行链
  - Chaos 运行：run 默认织入 before_start/before_close，再由两者内部触发事件

  今日学习补充要点：
  - 理解了完整命令执行链：`manager.py → Manager.run/_parse → Argv → BaseRunner.run_task → run_local(exec main 文件) → MySpider().run()`，以及 `--workdir` 和 `-a/-extra/-env/-rpc` 对运行环境的影响。
  - 看清了 `BaseRunner.run_local` 中 `exec(f.read(), {"__name__": "__main__", **argv.args, **argv.extra})` 的含义：使用自定义全局环境执行脚本，把 CLI 参数注入为全局变量，并触发 `if __name__ == "__main__"` 分支。
  - 深入了 `MetaClass + Chaos/Pangu` 生命周期织入：实例化时自动用 `_when_run/_when_before_start/_when_before_close` 包装对应方法，`run()` 实际执行顺序变为 `before_start → 业务 run → before_close`，两侧通过 `make_context + EventManager.invoke` 自动触发对应阶段事件。

  Chaos/MetaClass 运行与事件织入简要总结：

  ```
  spider = MySpider()  # 继承自 Chaos/Pangu

  # 实例化阶段（MetaClass.__call__）：
  # - _when_xxx 方法自动包装对应 xxx（如 run/before_start/before_close）
  # - 带 __event__ 的方法自动注册为事件处理器（通过 instance.use → EventManager）
  # - 若实现 install()，在拦截器与事件注册完成后调用一次

  spider.run(...)
    -> _when_run 包装：
       before_start()          # 前置钩子
         -> make_context(BEFORE_START)
         -> EventManager.invoke(...)  # 调用 BEFORE_START 事件
         -> 原始 before_start()
       原始 run(...) 逻辑
       before_close()          # 收尾钩子
         -> make_context(BEFORE_CLOSE)
         -> EventManager.invoke(...)  # 调用 BEFORE_CLOSE 事件
         -> 原始 before_close()
  ```

### Day 3
- 日期：____
- 目标：掌握 CLI/RPC 启动与参数解析
- 任务：
  - 阅读 `Manager._parse/run_adapter` 与 `BaseRunner.run_task`；尝试 base64/参数化启动
  - 记录 main 加载策略与 rpc 适配点
- 资料：`bricks/client/manage.py:1`、`bricks/client/runner.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：
  CLI/RPC 启动与参数解析要点

  ```
  CLI -> Argv.get_parser -> Manager._parse -> Argv(dataclass)
      -> run_adapter(form) -> Manager.run_task -> BaseRunner.run_task
      -> [无 rpc] run_local(exec 文件) | [有 rpc] RpcProxy.start
  ```

  参数映射（示例）：
  - 位置：`filename`=manager.py，`form`=run_task
  - 选项：`-m/--main`=example/spider/air.py；`--workdir`=项目根目录
  - 多次键值：`-a/--args`、`-extra/--extra`、`-env/--env`、`-rpc/--rpc`
  - 特殊：`base64://...` 支持整体命令打包后再解码

### Day 4
- 日期：____
- 目标：熟悉状态常量与事件枚举
- 任务：
  - 通读 `bricks/state.py`，整理 `const` 各阶段事件用途
  - 扫描 `plugins` 与 `core/events.py`，建立事件→插件映射表
- 资料：`bricks/state.py:1`、`bricks/core/events.py:1`、`bricks/plugins/on_request.py:1`
- 难度：3/5；预计时长：4h
- 今日总结：

### Day 5
- 日期：____
- 目标：第 1 周复盘与问题清单
- 任务：
  - 汇总本周启动链路、事件点位、问题与疑问
  - 在仓库创建学习笔记或 issue backlog
- 资料：本周笔记
- 难度：1/5；预计时长：2h
- 今日总结：

### Day 6（可选）
- 日期：____
- 目标：缓冲/补坑
- 任务：补齐前几日未完成项或加深任一主题
- 难度：1/5；预计时长：弹性
- 今日总结：

### Day 7（可选）
- 日期：____
- 目标：选修阅读或休息
- 任务：可预研下载器或代理管理
- 资料：`bricks/downloader/__init__.py:1`、`bricks/lib/proxies.py:1`
- 难度：1/5；预计时长：弹性
- 今日总结：

### Day 8
- 日期：____
- 目标：理解元类装配与生命周期骨架
- 任务：
  - 精读 `genesis.py`（MetaClass/Chaos/Pangu），梳理 `_when_*` 与 `install()` 注入点
  - 画出 `run/launch` 触发路径
- 资料：`bricks/core/genesis.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 9
- 日期：____
- 目标：掌握 Flow 的分支/回滚/后台任务
- 任务：
  - 阅读 `context.py` 中 `Context/Flow`、`branch/rollback/background`
  - 用小函数验证 `background(action=submit/active)` 行为
- 资料：`bricks/core/context.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 10
- 日期：____
- 目标：深入事件注册与触发
- 任务：
  - 阅读 `core/events.py`，梳理 permanent/disposable 注册区别与匹配规则
  - 编写 1 个最小插件并验证触发
- 资料：`bricks/core/events.py:1`、`bricks/plugins/on_request.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 11
- 日期：____
- 目标：掌握线程级调度 Dispatcher
- 任务：
  - 读 `dispatch.py`，理解 `_TaskQueue/Worker/Dispatcher`
  - 写 demo：提交同步与异步任务、观察 worker 伸缩与取消
- 资料：`bricks/core/dispatch.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 12
- 日期：____
- 目标：掌握时间级调度 Scheduler
- 任务：
  - 读 `scheduler.py`，理解 `BaseTrigger` 模式与 `Cron/Interval/Date`
  - 用 `get_fire_times()` 验证表达式与不同 mode 的影响
- 资料：`bricks/utils/scheduler.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 13
- 日期：____
- 目标：整理“调度 FAQ”与时序图
- 任务：总结 Dispatcher×Scheduler 协作、常见陷阱与优化点
- 难度：2/5；预计时长：2h
- 今日总结：

### Day 14（可选）
- 日期：____
- 目标：缓冲/补坑
- 难度：1/5；预计时长：弹性
- 今日总结：

### Day 15
- 日期：____
- 目标：精读 Air Spider
- 任务：
  - 学习 `bricks/spider/air.py` 的 `Context` 字段与信号控制
  - 跟踪一次完整请求→解析→存储流程
- 资料：`bricks/spider/air.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 16
- 日期：____
- 目标：实现第一个自定义 Spider
- 任务：
  - 选择公开接口/页面作为数据源，完成请求与解析
  - 使用本地队列完成最小 pipeline（或打印）
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 17
- 日期：____
- 目标：编写请求前后插件
- 任务：
  - 实现 `Before.fake_ua` 或日志打印插件，接入事件流
  - 使用 `Context.get_context()` 读取 request/response
- 资料：`bricks/plugins/on_request.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 18
- 日期：____
- 目标：掌握 TaskQueue 常用操作
- 任务：
  - 练习 `put/replace/remove` 与 `success/failure/retry`
  - 验证 `division/branch/background` 行为差异
- 资料：`bricks/lib/queues/__init__.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 19
- 日期：____
- 目标：体验配置式 Spider（form/template）
- 任务：
  - 运行并对比配置项与 Air 的差异；评估适用场景
- 资料：`bricks/spider/form.py:1`、`bricks/spider/template.py:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 20
- 日期：____
- 目标：实现第二个插件（指标/告警）
- 任务：
  - 记录响应时间/状态码，或对异常进行上报
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 21（可选）
- 日期：____
- 目标：第 3 周复盘与补坑
- 难度：2/5；预计时长：弹性
- 今日总结：

### Day 22
- 日期：____
- 目标：深入队列实现与分布式准备
- 任务：
  - 阅读 Local/Redis/Smart 队列差异；如可行，临时搭建 Redis 做最小验证
- 资料：`bricks/lib/queues/local.py:1`、`bricks/lib/queues/redis_.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 23
- 日期：____
- 目标：扩展 Downloader 或增强请求构建
- 任务：
  - 基于 `AbstractDownloader` 实现一个轻量扩展（如签名/鉴权/重试策略）
- 资料：`bricks/downloader/__init__.py:1`
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 24
- 日期：____
- 目标：了解 RPC 与 API 化（可选）
- 任务：
  - 尝试通过 `RpcProxy` 暴露 Spider；理解多模式（http/grpc/websocket）差异
- 资料：`bricks/client/runner.py:1`、`bricks/rpc:1`
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 25
- 日期：____
- 目标：选定小功能并完成设计
- 任务：
  - 候选示例：新增调度模式参数、下载器扩展、CLI 参数校验、日志格式优化
  - 写设计说明与改动影响面评估
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 26
- 日期：____
- 目标：实现小功能（编码）
- 任务：按设计方案完成实现与自测脚本
- 难度：4/5；预计时长：4h
- 今日总结：

### Day 27
- 日期：____
- 目标：测试与文档
- 任务：
  - 增补示例与使用说明；根据需要编写最小测试或脚本
- 难度：3/5；预计时长：3h
- 今日总结：

### Day 28
- 日期：____
- 目标：总结与展望
- 任务：
  - 输出技术复盘（调度、事件、队列、扩展点）；列出后续优化 backlog
- 难度：2/5；预计时长：2h
- 今日总结：
