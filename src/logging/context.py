"""
日志上下文管理模块.

提供基于 contextvars 的上下文管理，支持：
- Trace ID 追踪
- Request ID 追踪
- 自定义上下文数据
- 异步安全的上下文传递
"""

import uuid
from contextvars import ContextVar, copy_context
from functools import wraps
from typing import Any, Callable, TypeVar

# 上下文变量定义
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
_extra_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "extra_context", default=None
)

F = TypeVar("F", bound=Callable[..., Any])


def generate_trace_id() -> str:
    """生成唯一的 trace ID."""
    return uuid.uuid4().hex[:16]


def generate_request_id() -> str:
    """生成唯一的 request ID."""
    return uuid.uuid4().hex[:12]


# Trace ID 操作
def set_trace_id(trace_id: str | None = None) -> str:
    """设置 trace ID，如果未提供则自动生成."""
    if trace_id is None:
        trace_id = generate_trace_id()
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    """获取当前 trace ID."""
    return _trace_id.get()


def clear_trace_id() -> None:
    """清除 trace ID."""
    _trace_id.set(None)


# Request ID 操作
def set_request_id(request_id: str | None = None) -> str:
    """设置 request ID，如果未提供则自动生成."""
    if request_id is None:
        request_id = generate_request_id()
    _request_id.set(request_id)
    return request_id


def get_request_id() -> str | None:
    """获取当前 request ID."""
    return _request_id.get()


def clear_request_id() -> None:
    """清除 request ID."""
    _request_id.set(None)


# User ID 操作
def set_user_id(user_id: str | None) -> None:
    """设置用户 ID."""
    _user_id.set(user_id)


def get_user_id() -> str | None:
    """获取当前用户 ID."""
    return _user_id.get()


# Session ID 操作
def set_session_id(session_id: str | None) -> None:
    """设置会话 ID."""
    _session_id.set(session_id)


def get_session_id() -> str | None:
    """获取当前会话 ID."""
    return _session_id.get()


# 额外上下文操作
def set_context(key: str, value: Any) -> None:
    """设置额外的上下文数据."""
    ctx = _extra_context.get()
    if ctx is None:
        ctx = {}
    ctx = ctx.copy()
    ctx[key] = value
    _extra_context.set(ctx)


def get_context(key: str, default: Any = None) -> Any:
    """获取额外的上下文数据."""
    ctx = _extra_context.get()
    if ctx is None:
        return default
    return ctx.get(key, default)


def get_all_context() -> dict[str, Any]:
    """获取所有上下文数据."""
    result = {}

    trace_id = get_trace_id()
    if trace_id:
        result["trace_id"] = trace_id

    request_id = get_request_id()
    if request_id:
        result["request_id"] = request_id

    user_id = get_user_id()
    if user_id:
        result["user_id"] = user_id

    session_id = get_session_id()
    if session_id:
        result["session_id"] = session_id

    extra = _extra_context.get()
    if extra:
        result.update(extra)

    return result


def clear_all_context() -> None:
    """清除所有上下文数据."""
    _trace_id.set(None)
    _request_id.set(None)
    _user_id.set(None)
    _session_id.set(None)
    _extra_context.set({})


class LogContext:
    """日志上下文管理器，支持 with 语句."""

    def __init__(
        self,
        trace_id: str | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        auto_generate_trace: bool = True,
        **extra: Any,
    ) -> None:
        self._trace_id = trace_id
        self._request_id = request_id
        self._user_id = user_id
        self._session_id = session_id
        self._auto_generate_trace = auto_generate_trace
        self._extra = extra
        self._tokens: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        # 保存当前值并设置新值
        if self._trace_id or self._auto_generate_trace:
            self._tokens["trace_id"] = _trace_id.set(
                self._trace_id or generate_trace_id()
            )

        if self._request_id:
            self._tokens["request_id"] = _request_id.set(self._request_id)

        if self._user_id:
            self._tokens["user_id"] = _user_id.set(self._user_id)

        if self._session_id:
            self._tokens["session_id"] = _session_id.set(self._session_id)

        if self._extra:
            old_extra = _extra_context.get() or {}
            new_extra = {**old_extra, **self._extra}
            self._tokens["extra_context"] = _extra_context.set(new_extra)

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 恢复原始值
        for name, token in self._tokens.items():
            var = {
                "trace_id": _trace_id,
                "request_id": _request_id,
                "user_id": _user_id,
                "session_id": _session_id,
                "extra_context": _extra_context,
            }.get(name)
            if var:
                var.reset(token)


def with_trace(func: F) -> F:
    """装饰器：为函数调用自动添加 trace ID."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with LogContext(auto_generate_trace=True):
            return func(*args, **kwargs)

    return wrapper  # type: ignore


def with_context(**context_kwargs: Any) -> Callable[[F], F]:
    """装饰器：为函数调用添加指定的上下文."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with LogContext(**context_kwargs):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def copy_context_to_thread(func: F) -> F:
    """装饰器：将上下文复制到新线程."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx = copy_context()
        return ctx.run(func, *args, **kwargs)

    return wrapper  # type: ignore
