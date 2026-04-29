# -*- coding: utf-8 -*-
"""模型项卡片组件。"""

from pathlib import Path
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy, QWidget
from PyQt6.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    CardWidget,
    CommandBar,
    Action,
    CaptionLabel,
    FluentIcon,
    RadioButton,
)
from ui.components.scrolling_name_label import ScrollingNameLabel

class ModelItemCard(CardWidget):
    """单个模型项卡片。
    
    功能描述：
        用于在模型管理列表中展示单个模型文件，提供模型名称、备注展示以及相关操作。
        
    Attributes:
        model_type (str): 模型类型，如 "PA" 或 "DTOA"。
        file_path (Path): 模型文件的完整路径。
    """
    deleteRequested = pyqtSignal(str, str)
    renameRequested = pyqtSignal(str, str)
    remarkRequested = pyqtSignal(str, str)
    enabledToggled = pyqtSignal(str, str, bool)
    
    def __init__(
        self,
        model_type: str,
        file_path: str,
        display_name: str = None,
        remark_text: str = "",
        is_enabled: bool = False,
        is_system_default: bool = False,
        parent=None,
    ):
        """初始化模型项卡片。

        Args:
            model_type (str): 模型类型标识，通常为 ``PA`` 或 ``DTOA``。
            file_path (str): 模型文件完整路径。
            display_name (str | None): 模型显示名称，未传入时使用文件名。
            remark_text (str): 模型备注文本，默认值为空字符串。
            is_enabled (bool): 当前模型是否已启用，默认值为 False。
            is_system_default (bool): 是否为系统默认模型，默认值为 False。
            parent (QWidget | None): 父组件。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前构造函数不主动抛出异常。
        """
        super().__init__(parent)
        self.model_type = model_type
        self.file_path = Path(file_path)
        self.display_name = display_name or self.file_path.name
        self.remark_text = remark_text
        self.has_remark = bool(self.remark_text.strip())
        self.is_enabled = is_enabled
        self.is_system_default = is_system_default
        # 设置卡片对象名，供 QSS 统一管理样式
        self.setObjectName("modelItemCard")
        # 固定纵向策略，避免在列表中被拉伸均分高度
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        
        self.setFixedHeight(70)
        
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(20, 0, 20, 0)
        self.hBoxLayout.setSpacing(10)
        
        # 徽标
        self.badgeLabel = QLabel(model_type)
        # 设置徽标对象名，供 QSS 统一管理样式
        self.badgeLabel.setObjectName("modelTypeBadge")
        # 写入模型类型属性，供 QSS 按类型差异化着色
        self.badgeLabel.setProperty("modelType", model_type)
        self.badgeLabel.setFixedSize(40, 40)
        self.badgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 启用单选按钮
        self.enableBtn = RadioButton("", self)
        self.enableBtn.setObjectName("modelEnableButton")
        self.enableBtn.setFixedWidth(16)
        self.enableBtn.setChecked(self.is_enabled)
        
        # 文本
        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 14, 0, 14)
        self.textLayout.setSpacing(2)
        
        self.nameLabel = ScrollingNameLabel(self.display_name, max_width=260, parent=self)
        
        self.textLayout.addWidget(self.nameLabel)
        if self.has_remark:
            # 仅在存在备注时创建备注文本
            self.remarkLabel = CaptionLabel(self._build_remark_text())
            # 设置备注对象名，供 QSS 统一管理样式
            self.remarkLabel.setObjectName("modelRemarkLabel")
            self.remarkLabel.setToolTip(self.remark_text.strip())
            self.textLayout.addWidget(self.remarkLabel)
        
        # 命令栏
        self.commandBar = CommandBar(self)
        self.commandBar.setObjectName("modelCommandBar")
        self.commandBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        # 仅为可编辑模型创建命令动作
        self.remarkAction = Action(FluentIcon.EDIT, "编辑备注")
        self.renameAction = Action(FluentIcon.EDIT, "重命名")
        self.deleteAction = Action(FluentIcon.DELETE, "删除")
        self.deleteAction.setProperty("danger", True)

        # 创建命令栏占位容器，确保隐藏命令栏时保留布局位置
        self.commandBarContainer = QWidget(self)
        self.commandBarContainer.setObjectName("modelCommandBarContainer")
        self.commandBarContainer.setFixedWidth(100)
        self.commandBarLayout = QHBoxLayout(self.commandBarContainer)
        self.commandBarLayout.setContentsMargins(0, 0, 0, 0)
        self.commandBarLayout.setSpacing(0)
        self.commandBarLayout.addWidget(self.commandBar)
        # 默认隐藏命令栏，悬浮时显示
        self.commandBar.setVisible(False)
        
        self.enableBtn.toggled.connect(self._onEnableToggled)
        self.remarkAction.triggered.connect(self._onEditRemark)
        self.commandBar.addAction(self.remarkAction)

        if not self.is_system_default:
            # 绑定可编辑模型的动作信号
            self.renameAction.triggered.connect(self._onRename)
            self.deleteAction.triggered.connect(self._onDelete)
            self.commandBar.addAction(self.renameAction)
            self.commandBar.addAction(self.deleteAction)
        
        # 组装
        self.hBoxLayout.addWidget(self.enableBtn)
        self.hBoxLayout.addWidget(self.badgeLabel)
        self.hBoxLayout.addLayout(self.textLayout)
        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.commandBarContainer)
        # 应用启用态样式
        self._apply_enabled_style()
        
    def _onRename(self):
        """触发重命名信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        # 发射重命名请求信号，由控制器统一弹出对话框
        self.renameRequested.emit(str(self.file_path), self.display_name)

    def _onEditRemark(self) -> None:
        """触发备注编辑信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 发射备注编辑请求信号，由控制器统一弹出对话框
        self.remarkRequested.emit(str(self.file_path), self.remark_text)
        
    def _onDelete(self):
        """触发删除信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        # 发射删除请求信号，由控制器统一弹出确认框
        self.deleteRequested.emit(str(self.file_path), self.display_name)

    def _onEnableToggled(self, checked: bool) -> None:
        """处理启用开关切换。

        Args:
            checked (bool): 目标启用状态。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 同步本地状态并更新样式
        self.is_enabled = checked
        self._apply_enabled_style()
        # 发射启用状态变更请求，由控制器统一执行业务约束
        self.enabledToggled.emit(str(self.file_path), self.model_type, checked)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态并刷新显示。

        Args:
            enabled (bool): 目标启用状态。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 避免重复发射切换信号
        self.enableBtn.blockSignals(True)
        self.enableBtn.setChecked(enabled)
        self.enableBtn.blockSignals(False)
        self.is_enabled = enabled
        self._apply_enabled_style()

    def _apply_enabled_style(self) -> None:
        """应用启用状态样式。"""
        # 写入启用属性，供 QSS 按状态切换卡片样式
        self.setProperty("enabledModel", self.is_enabled)
        # 触发样式重绘，确保状态变化立即生效
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _build_remark_text(self) -> str:
        """构建备注展示文本。

        Args:
            无。

        Returns:
            str: 备注展示文本。

        Raises:
            无。
        """
        remark = self.remark_text.strip()
        if len(remark) <= 40:
            return remark
        return f"{remark[:37]}..."

    def enterEvent(self, event) -> None:
        """处理鼠标进入事件。"""
        # 悬浮时显示命令栏
        self.commandBar.setVisible(not self.is_system_default)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """处理鼠标离开事件。"""
        # 离开时隐藏命令栏
        self.commandBar.setVisible(False)
        super().leaveEvent(event)
