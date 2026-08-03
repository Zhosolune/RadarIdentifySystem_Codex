"""不同 Session 独立日志文件路由测试。"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from pytest import MonkeyPatch

import app.logger as logger_module
from app.logger import (
    RuntimeContextFilter,
    SessionRoutingHandler,
    bind_session_log_context,
    build_session_log_file_path,
    clear_all_logs,
    unbind_session_log_context,
)
from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore
from runtime.session_registry import SessionRegistry


def _build_router_logger(
    log_dir: Path,
) -> tuple[logging.Logger, SessionRoutingHandler]:
    """构造不向 root 传播的 Session 路由测试日志器。"""
    formatter = logging.Formatter(
        "[%(session_id)s] %(message)s",
    )
    handler = SessionRoutingHandler(log_dir, formatter)
    handler.addFilter(RuntimeContextFilter())
    test_logger = logging.getLogger(f"session-router-{id(handler)}")
    test_logger.handlers.clear()
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)
    return test_logger, handler


def _close_router_logger(
    test_logger: logging.Logger,
    handler: SessionRoutingHandler,
) -> None:
    """关闭测试日志器及其 Session 文件。"""
    test_logger.removeHandler(handler)
    handler.close()


def test_router_writes_only_registered_session_to_its_own_file(
    tmp_path: Path,
) -> None:
    """路由器应隔离 Session，并忽略未注册的数据包 ID。"""
    test_logger, handler = _build_router_logger(tmp_path)
    session_a_path = handler.register_session("SESSION_A")
    session_b_path = handler.register_session("SESSION_B")
    package_path = build_session_log_file_path("PACKAGE_ONLY", tmp_path)

    try:
        assert not session_a_path.exists()
        assert not session_b_path.exists()

        test_logger.info("A 的消息", extra={"session_id": "SESSION_A"})
        test_logger.info("B 的消息", extra={"session_id": "SESSION_B"})
        test_logger.info(
            "数据包导入消息",
            extra={"session_id": "PACKAGE_ONLY"},
        )
        handler.unregister_session("SESSION_A")
        test_logger.info(
            "A 注销后的消息",
            extra={"session_id": "SESSION_A"},
        )
    finally:
        _close_router_logger(test_logger, handler)

    assert "A 的消息" in session_a_path.read_text(encoding="utf-8")
    assert "B 的消息" not in session_a_path.read_text(encoding="utf-8")
    assert "A 注销后的消息" not in session_a_path.read_text(encoding="utf-8")
    assert "B 的消息" in session_b_path.read_text(encoding="utf-8")
    assert "A 的消息" not in session_b_path.read_text(encoding="utf-8")
    assert not package_path.exists()


def test_configure_logging_keeps_global_and_session_files(
    tmp_path: Path,
) -> None:
    """应用日志配置应同时保留全局文件和 Session 独立文件。"""
    project_root = Path(__file__).resolve().parents[2]
    script = "\n".join(
        (
            "import logging",
            "from app.logger import (",
            "    configure_logging,",
            "    register_session_log,",
            "    shutdown_logging,",
            ")",
            f"configure_logging({str(tmp_path)!r})",
            "register_session_log('SESSION_A')",
            "logger = logging.getLogger('integration')",
            "logger.info('session message', extra={'session_id': 'SESSION_A'})",
            "logger.info('global message', extra={'session_id': '-'})",
            "shutdown_logging()",
        )
    )

    subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    global_files = list(
        tmp_path.glob("RadarIdentifySystem_run_*.log")
    )
    session_files = list(
        (
            tmp_path
            / "sessions"
            / "SESSION_A"
        ).glob("RadarIdentifySystem_session_SESSION_A_*.log")
    )
    assert len(global_files) == 1
    assert len(session_files) == 1
    global_text = global_files[0].read_text(encoding="utf-8")
    session_text = session_files[0].read_text(encoding="utf-8")
    assert "session message" in global_text
    assert "global message" in global_text
    assert "session message" in session_text
    assert "global message" not in session_text


@pytest.mark.parametrize(
    ("configured_level", "expected_messages"),
    (
        ("DEBUG", ("debug-message", "info-message", "warn-message", "error-message")),
        ("INFO", ("info-message", "warn-message", "error-message")),
        ("WARN", ("warn-message", "error-message")),
        ("ERROR", ("error-message",)),
    ),
)
def test_configure_logging_filters_global_and_session_files_by_level(
    tmp_path: Path,
    configured_level: str,
    expected_messages: tuple[str, ...],
) -> None:
    """四级阈值应同时过滤全局日志与 Session 独立日志。"""
    project_root = Path(__file__).resolve().parents[2]
    level_dir = tmp_path / configured_level
    script = "\n".join(
        (
            "import logging",
            "from app.logger import configure_logging, register_session_log, shutdown_logging",
            f"configure_logging({str(level_dir)!r}, {configured_level!r})",
            "register_session_log('SESSION_LEVEL')",
            "logger = logging.getLogger('level-integration')",
            "logger.debug('debug-message', extra={'session_id': 'SESSION_LEVEL'})",
            "logger.info('info-message', extra={'session_id': 'SESSION_LEVEL'})",
            "logger.warning('warn-message', extra={'session_id': 'SESSION_LEVEL'})",
            "logger.error('error-message', extra={'session_id': 'SESSION_LEVEL'})",
            "shutdown_logging()",
        )
    )

    subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    global_file = next(level_dir.glob("RadarIdentifySystem_run_*.log"))
    session_file = next(
        (level_dir / "sessions" / "SESSION_LEVEL").glob(
            "RadarIdentifySystem_session_SESSION_LEVEL_*.log"
        )
    )
    all_messages = {
        "debug-message",
        "info-message",
        "warn-message",
        "error-message",
    }
    for log_file in (global_file, session_file):
        content = log_file.read_text(encoding="utf-8")
        for message in expected_messages:
            assert message in content
        for message in all_messages - set(expected_messages):
            assert message not in content
        if configured_level in {"DEBUG", "INFO", "WARN"}:
            assert "[WARN]" in content


def test_set_log_level_applies_immediately_without_reconfigure(
    tmp_path: Path,
) -> None:
    """运行时修改等级后应立即更新现有全局与 Session Handler。"""
    project_root = Path(__file__).resolve().parents[2]
    script = "\n".join(
        (
            "import logging",
            "from app.logger import configure_logging, register_session_log, set_log_level, shutdown_logging",
            f"configure_logging({str(tmp_path)!r}, 'DEBUG')",
            "register_session_log('SESSION_DYNAMIC')",
            "logger = logging.getLogger('dynamic-integration')",
            "logger.debug('before-change', extra={'session_id': 'SESSION_DYNAMIC'})",
            "set_log_level('WARN')",
            "logger.info('filtered-after-change', extra={'session_id': 'SESSION_DYNAMIC'})",
            "logger.warning('kept-after-change', extra={'session_id': 'SESSION_DYNAMIC'})",
            "shutdown_logging()",
        )
    )

    subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    global_file = next(tmp_path.glob("RadarIdentifySystem_run_*.log"))
    session_file = next(
        (tmp_path / "sessions" / "SESSION_DYNAMIC").glob(
            "RadarIdentifySystem_session_SESSION_DYNAMIC_*.log"
        )
    )
    for log_file in (global_file, session_file):
        content = log_file.read_text(encoding="utf-8")
        assert "before-change" in content
        assert "filtered-after-change" not in content
        assert "kept-after-change" in content


def test_router_keeps_concurrent_bound_contexts_separate(
    tmp_path: Path,
) -> None:
    """并发线程绑定不同上下文时应分别写入对应 Session 文件。"""
    test_logger, handler = _build_router_logger(tmp_path)
    session_a_path = handler.register_session("SESSION_A")
    session_b_path = handler.register_session("SESSION_B")

    def write_session_messages(session_id: str, prefix: str) -> None:
        """在线程上下文中连续写入当前 Session 消息。"""
        token = bind_session_log_context(session_id)
        try:
            for index in range(20):
                test_logger.info("%s-%d", prefix, index)
        finally:
            unbind_session_log_context(token)

    threads = [
        threading.Thread(
            target=write_session_messages,
            args=("SESSION_A", "A"),
        ),
        threading.Thread(
            target=write_session_messages,
            args=("SESSION_B", "B"),
        ),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        _close_router_logger(test_logger, handler)

    session_a_text = session_a_path.read_text(encoding="utf-8")
    session_b_text = session_b_path.read_text(encoding="utf-8")
    assert session_a_text.count("[SESSION_A] A-") == 20
    assert "[SESSION_B]" not in session_a_text
    assert session_b_text.count("[SESSION_B] B-") == 20
    assert "[SESSION_A]" not in session_b_text


def test_clear_all_logs_deletes_history_but_keeps_current_files(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """日志清理应覆盖 Session 历史文件并保留当前占用文件。"""
    current_global = tmp_path / "RadarIdentifySystem_run_current.log"
    current_global.write_text("current", encoding="utf-8")
    historical_global = tmp_path / "RadarIdentifySystem_run_old.log"
    historical_global.write_text("old", encoding="utf-8")
    historical_session = (
        tmp_path
        / "sessions"
        / "OLD_SESSION"
        / "RadarIdentifySystem_session_OLD_SESSION_old.log"
    )
    historical_session.parent.mkdir(parents=True)
    historical_session.write_text("old session", encoding="utf-8")

    test_logger, handler = _build_router_logger(tmp_path)
    current_session = handler.register_session("CURRENT_SESSION")
    test_logger.info(
        "current session",
        extra={"session_id": "CURRENT_SESSION"},
    )
    monkeypatch.setattr(
        logger_module,
        "_CURRENT_LOG_FILE_PATH",
        current_global,
    )
    monkeypatch.setattr(logger_module, "_SESSION_LOG_HANDLER", handler)

    try:
        deleted_count = clear_all_logs(tmp_path)
    finally:
        monkeypatch.setattr(logger_module, "_SESSION_LOG_HANDLER", None)
        _close_router_logger(test_logger, handler)

    assert deleted_count == 2
    assert current_global.exists()
    assert current_session.exists()
    assert not historical_global.exists()
    assert not historical_session.exists()


def test_session_registry_controls_log_route_lifecycle(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Session 注册、恢复和删除应同步日志路由生命周期。"""
    registered: list[str] = []
    unregistered: list[str] = []

    def record_registration(session_id: str) -> None:
        """记录一次 Session 日志注册。"""
        registered.append(session_id)

    def record_unregistration(session_id: str) -> None:
        """记录一次 Session 日志注销。"""
        unregistered.append(session_id)

    monkeypatch.setattr(
        "runtime.session_registry.register_session_log",
        record_registration,
    )
    monkeypatch.setattr(
        "runtime.session_registry.unregister_session_log",
        record_unregistration,
    )
    store = SessionStore(tmp_path / "sessions")
    registry = SessionRegistry(store)
    session = ProcessingSession(session_id="SESSION_A")

    registry.register(session)
    registry.close(session.session_id, delete_persisted=False)
    restored_registry = SessionRegistry(store)
    restored_registry.restore()

    assert registered == ["SESSION_A", "SESSION_A"]
    assert unregistered == ["SESSION_A"]
