import functools

class MetaClass(type):
    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)

        # 1) 收集事件处理函数：按 tag 分类
        instance._events = {}
        for name in dir(instance):
            func = getattr(instance, name)
            if callable(func) and hasattr(func, "__event__"):
                tag = func.__event__
                instance._events.setdefault(tag, []).append(func)

        # 2) 处理 _when_ 拦截器：自动包裹原方法
        for name in dir(instance):
            if not name.startswith("_when_"):
                continue
            raw_name = name.replace("_when_", "")
            raw_method = getattr(instance, raw_name, None)
            if not raw_method:
                continue
            wrapper_factory = getattr(instance, name)
            setattr(instance, raw_name, wrapper_factory(raw_method))

        return instance


def on_event(tag: str):
    """装饰器：给函数挂上 __event__ 标签"""
    def decorator(func):
        func.__event__ = tag
        return func
    return decorator


class Demo(metaclass=MetaClass):
    def run(self, x: int):
        print(f"  [run] 真实业务逻辑，x = {x}")

    def _when_run(self, raw):
        """拦截 run：前后日志 + 运行后触发 after_run 事件"""
        @functools.wraps(raw)
        def wrapper(*args, **kwargs):
            print(">>> before run")
            for f in self._events.get("before_run", []):
                f()
            ret = raw(*args, **kwargs)
            print("<<< after run")

            # 运行完后自动触发 tag == "after_run" 的事件处理函数
            for f in self._events.get("after_run", []):
                f()
            return ret
        return wrapper

    @on_event("after_run")
    def handle_after_run(self):
        print("  [event] handle_after_run 自动在 run() 后被调用")

    @on_event("before_run")
    def handle_before_run(self):
        print("  [event] handle_before_run 自动在 run() 前被调用")

    @on_event("custom")
    def other_handler(self):
        print("  [event] other_handler（不会自动触发，因为 tag=custom）")


if __name__ == "__main__":
    demo = Demo()
    demo.run(42)
