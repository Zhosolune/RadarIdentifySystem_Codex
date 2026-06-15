"""会话日志上下文单元测试。

验证 app/logger.py 中 RuntimeContextFilter 与 session_id contextvar 的协同行为，
确保 core/infra 层在 Worker 绑定 session 后，日志能自动带上正确的 session_id，
为未来多数据包并行处理提供可靠的会话区分标记。
"""

from __future__ import annotations

import logging

from app.logger import (
    RuntimeContextFilter,
    _session_id_ctx,
    bind_session_log_context,
    unbind_session_log_context,
)


def _make_record(session_id_set: bool) -> logging.LogRecord:
    """构造一条日志记录。

    功能描述：
        生成最小可用的 LogRecord，用于驱动 Filter.filter()。
        session_id_set 为 True 时附加 session_id 属性，模拟显式 extra 传参。

    参数说明：
        session_id_set (bool): 是否在 record 上预置 session_id 属性。

    返回值说明：
        logging.LogRecord: 构造的日志记录对象。

    异常说明：
        无。
    """
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="测试消息",
        args=None,
        exc_info=None,
    )
    if session_id_set:
        record.session_id = "EXPLICIT"  # 模拟显式 extra 传参
    return record


def test_filter_defaults_to_dash_when_unbound() -> None:
    """未绑定 context 时，Filter 应回退为默认值 '-'。

    功能描述：
        验证启动阶段或无 session 上下文时，日志 session_id 字段为 '-'。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当 session_id 不为 '-' 时抛出。
    """
    # 确保未被绑定（防御其他测试污染）
    assert _session_id_ctx.get() == "-"

    filt = RuntimeContextFilter()
    record = _make_record(session_id_set=False)
    filt.filter(record)

    assert record.session_id == "-"


def test_filter_picks_up_bound_context() -> None:
    """绑定 context 后，Filter 应回填绑定的 session_id。

    功能描述：
        模拟 Worker.run() 入口 bind_session_log_context 的场景，
        验证未显式传 extra 的日志自动归属当前 session。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当 session_id 不为绑定值时抛出。
    """
    token = bind_session_log_context("SESS_A")
    try:
        filt = RuntimeContextFilter()
        record = _make_record(session_id_set=False)
        filt.filter(record)

        assert record.session_id == "SESS_A"
    finally:
        unbind_session_log_context(token)


def test_explicit_extra_overrides_context() -> None:
    """显式 extra 优先于 contextvar 兜底。

    功能描述：
        验证当调用方已通过 extra 主动传参时，Filter 不用 contextvar 覆盖，
        保留显式传参的优先级。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当 session_id 被覆盖为绑定值时抛出。
    """
    token = bind_session_log_context("SESS_A")
    try:
        filt = RuntimeContextFilter()
        record = _make_record(session_id_set=True)  # 已带 "EXPLICIT"
        filt.filter(record)

        assert record.session_id == "EXPLICIT"
    finally:
        unbind_session_log_context(token)


def test_unbind_restores_previous_value() -> None:
    """unbind 应回退到 bind 前的状态。

    功能描述：
        验证 finally 中的 unbind_session_log_context 能正确复位 contextvar，
        防止 session_id 泄漏到线程池复用的后续无关日志。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当复位后值不正确时抛出。
    """
    assert _session_id_ctx.get() == "-"

    token = bind_session_log_context("SESS_B")
    assert _session_id_ctx.get() == "SESS_B"

    unbind_session_log_context(token)
    assert _session_id_ctx.get() == "-"


def test_nested_bindings_restore_in_order() -> None:
    """嵌套绑定时，unbind 应按序复位（栈式语义）。

    功能描述：
        模拟主线程 workflow 绑定后，再进入嵌套作用域绑定不同 session，
        验证内层 unbind 后回到外层值，外层 unbind 后回到默认值。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当任一层级复位后值不正确时抛出。
    """
    outer = bind_session_log_context("OUTER")
    try:
        assert _session_id_ctx.get() == "OUTER"

        inner = bind_session_log_context("INNER")
        try:
            assert _session_id_ctx.get() == "INNER"
        finally:
            unbind_session_log_context(inner)

        assert _session_id_ctx.get() == "OUTER"
    finally:
        unbind_session_log_context(outer)

    assert _session_id_ctx.get() == "-"
