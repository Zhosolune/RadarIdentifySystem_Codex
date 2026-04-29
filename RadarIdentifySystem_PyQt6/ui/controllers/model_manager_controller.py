# -*- coding: utf-8 -*-
"""模型管理控制器。"""

import os
import shutil
import stat
from pathlib import Path
import logging

from PyQt6.QtCore import QObject, Qt
from qfluentwidgets import InfoBar, InfoBarPosition, BodyLabel

from app.model_bootstrap import (
    collect_available_model_files,
    ensure_user_model_dir,
    get_builtin_model_dir,
    get_display_name,
    get_user_model_dir,
    is_builtin_model,
    resolve_enabled_model,
    set_enabled_model_path,
)
from ui.dialogs.import_model_dialog import ImportModelDialog
from ui.dialogs.rename_model_dialog import RenameModelDialog
from ui.dialogs.delete_model_dialog import DeleteModelDialog
from ui.dialogs.edit_model_remark_dialog import EditModelRemarkDialog
from ui.components.model_item_card import ModelItemCard
from infra.model_registry import ModelRegistry

LOGGER = logging.getLogger(__name__)

class ModelManagerController(QObject):
    """模型管理控制器。

    负责处理模型管理界面的业务逻辑，包括加载模型列表、导入模型、重命名和删除操作。

    Args:
        view (ModelManagerInterface): 绑定的视图实例。
    """

    def __init__(self, view) -> None:
        """初始化模型管理控制器。

        绑定视图对象，并连接按钮点击与配置变更信号。

        Args:
            view (ModelManagerInterface): 绑定的视图实例。
        """
        super().__init__(view)
        self.view = view

        # 绑定视图交互信号
        self.view.import_model_card.button.clicked.connect(self.handle_import_model)
        self.view.segmentedWidget.currentItemChanged.connect(self._on_segment_changed)

        # 加载当前分页列表
        self.load_models()

    def _on_segment_changed(self, item_key: str):
        """处理分段组件切换事件。

        Args:
            item_key (str): 切换的目标项路由标识（如 "PA" 或 "DTOA"）。
        """
        self.load_models()

    def load_models(self):
        """加载并渲染模型列表。

        清空当前列表容器，扫描目标目录下的模型文件，并生成卡片项添加到视图布局中。
        """
        # 清空当前列表
        while self.view.listLayout.count():
            item = self.view.listLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_route = self.view.segmentedWidget.currentRouteKey()
        current_type = current_route if current_route else "PA"

        try:
            model_files = self._collect_model_files(current_type)
            enabled_path = self._ensure_enabled_model_for_type(current_type)

            if not model_files:
                emptyLabel = BodyLabel(
                    "当前类型暂无可用模型，请先导入模型文件。"
                )
                # 设置空状态标签对象名，供样式表统一管理
                emptyLabel.setObjectName("modelEmptyLabel")
                # 设置空状态标签上边距，避免与顶部区域贴近
                emptyLabel.setContentsMargins(0, 40, 0, 0)
                emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.view.listLayout.addWidget(emptyLabel)
            else:
                for file_path in model_files:
                    is_system_default = self._is_builtin_model(file_path, current_type)
                    display_name = self._get_display_name(file_path, current_type)
                    remark_text = ModelRegistry.get_remark(file_path)
                    card = ModelItemCard(
                        current_type,
                        file_path,
                        display_name,
                        remark_text=remark_text,
                        is_enabled=os.path.normpath(file_path) == enabled_path,
                        is_system_default=is_system_default,
                        parent=self.view,
                    )
                    # 绑定卡片请求信号
                    card.deleteRequested.connect(self.request_delete_model)
                    card.renameRequested.connect(self.request_rename_model)
                    card.remarkRequested.connect(self.request_edit_remark)
                    card.enabledToggled.connect(self.handle_enable_toggled)
                    self.view.listLayout.addWidget(card)

            # 添加底部弹性空间，确保卡片从顶部开始排列
            self.view.listLayout.addStretch(1)

        except Exception as e:
            LOGGER.error(f"加载模型列表失败: {e}")

    def _get_builtin_model_dir(self, model_type: str) -> Path:
        """获取系统内置模型目录路径。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。

        Returns:
            Path: 系统内置模型目录绝对路径。

        Raises:
            ValueError: 不支持的模型类型会抛出异常。
        """
        return get_builtin_model_dir(model_type)

    def _get_user_model_dir(self, model_type: str) -> Path:
        """获取用户导入模型目录路径。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。

        Returns:
            Path: 用户模型目录绝对路径。

        Raises:
            ValueError: 不支持的模型类型会抛出异常。
        """
        return get_user_model_dir(model_type)

    def _is_builtin_model(self, file_path: str, model_type: str) -> bool:
        """判断模型是否属于系统内置目录。

        Args:
            file_path (str): 模型文件绝对路径。
            model_type (str): 模型类型。

        Returns:
            bool: 属于系统内置目录返回 True，否则返回 False。

        Raises:
            无。
        """
        return is_builtin_model(file_path, model_type)

    def _collect_model_files(self, model_type: str) -> list[str]:
        """收集指定类型的可用模型文件。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。

        Returns:
            list[str]: 系统目录与用户目录合并后的模型路径列表。

        Raises:
            ValueError: 不支持的模型类型会抛出异常。
        """
        return collect_available_model_files(model_type)

    def _infer_model_type(self, file_path: str) -> str:
        """根据模型路径推断模型类型。

        Args:
            file_path (str): 模型文件绝对路径。

        Returns:
            str: 推断出的模型类型，返回 ``PA`` 或 ``DTOA``。

        Raises:
            ValueError: 路径不在已知模型目录下时抛出异常。
        """
        normalized = os.path.normpath(file_path)
        for model_type in ("PA", "DTOA"):
            # 匹配系统内置目录
            builtin_dir = os.path.normpath(str(self._get_builtin_model_dir(model_type)))
            if normalized.startswith(f"{builtin_dir}{os.sep}"):
                return model_type
            # 匹配用户导入目录
            user_dir = os.path.normpath(str(self._get_user_model_dir(model_type)))
            if normalized.startswith(f"{user_dir}{os.sep}"):
                return model_type
        raise ValueError(f"无法根据路径推断模型类型: {file_path}")

    def _get_display_name(self, file_path: str, model_type: str | None = None) -> str:
        """获取模型展示名称。

        Args:
            file_path (str): 模型文件绝对路径。
            model_type (str | None): 模型类型，未传入时自动推断。

        Returns:
            str: 展示名称。

        Raises:
            ValueError: 路径无法推断类型时抛出异常。
        """
        resolved_type = model_type or self._infer_model_type(file_path)
        return get_display_name(file_path, resolved_type)

    def _ensure_enabled_model_for_type(self, model_type: str) -> str | None:
        """确保指定类型存在有效启用模型。

        Args:
            model_type (str): 模型类型。

        Returns:
            str | None: 生效的启用模型路径，无可用模型时返回 None。

        Raises:
            ValueError: 模型类型不支持时抛出异常。
        """
        model_files = self._collect_model_files(model_type)
        return resolve_enabled_model(model_type, model_files=model_files)

    def handle_import_model(self):
        """处理导入模型事件。

        弹出自定义导入对话框，将选中的模型文件复制到用户模型目录。
        若指定了自定义名称，则更新到元数据中。
        """
        current_route = self.view.segmentedWidget.currentRouteKey()
        default_type = current_route if current_route else "PA"

        dialog = ImportModelDialog(default_type, self.view)
        if dialog.exec():
            model_type, src_path, custom_name, remark_text = dialog.getModelInfo()

            if not src_path or not os.path.exists(src_path):
                InfoBar.error(
                    title="导入失败",
                    content="无效的模型文件路径",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self.view,
                )
                return

            # 保存到用户模型目录，避免写入安装目录
            dest_dir = ensure_user_model_dir(model_type)
            
            file_name = os.path.basename(src_path)
            dest_path = dest_dir / file_name

            try:
                shutil.copy2(src_path, dest_path)
                
                # 如果输入了自定义名称，则保存到注册表
                if custom_name:
                    ModelRegistry.set_name(str(dest_path), custom_name)
                if remark_text:
                    # 保存导入时填写的备注
                    ModelRegistry.set_remark(str(dest_path), remark_text)

                InfoBar.success(
                    title="导入成功",
                    content=f"已成功导入 {model_type} 模型: {file_name}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self.view,
                )
                # 导入后刷新该类型启用状态
                resolve_enabled_model(
                    model_type,
                    model_files=self._collect_model_files(model_type),
                )
                self.load_models()
            except Exception as e:
                LOGGER.error(f"导入模型失败 {src_path}: {e}")
                InfoBar.error(
                    title="导入失败",
                    content=str(e),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self.view,
                )

    def request_rename_model(self, file_path: str, current_name: str) -> None:
        """处理重命名弹窗请求。

        Args:
            file_path (str): 模型文件绝对路径。
            current_name (str): 当前展示名称。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        model_type = self._infer_model_type(file_path)
        if self._is_builtin_model(file_path, model_type):
            InfoBar.warning(
                title="操作受限",
                content="系统默认模型不支持重命名",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            return

        # 使用子界面作为父对象，确保弹窗在页面级展示
        dialog = RenameModelDialog(current_name, self.view)
        if not dialog.exec():
            return

        # 获取并清理用户输入
        new_name = dialog.get_model_name().strip()
        if not new_name or new_name == current_name:
            return
        # 执行重命名业务
        self.handle_rename_model(file_path, new_name)

    def request_delete_model(self, file_path: str, display_name: str) -> None:
        """处理删除确认弹窗请求。

        Args:
            file_path (str): 模型文件绝对路径。
            display_name (str): 模型展示名称。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        model_type = self._infer_model_type(file_path)
        if self._is_builtin_model(file_path, model_type):
            InfoBar.warning(
                title="操作受限",
                content="系统默认模型不支持删除",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            return

        # 使用子界面作为父对象，确保弹窗在页面级展示
        dialog = DeleteModelDialog(display_name, self.view)
        if not dialog.exec():
            return

        # 执行删除业务
        self.handle_delete_model(file_path)

    def request_edit_remark(self, file_path: str, current_remark: str) -> None:
        """处理备注编辑弹窗请求。

        Args:
            file_path (str): 模型文件绝对路径。
            current_remark (str): 当前备注文本。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 使用子界面作为父对象，确保弹窗在页面级展示
        dialog = EditModelRemarkDialog(current_remark, self.view)
        if not dialog.exec():
            return

        # 获取并清理用户输入
        new_remark = dialog.get_remark().strip()
        if new_remark == current_remark.strip():
            return
        # 执行备注保存业务
        self.handle_edit_remark(file_path, new_remark)

    def handle_enable_toggled(self, file_path: str, model_type: str, checked: bool) -> None:
        """处理模型启用状态切换。

        Args:
            file_path (str): 模型文件绝对路径。
            model_type (str): 模型类型。
            checked (bool): 目标启用状态。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if not checked:
            # 禁止取消当前类型唯一启用模型，直接刷新回滚状态
            self.load_models()
            return

        try:
            # 写入当前类型启用模型路径
            set_enabled_model_path(model_type, file_path)
            LOGGER.info(
                "模型启用状态已变更: type=%s, name=%s, enabled=%s",
                model_type,
                self._get_display_name(file_path, model_type),
                file_path,
            )
            InfoBar.success(
                title="启用成功",
                content=f"已启用 {model_type} 模型: {self._get_display_name(file_path, model_type)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1800,
                parent=self.view,
            )
            # 刷新列表，确保同类型只有一个开关处于选中
            self.load_models()
        except Exception as e:
            LOGGER.error(f"切换启用模型失败: {e}")
            InfoBar.error(
                title="启用失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self.view,
            )

    def handle_delete_model(self, file_path: str):
        """处理删除模型事件。

        从磁盘中删除指定的模型文件，并刷新列表展示。

        Args:
            file_path (str): 待删除模型文件的绝对路径。
        """
        model_type = self._infer_model_type(file_path)
        if self._is_builtin_model(file_path, model_type):
            # 拦截系统默认模型删除请求
            InfoBar.warning(
                title="操作受限",
                content="系统默认模型不支持删除",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            return

        try:
            # 删除模型文件（先按普通权限尝试）
            os.remove(file_path)
        except PermissionError:
            # 兜底处理只读文件，先改为可写再删除
            os.chmod(file_path, stat.S_IWRITE)
            os.remove(file_path)
        except Exception as e:
            LOGGER.error(f"删除模型失败: {e}")
            InfoBar.error(
                title="删除失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            return

        try:
            # 清理模型元数据映射
            ModelRegistry.remove_name(file_path)
            # 删除后重新解析该类型启用项
            resolve_enabled_model(
                model_type,
                model_files=self._collect_model_files(model_type),
            )
            InfoBar.success(
                title="删除成功",
                content=f"已删除模型: {os.path.basename(file_path)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            self.load_models()
        except Exception as e:
            LOGGER.error(f"删除后刷新模型元数据失败: {e}")
            InfoBar.error(
                title="删除失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )

    def handle_rename_model(self, file_path: str, new_name: str):
        """处理重命名模型事件。

        仅更新模型元数据中的显示名称，不直接修改磁盘上的模型源文件。

        Args:
            file_path (str): 原模型文件的绝对路径。
            new_name (str): 新的模型名称。
        """
        model_type = self._infer_model_type(file_path)
        if self._is_builtin_model(file_path, model_type):
            # 拦截系统默认模型重命名请求
            InfoBar.warning(
                title="操作受限",
                content="系统默认模型不支持重命名",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            return

        try:
            ModelRegistry.set_name(file_path, new_name)
            InfoBar.success(
                title="重命名成功",
                content=f"模型已重命名为: {new_name}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            self.load_models()
        except Exception as e:
            LOGGER.error(f"重命名模型失败: {e}")
            InfoBar.error(
                title="重命名失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )

    def handle_edit_remark(self, file_path: str, remark_text: str) -> None:
        """处理模型备注编辑事件。

        Args:
            file_path (str): 模型文件绝对路径。
            remark_text (str): 新的备注文本。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        try:
            # 保存模型备注
            ModelRegistry.set_remark(file_path, remark_text)
            InfoBar.success(
                title="保存成功",
                content="模型备注已更新",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
            self.load_models()
        except Exception as e:
            LOGGER.error(f"保存模型备注失败: {e}")
            InfoBar.error(
                title="保存失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.view,
            )
