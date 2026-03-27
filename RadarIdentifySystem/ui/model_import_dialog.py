from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, 
    QGroupBox, QLineEdit
)
from PyQt5.QtCore import Qt
from pathlib import Path
import os
import shutil
from cores.log_manager import LogManager
from common.paths import Paths
from ui.components.custom_dialog import BaseFramelessDialog
from ui.components.input_dialog import CustomInputDialog
from ui.components.message_box import CustomMessageBox


class ModelImportDialog(BaseFramelessDialog):
    """模型导入对话框

    提供PA模型和DTOA模型的导入功能
    """

    def __init__(self, parent=None, data_controller=None, styles=None):
        """初始化模型导入对话框

        Args:
            parent: 父窗口
            data_controller: 数据控制器实例
            styles: 样式表字典
        """
        super().__init__(parent, title="载入模型")
        self.data_controller = data_controller
        self.predictor = data_controller.predictor if data_controller else None
        self.styles = styles if styles else {}
        self.logger = LogManager()
        self.model_paths = {"pa": "", "dtoa": ""}
        self.model_names = {"pa": "", "dtoa": ""}  # 存储自定义模型名称
        self.last_dir = str(Path.home())

        self.setFixedSize(700, 500)
        
        self._setup_content_ui()

    def _setup_content_ui(self):
        """设置内容区域UI"""
        # 追加特定样式
        current_style = self.styleSheet()
        new_style = current_style + """
            QLabel, QPushButton, QLineEdit {
                font-size: 14px;
            }
            QGroupBox {
                font-family: "Microsoft YaHei";
                font-size: 16px;
                font-weight: bold;
                color: #4772c3;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                margin-top: 20px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4772c3;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
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
                border: 1px solid #d0d0d0;
            }
            QMessageBox QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        self.setStyleSheet(new_style)

        # 按钮样式
        btn_style = """
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
            QPushButton:disabled {
                color: #cccccc;
                border-color: #cccccc;
                background-color: #f5f5f5;
            }
        """

        primary_btn_style = """
            QPushButton {
                background-color: #4772c3;
                border: 1px solid #4772c3;
                color: white;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #3C61A5;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border: 1px solid #cccccc;
                color: #ffffff;
            }
        """

        path_label_style = """
            QLabel {
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                padding: 5px;
                background-color: #FAFAFA;
                color: #666666;
                margin-right: 8px;
            }
        """

        # 创建PA模型模块
        self.pa_group = QGroupBox("PA模型")
        pa_layout = QVBoxLayout(self.pa_group)

        # PA模型路径布局
        pa_path_layout = QHBoxLayout()
        self.pa_path_label = QLabel()
        self.pa_path_label.setStyleSheet(path_label_style)
        self.pa_path_label.setMinimumWidth(350)
        self.pa_path_label.setText("未选择文件")
        
        # PA模型按钮布局
        self.pa_browse_btn = QPushButton("浏览")
        self.pa_browse_btn.setStyleSheet(btn_style)
        self.pa_browse_btn.setFixedWidth(80)
        self.pa_browse_btn.setCursor(Qt.PointingHandCursor)
        self.pa_browse_btn.clicked.connect(self._browse_pa_model)

        self.pa_clear_btn = QPushButton("清除")
        self.pa_clear_btn.setStyleSheet(btn_style)
        self.pa_clear_btn.setFixedWidth(80)
        self.pa_clear_btn.setCursor(Qt.PointingHandCursor)
        self.pa_clear_btn.clicked.connect(self._clear_pa_model)

        self.pa_import_btn = QPushButton("导入")
        self.pa_import_btn.setFixedWidth(80)
        self.pa_import_btn.setStyleSheet(primary_btn_style)
        self.pa_import_btn.setCursor(Qt.PointingHandCursor)
        self.pa_import_btn.clicked.connect(self._import_pa_model)
        self.pa_import_btn.setEnabled(False)  # 初始状态禁用

        pa_path_layout.addWidget(self.pa_path_label)
        pa_path_layout.addWidget(self.pa_browse_btn)
        pa_path_layout.addWidget(self.pa_clear_btn)
        pa_path_layout.addWidget(self.pa_import_btn)
        pa_layout.addLayout(pa_path_layout)

        # 创建DTOA模型模块
        self.dtoa_group = QGroupBox("DTOA模型")
        dtoa_layout = QVBoxLayout(self.dtoa_group)

        # DTOA模型路径布局
        dtoa_path_layout = QHBoxLayout()
        self.dtoa_path_label = QLabel()
        self.dtoa_path_label.setStyleSheet(path_label_style)
        self.dtoa_path_label.setMinimumWidth(350)
        self.dtoa_path_label.setText("未选择文件")

        # DTOA模型按钮布局
        self.dtoa_browse_btn = QPushButton("浏览")
        self.dtoa_browse_btn.setStyleSheet(btn_style)
        self.dtoa_browse_btn.setFixedWidth(80)
        self.dtoa_browse_btn.setCursor(Qt.PointingHandCursor)
        self.dtoa_browse_btn.clicked.connect(self._browse_dtoa_model)

        self.dtoa_clear_btn = QPushButton("清除")
        self.dtoa_clear_btn.setStyleSheet(btn_style)
        self.dtoa_clear_btn.setFixedWidth(80)
        self.dtoa_clear_btn.setCursor(Qt.PointingHandCursor)
        self.dtoa_clear_btn.clicked.connect(self._clear_dtoa_model)

        self.dtoa_import_btn = QPushButton("导入")
        self.dtoa_import_btn.setStyleSheet(primary_btn_style)
        self.dtoa_import_btn.setFixedWidth(80)
        self.dtoa_import_btn.setCursor(Qt.PointingHandCursor)
        self.dtoa_import_btn.clicked.connect(self._import_dtoa_model)
        self.dtoa_import_btn.setEnabled(False)  # 初始状态禁用

        dtoa_path_layout.addWidget(self.dtoa_path_label)
        dtoa_path_layout.addWidget(self.dtoa_browse_btn)
        dtoa_path_layout.addWidget(self.dtoa_clear_btn)
        dtoa_path_layout.addWidget(self.dtoa_import_btn)
        dtoa_layout.addLayout(dtoa_path_layout)

        # 添加模块到容器布局
        self.add_content_widget(self.pa_group)
        self.add_content_widget(self.dtoa_group)
        self.add_content_stretch()

        # 底部按钮布局
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setStyleSheet(btn_style)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("完成")
        self.confirm_btn.setFixedWidth(100)
        self.confirm_btn.setStyleSheet(primary_btn_style)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.clicked.connect(self._on_confirm)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.confirm_btn)
        self.add_content_layout(button_layout)

    def _browse_pa_model(self):
        """浏览并选择PA模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择PA模型文件", self.last_dir, "ONNX模型 (*.onnx);;所有文件 (*)")
        if file_path:
            # 询问是否重命名
            name, ok = CustomInputDialog.get_text(
                self, 
                "模型重命名", 
                "请输入模型名称（选填）:\n若不重命名则保持默认模型名称",
                ""
            )
            if ok:
                self.model_names["pa"] = name.strip()
            else:
                self.model_names["pa"] = ""

            self.pa_path_label.setText(file_path)
            self.model_paths["pa"] = file_path
            self.last_dir = str(Path(file_path).parent)
            self.pa_import_btn.setEnabled(True)  # 启用导入按钮

    def _browse_dtoa_model(self):
        """浏览并选择DTOA模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择DTOA模型文件", self.last_dir, "ONNX模型 (*.onnx);;所有文件 (*)")
        if file_path:
            # 询问是否重命名
            name, ok = CustomInputDialog.get_text(
                self, 
                "模型重命名", 
                "请输入模型名称（选填）:\n若不重命名则保持默认模型名称",
                ""
            )
            if ok:
                self.model_names["dtoa"] = name.strip()
            else:
                self.model_names["dtoa"] = ""

            self.dtoa_path_label.setText(file_path)
            self.model_paths["dtoa"] = file_path
            self.last_dir = str(Path(file_path).parent)
            self.dtoa_import_btn.setEnabled(True)  # 启用导入按钮

    def _clear_pa_model(self):
        """清除PA模型路径"""
        self.pa_path_label.setText("未选择文件")
        self.model_paths["pa"] = ""
        self.pa_import_btn.setEnabled(False)  # 禁用导入按钮

    def _clear_dtoa_model(self):
        """清除DTOA模型路径"""
        self.dtoa_path_label.setText("未选择文件")
        self.model_paths["dtoa"] = ""
        self.dtoa_import_btn.setEnabled(False)  # 禁用导入按钮

    def _import_pa_model(self):
        """导入单个PA模型"""
        try:
            if not self.model_paths["pa"]:
                return

            model_dir = Paths.get_model_dir()
            if not model_dir.exists():
                os.makedirs(model_dir, exist_ok=True)

            # 处理PA模型
            pa_model_path = self.model_paths["pa"]
            
            # 使用重命名（如果存在）
            if self.model_names["pa"]:
                pa_filename = f"{self.model_names['pa']}_PA.onnx"
            else:
                # 即使不重命名，也要确保文件名以 _PA.onnx 结尾，否则列表无法识别
                original_name = Path(pa_model_path).name
                if not original_name.endswith("_PA.onnx"):
                    pa_filename = f"{Path(pa_model_path).stem}_PA.onnx"
                else:
                    pa_filename = original_name
                
            pa_target_path = model_dir / pa_filename

            # 复制模型文件
            shutil.copy2(pa_model_path, pa_target_path)

            # 加载PA模型
            if self.predictor and self.predictor.load_pa_model(str(pa_target_path)):
                # 注册模型到映射表
                display_name = self.model_names["pa"] if self.model_names["pa"] else Path(pa_model_path).stem
                if self.data_controller:
                    self.data_controller.register_model(display_name, pa_filename, "PA")
                    self.data_controller.emit_models_changed()
                    
                CustomMessageBox.information(self, "模型导入", f"PA模型导入成功: {pa_filename}")
                self.logger.info(f"PA模型导入成功: {pa_filename}")
            else:
                CustomMessageBox.warning(self, "模型导入", "PA模型导入失败，请检查模型文件格式")
                self.logger.warning("PA模型导入失败")

        except Exception as e:
            CustomMessageBox.critical(self, "错误", f"PA模型导入失败: {str(e)}")
            self.logger.error(f"PA模型导入失败: {str(e)}")

    def _import_dtoa_model(self):
        """导入单个DTOA模型"""
        try:
            if not self.model_paths["dtoa"]:
                return

            model_dir = Paths.get_model_dir()
            if not model_dir.exists():
                os.makedirs(model_dir, exist_ok=True)

            # 处理DTOA模型
            dtoa_model_path = self.model_paths["dtoa"]
            
            # 使用重命名（如果存在）
            if self.model_names["dtoa"]:
                dtoa_filename = f"{self.model_names['dtoa']}_DTOA.onnx"
            else:
                # 即使不重命名，也要确保文件名以 _DTOA.onnx 结尾，否则列表无法识别
                original_name = Path(dtoa_model_path).name
                if not original_name.endswith("_DTOA.onnx"):
                    dtoa_filename = f"{Path(dtoa_model_path).stem}_DTOA.onnx"
                else:
                    dtoa_filename = original_name
                
            dtoa_target_path = model_dir / dtoa_filename

            # 复制模型文件
            shutil.copy2(dtoa_model_path, dtoa_target_path)

            # 加载DTOA模型
            if self.predictor and self.predictor.load_dtoa_model(str(dtoa_target_path)):
                # 注册模型到映射表
                display_name = self.model_names["dtoa"] if self.model_names["dtoa"] else Path(dtoa_model_path).stem
                if self.data_controller:
                    self.data_controller.register_model(display_name, dtoa_filename, "DTOA")
                    self.data_controller.emit_models_changed()
                    
                CustomMessageBox.information(self, "模型导入", f"DTOA模型导入成功: {dtoa_filename}")
                self.logger.info(f"DTOA模型导入成功: {dtoa_filename}")
            else:
                CustomMessageBox.warning(self, "模型导入", "DTOA模型导入失败，请检查模型文件格式")
                self.logger.warning("DTOA模型导入失败")

        except Exception as e:
            CustomMessageBox.critical(self, "错误", f"DTOA模型导入失败: {str(e)}")
            self.logger.error(f"DTOA模型导入失败: {str(e)}")

    def _on_confirm(self):
        """确认按钮点击事件
        
        直接关闭窗口，不显示提示，不执行实际导入逻辑。
        """
        self.accept()
