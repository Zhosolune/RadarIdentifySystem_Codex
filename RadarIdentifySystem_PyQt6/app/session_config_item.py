"""Session 设置卡适配项。

该模块提供面向 app/UI 层的轻量配置适配，绑定 ``SessionConfigSnapshot`` 的点号路径字段。
它不是全局 ``qconfig`` 的直接替代品，不能直接传给 qfluentwidgets 的全局
``qconfig.set()`` 使用；后续应通过 ``SessionConfigWriter`` 或手动信号绑定写入 session 快照。

Example:
    >>> from core.models.session_config import SessionConfigSnapshot
    >>> snapshot = SessionConfigSnapshot.default()
    >>> item = SessionConfigItem(snapshot, "clustering.eps_cf", 2.0)
    >>> SessionConfigWriter().set(item, 3.5)
    >>> snapshot.clustering.eps_cf
    3.5
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal
from qfluentwidgets import BoolValidator, RangeValidator

from core.models.session_config import SessionConfigSnapshot


ValidatorType = BoolValidator | RangeValidator


class SessionConfigItem(QObject):
    """绑定到 session 配置快照字段的轻量配置项。

    该类只面向 session 专用设置卡或手动绑定，不兼容全局 ``qconfig.set()``。

    Attributes:
        valueChanged: 字段值变更信号。
        snapshot: 目标 session 配置快照。
        group: 字段路径所属分组。
        name: 字段名称。
        path: 点号分隔字段路径。
        validator: 可选 qfluentwidgets 校验器。
        defaultValue: 配置项默认值。
        value: 当前字段值。
    """

    valueChanged = pyqtSignal(object)

    def __init__(
        self,
        snapshot: SessionConfigSnapshot,
        path: str,
        default: object,
        validator: ValidatorType | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        """创建 session 配置项。

        Args:
            snapshot [SessionConfigSnapshot]: 目标 session 配置快照。
            path [str]: 点号分隔的字段路径，至少包含两段，例如 ``clustering.eps_cf``。
            default [object]: 默认值。
            validator [ValidatorType | None]: qfluentwidgets 校验器，默认不校验。
            on_changed [Callable[[], None] | None]: 值变化后的保存回调，默认不回调。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当字段路径不合法或字段不存在时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "clustering.eps_cf", 2.0)
            >>> item.set(3.5)
            >>> snapshot.clustering.eps_cf
            3.5
        """
        super().__init__()
        self.snapshot = snapshot
        self.path = path
        self.group, self.name = self._split_path(path)
        self.validator = validator
        self.defaultValue = default
        self._on_changed = on_changed
        self._read()

    @property
    def value(self) -> object:
        """返回当前字段值。

        Returns:
            object: 当前绑定字段的值。

        Raises:
            ValueError: 当字段路径不合法或字段不存在时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> SessionConfigItem(snapshot, "recognition.max_candidates", 5).value
            5
        """
        return self._read()

    @value.setter
    def value(self, new_value: object) -> None:
        self.set(new_value)

    def set(self, new_value: object) -> None:
        """设置当前字段值并触发保存回调。

        Args:
            new_value [object]: 需要写入的新值，会先经过可选校验器修正。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当字段路径不合法或字段不存在时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "business.auto_export", False)
            >>> item.set(True)
            >>> item.value
            True
        """
        corrected = self.validator.correct(new_value) if self.validator else new_value
        old_value = self._read()
        if old_value == corrected:
            return

        # 先写回快照，确保信号订阅方读取到最新 session 配置值。
        self._write(corrected)
        self.valueChanged.emit(corrected)
        if self._on_changed:
            self._on_changed()

    @staticmethod
    def _split_path(path: str) -> tuple[str, str]:
        """拆分并校验点号路径。"""
        parts = path.split(".")
        if len(parts) < 2 or any(not part for part in parts):
            raise ValueError(f"无效的 session 配置路径：{path}")
        return ".".join(parts[:-1]), parts[-1]

    def _target(self) -> tuple[object, str]:
        """返回字段所属对象与字段名。"""
        target: object = self.snapshot
        parts = self.path.split(".")
        for part in parts[:-1]:
            if not hasattr(target, part):
                raise ValueError(f"无效的 session 配置路径：{self.path}")
            target = getattr(target, part)

        field_name = parts[-1]
        if not hasattr(target, field_name):
            raise ValueError(f"无效的 session 配置路径：{self.path}")
        return target, field_name

    def _read(self) -> object:
        """读取绑定字段。"""
        target, field_name = self._target()
        return getattr(target, field_name)

    def _write(self, value: object) -> None:
        """写入绑定字段。"""
        target, field_name = self._target()
        setattr(target, field_name, value)


class SessionConfigWriter:
    """Session 设置项读写器。

    该写入器用于后续自定义 writer 版本设置卡或手动绑定，不修改全局 ``qconfig`` 状态。
    """

    def get(self, item: SessionConfigItem) -> object:
        """读取 session 设置项当前值。

        Args:
            item [SessionConfigItem]: 需要读取的 session 设置项。

        Returns:
            object: 设置项绑定字段的当前值。

        Raises:
            ValueError: 当设置项路径不合法或字段不存在时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "business.auto_export", False)
            >>> SessionConfigWriter().get(item)
            False
        """
        return item.value

    def set(self, item: SessionConfigItem, value: object) -> None:
        """写入 session 设置项当前值。

        Args:
            item [SessionConfigItem]: 需要写入的 session 设置项。
            value [object]: 需要写入的新值。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当设置项路径不合法或字段不存在时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "business.auto_export", False)
            >>> SessionConfigWriter().set(item, True)
            >>> snapshot.business.auto_export
            True
        """
        item.set(value)
