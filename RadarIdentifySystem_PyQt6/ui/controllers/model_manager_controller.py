# -*- coding: utf-8 -*-
"""模型管理控制器。"""

import os
import shutil
import stat
from pathlib import Path
import logging

from PyQt6.QtCore import QObject, Qt
from qfluentwidgets import InfoBar, InfoBarPosition, BodyLabel, qconfig

from app.app_config import appConfig
from ui.dialogs.import_model_dialog import ImportModelDialog
from ui.dialogs.rename_model_dialog import RenameModelDialog
from ui.dialogs.delete_model_dialog import DeleteModelDialog
from ui.components.model_item_card import ModelItemCard
from utils.model_registry import ModelRegistry

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

        # 初始化加载
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

        # 模型固定存放在 resources/models/PA 或 resources/models/DTOA
        model_dir = self._get_model_dir(current_type)

        # 确保目录存在
        if not model_dir.exists():
            try:
                model_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                LOGGER.warning(f"无法创建模型目录 {model_dir}: {e}")

        try:
            files_found = False
            if model_dir.exists():
                files = [
                    f for f in os.listdir(model_dir)
                    if f.endswith((".onnx", ".pkl", ".pt", ".pth"))
                ]

                model_files: list[str] = []
                for file_name in files:
                    files_found = True
                    file_path = os.path.join(model_dir, file_name)
                    model_files.append(file_path)

                # 仅读取当前启用模型，不执行自动修正（切换列表只是查看，避免不必要的状态变更）
                enabled_path = ModelRegistry.get_enabled_model(current_type)
                # 检查启用模型是否在当前列表中，若不在则忽略该启用状态
                norm_files = [os.path.normpath(p) for p in model_files]
                if enabled_path and enabled_path not in norm_files:
                    enabled_path = None

                for file_path in model_files:
                    display_name = ModelRegistry.get_name(file_path)
                    card = ModelItemCard(
                        current_type,
                        file_path,
                        display_name,
                        is_enabled=ModelRegistry.is_enabled(current_type, file_path),
                        parent=self.view,
                    )
                    # 绑定卡片请求信号，由控制器统一管理弹窗交互
                    card.deleteRequested.connect(self.request_delete_model)
                    card.renameRequested.connect(self.request_rename_model)
                    card.enabledToggled.connect(self.handle_enable_toggled)
                    self.view.listLayout.addWidget(card)

            if not files_found:
                emptyLabel = BodyLabel(
                    "配置的模型目录为空，请先导入模型文件或添加模型目录。"
                )
                # 设置空状态标签对象名，供样式表统一管理
                emptyLabel.setObjectName("modelEmptyLabel")
                # 设置空状态标签上边距，避免与顶部区域贴近
                emptyLabel.setContentsMargins(0, 40, 0, 0)
                emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.view.listLayout.addWidget(emptyLabel)

            # 添加底部弹性空间，确保卡片从顶部开始排列
            self.view.listLayout.addStretch(1)
            # 同步识别流程使用的模型路径配置
            self._sync_model_paths_to_config()

        except Exception as e:
            LOGGER.error(f"加载模型列表失败: {e}")

    def _get_model_dir(self, model_type: str) -> Path:
        """获取指定模型类型的目录路径。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。

        Returns:
            Path: 模型目录绝对路径。

        Raises:
            ValueError: 不支持的模型类型会抛出异常。
        """
        if model_type not in ("PA", "DTOA"):
            raise ValueError(f"不支持的模型类型: {model_type}")
        # 返回模型目录路径
        return Path(__file__).parent.parent.parent / "resources" / "models" / model_type

    def _sync_model_paths_to_config(self) -> None:
        """同步启用模型路径到全局配置。"""
        # 同步 PA 启用模型路径
        pa_enabled = ModelRegistry.get_enabled_model("PA")
        if pa_enabled:
            qconfig.set(appConfig.modelPaPath, pa_enabled)
        # 同步 DTOA 启用模型路径
        dtoa_enabled = ModelRegistry.get_enabled_model("DTOA")
        if dtoa_enabled:
            qconfig.set(appConfig.modelDtoaPath, dtoa_enabled)

    def handle_import_model(self):
        """处理导入模型事件。

        弹出自定义导入对话框，将选中的模型文件复制到 resources/models 的对应目录下。
        若指定了自定义名称，则更新到元数据中。
        """
        current_route = self.view.segmentedWidget.currentRouteKey()
        default_type = current_route if current_route else "PA"

        dialog = ImportModelDialog(default_type, self.view)
        if dialog.exec():
            model_type, src_path, custom_name = dialog.getModelInfo()

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

            # 保存到指定的模型目录下
            dest_dir = Path(__file__).parent.parent.parent / "resources" / "models" / model_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            file_name = os.path.basename(src_path)
            dest_path = dest_dir / file_name

            try:
                shutil.copy2(src_path, dest_path)
                
                # 如果输入了自定义名称，则保存到注册表
                if custom_name:
                    ModelRegistry.set_name(str(dest_path), custom_name)

                InfoBar.success(
                    title="导入成功",
                    content=f"已成功导入 {model_type} 模型: {file_name}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self.view,
                )
                # 导入后自动修正并同步启用状态
                model_files = [
                    str(dest_dir / f) for f in os.listdir(dest_dir)
                    if f.endswith((".onnx", ".pkl", ".pt", ".pth"))
                ]
                ModelRegistry.ensure_enabled_model(model_type, model_files)
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
        # 使用子界面作为父对象，确保弹窗在页面级展示
        dialog = DeleteModelDialog(display_name, self.view)
        if not dialog.exec():
            return

        # 执行删除业务
        self.handle_delete_model(file_path)

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
            # 设置当前类型启用模型，天然覆盖旧启用项
            ModelRegistry.set_enabled_model(model_type, file_path)
            LOGGER.info(
                "模型启用状态已变更: type=%s, enabled=%s",
                model_type,
                file_path,
            )
            # 同步配置路径
            self._sync_model_paths_to_config()
            InfoBar.success(
                title="启用成功",
                content=f"已启用 {model_type} 模型: {Path(file_path).name}",
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
            model_type = Path(file_path).parent.name.upper()
            ModelRegistry.remove_name(file_path)
            # 删除后自动修正该类型启用项
            model_dir = self._get_model_dir(model_type)
            model_files = [
                str(model_dir / f) for f in os.listdir(model_dir)
                if f.endswith((".onnx", ".pkl", ".pt", ".pth"))
            ] if model_dir.exists() else []
            ModelRegistry.ensure_enabled_model(model_type, model_files)
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
