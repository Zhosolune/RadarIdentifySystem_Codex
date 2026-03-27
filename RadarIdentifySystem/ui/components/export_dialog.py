"""导出对话框组件

提供仪表盘数据导出功能的对话框界面。
"""

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QFrame,
    QScrollArea,
    QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen
import sys

from .directory_picker_card import DirectoryPickerCard
from .option_setting_card import OptionSettingCard, InputOptionSettingCard
from .circle_progress import CircleProgressBar
from .toast_notification import ToastNotification
from .flow_check_setting_card import FlowCheckSettingCard
from .custom_dialog import BaseFramelessDialog

# 尝试导入配置模块
try:
    from ui.default_config import get_default_config
    _config_available = True
except ImportError:
    _config_available = False

class ExportDialog(BaseFramelessDialog):
    """导出对话框

    用于导出仪表盘数据的对话框，提供蓝色边框和白色容器的样式，
    底部包含取消和导出按钮。

    Signals:
        export_confirmed: 用户点击导出按钮时发出
    """

    export_confirmed = pyqtSignal(dict)  # 发送导出配置字典

    def __init__(self, parent=None):
        """初始化导出对话框

        Args:
            parent: 父窗口
        """
        super().__init__(parent, title="导出为Excel")
        
        # 配置管理
        self._config = get_default_config() if _config_available else None
        
        self.setFixedSize(600, 450)
        self.setModal(True)
        
        self._setup_content_ui()
        self._setup_overlay()
        self._load_config()

    def _setup_content_ui(self):
        """设置对话框内容UI"""
        # 设置样式
        current_style = self.styleSheet()
        new_style = current_style + """
            * {
                font-family: "Microsoft YaHei";
                font-size: 16px;
                color: #4772c3;
                border: none;
                background-color: transparent;
            }
        """
        self.setStyleSheet(new_style)

        # 调整内容边距
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        
        # 标题标签（在滚动区域外面）
        title_label = QLabel("导出选项")
        title_label.setContentsMargins(10, 10, 10, 0)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; border: none;")
        self.add_content_widget(title_label)

        # 创建可滚动区域的内容容器
        scroll_content_widget = QWidget()
        scroll_content_widget.setStyleSheet("border: none; background-color: white;")
        scroll_content_layout = QVBoxLayout(scroll_content_widget)
        scroll_content_layout.setContentsMargins(10, 0, 10, 0)

        # 内容区域（预留给具体导出选项）
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("border: none;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(5)

        # 1. 导出路径
        self._path_card = DirectoryPickerCard(
            title="导出路径",
            subtitle="选择文件导出的位置",
            icon_path= "",
            button_text="选择文件夹",
        )
        self._path_card.directory_selected.connect(self._on_export_path_changed)
        self._content_layout.addWidget(self._path_card)

        # 2. 波段选择（流式复选卡）
        self._band_select_card = FlowCheckSettingCard(
            title="导出波段",
            subtitle="选择需要导出的脉冲数据所在的波段",
            items_per_row=4
        )
        self._band_select_card.selection_changed.connect(self._on_band_selection_changed)
        self._content_layout.addWidget(self._band_select_card)

        # 3. 波段导出方式
        self._band_export_card = OptionSettingCard(
            title="导出方式",
            subtitle="选择不同波段数据导出的方式",
        )
        self._band_export_card.add_option("分别导出为独立的Excel文件", checked=True)
        self._band_export_card.add_option("导出为一个Excel文件内不同的sheet", checked=False)
        self._band_export_card.option_changed.connect(self._on_band_export_mode_changed)
        self._content_layout.addWidget(self._band_export_card)

        # 4. 大文件切分方式 - 使用 InputOptionSettingCard
        self._split_card = InputOptionSettingCard(
            title="大文件切分方式",
            subtitle="当文件过大时，选择切分文件的方式"
        )
        self._split_card.add_option_with_input(
            label="按文件大小切分",
            default_value="100",
            unit="MB",
            checked=False
        )
        self._split_card.add_option_with_input(
            label="按数量平均切分",
            default_value="10",
            unit="个",
            checked=False
        )
        self._split_card.add_option_with_input(
            label="按数据条数切分",
            default_value="100000",
            unit="条",
            checked=False
        )
        self._split_card.add_option(
            label="不切分",
            checked=True
        )
        self._split_card.value_changed.connect(self._on_split_value_changed)
        self._split_card.confirmed.connect(self._on_split_confirmed)
        self._content_layout.addWidget(self._split_card)

        # 将内容卡片区域添加到滚动内容
        scroll_content_layout.addWidget(self._content_widget)
        scroll_content_layout.addStretch(1)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)  # 关键：去除边框
        scroll_area.setFrameShadow(QFrame.Plain)
        scroll_area.setLineWidth(0)
        scroll_area.setMidLineWidth(0)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 设置 viewport 的边距，使滚动条覆盖在内容上而不是挤压空间
        # 右边距设为负值，让内容延伸到滚动条下方
        scroll_area.setViewportMargins(0, 0, -4, 0)  # -4 对应滚动条宽度
        
        # 降低滚动速度
        scroll_area.verticalScrollBar().setSingleStep(5)  # 默认是15，降低到5
        
        # 设置viewport无边框
        scroll_area.viewport().setStyleSheet("border: none; background-color: white;")
        
        # 直接在滚动条上设置样式（更窄的滑块：4px）
        scrollbar_style = """
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.4);
                border-radius: 2px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.55);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(0, 0, 0, 0.7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }
        """
        scroll_area.verticalScrollBar().setStyleSheet(scrollbar_style)
        
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        
        self.add_content_widget(scroll_area)

        # 底部按钮区域
        cancel_export_buttons = QWidget()
        cancel_export_buttons.setStyleSheet("border: none;")
        button_layout = QHBoxLayout(cancel_export_buttons)
        button_layout.setContentsMargins(10, 0, 10, 10)
        button_layout.setSpacing(10)

        # 取消按钮
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #4772c3;
                padding: 2px;
                border: 1px solid #4772c3;
                border-radius: 3px;
                min-width: 70px;
                max-width: 70px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E6F3FF;
            }
            QPushButton:disabled {
                color: #cccccc;
                border-color: #cccccc;
                background-color: #f5f5f5;
            }
        """)
        self._cancel_btn.clicked.connect(self.reject)

        # 导出按钮
        self._export_btn = QPushButton("导出")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4772c3;
                color: white;
                padding: 2px;
                border: 1px solid #4772c3;
                border-radius: 3px;
                min-width: 70px;
                max-width: 70px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3C61A5;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self._export_btn.clicked.connect(self._on_export_clicked)

        button_layout.addStretch(1)
        button_layout.addWidget(self._cancel_btn)
        button_layout.addWidget(self._export_btn)

        self.add_content_widget(cancel_export_buttons)

    def _on_export_clicked(self):
        """导出按钮点击处理"""
        # 检查是否有未保存的修改
        if self._split_card.has_unsaved_changes():
            ToastNotification.error("请先确认修改再导出", self)
            return
        
        # 收集导出配置
        export_config = self.get_export_config()
        self.export_confirmed.emit(export_config)
        # 不要调用 accept()，让 main_window 在导出完成后关闭对话框

    def _on_band_export_mode_changed(self, index: int, label: str):
        """波段导出方式切换处理"""
        self._save_band_export_config(index)
        self._refresh_card_states()

    def _on_split_value_changed(self, index: int, label: str, value: str):
        """切分方式值变化回调"""
        print(f"切分方式变化: {label}, 值: {value}")
        self._save_split_config(index, value)
        self._refresh_card_states()
    
    def _on_split_confirmed(self, index: int, label: str, value: str):
        """切分方式确认回调，显示保存成功提示"""
        ToastNotification.success("设置已保存", self)

    def _on_band_selection_changed(self, selected_labels: list):
        """波段选择变化回调
        
        Args:
            selected_labels: 当前选中的波段标签列表
        """
        print(f"已选择的波段: {selected_labels}")
        
        # 检查是否有波段被选中
        if not selected_labels:
            # 没有波段被选中，禁用导出按钮并显示警告
            self._export_btn.setEnabled(False)
            ToastNotification.warning("请至少勾选一个波段", self)
        else:
            # 有波段被选中，启用导出按钮
            self._export_btn.setEnabled(True)


    def _refresh_card_states(self):
        """刷新所有卡片的禁用状态
        
        规则：
        1. 选择"导出为一个文件"时：禁用切分方式卡的 header
        2. 切分方式为"不切分"时：禁用前两个选项的输入框组合
        3. 未被选中的选项：其输入框组合组件禁用
        """
        # 获取当前选中状态
        band_export_mode = self._band_export_card.get_selected_index()
        split_mode = self._split_card.get_selected_index()
        
        # 规则1：选择"导出为一个文件"(index=1) 时禁用切分方式卡 header
        is_single_file_mode = (band_export_mode == 1)
        self._split_card.set_header_enabled(not is_single_file_mode)
        
        if is_single_file_mode:
            # 导出为单文件时，强制设置为不切分（索引3）
            self._split_card.set_selected_option(3)
            split_mode = 3
        
        # 规则2和3：处理切分方式卡的输入框组合
        # 索引0: 按大小切分, 索引1: 按数量切分, 索引2: 按条数切分, 索引3: 不切分
        for i in range(4):
            if i == 3:
                # "不切分"选项没有输入框，跳过
                continue
            
            if split_mode == 3:
                # 切分方式为"不切分"时，禁用前三个选项的输入框组合
                self._split_card.set_input_widget_enabled(i, False)
            elif split_mode == i:
                # 当前选中的选项，启用其输入框组合
                self._split_card.set_input_widget_enabled(i, True)
            else:
                # 未选中的选项，禁用其输入框组合
                self._split_card.set_input_widget_enabled(i, False)

    def _on_export_path_changed(self, path: str):
        """导出路径变化回调"""
        if self._config:
            self._config.set_param("export_params.export_path", path)

    def _load_config(self):
        """从配置加载导出选项"""
        if not self._config:
            return
        
        params = self._config.params.export_params
        
        # 加载导出路径
        if params.export_path:
            self._path_card.set_directory(params.export_path)
        
        # 加载波段导出方式
        self._band_export_card.set_selected_option(params.band_export_mode)
        
        # 加载大文件切分方式
        self._split_card.set_selected_option(params.file_split_mode)
        
        # 加载切分值
        if params.file_split_mode == 0:
            # 按大小切分
            self._split_card.set_input_value(0, str(params.file_split_size_mb))
        elif params.file_split_mode == 1:
            # 按数量切分
            self._split_card.set_input_value(1, str(params.file_split_count))
        elif params.file_split_mode == 2:
            # 按条数切分
            self._split_card.set_input_value(2, str(getattr(params, 'file_split_rows', 100000)))
        
        # 初始刷新卡片状态
        self._refresh_card_states()

    def _save_band_export_config(self, index: int):
        """保存波段导出方式配置"""
        if self._config:
            self._config.set_param("export_params.band_export_mode", index)

    def _save_split_config(self, index: int, value: str):
        """保存大文件切分配置"""
        if not self._config:
            return
        
        self._config.set_param("export_params.file_split_mode", index)
        
        if index == 0:
            # 按大小切分
            try:
                size_mb = int(value) if value else 100
                self._config.set_param("export_params.file_split_size_mb", size_mb)
            except ValueError:
                pass
        elif index == 1:
            # 按数量切分  
            try:
                count = int(value) if value else 10
                self._config.set_param("export_params.file_split_count", count)
            except ValueError:
                pass
        elif index == 2:
            # 按条数切分
            try:
                rows = int(value) if value else 100000
                self._config.set_param("export_params.file_split_rows", rows)
            except ValueError:
                pass

    def _setup_overlay(self):
        """创建半透明蒙版和进度条"""
        # 半透明蒙版
        self._overlay = QWidget(self)
        self._overlay.setStyleSheet("background-color: rgba(255, 255, 255, 0.85);")
        self._overlay.hide()
        
        # 进度条布局
        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        
        # 圆环进度条
        self._progress_bar = CircleProgressBar()
        self._progress_bar.setFixedSize(100, 100)
        self._progress_bar.setStrokeWidth(8)
        overlay_layout.addWidget(self._progress_bar, 0, Qt.AlignCenter)
        
        # 进度提示标签
        self._progress_label = QLabel("正在导出...")
        self._progress_label.setStyleSheet("color: #4772c3; font-size: 14px;")
        self._progress_label.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(self._progress_label, 0, Qt.AlignCenter)

    def resizeEvent(self, event):
        """窗口大小变化时调整蒙版大小"""
        super().resizeEvent(event)
        if hasattr(self, '_overlay'):
            self._overlay.setGeometry(self.rect())

    def show_loading(self):
        """显示加载蒙版"""
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()
        self._overlay.show()
        self._progress_bar.setProgress(0)
        self._export_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

    def hide_loading(self):
        """隐藏加载蒙版"""
        self._overlay.hide()
        self._export_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)

    def update_progress(self, value: int):
        """更新进度值
        
        Args:
            value: 进度值 0-100
        """
        self._progress_bar.setProgress(value)

    def update_status(self, status: str):
        """更新状态提示文本
        
        Args:
            status: 状态文本
        """
        if hasattr(self, '_progress_label'):
            self._progress_label.setText(status)

    def set_available_bands(self, bands: list):
        """设置可用的波段列表
        
        根据解析的BIN文件数据动态设置可导出的波段选项
        
        Args:
            bands: 波段标签列表，例如 ["C波段", "X波段", "Ku波段"]
        """
        # 清除现有选项
        self._band_select_card.clear_options()
        
        # 添加新的波段选项，默认全选
        for band in bands:
            self._band_select_card.add_option(band, checked=True)
    
    def get_selected_bands(self) -> list:
        """获取当前选中的波段标签列表
        
        Returns:
            list: 选中的波段标签列表
        """
        return self._band_select_card.get_selected_labels()

    def get_export_config(self) -> dict:
        """获取当前导出配置
        
        Returns:
            dict: 导出配置字典
        """
        config = {
            "export_path": self._path_card.get_directory(),
            "band_export_mode": self._band_export_card.get_selected_index() if hasattr(self._band_export_card, 'get_selected_index') else 0,
            "file_split_mode": self._split_card.get_selected_index() if hasattr(self._split_card, 'get_selected_index') else 3,
            "selected_bands": self.get_selected_bands(),
        }
        
        # 如果配置可用，使用配置中的切分值
        if self._config:
            params = self._config.params.export_params
            config["file_split_size_mb"] = params.file_split_size_mb
            config["file_split_count"] = params.file_split_count
            config["file_split_rows"] = getattr(params, 'file_split_rows', 100000)
        else:
            config["file_split_size_mb"] = 100
            config["file_split_count"] = 10
            config["file_split_rows"] = 100000
        
        return config

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    # 创建并显示导出对话框
    dialog = ExportDialog()
    dialog.show()
    sys.exit(app.exec_())
