from typing import Dict, Set
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QWidget, QMessageBox, QAbstractItemView, QFrame,
    QLineEdit
)
from PyQt5.QtCore import Qt, QSize, QEvent, QObject
from PyQt5.QtGui import QPixmap, QIcon
from common.paths import Paths
from cores.log_manager import LogManager
from ui.components.custom_tooltip import install_custom_tooltip
from ui.components.custom_dialog import BaseFramelessDialog
from ui.components.message_box import CustomMessageBox
import os
import re

class ModelManagerDialog(BaseFramelessDialog):
    """模型管理对话框
    
    采用三栏式布局：
    - 左侧：PA/DTOA导航
    - 中间：已加载模型列表
    - 右侧：待移除模型列表
    """
    
    def __init__(self, parent=None, data_controller=None, styles=None):
        super().__init__(parent, title="管理模型")
        self.data_controller = data_controller
        self.styles = styles or {}
        self.logger = LogManager()
        
        # 存储待移除的模型 {category: set(model_names)}
        self.pending_removals: Dict[str, Set[str]] = {
            "PA": set(),
            "DTOA": set()
        }
        
        self.setFixedSize(900, 600)
            
        self._setup_content_ui()
        
        # 初始化显示
        self.nav_list.setCurrentRow(0)
        
    def _setup_content_ui(self):
        """设置内容UI"""
        # 调整内容区域边距
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)

        # 设置特定样式
        current_style = self.styleSheet()
        new_style = current_style + """
            QListWidget {
                font-family: "Microsoft YaHei";
                font-size: 16px;
                color: #4772c3;
            }
            QMessageBox {
                background-color: white;
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QMessageBox QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QMessageBox QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        self.setStyleSheet(new_style)

        # 三栏内容区域
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0) # 减小间距
        
        # 定义列表通用样式
        list_style = """
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                outline: none;
                padding: 5px;
            }
            QListWidget::item {
                border: none;
                border-radius: 5px;
                margin-top: 2px;
                margin-bottom: 2px;
                padding-left: 4px;
                height: 40px;
                color: #4772c3;
            }
            QListWidget::item:selected {
                background-color: #4772c3;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #4772c3;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #E6F3FF;
                color: #4772c3;
            }
        """
        
        # 左侧：导航栏
        nav_container = QWidget()
        nav_container.setFixedWidth(160)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(5)
        nav_label = QLabel("模型类别")
        nav_label.setStyleSheet("font-weight: bold; border: none; font-size: 18px;")
        nav_layout.addWidget(nav_label)
        
        self.nav_list = QListWidget()
        self.nav_list.addItems(["PA模型", "DTOA模型"])
        self.nav_list.setStyleSheet(list_style)
        self.nav_list.currentItemChanged.connect(self._refresh_lists)
            
        nav_layout.addWidget(self.nav_list)
        content_layout.addWidget(nav_container)
        content_layout.addSpacing(10)
        
        # 中间：已加载模型
        middle_container = QWidget()
        middle_layout = QVBoxLayout(middle_container)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(5)
        middle_label = QLabel("已加载模型")
        middle_label.setStyleSheet("font-weight: bold; border: none; font-size: 18px;")
        middle_layout.addWidget(middle_label)
        
        self.loaded_list = QListWidget()
        self.loaded_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.loaded_list.setStyleSheet(list_style)
            
        middle_layout.addWidget(self.loaded_list)
        content_layout.addWidget(middle_container)
        
        # 中间箭头图标占位
        arrow_container = QWidget()
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setAlignment(Qt.AlignCenter)
        
        arrow_label = QLabel()
        arrow_label.setFixedSize(32, 32)
        arrow_label.setStyleSheet("border: none")
        
        # 尝试加载右箭头图标
        arrow_icon_path = Paths.get_resource_path("resources/Arrow/arrow-right-left.png")
        arrow_label.setPixmap(QPixmap(str(arrow_icon_path)))
        arrow_label.setScaledContents(True)
        
        arrow_layout.addWidget(arrow_label)
        content_layout.addWidget(arrow_container)
        
        # 右侧：移除区域
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        right_label = QLabel("待移除")
        right_label.setStyleSheet("font-weight: bold; border: none; font-size: 18px;")
        right_layout.addWidget(right_label)
        
        self.remove_list = QListWidget()
        self.remove_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.remove_list.setStyleSheet(list_style)
            
        right_layout.addWidget(self.remove_list)
        content_layout.addWidget(right_container)
        
        self.add_content_layout(content_layout)
        
        # 底部按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #4772c3;
                border: 1px solid #4772c3;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #E6F3FF;
            }
        """)
            
        self.confirm_btn = QPushButton("完成")
        self.confirm_btn.setFixedWidth(100)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #4772c3;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #3C61A5;
            }
        """)
            
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        
        self.add_content_layout(btn_layout)
        
    def _get_current_category(self) -> str:
        """获取当前选中的类别 (PA 或 DTOA)"""
        current_item = self.nav_list.currentItem()
        if not current_item:
            return "PA"
        text = current_item.text()
        return "PA" if "PA" in text else "DTOA"

    def _refresh_lists(self):
        """刷新中间和右侧列表"""
        category = self._get_current_category()
        
        # 清空列表
        self.loaded_list.clear()
        self.remove_list.clear()
        
        # 获取所有模型
        if category == "PA":
            all_models = self.data_controller.get_pa_model_list()
        else:
            all_models = self.data_controller.get_dtoa_model_list()
            
        # 过滤系统默认模型 (通常不允许删除)
        all_models = [m for m in all_models if m != "系统默认"]
        
        # 分类模型
        pending = self.pending_removals[category]
        loaded_models = [m for m in all_models if m not in pending]
        remove_models = [m for m in all_models if m in pending]
        
        # 填充中间列表 (已加载)
        for model_name in loaded_models:
            self._add_item_to_loaded_list(model_name)
            
        # 填充右侧列表 (待移除)
        for model_name in remove_models:
            self._add_item_to_remove_list(model_name)

    def _add_item_to_loaded_list(self, model_name):
        """添加项目到已加载列表"""
        item = QListWidgetItem(self.loaded_list)
        # 显式设置Item大小，确保有足够空间
        item.setSizeHint(QSize(0, 40))
        
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent; border: none;") # 确保透明背景
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0) # 减少上下边距
        layout.setSpacing(5)
        
        # 显示名称的标签
        name_label = QLabel(model_name)
        name_label.setStyleSheet("color: #333333;")
        
        # 编辑名称的输入框 (初始隐藏)
        name_edit = QLineEdit(model_name)
        name_edit.setVisible(False)
        name_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #4772c3;
                border-radius: 2px;
                color: #333333;
                selection-background-color: #4772c3;
                selection-color: white;
            }
        """)
        
        # 按钮容器
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)
        
        # 重命名按钮
        rename_btn = QPushButton()
        rename_btn.setFixedSize(24, 24)
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_icon_path = Paths.get_resource_path("resources/icons/rename.png")
        rename_btn.setIcon(QIcon(str(rename_icon_path)))
        install_custom_tooltip(rename_btn, "重命名")

        # 移除按钮
        remove_btn = QPushButton()
        remove_btn.setFixedSize(24, 24)
        remove_btn.setCursor(Qt.PointingHandCursor)
        # remove_btn.setText("×")
        delete_icon_path = Paths.get_resource_path("resources/Arrow/arrow-right-to-line.png")
        remove_btn.setIcon(QIcon(str(delete_icon_path)))
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
        """)
        install_custom_tooltip(remove_btn, "移除模型")
        
        btn_layout.addWidget(rename_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(remove_btn)
        
        layout.addWidget(name_label)
        layout.addWidget(name_edit)
        layout.addStretch()
        layout.addWidget(btn_container)
        
        self.loaded_list.setItemWidget(item, widget)
        
        # 绑定事件
        category = self._get_current_category()
        
        # 定义取消重命名函数
        def cancel_rename():
            name_label.setVisible(True)
            name_edit.setVisible(False)
            rename_btn.setVisible(True)
            remove_btn.setVisible(True)
            name_edit.setText(model_name) # 恢复原名

        # 重命名逻辑
        def start_rename():
            name_label.setVisible(False)
            name_edit.setVisible(True)
            rename_btn.setVisible(False)
            remove_btn.setVisible(False)
            name_edit.setFocus()
            name_edit.selectAll()
            
        def finish_rename(show_error=True):
            # 防止重入（例如回车弹窗导致失去焦点再次触发）
            if getattr(name_edit, "_processing_rename", False):
                return
            name_edit._processing_rename = True
            
            try:
                new_name = name_edit.text().strip()
                old_name = model_name
                
                # 校验特殊字符
                if re.search(r'[\\/:*?"<>|]', new_name):
                    if show_error:
                        CustomMessageBox.warning(self, "无效名称", "模型名称不能包含以下字符: \\ / : * ? \" < > |")
                        name_edit.setFocus()
                    else:
                        cancel_rename()
                    return
                
                if new_name and new_name != old_name:
                    # 执行重命名
                    success, msg = self.data_controller.rename_model(old_name, new_name, category)
                    if success:
                        # 更新界面
                        self._refresh_lists()
                        self.data_controller.emit_models_changed() # 通知主窗口更新
                        self.logger.info(f"重命名模型成功: {old_name} -> {new_name}")
                        return # 成功后列表已刷新，无需后续UI恢复
                    else:
                        if show_error:
                            CustomMessageBox.warning(self, "重命名失败", msg)
                            name_edit.setText(old_name)
                            name_edit.setFocus()
                        else:
                            cancel_rename()
                        return

                # 如果名称未改变或为空，视为取消
                cancel_rename()
                
            finally:
                name_edit._processing_rename = False
            
        rename_btn.clicked.connect(start_rename)
        # 移除旧的 returnPressed 连接，改用 EventFilter 统一处理
        # name_edit.returnPressed.connect(finish_rename)
        
        # 移除逻辑
        def on_remove():
            self.pending_removals[category].add(model_name)
            self._refresh_lists()
            
        remove_btn.clicked.connect(on_remove)

        # 添加事件过滤器处理回车和失去焦点
        class RenameEventFilter(QObject):
            def __init__(self, parent=None):
                super().__init__(parent)
                
            def eventFilter(self, obj, event):
                if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    finish_rename(show_error=True)
                    return True
                elif event.type() == QEvent.FocusOut:
                    finish_rename(show_error=False)
                    return True # 这里的返回值影响不大，因为FocusOut主要是通知
                return super().eventFilter(obj, event)

        key_filter = RenameEventFilter(name_edit)
        name_edit.installEventFilter(key_filter)
        # 保持引用防止被垃圾回收
        name_edit._key_filter = key_filter

    def _add_item_to_remove_list(self, model_name):
        """添加项目到待移除列表"""
        item = QListWidgetItem(self.remove_list)
        item.setSizeHint(QSize(0, 40))
        
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent; border: none;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        
        name_label = QLabel(model_name)
        name_label.setStyleSheet("color: #666666; text-decoration: line-through;")
        
        undo_btn = QPushButton()
        undo_btn.setFixedSize(24, 24)
        undo_btn.setCursor(Qt.PointingHandCursor)
        # undo_btn.setText("↩")
        refresh_icon_path = Paths.get_resource_path("resources/icons/undo.png")
        undo_btn.setIcon(QIcon(str(refresh_icon_path)))
        undo_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #4772c3;
                font-weight: bold;
                font-size: 16px;
            }
        """)
        install_custom_tooltip(undo_btn, "撤销移除")
        
        category = self._get_current_category()
        def on_undo():
            if model_name in self.pending_removals[category]:
                self.pending_removals[category].remove(model_name)
                self._refresh_lists()
        
        undo_btn.clicked.connect(on_undo)
        
        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(undo_btn)
        
        self.remove_list.setItemWidget(item, widget)

    def _on_confirm(self):
        """确认更改"""
        # 执行所有待移除操作
        has_changes = False
        
        for category, models in self.pending_removals.items():
            if not models:
                continue
                
            for model_name in models:
                if self.data_controller.delete_model(model_name, category):
                    self.logger.info(f"已移除 {category} 模型: {model_name}")
                    has_changes = True
                else:
                    self.logger.error(f"移除失败: {model_name}")
                    
        if has_changes:
            CustomMessageBox.information(self, "完成", "模型已移除。")
            self.data_controller.emit_models_changed()
            
        self.accept()
