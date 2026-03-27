from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QTableWidgetItem,
    QPushButton,
    QCheckBox,
)
from .style_manager import StyleManager
from .ui_functions import setup_ui
from .data_controller import DataController
from .default_config import get_params
from pathlib import Path
from .loading_spinner import LoadingSpinner
from .rectangle_animation import RectangleAnimation
from .components import DashboardWidget, ExportDialog
from .components.message_box import CustomMessageBox
import os
from cores.log_manager import LogManager
from PyQt5.QtCore import Qt
import shutil
from enum import IntEnum


class NextSliceChoice(IntEnum):
    """下一片选择的枚举类"""

    CONTINUE = 0  # 继续
    CANCEL = 1  # 取消
    SAVE_CONTINUE = 2  # 保存再继续


class MainWindow(QMainWindow):
    """主窗口类

    负责创建和管理主要的用户界面，处理用户交互，并协调数据处理流程。

    Attributes:
        styles (dict): UI样式字典
        dimensions (dict): UI尺寸字典
        data_controller (DataController): 数据控制器实例
        loading_spinner (LoadingSpinner): 加载动画实例
    """

    def __init__(self):
        """初始化主窗口类"""
        super().__init__()
        self.logger = LogManager()
        self.logger.info("初始化主窗口")

        # 保存选项设置 - 只在本次会话中有效，不从QSettings中读取
        self.only_show_save_failures = None

        # 初始化样式管理器
        self.styles = StyleManager.get_styles()
        self.dimensions = StyleManager.get_dimensions()

        # 初始化参数配置
        self.params = get_params()

        # 初始化数据控制器
        self.data_controller = DataController()

        # 设置窗口基本属性
        self._setup_window()

        # 设置UI，注入参数实例
        setup_ui(self, self.params)

        # 创建加载动画
        self.loading_spinner = LoadingSpinner(self)
        # 设置加载动画的初始大小和位置
        self.loading_spinner.resize(self.size())
        self.loading_spinner.move(0, 0)

        # 创建矩形动画（用于全速处理）
        self.rectangle_animation = None

        # 设置信号连接
        self._setup_connections()

        # 初始化按钮状态：只启用浏览和导入按钮
        # 初始时禁用所有按钮
        self._update_buttons_state(False)
        # self.browse_import_btn.setEnabled(True)
        self.browse_save_btn1.setEnabled(True)
        self.browse_save_btn2.setEnabled(True)

        # 连接表格更新信号
        self.data_controller.table_data_ready.connect(self.update_table_data)

        # 添加结果目录路径
        self.figures_results_dir = Path("results/figures")
        self.excel_results_dir = Path("results")  # 保存excel结果的默认目录
        self.temp_dir = Path("temp")

        # 添加重置切片的自动选项属性
        self.auto_reset = None

        # 初始化保存功能变量
        self.auto_save = False  # 默认关闭自动保存
        self.save_dir = None
        self.full_speed_processed = False
        # 更新是否导入成功状态
        self.import_success = False

        # 记录上一次处理的文件和保存路径
        self.last_processed_file = None
        self.last_processed_save_dir = None

        # 记录上次处理时的参数
        self.last_process_params = {}

        # 记录按钮状态
        self.buttons_state = {}

        # 记录已激活的波段索引（用于判断是否切换了波段）
        self._activated_band_index = None

        # 初始化路径标签样式（默认为未选择状态）
        if hasattr(self, "update_path_label_style"):
            self.update_path_label_style(False)

        self.logger.info("主窗口初始化完成")

    def _setup_connections(self):
        """设置信号连接

        连接所有控件的信号和槽
        """
        try:
            # 数据控制器信号
            self.data_controller.slice_info_updated1.connect(
                lambda info: self.slice_info_label1.setText(info)
            )
            self.data_controller.slice_info_updated2.connect(
                lambda info: self.slice_info_label2.setText(info)
            )
            self.data_controller.process_started.connect(self._on_process_started)
            self.data_controller.process_finished.connect(self._on_process_finished)
            self.data_controller.cluster_result_ready.connect(
                self.update_cluster_display
            )
            self.data_controller.data_ready.connect(self._on_data_import_completed)
            self.data_controller.slice_images_ready.connect(self.update_slice_display)
            self.data_controller.identify_ready.connect(
                lambda success, count, can_merge: self.on_identify_finished(
                    success, count, can_merge
                )
            )
            self.data_controller.slice_finished.connect(self._on_slice_finished)

            # 全速处理相关连接
            self.data_controller.process_started_fs.connect(self._on_process_started_fs)
            self.data_controller.slice_finished_fs.connect(self._on_slice_finished_fs)
            self.data_controller.progress_updated_fs.connect(self._update_progress_fs)
            self.data_controller.process_finished_fs.connect(
                self._on_process_finished_fs
            )
            self.data_controller.start_save_fs.connect(self._on_start_save_fs)

            # 按钮事件
            # self.browse_import_btn.clicked.connect(self.browse_import_file)
            # self.import_btn.clicked.connect(self.import_data)
            self.start_slice_btn.clicked.connect(self._on_start_slice)
            self.identify_btn.clicked.connect(self._on_identify)
            self.next_cluster_btn.clicked.connect(self._on_next_cluster)
            self.next_slice_btn.clicked.connect(self._on_next_slice)
            self.reset_slice_btn.clicked.connect(self._on_reset_slice)
            self.redraw_btn.clicked.connect(self._on_redraw)
            self.start_process_btn.clicked.connect(self._on_start_process)
            self.browse_save_btn1.clicked.connect(self.browse_save_file)
            self.browse_save_btn2.clicked.connect(self.browse_save_file)
            self.save_btn.clicked.connect(self.save_results)
            self.merge_menu_btn.clicked.connect(
                self.open_merge_window
            )  # 连接合并菜单按钮

            # 导入数据按钮事件（激活选中波段数据并切换到处理界面）
            self.import_data_btn.clicked.connect(self._on_import_data_clicked)
            self.back_btn.clicked.connect(self.switch_to_import_interface)

            # 返回数据处理界面按钮事件
            self.return_to_process_btn.clicked.connect(self.switch_to_process_interface)

            # 波段标签切换事件（检测是否切换到不同波段）
            self.dashboard_tab_bar.tab_changed.connect(self._on_dashboard_band_changed)

            # 数据库目录卡片事件
            self.import_files_card.action_clicked.connect(
                self._on_add_database_directory
            )
            # 初始化已保存的数据库目录
            self._load_database_paths()

            # 命令栏事件
            self.import_command_bar.refresh_clicked.connect(self._on_refresh_files)
            self.import_command_bar.delete_clicked.connect(self._on_delete_files)
            self.import_command_bar.parse_clicked.connect(self._on_parse_file)
            self.import_command_bar.strategy_changed.connect(self._on_strategy_changed)

            # 文件类型标签切换事件
            self.import_tab_bar.tab_changed.connect(self._on_import_tab_changed)

            # 导出按钮事件
            self.export_dashboard_btn.clicked.connect(self._on_export_dashboard)

            # 文件列表选中状态改变事件（禁用/启用标签切换）
            for tab_name, file_list in self.import_file_lists.items():
                file_list.selection_changed.connect(self._on_file_selection_changed)

            # 参数输入框变化事件，用于检测参数更改
            for i in range(len(self.param_inputs)):
                self.param_inputs[i].textChanged.connect(self._on_param_changed)
            for i in range(len(self.merge_param_inputs)):
                self.merge_param_inputs[i].textChanged.connect(self._on_param_changed)

            # 切片编号输入框回车键事件，触发重绘按钮点击
            self.additional_input.returnPressed.connect(self._on_redraw)

        except Exception as e:
            self.logger.error(f"设置信号连接出错: {str(e)}")

    def _on_import_tab_changed(self, index: int):
        """导入文件标签页切换事件"""
        try:
            # 获取当前标签名
            tab_names = ["Excel", "Bin", "MAT"]
            if index < len(tab_names):
                tab_name = tab_names[index]
                # 设置命令栏模式：Bin模式下显示选项按钮
                is_bin = (tab_name == "Bin")
                if hasattr(self, 'import_command_bar'):
                    self.import_command_bar.set_bin_mode(is_bin)
        except Exception as e:
            self.logger.error(f"标签页切换处理出错: {str(e)}")

    def _on_strategy_changed(self, strategy: str):
        """解析策略改变事件处理"""
        try:
            self.logger.info(f"解析策略改变为: {strategy}")
            # 策略改变时不再自动触发解析，仅更新状态
        except Exception as e:
            self.logger.error(f"策略改变处理出错: {str(e)}")

    def _on_param_changed(self):
        """参数输入框内容变化的响应函数，检测是否需要重新启用开始处理按钮"""
        try:
            # 检查是否有导入数据
            has_data = (
                hasattr(self.data_controller, "processor")
                and self.data_controller.processor is not None
                and hasattr(self.data_controller.processor, "data")
                and self.data_controller.processor.data is not None
            )

            # 如果已经全速处理过且有导入数据，检查参数是否更改
            if self.full_speed_processed and has_data:
                current_params = self._get_current_params()

                # 判断参数是否变化
                params_changed = False
                if self.last_process_params:
                    # 对比每个参数
                    for param_name, param_value in current_params.items():
                        if (
                            param_name in self.last_process_params
                            and self.last_process_params[param_name] != param_value
                        ):
                            params_changed = True
                            self.logger.info(
                                f"参数 {param_name} 已更改: {self.last_process_params[param_name]} -> {param_value}"
                            )
                            break

                if params_changed:
                    self.logger.info("参数已更改，重置全速处理状态")
                    self.full_speed_processed = False

                    # 如果已经设置了保存路径，启用开始处理按钮
                    if self.save_dir:
                        self.logger.info("参数已更改且有保存路径，启用开始处理按钮")
                        self.start_process_btn.setEnabled(True)
        except Exception as e:
            self.logger.error(f"参数变更处理时出错: {str(e)}")

    def open_merge_window(self):
        """激活横向滚动容器并滚动到合并界面

        触发横向滚动容器的滚动动画，滚动到合并界面。
        """
        try:
            # 获取横向滚动容器并触发滚动到合并界面
            if hasattr(self, "scroll_container"):
                # 先启用滚动功能
                self.scroll_container.enable_scroll(True)
                # 然后滚动到合并界面
                self.scroll_container.scroll_to_merge_view()
                self.logger.info("滚动到合并界面")
            else:
                self.logger.error("横向滚动容器未找到")
                QMessageBox.critical(self, "错误", "横向滚动容器未找到")
        except Exception as e:
            self.logger.error(f"滚动到合并界面出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"滚动到合并界面出错: {str(e)}")

    def switch_to_process_interface(self):
        """切换到数据处理界面

        从数据导入界面切换到数据处理界面，带滑动动画效果。
        """
        try:
            if hasattr(self, "right_stacked_widget"):
                self.right_stacked_widget.slide_to_index(1)
                self.logger.info("切换到数据处理界面")
                # 隐藏返回处理界面按钮
                if hasattr(self, 'return_to_process_btn'):
                    self.return_to_process_btn.hide()
            else:
                self.logger.error("右侧堆叠控件未找到")
        except Exception as e:
            self.logger.error(f"切换到数据处理界面出错: {str(e)}")

    def switch_to_import_interface(self):
        """切换到数据导入界面

        从数据处理界面返回到数据导入界面，带滑动动画效果。
        """
        try:
            if hasattr(self, "right_stacked_widget"):
                self.right_stacked_widget.slide_to_index(0)
                self.logger.info("切换到数据导入界面")
                # 如果已经导入过数据，显示"返回数据处理界面"按钮
                if hasattr(self, 'return_to_process_btn') and self.import_success:
                    self.return_to_process_btn.show()
            else:
                self.logger.error("右侧堆叠控件未找到")
        except Exception as e:
            self.logger.error(f"切换到数据导入界面出错: {str(e)}")

    def _load_database_paths(self):
        """加载已保存的数据库目录路径到卡片中"""
        try:
            from .default_config import get_default_config

            config = get_default_config()
            paths = config.get_database_paths()

            for path in paths:
                self._add_database_path_to_card(path)

            self.logger.info(f"已加载 {len(paths)} 个数据库目录")

            # 加载保存的文件列表
            self._load_import_files()
        except Exception as e:
            self.logger.error(f"加载数据库目录失败: {str(e)}")

    def _add_database_path_to_card(self, path: str):
        """将目录路径添加到卡片中

        Args:
            path: 目录路径
        """
        item = self.import_files_card.add_content_item(path)
        # 连接删除信号
        item.delete_clicked.connect(
            lambda card: self._on_remove_database_directory(card)
        )

    def _on_add_database_directory(self):
        """添加新目录按钮点击事件"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            from .default_config import get_default_config

            # 打开目录选择对话框
            directory = QFileDialog.getExistingDirectory(
                self,
                "选择数据库目录",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
            )

            if directory:
                config = get_default_config()
                if config.add_database_path(directory):
                    # 添加到卡片
                    self._add_database_path_to_card(directory)
                    # 展开卡片显示新添加的项
                    if not self.import_files_card.is_expanded():
                        self.import_files_card.expand()
                else:
                    QMessageBox.warning(self, "提示", "该目录已存在于列表中")

        except Exception as e:
            self.logger.error(f"添加数据库目录出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"添加目录失败: {str(e)}")

    def _on_remove_database_directory(self, card):
        """移除数据库目录

        Args:
            card: 被删除的卡片项
        """
        try:
            from .default_config import get_default_config

            path = card.get_text()
            config = get_default_config()
            config.remove_database_path(path)
            self.logger.info(f"已移除数据库目录: {path}")

        except Exception as e:
            self.logger.error(f"移除数据库目录出错: {str(e)}")

    def _load_import_files(self):
        """加载保存的文件列表"""
        try:
            from .default_config import get_default_config
            config = get_default_config()

            for tab_name in ["Excel", "Bin", "MAT"]:
                files = config.get_import_files(tab_name)
                if files and tab_name in self.import_file_lists:
                    # 过滤掉不存在的文件
                    existing_files = [f for f in files if os.path.exists(f)]
                    self.import_file_lists[tab_name].set_files(existing_files)

            self.logger.info("已加载保存的文件列表")
        except Exception as e:
            self.logger.error(f"加载文件列表失败: {str(e)}")

    def _save_import_files(self):
        """保存当前文件列表到配置"""
        try:
            from .default_config import get_default_config
            config = get_default_config()

            for tab_name in ["Excel", "Bin", "MAT"]:
                if tab_name in self.import_file_lists:
                    file_list = self.import_file_lists[tab_name]
                    files = [item.file_path() for item in file_list._items]
                    config.set_import_files(tab_name, files)

            self.logger.info("已保存文件列表")
        except Exception as e:
            self.logger.error(f"保存文件列表失败: {str(e)}")

    def _on_refresh_files(self):
        """刷新文件列表

        从数据库目录中扫描Excel、Bin、MAT文件并显示在对应标签页
        """
        try:
            from .default_config import get_default_config
            import glob

            config = get_default_config()
            database_paths = config.get_database_paths()
            excluded_files = config.get_excluded_files()  # 获取排除列表

            # 定义文件类型扩展名
            file_types = {
                "Excel": ["*.xlsx", "*.xls"],
                "Bin": ["*.bin"],
                "MAT": ["*.mat"]
            }

            # 扫描各类型文件
            for tab_name, extensions in file_types.items():
                files = []
                for db_path in database_paths:
                    if os.path.exists(db_path):
                        for ext in extensions:
                            # 搜索目录
                            pattern = os.path.join(db_path, ext)
                            found_files = glob.glob(pattern)
                            # 过滤隐藏文件和系统文件
                            for f in found_files:
                                try:
                                    import ctypes
                                    attrs = ctypes.windll.kernel32.GetFileAttributesW(f)
                                    # FILE_ATTRIBUTE_HIDDEN = 0x2, FILE_ATTRIBUTE_SYSTEM = 0x4
                                    if attrs != -1 and not (attrs & 0x2) and not (attrs & 0x4):
                                        files.append(f)
                                except Exception:
                                    # 如果获取属性失败，默认添加
                                    files.append(f)

                # 过滤掉排除列表中的文件
                files = [f for f in files if f not in excluded_files]

                # 更新对应标签页的文件列表
                if tab_name in self.import_file_lists:
                    self.import_file_lists[tab_name].set_files(files)
                    # 保存文件列表到配置
                    config.set_import_files(tab_name, files)

            self.logger.info(f"已刷新文件列表，扫描了 {len(database_paths)} 个目录")

        except Exception as e:
            self.logger.error(f"刷新文件列表出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"刷新文件列表失败: {str(e)}")

    def _on_delete_files(self):
        """删除选中的文件"""
        try:
            # 获取当前标签页
            current_index = self.import_tab_bar.currentIndex()
            tab_names = ["Excel", "Bin", "MAT"]
            if current_index < len(tab_names):
                current_tab = tab_names[current_index]
                if current_tab in self.import_file_lists:
                    file_list = self.import_file_lists[current_tab]
                    selected_files = file_list.get_selected_files()

                    if not selected_files:
                        QMessageBox.information(self, "提示", "请先选择要移除的文件")
                        return

                    # 确认删除
                    reply = QMessageBox.question(
                        self,
                        "确认移除",
                        f"确定要从列表中移除选中的 {len(selected_files)} 个文件吗？\n（文件不会从磁盘删除）",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        from .default_config import get_default_config
                        config = get_default_config()

                        # 将移除的文件添加到排除列表
                        for f in selected_files:
                            config.add_excluded_file(f)

                        # 清除选中状态并从列表移除
                        file_list.clear_selection()
                        # 获取当前所有文件，排除选中的
                        current_files = [item.file_path() for item in file_list._items 
                                        if item.file_path() not in selected_files]
                        # 重新设置文件列表
                        file_list.set_files(current_files)
                        # 保存文件列表到配置
                        config.set_import_files(current_tab, current_files)
                        self.logger.info(f"已从列表移除 {len(selected_files)} 个文件")

        except Exception as e:
            self.logger.error(f"移除文件出错: {str(e)}")

    def _on_export_dashboard(self):
        """导出仪表盘数据按钮点击事件"""
        try:
            # 创建并显示导出对话框
            self._export_dialog = ExportDialog(self)
            self._export_dialog.export_confirmed.connect(self._do_export_dashboard)
            
            # 设置可用的波段列表
            if hasattr(self, '_bin_parse_result') and self._bin_parse_result:
                bands = self._bin_parse_result.get("bands", {})
                band_order = ["L", "S", "C"]
                valid_bands = [b for b in band_order if bands.get(b) is not None]
                # 转换为中文波段名称
                band_labels = [f"{b}波段" for b in valid_bands]
                self._export_dialog.set_available_bands(band_labels)
            
            self._export_dialog.exec_()

        except Exception as e:
            self.logger.error(f"打开导出对话框出错: {str(e)}")
            CustomMessageBox.critical(self, "错误", f"打开导出对话框失败: {str(e)}")


    def _do_export_dashboard(self, export_config: dict):
        """执行仪表盘数据导出
        
        Args:
            export_config: 导出配置字典
        """
        try:
            self.logger.info(f"执行仪表盘数据导出: {export_config}")
            
            # 检查是否有 BIN 解析结果
            if not hasattr(self, '_bin_parse_result') or self._bin_parse_result is None:
                CustomMessageBox.warning(self, "警告", "没有可导出的数据")
                return
            
            # 显示加载蒙版
            if hasattr(self, '_export_dialog') and self._export_dialog:
                self._export_dialog.show_loading()
            
            # 获取原文件名（不含扩展名）
            source_file_name = "export"
            if hasattr(self, '_current_parse_file_path') and self._current_parse_file_path:
                import os
                source_file_name = os.path.splitext(os.path.basename(self._current_parse_file_path))[0]
            
            # 创建导出工作线程
            from cores.ThreadWorker import ExportWorker
            
            self._export_worker = ExportWorker(self._bin_parse_result, export_config, source_file_name)
            self._export_worker.progress.connect(self._on_export_progress)
            self._export_worker.status.connect(self._on_export_status)
            self._export_worker.finished.connect(self._on_export_finished)
            self._export_worker.start()
            
        except Exception as e:
            self.logger.error(f"导出仪表盘数据出错: {str(e)}")
            if hasattr(self, '_export_dialog') and self._export_dialog:
                self._export_dialog.hide_loading()
            CustomMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _on_export_progress(self, value: int):
        """导出进度更新回调"""
        if hasattr(self, '_export_dialog') and self._export_dialog:
            self._export_dialog.update_progress(value)

    def _on_export_status(self, status: str):
        """导出状态更新回调"""
        if hasattr(self, '_export_dialog') and self._export_dialog:
            self._export_dialog.update_status(status)

    def _on_export_finished(self, success: bool, message: str):
        """导出完成回调"""
        try:
            # 隐藏加载蒙版
            if hasattr(self, '_export_dialog') and self._export_dialog:
                self._export_dialog.hide_loading()
                self._export_dialog.accept()  # 关闭对话框
                self._export_dialog = None
            
            # 清理工作线程
            self._export_worker = None
            
            if success:
                CustomMessageBox.information(self, "成功", message)
            else:
                CustomMessageBox.warning(self, "导出失败", message)
                
        except Exception as e:
            self.logger.error(f"导出完成处理出错: {str(e)}")

    def _on_parse_file(self):
        """解析选中的文件"""
        try:
            # 获取当前标签页
            current_index = self.import_tab_bar.currentIndex()
            tab_names = ["Excel", "Bin", "MAT"]
            if current_index >= len(tab_names):
                return

            current_tab = tab_names[current_index]

            # 获取选中的文件
            if current_tab not in self.import_file_lists:
                return

            file_list = self.import_file_lists[current_tab]
            selected_file = file_list.get_selected_file()

            if not selected_file:
                QMessageBox.information(self, "提示", "请先选择要解析的文件")
                return

            # 重置仪表盘标签页和卡片状态
            self._reset_dashboard()

            # 根据文件类型进行不同处理
            if current_tab == "Excel":
                self._parse_excel_file(selected_file)
            elif current_tab == "Bin":
                self._parse_bin_file(selected_file)
            elif current_tab == "MAT":
                # TODO: 实现MAT文件解析
                QMessageBox.information(self, "提示", "MAT文件解析功能待实现")

        except Exception as e:
            self.logger.error(f"解析文件出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"解析文件失败: {str(e)}")

    def _reset_dashboard(self):
        """重置仪表盘标签页和卡片状态"""
        try:
            if hasattr(self, 'dashboard_tab_bar'):
                # 移除现有标签
                while self.dashboard_tab_bar.count() > 0:
                    self.dashboard_tab_bar.removeTab(0)

                # 移除现有仪表盘组件
                while self.dashboard_tab_stack.count() > 0:
                    widget = self.dashboard_tab_stack.widget(0)
                    self.dashboard_tab_stack.removeWidget(widget)

                # 添加一个空白的初始标签页
                self.dashboard_tab_bar.add_tab("", "")
                
                dashboard = DashboardWidget()
                dashboard.clear_values()
                self.dashboard_tab_stack.addWidget(dashboard)

            # 重置文件信息标签
            if hasattr(self, 'dashboard_info_label'):
                self.dashboard_info_label.setText("文件信息")

            # 重置已激活波段索引
            self._activated_band_index = None

            # 禁用导出按钮
            if hasattr(self, 'export_dashboard_btn'):
                self.export_dashboard_btn.setEnabled(False)

            self.logger.debug("仪表盘状态已重置")

        except Exception as e:
            self.logger.error(f"重置仪表盘状态出错: {str(e)}")

    def _parse_excel_file(self, file_path: str):
        """解析Excel文件（使用子线程）

        Args:
            file_path: Excel文件路径
        """
        try:
            self.logger.info(f"开始解析Excel文件: {file_path}")

            # 清空所有显示内容
            self._clear_all_displays()

            # 禁用导入数据按钮
            if hasattr(self, 'import_data_btn'):
                self.import_data_btn.setEnabled(False)

            # 保存当前文件路径供回调使用
            self._current_parse_file_path = file_path

            # 开始动画
            self._on_process_started()

            # 使用data_controller的import_data方法（内部使用DataWorker子线程）
            # 连接解析完成的回调
            self.data_controller.process_finished.disconnect()
            self.data_controller.process_finished.connect(self._on_process_finished)

            # 在data_controller中暂存对main_window的回调需求
            # 为了避免修改data_controller结构，我们直接创建工作线程
            from cores.ThreadWorker import DataWorker

            self._parse_worker = DataWorker(file_path)
            self._parse_worker.finished.connect(self._on_parse_excel_finished)
            self._parse_worker.start()

        except Exception as e:
            self._on_process_finished()
            self.logger.error(f"解析Excel文件出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"解析Excel文件失败: {str(e)}")

    def _on_parse_excel_finished(self, success: bool, message: str, result: dict, data: object):
        """解析Excel文件完成的回调

        Args:
            success: 是否成功
            message: 消息
            result: 处理结果字典
            data: 处理后的数据
        """
        try:
            # 结束动画
            self._on_process_finished()

            if not success:
                QMessageBox.critical(self, "错误", message)
                return

            # 更新数据控制器的数据
            if data is not None:
                self.data_controller.data = data
                self.data_controller.processor.data = data

            # 更新仪表盘 - 获取第一个仪表盘组件
            if hasattr(self, 'dashboard_tab_stack') and self.dashboard_tab_stack.count() > 0:
                current_dashboard = self.dashboard_tab_stack.widget(0)
                if current_dashboard:
                    current_dashboard.update_values(result)
                    self.logger.info(f"已更新仪表盘：总脉冲数={result.get('total_pulses')}")
                else:
                    self.logger.warning("未找到仪表盘组件")
            else:
                self.logger.warning("dashboard_tab_stack 不存在或为空")

            # 更新标签页名称（使用波段名）
            band = result.get("band", "未知")
            if band and hasattr(self, 'dashboard_tab_bar'):
                # 更新第一个标签页名称
                self.dashboard_tab_bar.set_tab_text(0, f"{band}")

            # 更新文件信息标签
            if hasattr(self, 'dashboard_info_label') and hasattr(self, '_current_parse_file_path'):
                file_name = os.path.basename(self._current_parse_file_path)
                self.dashboard_info_label.setText("当前文件: " + file_name)

            # 清除文件选中状态
            current_index = self.import_tab_bar.currentIndex()
            tab_names = ["Excel", "Bin", "MAT"]
            if current_index < len(tab_names):
                current_tab = tab_names[current_index]
                if current_tab in self.import_file_lists:
                    self.import_file_lists[current_tab].clear_selection()

            # 启用导入数据按钮
            if hasattr(self, 'import_data_btn'):
                self.import_data_btn.setEnabled(True)

            # 保存解析结果供激活时使用（Excel只有一个波段，直接保存数据）
            self._parsed_data = data
            self._parsed_result = result
            self._parse_type = "excel"

            self.logger.info(f"Excel文件解析完成: {self._current_parse_file_path}")

            # 更新已选中信息标签
            self._update_selected_info_label()

        except Exception as e:
            self.logger.error(f"解析Excel文件回调出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"解析Excel文件失败: {str(e)}")
        finally:
            # 清理工作线程
            self._parse_worker = None

    def _parse_bin_file(self, file_path: str):
        """解析Bin文件（使用子线程）

        Args:
            file_path: Bin文件路径
        """
        try:
            self.logger.info(f"开始解析Bin文件: {file_path}")

            # 清空所有显示内容
            self._clear_all_displays()

            # 禁用导入数据按钮
            if hasattr(self, 'import_data_btn'):
                self.import_data_btn.setEnabled(False)

            # 保存当前文件路径供回调使用
            self._current_parse_file_path = file_path

            # 开始动画
            self._on_process_started()

            # 创建Bin解析工作线程
            from cores.ThreadWorker import BinWorker

            # 获取当前解析策略
            strategy = "amplitude"  # 默认
            if hasattr(self, 'import_command_bar'):
                strategy = self.import_command_bar.get_current_strategy()
            
            self.logger.info(f"使用解析策略: {strategy}")
            
            self._bin_worker = BinWorker(file_path, strategy)
            self._bin_worker.finished.connect(self._on_parse_bin_finished)
            self._bin_worker.start()

        except Exception as e:
            self._on_process_finished()
            self.logger.error(f"解析Bin文件出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"解析Bin文件失败: {str(e)}")

    def _on_parse_bin_finished(self, success: bool, result: dict):
        """解析Bin文件完成的回调

        Args:
            success: 是否成功
            result: 解析结果字典
        """
        try:
            # 结束动画
            self._on_process_finished()

            if not success:
                error_msg = result.get("error", "未知错误")
                QMessageBox.critical(self, "错误", f"Bin文件解析失败: {error_msg}")
                return

            # 保存解析结果供后续使用
            self._bin_parse_result = result

            # 更新仪表盘显示多个波段
            bands = result.get("bands", {})
            discarded = result.get("discarded_count", 0)

            # 清空并重新添加波段标签
            if hasattr(self, 'dashboard_tab_bar'):
                # 移除现有标签
                while self.dashboard_tab_bar.count() > 0:
                    self.dashboard_tab_bar.removeTab(0)

                # 移除现有仪表盘组件
                while self.dashboard_tab_stack.count() > 0:
                    widget = self.dashboard_tab_stack.widget(0)
                    self.dashboard_tab_stack.removeWidget(widget)

                # 添加各波段标签
                band_order = ["L", "S", "C"]
                for band_key in band_order:
                    band_info = bands.get(band_key)
                    if band_info is not None:
                        band_result = band_info.get("result", {})
                        band_name = band_result.get("band", f"{band_key}波段")

                        # 添加标签
                        self.dashboard_tab_bar.add_tab(band_name, "")

                        # 创建并添加仪表盘
                        dashboard = DashboardWidget()
                        dashboard.update_values(band_result)
                        self.dashboard_tab_stack.addWidget(dashboard)

            # 更新文件信息标签
            if hasattr(self, 'dashboard_info_label'):
                file_name = os.path.basename(self._current_parse_file_path)
                self.dashboard_info_label.setText(f"当前文件: {file_name} (已丢弃 {discarded} 条)")

            # 清除文件选中状态
            current_index = self.import_tab_bar.currentIndex()
            tab_names = ["Excel", "Bin", "MAT"]
            if current_index < len(tab_names):
                current_tab = tab_names[current_index]
                if current_tab in self.import_file_lists:
                    self.import_file_lists[current_tab].clear_selection()

            # 启用导入数据按钮（如果有波段数据）
            has_bands = any(bands.get(b) is not None for b in ["L", "S", "C"])
            if has_bands and hasattr(self, 'import_data_btn'):
                self.import_data_btn.setEnabled(True)
            
            # 启用导出按钮（BIN 解析完成后）
            if has_bands and hasattr(self, 'export_dashboard_btn'):
                self.export_dashboard_btn.setEnabled(True)

            # 保存解析结果供激活时使用
            self._bin_parse_result = result
            self._parse_type = "bin"

            self.logger.info(f"Bin文件解析完成: {self._current_parse_file_path}")

            # 更新已选中信息标签
            self._update_selected_info_label()

        except Exception as e:
            self.logger.error(f"解析Bin文件回调出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"处理Bin文件结果失败: {str(e)}")
        finally:
            # 清理工作线程
            self._bin_worker = None

    def _on_import_data_clicked(self):
        """导入数据按钮点击事件

        根据解析类型激活对应的波段数据，然后切换到处理界面
        """
        try:
            self.logger.info("导入数据按钮被点击")

            # 清空所有显示内容
            self._clear_all_displays()

            if not hasattr(self, '_parse_type'):
                QMessageBox.warning(self, "警告", "请先解析文件")
                return

            if self._parse_type == "excel":
                # Excel文件：直接使用已解析的数据
                if not hasattr(self, '_parsed_data') or self._parsed_data is None:
                    QMessageBox.warning(self, "警告", "未找到Excel解析数据")
                    return

                # 激活数据
                self.data_controller.processor.activate_band_data(self._parsed_data)
                self.data_controller.data = self._parsed_data
                self.data_controller.processor.data = self._parsed_data
                
                # 同步plotter配置
                if hasattr(self.data_controller.processor, "plotter"):
                    self.data_controller.plotter = self.data_controller.processor.plotter

                # 更新切片信息
                result = self._parsed_result
                band = result.get("band", "未知")
                slice_count = result.get("slice_count", 0)
                self.data_controller.slice_info_updated1.emit(f"数据包位于{band}，")
                self.data_controller.slice_info_updated2.emit(f"预计将获得{slice_count}个250ms切片")
                self.data_controller.sliced_data_count_tmp = slice_count  # 保存预计切片数

                self.logger.info(f"Excel数据已激活，波段: {band}")

            elif self._parse_type == "bin":
                # Bin文件：从临时文件加载当前选中波段的数据
                if not hasattr(self, '_bin_parse_result'):
                    QMessageBox.warning(self, "警告", "未找到Bin解析结果")
                    return

                # 获取当前选中的波段
                current_band_index = self.dashboard_tab_bar.currentIndex()
                band_order = ["L", "S", "C"]
                bands = self._bin_parse_result.get("bands", {})

                # 找出有效的波段顺序
                valid_bands = [b for b in band_order if bands.get(b) is not None]
                if current_band_index >= len(valid_bands):
                    QMessageBox.warning(self, "警告", "未选中有效波段")
                    return

                selected_band = valid_bands[current_band_index]
                band_info = bands.get(selected_band)
                temp_file = band_info.get("temp_file")

                if not temp_file or not os.path.exists(temp_file):
                    QMessageBox.warning(self, "警告", f"临时文件不存在: {temp_file}")
                    return

                # 如果是切换波段后的重新导入，清空之前的显示内容
                if self._activated_band_index is not None and current_band_index != self._activated_band_index:
                    self.logger.info("切换波段后重新导入，清空之前的状态")
                    self._clear_all_displays()

                # 从临时文件加载数据
                import numpy as np
                data = np.load(temp_file)

                # 激活数据
                self.data_controller.processor.activate_band_data(data)
                self.data_controller.data = data
                self.data_controller.processor.data = data

                # 同步plotter配置
                if hasattr(self.data_controller.processor, "plotter"):
                    self.data_controller.plotter = self.data_controller.processor.plotter

                # 更新切片信息
                result = band_info.get("result", {})
                band = result.get("band", f"{selected_band}波段")
                slice_count = result.get("slice_count", 0)
                self.data_controller.slice_info_updated1.emit(f"数据包位于{band}，")
                self.data_controller.slice_info_updated2.emit(f"预计将获得{slice_count}个250ms切片")
                self.data_controller.sliced_data_count_tmp = slice_count  # 保存预计切片数

                self.logger.info(f"Bin波段数据已激活，波段: {band}")

                # 记录已激活的波段索引
                self._activated_band_index = current_band_index

            # 更新状态
            self.import_success = True
            self.data_controller.update_last_file_path(self._current_parse_file_path)

            # 重置滚动容器/合并界面
            if hasattr(self, "scroll_container") and self.scroll_container:
                self.scroll_layout_manager._on_reset_merge()
                self.scroll_container.enable_scroll(False)

            # 发射数据准备信号
            self.data_controller.data_ready.emit(True)

            # 切换到处理界面
            self.switch_to_process_interface()

            # 禁用导入数据按钮（防止重复点击）
            self.import_data_btn.setEnabled(False)

        except Exception as e:
            self.logger.error(f"导入数据出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"导入数据失败: {str(e)}")

    def _on_dashboard_band_changed(self, index: int):
        """仪表盘波段标签切换事件

        当用户切换到不同波段时，检查是否需要重新启用导入按钮

        Args:
            index: 新选中的标签索引
        """
        try:
            # 只在bin文件解析后且已有激活波段的情况下处理
            if (getattr(self, '_parse_type', None) == 'bin' 
                and self._activated_band_index is not None
                and hasattr(self, '_bin_parse_result')):
                
                # 如果切换到了不同的波段，启用导入按钮
                if index != self._activated_band_index:
                    self.logger.info(f"波段切换: {self._activated_band_index} -> {index}，启用导入按钮")
                    self.import_data_btn.setEnabled(True)
                else:
                    # 切换回已激活的波段，禁用导入按钮
                    self.import_data_btn.setEnabled(False)
            
            # 更新已选中信息标签
            self._update_selected_info_label()
                    
        except Exception as e:
            self.logger.error(f"处理波段切换事件出错: {str(e)}")

    def _update_selected_info_label(self):
        """更新已选中信息标签"""
        try:
            if not hasattr(self, 'selected_info_label'):
                return

            # 获取文件名
            file_path = getattr(self, '_current_parse_file_path', None)
            if not file_path:
                self.selected_info_label.hide()
                return

            import os
            file_name = os.path.basename(file_path)

            # 获取当前选中的波段标签
            band_name = ""
            if hasattr(self, 'dashboard_tab_bar') and self.dashboard_tab_bar.count() > 0:
                current_index = self.dashboard_tab_bar.currentIndex()
                band_name = self.dashboard_tab_bar.tabText(current_index)

            # 构建显示文本
            if band_name:
                text = f"已选中: {file_name} - {band_name}"
            else:
                text = f"已选中: {file_name}"

            self.selected_info_label.setText(text)
            self.selected_info_label.show()

        except Exception as e:
            self.logger.error(f"更新已选中信息标签出错: {str(e)}")

    def _on_file_selection_changed(self, has_selection: bool):
        """文件选中状态改变

        当有文件被选中时禁用标签切换，取消选中时恢复

        Args:
            has_selection: 是否有文件被选中
        """
        try:
            # 禁用/启用标签栏
            self.import_tab_bar.setEnabled(not has_selection)

            # 更新标签栏样式提示禁用状态
            if has_selection:
                self.import_tab_bar.setStyleSheet("""
                    QTabBar {
                        border: none;
                        background: transparent;
                        font-family: "Microsoft YaHei";
                        font-size: 14px;
                    }
                    QTabBar::tab {
                        border: none;
                        background: transparent;
                        color: #999999;
                    }
                    QTabBar::tab:first {
                        margin-left: 10px;
                    }
                """)
            else:
                self.import_tab_bar.setStyleSheet("""
                    QTabBar {
                        border: none;
                        background: transparent;
                        font-family: "Microsoft YaHei";
                        font-size: 14px;
                    }
                    QTabBar::tab {
                        border: none;
                        background: transparent;
                    }
                    QTabBar::tab:first {
                        margin-left: 10px;
                    }
                """)
        except Exception as e:
            self.logger.error(f"更新标签状态出错: {str(e)}")

    def _get_current_params(self):
        """获取当前的参数设置

        获取用户在界面上输入的所有参数值，包括聚类参数、识别参数和合并参数。

        Returns:
            dict: 包含所有参数的字典
        """
        params = {}
        try:
            # 获取基础参数（聚类参数和识别参数）
            for i, param_name in enumerate(
                [
                    "epsilon_CF",
                    "epsilon_PW",
                    "min_pts",
                    "pa_weight",
                    "dtoa_weight",
                    "threshold",
                ]
            ):
                if i < len(self.param_inputs):
                    text = self.param_inputs[i].text().strip()
                    if text and text.replace(".", "", 1).isdigit():  # 允许小数点
                        params[param_name] = float(text)

            # 获取合并参数（如果存在merge_param_inputs）
            if hasattr(self, "merge_param_inputs") and self.merge_param_inputs:
                merge_param_names = [
                    "pri_equal_doa_tolerance",
                    "pri_different_doa_tolerance",
                    "pri_different_cf_tolerance",
                    "pri_none_doa_tolerance",
                ]

                for i, param_name in enumerate(merge_param_names):
                    if i < len(self.merge_param_inputs):
                        text = self.merge_param_inputs[i].text().strip()
                        if text and text.replace(".", "", 1).isdigit():  # 允许小数点
                            params[param_name] = float(text)

        except Exception as e:
            self.logger.error(f"获取当前参数出错: {str(e)}")
        return params

    def _on_start_process(self):
        """全速处理按钮点击事件处理"""
        try:
            # 检查保存路径是否已设置
            if not hasattr(self, "save_dir") or not self.save_dir:
                self.logger.warning("未设置保存目录")
                self.trigger_path_label_blink()  # 闪烁保存路径提示
                QMessageBox.warning(self, "警告", "请先选择保存目录")
                return

            # 检查是否已导入数据
            if (
                not self.data_controller.processor
                or len(self.data_controller.processor.data) == 0
            ):
                QMessageBox.warning(self, "警告", "请先导入雷达数据")
                return

            # 获取当前用户输入的参数
            current_user_params = self._get_current_params()
            self.logger.info(f"获取用户输入参数: {current_user_params}")

            # 更新DataController中的参数
            self.data_controller.update_params_from_inputs(current_user_params)
            self.logger.info("已更新DataController参数")

            # 保存当前参数用于后续比较
            self.last_process_params = current_user_params
            self.logger.info(f"记录处理参数: {self.last_process_params}")

            # 获取当前按钮状态
            self.buttons_state = self.get_buttons_state()

            # 禁用所有按钮
            self._update_buttons_state(False)
            self.browse_save_btn1.setEnabled(False)
            self.browse_save_btn2.setEnabled(False)

            # 执行全速处理
            success = self.data_controller.full_speed_process()

            if not success:
                QMessageBox.critical(self, "错误", "启动全速处理失败")
                # 还原按钮状态
                self.set_buttons_state(self.buttons_state)

        except Exception as e:
            self.logger.error(f"全速处理出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"全速处理出错: {str(e)}")
            # 还原按钮状态
            if hasattr(self, "buttons_state"):
                self.set_buttons_state(self.buttons_state)

    def mousePressEvent(self, event):
        """处理鼠标点击事件

        当点击非输入框区域时，清除当前输入框的焦点。
        当点击文件列表外的区域时，取消文件选中状态。

        Args:
            event: 鼠标事件对象
        """
        # 获取当前焦点控件
        focused_widget = QApplication.focusWidget()
        # 如果有控件被选中且是输入框
        if isinstance(focused_widget, QLineEdit):
            # 清除焦点
            focused_widget.clearFocus()
        
        # 检查是否点击在文件列表外，若是则取消选中
        try:
            click_pos = event.pos()
            widget_at_pos = self.childAt(click_pos)
            
            is_in_file_list = False
            if widget_at_pos:
                parent = widget_at_pos
                while parent:
                    if hasattr(self, 'import_file_lists'):
                        for file_list in self.import_file_lists.values():
                            if parent == file_list:
                                is_in_file_list = True
                                break
                    if is_in_file_list:
                        break
                    parent = parent.parent()
            
            if not is_in_file_list and hasattr(self, 'import_file_lists'):
                for file_list in self.import_file_lists.values():
                    if file_list.has_selection():
                        file_list.clear_selection()
        except Exception as e:
            self.logger.error(f"处理文件列表选中状态时出错: {str(e)}")
        
        # 调用父类的鼠标点击事件
        super().mousePressEvent(event)

    def _setup_window(self):
        """设置窗口基本属性

        配置窗口标题、尺寸和样式。
        """
        self.setWindowTitle("雷达信号多维参数联合智能分选")
        self.setMinimumSize(
            self.dimensions["window_min_width"], self.dimensions["window_min_height"]
        )
        self.resize(self.dimensions["window_width"], self.dimensions["window_height"])
        self.setStyleSheet(self.styles["main_window"])

        # 创建菜单栏
        self.menubar = self.menuBar()
        self.menubar.setStyleSheet(self.styles["menubar"])

        # 创建文件菜单
        self.file_menu = self.menubar.addMenu("文件")
        self.file_menu.setStyleSheet(self.styles["menu"])

        # 添加文件菜单项
        self.import_action = self.file_menu.addAction("导入数据")
        self.import_action.triggered.connect(self.browse_import_file)

        self.save_action = self.file_menu.addAction("保存结果")
        self.save_action.triggered.connect(self.save_results)

        self.file_menu.addSeparator()

        self.exit_action = self.file_menu.addAction("退出")
        self.exit_action.triggered.connect(self.close)

        # 创建模型菜单
        self.model_menu = self.menubar.addMenu("模型")
        self.model_menu.setStyleSheet(self.styles["menu"])

        # 添加模型菜单项
        self.load_model_action = self.model_menu.addAction("载入模型")
        self.load_model_action.triggered.connect(self._load_model)

        self.manage_model_action = self.model_menu.addAction("管理模型")
        self.manage_model_action.triggered.connect(self._show_model_manager)

        # 创建设置菜单
        self.settings_menu = self.menubar.addMenu("设置")
        self.settings_menu.setStyleSheet(self.styles["menu"])

        # 添加设置菜单项
        self.default_config_action = self.settings_menu.addAction("首选项")
        self.default_config_action.triggered.connect(self._show_config_dialog)

        # 创建帮助菜单
        self.help_menu = self.menubar.addMenu("帮助")
        self.help_menu.setStyleSheet(self.styles["menu"])

        # 添加帮助菜单项
        self.about_action = self.help_menu.addAction("关于")
        self.about_action.triggered.connect(self._show_about_dialog)

        # 初始化菜单项状态
        self.save_action.setEnabled(False)

    def setup_ui(self):
        """设置UI界面

        调用ui_functions模块来设置界面布局和控件。
        """
        setup_ui(self)

    def browse_import_file(self):
        """浏览文件按钮点击事件处理

        打开文件选择对话框，允许用户选择Excel文件。
        从上次访问的目录开始浏览。
        """
        # 获取上次访问的目录
        initial_dir = self.data_controller.get_last_directory()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Excel文件",
            initial_dir,  # 使用上次的目录
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )

        if file_path:  # 只检查是否选择了文件
            path = Path(file_path)
            if path.suffix.lower() in [".xlsx", ".xls"]:
                self.import_path.setText(file_path)
                # self.import_btn.setEnabled(True)  # 启用导入按钮
            else:
                QMessageBox.warning(self, "错误", "请选择Excel文件")
                self.import_path.setText("")
                # self.import_btn.setEnabled(False)

    def import_data(self):
        """导入数据"""
        try:
            file_path = self.import_path.text()
            if not file_path:
                QMessageBox.warning(self, "警告", "请选择要导入的文件")
                return

            # 清空所有显示内容
            self._clear_all_displays()

            # 显示加载动画
            self._on_process_started()

            # 在工作线程中导入数据
            success, message = self.data_controller.import_data(file_path)

            if not success:
                QMessageBox.warning(self, "错误", message)
                self._on_process_finished()
            else:
                # 更新最后使用的文件路径
                self.data_controller.update_last_file_path(file_path)

                # 更新是否导入成功状态
                self.import_success = True

                # 记录当前导入的文件路径
                current_file = self.import_path.text()
                self.logger.info(f"成功导入文件: {current_file}")
                self.logger.info(f"上次处理的文件: {self.last_processed_file}")

                if hasattr(self, "scroll_container") and self.scroll_container:
                    # 禁用滚动功能（会自动回到初始位置）
                    self.scroll_layout_manager._on_reset_merge()
                    self.logger.info("已重置合并界面状态")

                # 滚动容器回到初始状态并禁用滚动
                if hasattr(self, "scroll_container") and self.scroll_container:
                    # 禁用滚动功能（会自动回到初始位置）
                    self.scroll_container.enable_scroll(False)
                    self.logger.info("滚动容器已回到初始状态并禁用滚动")

                # 检查是否需要重新启用全速处理按钮
                if self.full_speed_processed:
                    # 判断是否是新导入的文件
                    if self.last_processed_file != current_file:
                        # 新导入的文件，重置状态
                        self.full_speed_processed = False
                        self.last_processed_file = None
                        self.logger.info("导入了新文件，重置全速处理状态")

                # 如果已经指定了保存路径且未全速处理过，启用开始处理按钮
                if self.save_dir and not self.full_speed_processed:
                    self.start_process_btn.setEnabled(True)
                    # 重置进度条状态
                    self.progress_bar.setValue(0)
                    self.progress_label.setText("0%")
                    self.logger.info("已导入文件且设置保存路径，启用开始处理按钮")

        except Exception as e:
            self.logger.error(f"导入数据时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"导入数据失败: {str(e)}")
            self._on_process_finished()

    def _clear_all_displays(self):
        """清空所有显示内容"""
        try:
            # 清空左侧切片图像
            if hasattr(self, "left_plots"):
                for plot in self.left_plots:
                    plot.clear()

            # 重置左侧标题
            self.left_title.setText("第0个切片数据 原始图像")

            # 清空中间聚类图像
            if hasattr(self, "middle_plots"):
                for plot in self.middle_plots:
                    plot.clear()
                # 重置标题
                self.middle_title.setText("CF/PW维度聚类 第0类")

            # 清空表格数据
            if hasattr(self, "table"):
                for row in range(self.table.rowCount()):
                    item = QTableWidgetItem(" ")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, 1, item)

            # 清空切片信息标签
            if hasattr(self, "slice_info_label1"):
                self.slice_info_label1.setText("数据包位于？波段，")
            if hasattr(self, "slice_info_label2"):
                self.slice_info_label2.setText("预计将获得  0  个250ms切片")

            # 清空文件路径输入框
            if hasattr(self, "file_path_input"):
                self.file_path_input.clear()

            # 禁用所有操作按钮
            self._update_buttons_state(False)

            # 清理数据控制器状态
            if hasattr(self, "data_controller"):
                self.data_controller.cleanup()

            # 清理图像文件
            self.cleanup_images(close_window=False)

            self.logger.debug("已清空所有显示内容")

        except Exception as e:
            self.logger.error(f"清空显示内容时出错: {str(e)}")

    def browse_save_file(self):
        """浏览保存文件的位置"""
        try:
            if self.data_controller.processor.data is None:
                QMessageBox.warning(self, "警告", "请先导入数据")
                return

            if not self.excel_results_dir.exists():
                os.makedirs(str(self.excel_results_dir), exist_ok=True)

            if self.save_dir:
                initial_dir = self.save_dir
            else:
                initial_dir = str(self.excel_results_dir)

            # 打开文件夹选择对话框
            save_dir = QFileDialog.getExistingDirectory(
                self, "选择保存目录", initial_dir, QFileDialog.ShowDirsOnly
            )

            if save_dir:
                self.logger.info(
                    f"用户选择了新的保存目录: {save_dir}, 原目录: {self.save_dir}"
                )

                # 判断是否与当前路径不同
                path_changed = self.save_dir != save_dir
                if path_changed:
                    self.logger.info("保存路径已更改")

                # 更新路径显示
                self.save_path_label1.setText(save_dir)
                self.save_path_label2.setText(save_dir)
                # 更新样式为已选择路径
                self.update_path_label_style(True)
                # 保存用户选择的路径
                self.save_dir = save_dir
                # 同时更新DataController的保存目录
                self.data_controller.set_save_dir(save_dir)

                # 检查是否已导入数据
                has_data = (
                    hasattr(self.data_controller, "processor")
                    and self.data_controller.processor is not None
                    and hasattr(self.data_controller.processor, "data")
                    and len(self.data_controller.processor.data) > 0
                )

                # 判断当前文件是否与上次处理的文件不同（使用解析选中的文件路径）
                current_file = getattr(self, '_current_parse_file_path', None)
                is_new_file = current_file and (
                    self.last_processed_file != current_file
                )

                self.logger.info(
                    f"数据控制器状态检查 - 是否有导入数据: {has_data}, 是否是新文件: {is_new_file}"
                )

                if self.full_speed_processed and path_changed:
                    # 如果全速处理过且保存路径已更改，重置全速处理状态
                    self.logger.info("保存路径已更改，重置全速处理状态")
                    self.full_speed_processed = False
                    self.last_processed_save_dir = None

                if self.full_speed_processed and is_new_file:
                    # 如果全速处理过且当前是新文件，重置全速处理状态
                    self.logger.info("导入了新文件，重置全速处理状态")
                    self.full_speed_processed = False
                    self.last_processed_file = None

                # 判断是否启用开始处理按钮：有数据且（是新文件或未全速处理过）
                should_enable = has_data and not self.full_speed_processed

                if should_enable:
                    self.logger.info("启用开始处理按钮")
                    self.start_process_btn.setEnabled(True)
                else:
                    reason = []
                    if not has_data:
                        reason.append("无导入数据")
                    if self.full_speed_processed:
                        reason.append("已全速处理过")
                    self.logger.info(f"不满足启用条件，原因: {', '.join(reason)}")
                    self.start_process_btn.setEnabled(False)

        except Exception as e:
            self.logger.error(f"选择保存目录时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"选择保存目录失败: {str(e)}")

    def get_current_save_dir(self):
        """获取当前保存目录"""
        return self.save_dir

    def save_results(self):
        """保存识别结果"""
        try:
            if not hasattr(self, "save_dir") or not self.save_dir:
                QMessageBox.warning(self, "警告", "请先选择保存目录")
                # 触发路径标签闪烁效果
                self.trigger_path_label_blink()
                return

            # 调用数据控制器的保存方法
            success, message = self.data_controller.save_results(
                self.save_dir, only_valid=True
            )

            self._do_failed_save(success, message)

        except Exception as e:
            self.logger.error(f"保存结果时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存结果失败: {str(e)}")

    def _do_failed_save(self, success: bool, message: str):
        """保存失败时的处理"""
        if success:
            # 禁用保存按钮并将文字改为"已保存"
            self.save_btn.setEnabled(False)
            self.save_btn.setText("已保存")

            # 检查当前会话中的设置
            if self.only_show_save_failures is not None:
                if self.only_show_save_failures:
                    self.logger.info(f"保存成功，已不显示成功消息: {self.save_dir}")
                    return

            # 创建自定义消息框
            msg_box = QMessageBox(
                QMessageBox.Information, "成功", f"结果已成功保存到: {self.save_dir}"
            )

            # 添加复选框
            checkbox = QCheckBox("只在保存失败时显示")
            # 设置初始状态
            if self.only_show_save_failures is not None:
                checkbox.setChecked(self.only_show_save_failures)
            else:
                checkbox.setChecked(False)

            # 设置复选框到对话框
            msg_box.setCheckBox(checkbox)

            # 显示对话框
            msg_box.exec_()

            # 保存用户选择，但仅在当前会话有效
            self.only_show_save_failures = checkbox.isChecked()
            self.logger.info(
                f"保存选项设置已更新: only_show_save_failures = {self.only_show_save_failures}"
            )
        else:
            # 保存失败总是显示警告
            QMessageBox.warning(self, "警告", f"保存失败: {message}")

    def _reset_save_button(self):
        """重置保存按钮状态"""
        if hasattr(self, "save_btn"):
            self.save_btn.setText("保存")

            # 检查是否有有效聚类
            has_valid_clusters = (
                hasattr(self, "data_controller")
                and hasattr(self.data_controller, "valid_clusters")
                and len(self.data_controller.valid_clusters) > 0
            )

            # 检查当前切片是否已保存
            already_saved = (
                hasattr(self, "data_controller")
                and hasattr(self.data_controller, "is_current_slice_saved")
                and self.data_controller.is_current_slice_saved()
            )

            if already_saved:
                # 如果已保存，禁用按钮并显示"已保存"
                self.save_btn.setEnabled(False)
                self.save_btn.setText("已保存")
                self.logger.debug(
                    f"切片 {self.data_controller.current_slice_idx + 1} 在当前参数设置下已保存"
                )
            else:
                # 只有当有有效聚类且未保存过时才启用保存按钮
                self.save_btn.setEnabled(has_valid_clusters)
                if has_valid_clusters:
                    self.save_btn.setEnabled(True)
                    self.logger.debug("有有效聚类且未保存，已启用保存按钮")
                else:
                    self.save_btn.setEnabled(False)
                    self.logger.debug("无有效聚类，已禁用保存按钮")

            # 更新路径标签样式（根据是否有保存路径）
            if hasattr(self, "update_path_label_style"):
                has_save_path = hasattr(self, "save_dir") and self.save_dir
                self.update_path_label_style(has_save_path)

    def _on_process_started(self):
        """数据处理开始时的处理"""
        try:
            self.logger.debug("开始处理，显示加载动画")
            # 禁用按钮
            # self.import_btn.setEnabled(False)
            # self.browse_import_btn.setEnabled(False)
            self.start_slice_btn.setEnabled(False)
            self.identify_btn.setEnabled(False)
            self.next_slice_btn.setEnabled(False)
            self.next_cluster_btn.setEnabled(False)

            # 显示加载动画
            self.loading_spinner.resize(self.size())
            self.loading_spinner.move(0, 0)
            self.loading_spinner.raise_()
            self.loading_spinner.start()

            # 强制更新界面
            QApplication.processEvents()

        except Exception as e:
            self.logger.error(f"显示加载动画时出错: {str(e)}")

    def _on_process_finished(self):
        """数据处理完成时的处理"""
        try:
            self.logger.debug("处理完成，停止加载动画")
            # self.import_btn.setEnabled(True)
            # self.browse_import_btn.setEnabled(True)
            self.loading_spinner.stop()

        except Exception as e:
            self.logger.error(f"处理完成回调出错: {str(e)}")

    def _on_start_slice(self):
        """开始切片按钮点击事件处理"""
        try:
            self._on_process_started()  # 显示加载动画
            success = self.data_controller.start_slicing()  # 开始切片处理

            if not success:
                QMessageBox.warning(self, "错误", "切片处理失败")
                self._on_process_finished()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"切片处理出错: {str(e)}")
            self._on_process_finished()

    def _on_identify(self):
        """识别按钮点击事件处理"""
        try:
            # 禁用所有按钮
            self._update_buttons_state(False)
            # 开始识别处理
            self._do_identify()
        except ValueError:
            QMessageBox.warning(self, "参数错误", "请输入有效的数值")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"识别处理出错: {str(e)}")

    def _do_identify(self, skip_loading_animation=False):
        """执行识别处理

        Args:
            skip_loading_animation (bool): 是否跳过加载动画显示，用于自动识别时避免重复显示
        """
        try:
            # 获取并验证参数
            epsilon_CF = float(self.param_inputs[0].text())
            epsilon_PW = float(self.param_inputs[1].text())
            min_pts = int(self.param_inputs[2].text())

            # 获取识别参数
            pa_threshold = float(self.param_inputs[3].text())
            dtoa_threshold = float(self.param_inputs[4].text())
            pa_weight = float(self.param_inputs[5].text())
            dtoa_weight = float(self.param_inputs[6].text())
            threshold = float(self.param_inputs[7].text())

            # 验证参数
            if epsilon_CF <= 0 or epsilon_PW <= 0 or min_pts <= 0:
                QMessageBox.warning(self, "参数错误", "参数必须大于0")
                return

            if (
                pa_threshold <= 0
                or dtoa_threshold <= 0
                or pa_weight <= 0
                or dtoa_weight <= 0
                or threshold <= 0
            ):
                QMessageBox.warning(self, "参数错误", "识别参数必须大于0")
                return

            # 设置参数并执行识别
            self.data_controller.set_cluster_params(epsilon_CF, epsilon_PW, min_pts)
            self.data_controller.set_identify_params(
                pa_threshold, dtoa_threshold, pa_weight, dtoa_weight, threshold
            )

            # 更新参数指纹，记录参数是否发生变化
            params_changed = self.data_controller.update_param_fingerprint()
            if params_changed:
                self.logger.info("参数已更改，生成了新的参数指纹")

            # 启动识别处理
            self.data_controller.start_identification()

        except ValueError as e:
            self.logger.error(f"参数格式错误: {str(e)}")
            QMessageBox.warning(self, "警告", "请检查参数格式是否正确")
            self.identify_btn.setEnabled(True)
        except Exception as e:
            self.logger.error(f"识别处理出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"识别处理失败: {str(e)}")
            self.identify_btn.setEnabled(True)

    def update_cluster_display(
        self,
        dim_name: str,
        cluster_valid_idx: str,
        cluster_idx: str,
        cluster_info: dict,
    ):
        """更新聚类显示"""
        try:
            # 更新标题
            if self.data_controller.only_show_identify_result:
                self.middle_title.setText(
                    f"{dim_name}维度聚类 第{cluster_valid_idx}类 总第{cluster_idx}类"
                )
            else:
                self.middle_title.setText(f"{dim_name}维度聚类 第{cluster_valid_idx}类")

            # 获取图像路径
            image_paths = cluster_info.get("image_paths", {})

            # 按顺序显示5张图像
            # plot_types = ['CF', 'PW', 'PA', 'DOA', 'DTOA']
            plot_types = ["CF", "PW", "PA", "DTOA", "DOA"]

            # 遍历所有图像显示区域
            for i, plot_type in enumerate(plot_types):
                if i < len(self.middle_plots):
                    path = image_paths.get(plot_type)
                    if path and os.path.exists(path):
                        self.middle_plots[i].display_image(path)
                    else:
                        self.logger.warning(f"图像路径无效: {path}")
                        self.middle_plots[i].clear()

        except Exception as e:
            self.logger.error(f"更新聚类显示出错: {str(e)}")

    def update_slice_display(self, image_paths: dict):
        """更新切片图像显示"""
        try:
            if not hasattr(self, "left_plots"):
                self.logger.warning("self.left_plots 不存在")
                return

            # 更新标题
            slice_idx = self.data_controller.current_slice_idx + 1
            self.left_title.setText(f"第{slice_idx}个切片数据  原始图像")

            # 按顺序显示5张图像
            # plot_types = ['CF', 'PW', 'PA', 'DOA', 'DTOA']
            plot_types = ["CF", "PW", "PA", "DTOA", "DOA"]

            # 遍历所有图像显示区域
            for i, plot_type in enumerate(plot_types):
                if hasattr(self, "left_plots") and i < len(self.left_plots):
                    path = image_paths.get(plot_type)
                    if path and os.path.exists(path):
                        self.left_plots[i].display_image(path)
                    else:
                        self.left_plots[i].clear()

        except Exception as e:
            self.logger.error(f"更新切片图像显示时出错: {str(e)}")

    def _on_next_slice(self):
        """处理下一片按钮点击事件"""
        try:
            # 检查是否需要保存当前切片
            if self.save_btn.isEnabled():
                # 检查是否已经有保存的选择
                if not hasattr(self, "auto_next_slice_choice"):
                    self.auto_next_slice_choice = None

                # 如果没有保存的选择，显示对话框
                if self.auto_next_slice_choice is None:
                    # 创建自定义消息框
                    msg_box = QMessageBox(
                        QMessageBox.Question,
                        "提示",
                        "当前切片的识别结果尚未保存，是否继续切换？",
                    )

                    # 添加按钮
                    yes_button = QPushButton("继续")
                    cancel_button = QPushButton("取消")
                    save_button = QPushButton("保存再继续")

                    msg_box.addButton(yes_button, QMessageBox.ActionRole)
                    msg_box.addButton(cancel_button, QMessageBox.NoRole)
                    msg_box.addButton(save_button, QMessageBox.YesRole)

                    # 添加复选框
                    checkbox = QCheckBox("保持以上选择并不再询问")
                    msg_box.setCheckBox(checkbox)

                    # 显示对话框
                    reply = NextSliceChoice(msg_box.exec_())

                    # 如果用户勾选了复选框，保存选择
                    if checkbox.isChecked():
                        self.auto_next_slice_choice = reply
                else:
                    # 使用保存的选择
                    reply = self.auto_next_slice_choice

                # 根据用户选择执行操作
                if reply == NextSliceChoice.CANCEL:  # 取消
                    return
                elif reply == NextSliceChoice.SAVE_CONTINUE:  # 保存再继续
                    # 检查是否已选择保存目录
                    if not hasattr(self, "save_dir") or not self.save_dir:
                        QMessageBox.warning(self, "警告", "请先选择保存目录")
                        # 触发路径标签闪烁效果
                        self.trigger_path_label_blink()
                        return
                    # 保存当前切片，然后继续切换
                    success, message = self.data_controller.save_results(
                        self.save_dir, only_valid=True
                    )
                    # 保存失败时的处理
                    self._do_failed_save(success, message)

            # 显示加载动画
            self._on_process_started()

            # 禁用所有按钮，避免重复点击
            self._update_buttons_state(False)

            # 显示下一片
            if self.data_controller.show_next_slice():
                # 更新按钮状态
                self.identify_btn.setEnabled(True)

                # 检查是否有下一片可用
                has_next_slice, _ = self.data_controller.check_next_available()
                self.next_slice_btn.setEnabled(has_next_slice)

                # 重置保存按钮状态
                self.save_btn.setText("保存")
                self.save_btn.setEnabled(False)

                self.logger.debug("已显示下一片数据")

                # 检查并更新参数指纹
                self.data_controller.update_param_fingerprint()

                # 检查是否需要自动识别
                if self.auto_identify_checkbox.isChecked():
                    self.logger.debug("自动识别选项已启用，开始识别处理")
                    self._do_identify(skip_loading_animation=True)
                else:
                    # 如果不自动识别，则启用识别和重绘按钮并停止加载动画
                    self.identify_btn.setEnabled(True)
                    self.redraw_btn.setEnabled(True)
                    # 清空中间列图像
                    if hasattr(self, "middle_plots"):
                        for plot in self.middle_plots:
                            plot.clear()
                        # 重置标题
                        self.middle_title.setText("CF/PW维度聚类 第0类")

                    # 清空表格数据
                    if hasattr(self, "table"):
                        for row in range(self.table.rowCount()):
                            item = QTableWidgetItem(" ")
                            item.setTextAlignment(Qt.AlignCenter)
                            self.table.setItem(row, 1, item)

                    # 更新导航按钮状态
                    has_next_slice, _ = self.data_controller.check_next_available()
                    self.next_slice_btn.setEnabled(has_next_slice)

                    # 禁用下一类按钮，因为当前切片还未识别
                    self.next_cluster_btn.setEnabled(False)
                    self.reset_slice_btn.setEnabled(False)

                    # 更新保存按钮状态
                    self._reset_save_button()

                    self._on_process_finished()
            else:
                self.logger.warning("没有更多切片数据")
                QMessageBox.warning(self, "警告", "没有更多切片数据")
                # 如果没有更多切片，禁用下一片按钮
                self.next_slice_btn.setEnabled(False)
                self._on_process_finished()

        except Exception as e:
            self.logger.error(f"处理下一片按钮点击时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"显示下一片失败: {str(e)}")
            self._on_process_finished()

    def _on_next_cluster(self):
        """处理下一类按钮点击"""
        if self.data_controller.show_next_cluster():
            # 更新按钮状态
            self._update_navigation_buttons()
        else:
            # 当前切片的最后一个类别
            self.next_cluster_btn.setEnabled(False)

    def _update_navigation_buttons(self):
        """更新导航按钮状态"""
        # 检查是否有下一片/下一类
        has_next_slice, has_next_cluster = self.data_controller.check_next_available()

        # 更新按钮状态
        self.next_slice_btn.setEnabled(has_next_slice)
        self.next_cluster_btn.setEnabled(has_next_cluster)

    def resizeEvent(self, event):
        """窗口大小改变时重新定位加载动画"""
        super().resizeEvent(event)
        if hasattr(self, "loading_spinner"):
            # 不管是否可见都更新大小，确保下次显示时位置正确
            self.loading_spinner.resize(self.size())
            self.loading_spinner.move(0, 0)

        # 同时更新矩形动画的位置
        if (
            hasattr(self, "rectangle_animation")
            and self.rectangle_animation is not None
            and hasattr(self, "progress_bar")
        ):
            progress_bar_rect = self.progress_bar.geometry()
            self.rectangle_animation.setGeometry(
                progress_bar_rect.left(),
                progress_bar_rect.bottom() + 20,
                progress_bar_rect.width(),
                40,
            )

    def _update_buttons_state(self, enable: bool = True):
        """更新按钮状态

        Args:
            enable: 是否启用按钮
        """
        try:
            # 更新基本按钮状态
            # self.browse_import_btn.setEnabled(enable)
            # self.import_btn.setEnabled(enable)
            self.start_slice_btn.setEnabled(enable)
            self.identify_btn.setEnabled(enable)
            self.next_cluster_btn.setEnabled(enable)
            self.next_slice_btn.setEnabled(enable)
            self.reset_slice_btn.setEnabled(enable)
            self.redraw_btn.setEnabled(enable)
            self.merge_menu_btn.setEnabled(enable)
            self.start_process_btn.setEnabled(enable)
            self.save_btn.setEnabled(enable)

        except Exception as e:
            self.logger.error(f"更新按钮状态时出错: {str(e)}")

    def update_table_data(self, params: dict):
        """更新表格数据"""
        try:
            # # 参数映射表
            # param_mapping = {
            #     0: ('cf', '载频/MHz'),
            #     1: ('pw', '脉宽/us'),
            #     2: ('pri', 'PRI/us'),
            #     3: ('doa', 'DOA/°'),
            #     4: ('pa_label', 'PA预测分类'),
            #     5: ('pa_conf', 'PA预测概率'),
            #     6: ('dtoa_label', 'DTOA预测分类'),
            #     7: ('dtoa_conf', 'DTOA预测概率'),
            #     8: ('joint_prob', '联合预测概率')
            # }
            param_mapping = {
                0: ("cf", "载频/MHz"),
                1: ("pw", "脉宽/us"),
                2: ("pri", "PRI/us"),
                3: ("doa", "DOA/°"),
                4: ("pa_dict", "PA预测结果"),
                5: ("pa_label", "PA预测分类"),
                6: ("dtoa_dict", "DTOA预测结果"),
                7: ("dtoa_label", "DTOA预测分类"),
                8: ("joint_prob", "联合预测概率"),
            }

            # 更新表格第二列的数据
            for row, (key, _) in param_mapping.items():
                value = params.get(key)
                if value is not None:
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, 1, item)
                else:
                    # 如果参数值不存在，显示占位符
                    item = QTableWidgetItem(" ")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, 1, item)

        except Exception as e:
            self.logger.error(f"更新表格数据出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")

    def cleanup_images(self, close_window: bool = False):
        """清理所有生成的图像文件和临时文件"""
        try:
            # 清理 results/figures 目录
            if self.figures_results_dir.exists():
                self.logger.info("正在清理results/figures目录...")
                shutil.rmtree(self.figures_results_dir)
                self.logger.info("results/figures目录清理完成")

            # 清理 temp 目录
            if self.temp_dir.exists():
                self.logger.info("正在清理temp目录...")
                shutil.rmtree(self.temp_dir)
                self.logger.info("temp目录清理完成")

            if not close_window:
                # 重新创建目录
                self.figures_results_dir.mkdir(exist_ok=True)
                self.temp_dir.mkdir(exist_ok=True)
                self.logger.info("已重新创建必要目录")

        except PermissionError as e:
            self.logger.error(f"清理文件时权限错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"清理文件时出错: {str(e)}")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            self.logger.info("关闭主窗口")

            # 保存文件列表
            self._save_import_files()

            # 保存最后使用的文件路径
            self.data_controller.save_settings()

            # 清理资源
            if self.data_controller:
                self.data_controller.cleanup()

            # 清理图像
            self.cleanup_images(close_window=True)

            # 释放所有资源
            QApplication.processEvents()

        except Exception as e:
            self.logger.error(f"关闭窗口时出错: {str(e)}")

        # 接受关闭事件
        event.accept()

    def _on_data_import_completed(self, success: bool):
        """数据导入完成的回调"""
        if success:
            # 导入成功，只启用开始切片按钮
            self.start_slice_btn.setEnabled(True)
            self.identify_btn.setEnabled(False)
            self.next_slice_btn.setEnabled(False)
            self.next_cluster_btn.setEnabled(False)
            self.reset_slice_btn.setEnabled(False)  # 确保重置按钮也被禁用
            self.logger.debug("数据导入完成，已更新按钮状态")
        else:
            # 导入失败，禁用所有按钮
            self._update_buttons_state(False)
            self.logger.debug("数据导入失败，已禁用所有按钮")

    def on_identify_finished(self, success: bool, cluster_count: int, can_merge: bool):
        """识别完成回调

        Args:
            success (bool): 识别是否成功
            cluster_count (int): 有效类别数量
            can_merge (bool): 是否存在可合并的聚类
        """
        try:
            self.logger.debug("识别完成")

            # 根据识别结果更新按钮状态
            self.next_slice_btn.setEnabled(True)
            self.reset_slice_btn.setEnabled(True)
            self.redraw_btn.setEnabled(True)

            # 滚动容器回到初始状态并禁用滚动
            if hasattr(self, "scroll_container") and self.scroll_container:
                # 禁用滚动功能（会自动回到初始位置）
                self.scroll_layout_manager._on_reset_merge()
                self.logger.info("已重置合并界面状态")

            # 滚动容器回到初始状态并禁用滚动
            if hasattr(self, "scroll_container") and self.scroll_container:
                # 禁用滚动功能（会自动回到初始位置）
                self.scroll_container.enable_scroll(False)
                self.logger.info("滚动容器已回到初始状态并禁用滚动")

            if success:
                # 只有当有效类别数量大于1时才启用下一类按钮
                self.next_cluster_btn.setEnabled(cluster_count > 1)
                if cluster_count <= 1:
                    self.logger.debug("仅有一个有效类别，禁用下一类按钮")

                # 根据can_merge参数启用或禁用合并菜单按钮
                self.merge_menu_btn.setEnabled(can_merge)
                if can_merge:
                    self.logger.debug("存在可合并聚类，启用合并菜单按钮")
                else:
                    self.logger.debug("不存在可合并聚类，禁用合并菜单按钮")

                # 重置保存按钮状态
                self._reset_save_button()

                # 添加自动保存功能
                if hasattr(self, "auto_save") and self.auto_save:
                    self.logger.info("自动保存已启用，正在保存结果...")
                    self.save_results()

            else:
                self.logger.debug("识别失败，仅启用下一片按钮")
                self.next_cluster_btn.setEnabled(False)
                self.merge_menu_btn.setEnabled(False)  # 识别失败时禁用合并菜单按钮
                self.save_btn.setEnabled(False)
                self.save_btn.setText("保存")
                # 清空中间列图像
                if hasattr(self, "middle_plots"):
                    for plot in self.middle_plots:
                        plot.clear()
                    # 重置标题
                    self.middle_title.setText("CF/PW维度聚类 第0类")
                # 清空表格数据
                if hasattr(self, "table"):
                    for row in range(self.table.rowCount()):
                        item = QTableWidgetItem(" ")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(row, 1, item)

                QMessageBox.warning(self, "警告", "识别处理未能找到有效结果")

        except Exception as e:
            self.logger.error(f"处理完成回调出错: {str(e)}")

    def _on_reset_slice(self):
        """重置当前切片的处理结果"""
        try:
            # 检查当前会话中的设置
            if self.auto_reset is not None:
                if self.auto_reset:
                    self._do_reset_slice()
                return

            # 创建自定义消息框
            msg_box = QMessageBox(
                QMessageBox.Question,
                "确认重置",
                "确定要重置当前切片的所有处理结果吗？\n这将清除当前切片的识别结果。",
            )

            # 添加是/否按钮
            yes_button = QPushButton("是")
            no_button = QPushButton("否")
            msg_box.addButton(yes_button, QMessageBox.YesRole)
            msg_box.addButton(no_button, QMessageBox.NoRole)
            msg_box.setDefaultButton(yes_button)

            # 添加复选框
            checkbox = QCheckBox("保持此选项并不再询问")
            msg_box.setCheckBox(checkbox)

            # 显示对话框
            reply = msg_box.exec_()

            # 保存用户选择
            if checkbox.isChecked():
                self.auto_reset = reply == 0  # 0 表示点击了"是"

            # 如果用户点击了"是"，执行重置操作
            if reply == 0:
                self._do_reset_slice()

        except Exception as e:
            self.logger.error(f"重置切片时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"重置切片失败: {str(e)}")

    def _do_reset_slice(self):
        """执行重置切片操作"""
        try:
            # 显示加载动画
            self._on_process_started()

            # 调用数据控制器的重置方法
            if self.data_controller.reset_current_slice():
                # 清空中间列图像
                if hasattr(self, "middle_plots"):
                    for plot in self.middle_plots:
                        plot.clear()
                    # 重置标题
                    self.middle_title.setText("CF/PW维度聚类 第0类")

                # 清空表格数据
                if hasattr(self, "table"):
                    for row in range(self.table.rowCount()):
                        item = QTableWidgetItem(" ")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(row, 1, item)

                # 滚动容器回到初始状态并禁用滚动
                if hasattr(self, "scroll_container") and self.scroll_container:
                    # 禁用滚动功能（会自动回到初始位置）
                    self.scroll_container.enable_scroll(False)
                    self.logger.info("滚动容器已回到初始状态并禁用滚动")

                # 更新按钮状态
                self.identify_btn.setEnabled(True)
                self.next_cluster_btn.setEnabled(False)
                self.reset_slice_btn.setEnabled(False)
                self.next_slice_btn.setEnabled(True)
                self.save_btn.setEnabled(False)  # 禁用保存按钮
                self.merge_menu_btn.setEnabled(False)  # 禁用合并菜单按钮
                # 检查当前切片是否已保存
                already_saved = (
                    hasattr(self, "data_controller")
                    and hasattr(self.data_controller, "is_current_slice_saved")
                    and self.data_controller.is_current_slice_saved()
                )

                if already_saved:
                    # 如果已保存，禁用按钮并显示"已保存"
                    self.save_btn.setText("已保存")
                else:
                    self.save_btn.setText("保存")  # 重置保存按钮文本

                self.logger.info("当前切片已重置")
            else:
                QMessageBox.warning(self, "警告", "重置切片失败")

        except Exception as e:
            self.logger.error(f"执行重置切片操作时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"重置切片失败: {str(e)}")
        finally:
            self._on_process_finished()

    def _on_slice_finished(self, success: bool):
        """切片完成的回调"""
        try:
            if success:
                # 切片成功，启用识别按钮和下一片按钮
                self.identify_btn.setEnabled(True)
                self.next_slice_btn.setEnabled(True)
                self.redraw_btn.setEnabled(True)
                self.reset_slice_btn.setEnabled(False)
                self.next_cluster_btn.setEnabled(False)
                self.start_slice_btn.setEnabled(False)
                self.logger.debug("切片完成，已更新按钮状态")
            else:
                # 切片失败，禁用相关按钮
                self.identify_btn.setEnabled(False)
                self.next_slice_btn.setEnabled(False)
                self.redraw_btn.setEnabled(False)
                self.next_cluster_btn.setEnabled(False)
                self.reset_slice_btn.setEnabled(False)
                self.logger.debug("切片失败，已禁用相关按钮")
                QMessageBox.warning(self, "警告", "切片处理未能找到有效结果")
        except Exception as e:
            self.logger.error(f"切片完成回调出错: {str(e)}")

    def _on_redraw(self) -> None:
        """重绘按钮点击事件

        Args:
            None

        Returns:
            None: 无返回值

        Raises:
            Exception: 重绘操作失败时抛出异常
        """
        try:
            # 获取用户输入的切片编号
            slice_num = self.additional_input.text().strip()
            if not slice_num.isdigit():
                QMessageBox.warning(self, "警告", "请输入有效的切片编号")
                return
            elif int(slice_num) < 1 or int(slice_num) > len(
                self.data_controller.sliced_data
            ):
                QMessageBox.warning(self, "警告", "切片编号超出范围")
                return

            # 检查是否需要保存当前切片
            if self.save_btn.isEnabled():
                # 创建自定义消息框
                msg_box = QMessageBox(
                    QMessageBox.Question,
                    "提示",
                    "当前切片的识别结果尚未保存，是否仍要重绘？",
                )

                # 添加按钮
                yes_button = QPushButton("直接重绘")
                cancel_button = QPushButton("取消")
                save_button = QPushButton("保存再重绘")

                msg_box.addButton(yes_button, QMessageBox.ActionRole)
                msg_box.addButton(cancel_button, QMessageBox.NoRole)
                msg_box.addButton(save_button, QMessageBox.YesRole)

                # 显示对话框
                reply = msg_box.exec_()

                # 根据用户选择执行操作
                if reply == 1:  # 取消
                    return
                elif reply == 2:  # 保存再继续
                    # 保存当前切片，然后继续切换
                    success, message = self.data_controller.save_results(
                        self.save_dir, only_valid=True
                    )
                    if not success:
                        QMessageBox.warning(self, "警告", f"保存失败: {message}")
                        return

            # 显示加载动画
            self.loading_spinner.start()

            # 更新参数指纹
            self.data_controller.update_param_fingerprint()

            # 调用数据控制器的重绘方法
            success = self.data_controller.redraw_current_slice(int(slice_num))

            if success:
                self.next_cluster_btn.setEnabled(True)
                self.next_slice_btn.setEnabled(True)
                self.reset_slice_btn.setEnabled(True)

                # 重置保存按钮状态
                # self._reset_save_button()  # 不需要重复重置状态，在识别完成后回调函数内已经重置了

                # 若识别按钮未禁用，则将其禁用，避免重复识别
                if self.identify_btn.isEnabled():
                    self.identify_btn.setEnabled(False)
            else:
                QMessageBox.warning(self, "警告", "重绘切片失败")
                self.loading_spinner.stop()
        except Exception as e:
            self.logger.error(f"重绘切片出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"重绘切片失败: {str(e)}")
            self.loading_spinner.stop()

    def _on_process_started_fs(self):
        """全速处理开始时的UI更新"""
        self.logger.info("全速处理UI开始更新")

        # 禁用菜单中的保存、导入和模型导入
        self.import_action.setEnabled(False)
        self.save_action.setEnabled(False)
        self.load_model_action.setEnabled(False)

        # 重置进度条
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")

        # 显示矩形动画
        if self.rectangle_animation is None:
            # 如果动画组件还没有创建，创建它
            # 确保能获取到进度条组件的父容器
            if hasattr(self, "progress_bar") and self.progress_bar is not None:
                parent_widget = self.progress_bar.parent()
                self.rectangle_animation = RectangleAnimation(parent_widget)
                # 设置位置在进度条下方
                progress_bar_rect = self.progress_bar.geometry()
                self.rectangle_animation.setGeometry(
                    progress_bar_rect.left(),
                    progress_bar_rect.bottom() + 20,  # 距离进度条下方20像素
                    progress_bar_rect.width(),
                    40,  # 固定高度
                )

        # 更新处理详情标签
        if (
            hasattr(self, "process_detail_label")
            and self.process_detail_label is not None
        ):
            self.process_detail_label.setText("正在切片...")

        # 显示并启动矩形动画
        if self.rectangle_animation is not None:
            self.rectangle_animation.start()

    def _update_progress_fs(self, value):
        """更新全速处理进度条

        Args:
            value (int): 进度值（0-100）
        """
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(value)
            self.progress_label.setText(f"{value}%")

    def _on_start_save_fs(self):
        """更新保存数据界面提醒"""
        # 更新保存数据界面提醒
        if (
            hasattr(self, "process_detail_label")
            and self.process_detail_label is not None
        ):
            self.process_detail_label.setText("正在保存数据...")

    def _on_slice_finished_fs(self, success, slice_count):
        """全速处理切片完成时的UI更新

        Args:
            success (bool): 切片是否成功
            slice_count (int): 切片数量
        """
        if success:
            self.logger.info(f"全速处理获取了{slice_count}个切片")
            # 更新处理详情标签
            if (
                hasattr(self, "process_detail_label")
                and self.process_detail_label is not None
            ):
                self.process_detail_label.setText("正在聚类并识别...")

        else:
            self.logger.error("全速处理切片失败")
            QMessageBox.warning(self, "警告", "全速处理切片失败")

            # 停止矩形动画
            if (
                hasattr(self, "rectangle_animation")
                and self.rectangle_animation is not None
            ):
                self.rectangle_animation.stop()

    def _on_process_finished_fs(self, success):
        """全速处理完成时的UI更新

        Args:
            success (bool): 处理是否成功
        """
        # 停止矩形动画
        if (
            hasattr(self, "rectangle_animation")
            and self.rectangle_animation is not None
        ):
            self.rectangle_animation.stop()
            # 还原按钮状态
            self.set_buttons_state(self.buttons_state)
            # 启用菜单中的保存、导入和模型导入
            self.import_action.setEnabled(True)
            self.save_action.setEnabled(True)
            self.load_model_action.setEnabled(True)

        if success:
            # 更新进度条到100%
            self.progress_bar.setValue(100)
            self.progress_label.setText("100%")
            # 更新处理详情标签
            if (
                hasattr(self, "process_detail_label")
                and self.process_detail_label is not None
            ):
                # 处理详情标签
                self.process_detail_label.setText("已完成！")

            # 使用标准消息框
            msg_box = QMessageBox(
                QMessageBox.Information,
                "处理完成",
                "全速处理已完成，结果已保存到指定目录",
            )

            # 添加打开文件夹按钮
            open_folder_btn = msg_box.addButton(
                "打开文件保存路径", QMessageBox.ActionRole
            )
            # 添加确定按钮
            ok_btn = msg_box.addButton(QMessageBox.Ok)
            msg_box.setDefaultButton(ok_btn)

            # 设置全速处理状态为已处理
            self.full_speed_processed = True
            # 保存当前处理的文件和保存路径
            self.last_processed_file = self.import_path.text()
            self.last_processed_save_dir = self.save_dir

            # 禁用开始处理按钮，避免重复处理
            self.start_process_btn.setEnabled(False)

            self.logger.info(
                f"全速处理完成，已禁用开始处理按钮，记录处理文件: {self.last_processed_file}"
            )

            # 显示对话框
            msg_box.exec_()

            # 检查用户点击的按钮
            if msg_box.clickedButton() == open_folder_btn:
                self._open_save_folder(self.save_dir)
        else:
            # 显示错误提示
            QMessageBox.warning(self, "处理异常", "全速处理过程中发生错误")

    def _open_save_folder(self, folder_path):
        """打开保存文件夹

        Args:
            folder_path (str): 文件夹路径
        """
        try:
            if folder_path and os.path.exists(folder_path):
                self.logger.info(f"打开文件夹: {folder_path}")
                folder_path = os.path.normpath(folder_path)  # 规范化路径
                # 打开文件夹
                os.startfile(folder_path)
            else:
                self.logger.warning(f"文件夹路径无效: {folder_path}")
                QMessageBox.warning(self, "警告", "保存目录不存在或无效")
        except Exception as e:
            self.logger.error(f"打开保存文件夹时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开文件夹: {str(e)}")

    def get_buttons_state(self):
        """获取当前所有按钮的状态

        Returns:
            dict: 包含所有按钮状态的字典，键为按钮名称，值为启用状态(True/False)
        """
        try:
            buttons_state = {
                # "browse_import_btn": self.browse_import_btn.isEnabled(),
                # "import_btn": self.import_btn.isEnabled(),
                "start_slice_btn": self.start_slice_btn.isEnabled(),
                "identify_btn": self.identify_btn.isEnabled(),
                "next_slice_btn": self.next_slice_btn.isEnabled(),
                "next_cluster_btn": self.next_cluster_btn.isEnabled(),
                "reset_slice_btn": self.reset_slice_btn.isEnabled(),
                "redraw_btn": self.redraw_btn.isEnabled(),
                "merge_menu_btn": self.merge_menu_btn.isEnabled(),
                "start_process_btn": self.start_process_btn.isEnabled(),
                "browse_save_btn1": self.browse_save_btn1.isEnabled(),
                "browse_save_btn2": self.browse_save_btn2.isEnabled(),
                "save_btn": self.save_btn.isEnabled(),
            }
            return buttons_state
        except Exception as e:
            self.logger.error(f"获取按钮状态时出错: {str(e)}")
            return {}

    def set_buttons_state(self, buttons_state):
        """根据状态字典设置所有按钮的状态

        Args:
            buttons_state (dict): 包含按钮状态的字典，键为按钮名称，值为启用状态(True/False)

        Returns:
            bool: 设置是否成功
        """
        try:
            # 按钮名称与实际按钮对象的映射
            buttons_map = {
                # "browse_import_btn": self.browse_import_btn,
                # "import_btn": self.import_btn,
                "start_slice_btn": self.start_slice_btn,
                "identify_btn": self.identify_btn,
                "next_slice_btn": self.next_slice_btn,
                "next_cluster_btn": self.next_cluster_btn,
                "reset_slice_btn": self.reset_slice_btn,
                "redraw_btn": self.redraw_btn,
                "merge_menu_btn": self.merge_menu_btn,
                "start_process_btn": self.start_process_btn,
                "browse_save_btn1": self.browse_save_btn1,
                "browse_save_btn2": self.browse_save_btn2,
                "save_btn": self.save_btn,
            }

            # 根据状态字典设置按钮状态
            for btn_name, state in buttons_state.items():
                if btn_name in buttons_map:
                    buttons_map[btn_name].setEnabled(state)

            return True
        except Exception as e:
            self.logger.error(f"设置按钮状态时出错: {str(e)}")
            return False

    def _show_about_dialog(self):
        """显示关于对话框"""
        from PyQt5.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QHBoxLayout,
        )
        from PyQt5.QtGui import QFont
        from PyQt5.QtCore import Qt

        # 创建对话框
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("关于")
        about_dialog.setMinimumWidth(400)
        about_dialog.setStyleSheet(self.styles["dialog"])

        # 创建布局
        layout = QVBoxLayout(about_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 添加标题
        title_label = QLabel("雷达信号多维参数联合智能分选")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)

        # 添加版本信息
        version_label = QLabel("版本: 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)

        # 添加版权信息
        copyright_label = QLabel("© 2024 雷达识别系统开发团队。保留所有权利。")
        copyright_label.setAlignment(Qt.AlignCenter)

        # 添加说明
        description_label = QLabel(
            "本系统用于雷达信号的多维参数联合智能分选，实现信号聚类和识别功能。可处理多种雷达信号类型，并提供可视化分析结果。"
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignCenter)

        # 创建确定按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(about_dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()

        # 添加所有部件到布局
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addSpacing(10)
        layout.addWidget(description_label)
        layout.addSpacing(10)
        layout.addWidget(copyright_label)
        layout.addSpacing(10)
        layout.addLayout(button_layout)

        # 显示对话框
        about_dialog.exec_()

    def _load_model(self):
        """显示导入模型对话框

        使用ModelImportDialog类创建导入模型对话框
        """
        from ui.model_import_dialog import ModelImportDialog

        # 创建模型导入对话框
        dialog = ModelImportDialog(
            parent=self, data_controller=self.data_controller, styles=self.styles
        )

        # 显示对话框
        dialog.exec_()
        # 刷新模型列表
        self.data_controller.emit_models_changed()

    def _show_model_manager(self):
        """显示管理模型对话框"""
        from ui.model_manager_dialog import ModelManagerDialog

        dialog = ModelManagerDialog(
            parent=self, data_controller=self.data_controller, styles=self.styles
        )
        dialog.exec_()
        # 刷新模型列表
        self.data_controller.emit_models_changed()

    def _set_image_stretch_mode(self, mode_name):
        """设置图像拉伸显示模式

        Args:
            mode_name (str): 模式名称，可选值：'STRETCH', 'STRETCH_BILINEAR', 'STRETCH_NEAREST_PRESERVE'
        """
        try:
            from ui.plot_widget import ScaleMode

            # 根据模式名称获取对应的枚举值
            mode_mapping = {
                "STRETCH": ScaleMode.STRETCH,
                "STRETCH_BILINEAR": ScaleMode.STRETCH_BILINEAR,
                "STRETCH_NEAREST_PRESERVE": ScaleMode.STRETCH_NEAREST_PRESERVE,
            }

            if mode_name not in mode_mapping:
                self.logger.error(f"未知的图像显示模式: {mode_name}")
                return

            scale_mode = mode_mapping[mode_name]

            # 设置所有左侧图像显示控件的模式
            if hasattr(self, "left_plots"):
                for plot in self.left_plots:
                    if hasattr(plot, "set_scale_mode"):
                        plot.set_scale_mode(scale_mode)

            # 设置所有中间图像显示控件的模式
            if hasattr(self, "middle_plots"):
                for plot in self.middle_plots:
                    if hasattr(plot, "set_scale_mode"):
                        plot.set_scale_mode(scale_mode)

            # 设置所有合并界面图像显示控件的模式
            if hasattr(self, "merge_plots"):
                for plot in self.merge_plots:
                    if hasattr(plot, "set_scale_mode"):
                        plot.set_scale_mode(scale_mode)

            self.logger.info(f"已切换图像显示模式为: {mode_name}")

        except Exception as e:
            self.logger.error(f"设置图像显示模式时出错: {str(e)}")
            QMessageBox.warning(self, "警告", f"设置图像显示模式失败: {str(e)}")

    def _show_config_dialog(self):
        """显示默认参数配置对话框

        使用ConfigWindow类创建默认参数配置对话框
        """
        try:
            from ui.config_window import ConfigWindow

            # 创建配置窗口
            config_window = ConfigWindow(parent=self)

            # 连接配置保存信号到参数刷新方法
            config_window.config_saved.connect(
                self.data_controller.refresh_config_params
            )
            # 连接配置保存信号到UI参数同步方法
            config_window.config_saved.connect(self._sync_ui_params)

            # 显示窗口
            config_window.exec_()

            self.logger.info("打开默认参数配置窗口")

        except Exception as e:
            self.logger.error(f"打开配置窗口失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开配置窗口: {str(e)}")

    def _sync_ui_params(self) -> None:
        """同步UI参数值

        当配置窗口保存参数后，更新主界面中的参数输入框值，
        确保UI显示与配置文件保持一致。
        """
        try:
            from .default_config import get_params

            # 获取最新的配置参数
            params_config = get_params()

            # 检查param_inputs是否存在且有足够的元素
            if not hasattr(self, "param_inputs") or not self.param_inputs:
                self.logger.warning("param_inputs不存在，无法同步UI参数")
                return

            # 根据ui_functions.py中的参数顺序更新输入框
            # 聚类参数 (索引 0-2)
            if len(self.param_inputs) > 0:
                self.param_inputs[0].setText(
                    str(params_config.clustering_params.epsilon_CF)
                )
            if len(self.param_inputs) > 1:
                self.param_inputs[1].setText(
                    str(params_config.clustering_params.epsilon_PW)
                )
            if len(self.param_inputs) > 2:
                self.param_inputs[2].setText(
                    str(params_config.clustering_params.min_pts)
                )

            # 识别参数 (索引 3-7)
            if len(self.param_inputs) > 3:
                self.param_inputs[3].setText(
                    str(params_config.identification_params.pa_threshold)
                )
            if len(self.param_inputs) > 4:
                self.param_inputs[4].setText(
                    str(params_config.identification_params.dtoa_threshold)
                )
            if len(self.param_inputs) > 5:
                self.param_inputs[5].setText(
                    str(params_config.identification_params.pa_weight)
                )
            if len(self.param_inputs) > 6:
                self.param_inputs[6].setText(
                    str(params_config.identification_params.dtoa_weight)
                )
            if len(self.param_inputs) > 7:
                self.param_inputs[7].setText(
                    str(params_config.identification_params.threshold)
                )

            # 同步合并参数
            if hasattr(self, "merge_param_inputs") and self.merge_param_inputs:
                if len(self.merge_param_inputs) > 0:
                    self.merge_param_inputs[0].setText(
                        str(params_config.merge_params.pri_equal.doa_tolerance)
                    )
                if len(self.merge_param_inputs) > 1:
                    self.merge_param_inputs[1].setText(
                        str(params_config.merge_params.pri_different.doa_tolerance)
                    )
                if len(self.merge_param_inputs) > 2:
                    self.merge_param_inputs[2].setText(
                        str(params_config.merge_params.pri_different.cf_tolerance)
                    )
                if len(self.merge_param_inputs) > 3:
                    self.merge_param_inputs[3].setText(
                        str(params_config.merge_params.pri_none.doa_tolerance)
                    )

            self.logger.info("UI参数已同步更新")

        except Exception as e:
            self.logger.error(f"同步UI参数失败: {str(e)}")
            QMessageBox.warning(self, "警告", f"同步UI参数失败: {str(e)}")
