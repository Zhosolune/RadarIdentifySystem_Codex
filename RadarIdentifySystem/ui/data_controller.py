from typing import Tuple, List, Dict, Callable, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QSettings
from cores.data_processor import DataProcessor
from cores.cluster_processor import ClusterProcessor
from pathlib import Path
import os
import json
from cores.model_predictor import ModelPredictor
from cores.log_manager import LogManager
from cores.params_extractor import ParamsExtractor
import numpy as np
import pandas as pd
from cores.ThreadWorker import DataWorker, IdentifyWorker, SliceWorker, FullSpeedWorker
from .default_config import get_default_config, get_params
from common.paths import Paths

# 设置环境变量
# os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
# os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # 设置日志级别


# # 过滤警告信息
# warnings.filterwarnings('ignore', category=UserWarning)
class DataController(QObject):
    """数据控制器

    负责管理雷达信号数据的加载、处理、聚类和识别流程，并与UI层交互。

    """

    # 默认模型文件名
    DEFAULT_PA_MODEL = "03.16_SparseMorphNet_PA-checkpoint-19-f10.98-val_f11.00.onnx"
    DEFAULT_DTOA_MODEL = "02.09_ResNet_CA_Transformer_DTOA-final-73-accuracy1.00-val_accuracy0.99.onnx"

    PA_LABEL_NAMES = {0: "完整包络", 1: "残缺包络", 2: "部分包络", 3: "相扫", 4: "旁瓣", 5: "非雷达信号"}
    DTOA_LABEL_NAMES = {0: "常规", 1: "脉间参差", 2: "脉组参差", 3: "脉间脉组参差", 4: "组变脉间", 5: "非雷达信号"}
    # DTOA_LABEL_NAMES = {
    #     0: "常规_短",
    #     1: "常规_长",
    #     2: "脉间参差",
    #     3: "脉组参差_短",
    #     4: "脉组参差_长",
    #     5: "脉间脉组参差",
    #     6: "非雷达信号"
    # }
    # DTOA_LABEL_NAMES = {
    #     0: "常规",
    #     1: "脉间参差",
    #     2: "脉组参差_短",
    #     3: "脉组参差_长",
    #     4: "脉间脉组参差",
    #     5: "非雷达信号"
    # }

    # 更新切片信息
    slice_info_updated1 = pyqtSignal(str)
    slice_info_updated2 = pyqtSignal(str)
    process_status = pyqtSignal(bool, str)

    process_started = pyqtSignal()  # 新增：处理开始信号
    process_finished = pyqtSignal()  # 新增：处理结束信号

    cluster_result_ready = pyqtSignal(str, str, str, dict)  # 维度名称, 类别序号, 聚类数据字典

    # 添加新的信号
    slice_images_ready = pyqtSignal(dict)  # 发送切片图像路径
    data_ready = pyqtSignal(bool)  # 添加新信号
    identify_ready = pyqtSignal(bool, int, bool)  # 成功状态, 有效类别数量, 是否可合并
    table_data_ready = pyqtSignal(dict)  # 添加新信号用于更新表格数据
    slice_finished = pyqtSignal(bool)  # 切片完成信号

    # 全速处理专用信号
    process_started_fs = pyqtSignal()  # 全速处理开始信号
    process_finished_fs = pyqtSignal(bool)  # 全速处理完成信号
    progress_updated_fs = pyqtSignal(int)  # 全速处理进度更新信号
    start_save_fs = pyqtSignal()  # 全速处理开始保存信号
    slice_finished_fs = pyqtSignal(bool, int)  # 全速处理切片完成信号
    models_changed = pyqtSignal()  # 模型变更信号

    def __init__(self):
        """初始化数据控制器

        - 初始化所有处理器实例（数据、聚类、预测、绘图）
        - 设置必要的目录结构
        - 加载深度学习模型
        - 初始化处理参数和状态变量
        """
        super().__init__()
        self.sliced_data = None
        self.current_slice_idx = 0
        self.logger = LogManager()
        self.settings = QSettings("Company", "App")
        self.last_file_path = None  # 添加属性记录本次会话最后使用的路径
        self.last_save_path = None  # 添加属性记录本次会话最后使用的保存路径

        # 设置必要的目录
        self.results_dir = Path("results/figures")
        self.temp_dir = Path("temp")
        self.save_dir = None
        self._ensure_directories()

        # 初始化处理器和绘图器
        self.processor = DataProcessor()
        self.plotter = self.processor.plotter
        self.predictor = ModelPredictor()
        self.cluster_processor = ClusterProcessor()
        self.logger = LogManager()
        self.params_extractor = ParamsExtractor()
        # 设置绘图器的目录
        self.plotter.set_save_dir(str(self.results_dir))
        self.plotter.set_temp_dir(str(self.temp_dir))

        # 初始化数据相关属性
        self._workers = []
        self.worker = None
        self.identify_worker = None

        # 初始化数据相关属性
        self._workers = []  # 添加列表保持worker引用
        self.sliced_data_count_tmp = 0
        self.sliced_data_count = 0

        # 获取默认配置实例
        self.default_config = get_default_config()

        # 获取配置参数
        params_config = get_params()

        # 聚类参数 - 使用新的配置管理类的嵌套结构
        self.epsilon_CF = params_config.clustering_params.epsilon_CF
        self.epsilon_PW = params_config.clustering_params.epsilon_PW
        self.min_pts = params_config.clustering_params.min_pts

        # 判别参数 - 使用新的配置管理类的嵌套结构
        self.pa_threshold = params_config.identification_params.pa_threshold
        self.dtoa_threshold = params_config.identification_params.dtoa_threshold
        self.pa_weight = params_config.identification_params.pa_weight
        self.dtoa_weight = params_config.identification_params.dtoa_weight
        self.threshold = params_config.identification_params.threshold

        # 合并参数 - 使用新的配置管理类的嵌套结构
        self.pri_equal_doa_tolerance = params_config.merge_params.pri_equal.doa_tolerance
        self.pri_different_doa_tolerance = params_config.merge_params.pri_different.doa_tolerance
        self.pri_different_cf_tolerance = params_config.merge_params.pri_different.cf_tolerance
        self.pri_none_doa_tolerance = params_config.merge_params.pri_none.doa_tolerance

        # 存储当前有效的聚类结果
        self.valid_clusters = []  # 存储通过判别的聚类结果
        # 初始化通过判别的聚类结果与相关信息
        self.final_cluster_results = {"slice_idx": 0, "clusters": None, "cf_dim_count": 0, "pw_dim_count": 0, "total_cluster_count": 0}
        self.current_cluster_idx = -1  # 当前显示的类别索引
        # self.only_show_identify_result = False  # 默认显示所有聚类结果
        self.only_show_identify_result = True  # 默认仅显示识别结果

        # 合并后数据结构
        self.merged_clusters = []  # 存储合并后的聚类数据

        # 添加保存状态跟踪
        self.saved_states = {}  # 保存状态哈希映射
        self.current_param_fingerprint = self._generate_param_fingerprint()  # 当前参数指纹
        # 保存全速处理时的切片总数量，用来计算进度
        self.total_slice_count_fs = 0

        # 使用Path处理路径，确保跨平台兼容性
        try:
            # 模型目录路径
            model_dir = Paths.get_model_dir()

            # 确保模型目录存在
            if not model_dir.exists():
                raise FileNotFoundError(f"模型目录不存在: {model_dir}")

            # 构建模型文件路径
            dtoa_model = str(model_dir / self.DEFAULT_DTOA_MODEL)
            pa_model = str(model_dir / self.DEFAULT_PA_MODEL)
            
            # 检查模型文件是否存在
            if not Path(dtoa_model).exists():
                raise FileNotFoundError(f"DTOA模型文件不存在: {dtoa_model}")
            if not Path(pa_model).exists():
                raise FileNotFoundError(f"PA模型文件不存在: {pa_model}")

            # 创建预测器并加载模型
            self.predictor = ModelPredictor()
            self.predictor.load_models(dtoa_model, pa_model)

        except Exception as e:
            self.logger.error(f"模型加载失败: {str(e)}")

        # 设置临时目录
        temp_dir = Paths.get_user_data_dir() / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.predictor.set_temp_dir(str(temp_dir))

        self.current_slice_images = {}  # 存储当前切片的图像路径
        self.slice_worker = None

    def get_model_list(self) -> List[str]:
        """获取可用模型列表 (废弃，建议使用 get_pa_model_list 和 get_dtoa_model_list)"""
        # 为了兼容性保留，返回所有模型名称去重
        pa_models = set(self.get_pa_model_list())
        dtoa_models = set(self.get_dtoa_model_list())
        return sorted(list(pa_models | dtoa_models))

    def _load_model_registry(self) -> Dict[str, Dict[str, str]]:
        """加载模型注册表
        
        Returns:
            Dict: 模型注册表 {"PA": {显示名: 文件名}, "DTOA": {显示名: 文件名}}
        """
        registry_path = Paths.get_model_registry_path()
        try:
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {"PA": {}, "DTOA": {}}
        except Exception as e:
            self.logger.error(f"加载模型注册表失败: {str(e)}")
            return {"PA": {}, "DTOA": {}}

    def _save_model_registry(self, registry: Dict[str, Dict[str, str]]) -> bool:
        """保存模型注册表
        
        Args:
            registry: 模型注册表字典
            
        Returns:
            bool: 是否保存成功
        """
        registry_path = Paths.get_model_registry_path()
        try:
            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存模型注册表失败: {str(e)}")
            return False

    def _ensure_registry_sync(self, model_type: str) -> Dict[str, str]:
        """确保注册表与文件系统同步
        
        扫描模型目录，自动添加未注册的模型文件到注册表。
        
        Args:
            model_type: 模型类型 ("PA" 或 "DTOA")
            
        Returns:
            Dict: 该类型的模型映射 {显示名: 文件名}
        """
        registry = self._load_model_registry()
        model_dir = Paths.get_model_dir()
        suffix = "_PA.onnx" if model_type == "PA" else "_DTOA.onnx"
        
        # 确保类型键存在
        if model_type not in registry:
            registry[model_type] = {}
        
        type_registry = registry[model_type]
        
        # 获取所有已注册的文件名
        registered_files = set(type_registry.values())
        
        # 扫描目录中的模型文件
        if model_dir.exists():
            for file in model_dir.glob(f"*{suffix}"):
                filename = file.name
                # 如果文件未注册，自动添加
                if filename not in registered_files:
                    # 使用文件名（去除后缀）作为显示名
                    display_name = file.stem[:-len("_PA") if model_type == "PA" else -len("_DTOA")]
                    # 确保显示名称唯一
                    base_name = display_name
                    counter = 1
                    while display_name in type_registry:
                        display_name = f"{base_name}_{counter}"
                        counter += 1
                    type_registry[display_name] = filename
                    self.logger.info(f"自动注册模型: {display_name} -> {filename}")
        
        # 清理已不存在的文件
        files_to_remove = []
        for display_name, filename in type_registry.items():
            file_path = model_dir / filename
            if not file_path.exists():
                files_to_remove.append(display_name)
                self.logger.warning(f"模型文件不存在，从注册表移除: {display_name} -> {filename}")
        
        for name in files_to_remove:
            del type_registry[name]
        
        # 保存更新后的注册表
        self._save_model_registry(registry)
        
        return type_registry

    def register_model(self, display_name: str, filename: str, model_type: str) -> bool:
        """注册新模型到映射表
        
        Args:
            display_name: 显示名称
            filename: 实际文件名
            model_type: 模型类型 ("PA" 或 "DTOA")
            
        Returns:
            bool: 是否注册成功
        """
        try:
            registry = self._load_model_registry()
            
            if model_type not in registry:
                registry[model_type] = {}
            
            # 检查显示名称是否已存在
            if display_name in registry[model_type]:
                self.logger.warning(f"显示名称已存在: {display_name}")
                return False
            
            registry[model_type][display_name] = filename
            return self._save_model_registry(registry)
            
        except Exception as e:
            self.logger.error(f"注册模型失败: {str(e)}")
            return False

    def unregister_model(self, display_name: str, model_type: str) -> str:
        """从映射表中注销模型
        
        Args:
            display_name: 显示名称
            model_type: 模型类型 ("PA" 或 "DTOA")
            
        Returns:
            str: 被删除的文件名，如果失败返回空字符串
        """
        try:
            registry = self._load_model_registry()
            
            if model_type not in registry:
                return ""
            
            if display_name not in registry[model_type]:
                return ""
            
            filename = registry[model_type].pop(display_name)
            self._save_model_registry(registry)
            return filename
            
        except Exception as e:
            self.logger.error(f"注销模型失败: {str(e)}")
            return ""

    def get_pa_model_list(self) -> List[str]:
        """获取可用PA模型列表（返回显示名称）"""
        try:
            type_registry = self._ensure_registry_sync("PA")
            models = ["系统默认"] + sorted(type_registry.keys())
            return models
        except Exception as e:
            self.logger.error(f"获取PA模型列表出错: {str(e)}")
            return ["系统默认"]

    def get_dtoa_model_list(self) -> List[str]:
        """获取可用DTOA模型列表（返回显示名称）"""
        try:
            type_registry = self._ensure_registry_sync("DTOA")
            models = ["系统默认"] + sorted(type_registry.keys())
            return models
        except Exception as e:
            self.logger.error(f"获取DTOA模型列表出错: {str(e)}")
            return ["系统默认"]

    def _get_model_filename(self, display_name: str, model_type: str) -> str:
        """通过显示名称获取实际文件名
        
        Args:
            display_name: 显示名称
            model_type: 模型类型 ("PA" 或 "DTOA")
            
        Returns:
            str: 实际文件名，如果不存在返回空字符串
        """
        registry = self._load_model_registry()
        if model_type in registry and display_name in registry[model_type]:
            return registry[model_type][display_name]
        return ""

    def switch_model(self, model_name: str) -> bool:
        """切换模型 (同时切换两者，废弃)"""
        return self.switch_pa_model(model_name) and self.switch_dtoa_model(model_name)

    def switch_pa_model(self, model_name: str) -> bool:
        """切换PA模型"""
        try:
            model_dir = Paths.get_model_dir()
            if model_name == "系统默认":
                pa_model = str(model_dir / self.DEFAULT_PA_MODEL)
            else:
                # 通过注册表查找实际文件名
                filename = self._get_model_filename(model_name, "PA")
                if not filename:
                    self.logger.error(f"PA模型未注册: {model_name}")
                    return False
                pa_model = str(model_dir / filename)
            
            if not os.path.exists(pa_model):
                self.logger.error(f"PA模型文件缺失: {pa_model}")
                return False
                
            return self.predictor.load_pa_model(pa_model)
        except Exception as e:
            self.logger.error(f"切换PA模型失败: {str(e)}")
            return False

    def switch_dtoa_model(self, model_name: str) -> bool:
        """切换DTOA模型"""
        try:
            model_dir = Paths.get_model_dir()
            if model_name == "系统默认":
                dtoa_model = str(model_dir / self.DEFAULT_DTOA_MODEL)
            else:
                # 通过注册表查找实际文件名
                filename = self._get_model_filename(model_name, "DTOA")
                if not filename:
                    self.logger.error(f"DTOA模型未注册: {model_name}")
                    return False
                dtoa_model = str(model_dir / filename)
            
            if not os.path.exists(dtoa_model):
                self.logger.error(f"DTOA模型文件缺失: {dtoa_model}")
                return False
                
            return self.predictor.load_dtoa_model(dtoa_model)
        except Exception as e:
            self.logger.error(f"切换DTOA模型失败: {str(e)}")
            return False

    def rename_model(self, old_name: str, new_name: str, model_type: str) -> Tuple[bool, str]:
        """重命名模型（仅修改注册表，不操作物理文件）

        Args:
            old_name: 原显示名称
            new_name: 新显示名称
            model_type: 模型类型 ("PA" or "DTOA")

        Returns:
            tuple: (是否重命名成功, 消息)
        """
        try:
            registry = self._load_model_registry()
            
            if model_type not in registry:
                msg = f"模型类型不存在: {model_type}"
                self.logger.error(msg)
                return False, msg
            
            if old_name not in registry[model_type]:
                msg = f"原显示名称不存在: {old_name}"
                self.logger.error(msg)
                return False, msg
                
            if new_name in registry[model_type]:
                msg = f"新显示名称已被使用: {new_name}"
                self.logger.error(msg)
                return False, msg
            
            # 获取原文件名并更新映射
            filename = registry[model_type].pop(old_name)
            registry[model_type][new_name] = filename
            
            if self._save_model_registry(registry):
                msg = f"模型重命名成功: {old_name} -> {new_name}"
                self.logger.info(msg)
                self.emit_models_changed()
                return True, msg
            else:
                # 回滚
                registry[model_type][old_name] = filename
                del registry[model_type][new_name]
                msg = "保存注册表失败"
                return False, msg
            
        except Exception as e:
            msg = f"重命名模型失败: {str(e)}"
            self.logger.error(msg)
            return False, msg

    def delete_model(self, display_name: str, model_type: str) -> bool:
        """删除模型（注销并删除物理文件）
        
        Args:
            display_name: 显示名称
            model_type: 模型类型 ("PA" 或 "DTOA")
            
        Returns:
            bool: 是否删除成功
        """
        # 1. 注销
        filename = self.unregister_model(display_name, model_type)
        if not filename:
            return False
            
        # 2. 删除物理文件
        try:
            model_dir = Paths.get_model_dir()
            file_path = model_dir / filename
            if file_path.exists():
                os.remove(file_path)
                self.logger.info(f"已删除模型文件: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"删除模型文件失败: {str(e)}")
            # 即使文件删除失败，注册表已注销，也算部分成功
            return True

    def emit_models_changed(self):
        """发送模型变更信号"""
        self.models_changed.emit()

    def update_params_from_inputs(self, user_inputs: dict = None) -> None:
        """从用户输入更新参数

        根据用户输入更新所有参数，如果用户输入为空或无效，则使用配置文件中的默认值。

        Args:
            user_inputs (dict, optional): 用户输入的参数字典，键为参数名，值为用户输入值
        """
        try:
            # 如果没有提供用户输入，使用空字典
            if user_inputs is None:
                user_inputs = {}

            # 更新聚类参数
            self.epsilon_CF = self.default_config.get_param(user_inputs.get("epsilon_CF"), "clustering_params.epsilon_CF")
            self.epsilon_PW = self.default_config.get_param(user_inputs.get("epsilon_PW"), "clustering_params.epsilon_PW")
            self.min_pts = self.default_config.get_param(user_inputs.get("min_pts"), "clustering_params.min_pts")

            # 更新识别参数
            self.pa_threshold = self.default_config.get_param(user_inputs.get("pa_threshold"), "identification_params.pa_threshold")
            self.dtoa_threshold = self.default_config.get_param(user_inputs.get("dtoa_threshold"), "identification_params.dtoa_threshold")
            self.pa_weight = self.default_config.get_param(user_inputs.get("pa_weight"), "identification_params.pa_weight")
            self.dtoa_weight = self.default_config.get_param(user_inputs.get("dtoa_weight"), "identification_params.dtoa_weight")
            self.threshold = self.default_config.get_param(user_inputs.get("threshold"), "identification_params.threshold")

            # 更新合并参数
            self.pri_equal_doa_tolerance = self.default_config.get_param(user_inputs.get("pri_equal_doa_tolerance"), "merge_params.pri_equal.doa_tolerance")
            self.pri_different_doa_tolerance = self.default_config.get_param(
                user_inputs.get("pri_different_doa_tolerance"), "merge_params.pri_different.doa_tolerance"
            )
            self.pri_different_cf_tolerance = self.default_config.get_param(
                user_inputs.get("pri_different_cf_tolerance"), "merge_params.pri_different.cf_tolerance"
            )
            self.pri_none_doa_tolerance = self.default_config.get_param(user_inputs.get("pri_none_doa_tolerance"), "merge_params.pri_none.doa_tolerance")

            # 更新参数指纹
            self.current_param_fingerprint = self._generate_param_fingerprint()

            self.logger.info("参数已更新")

        except Exception as e:
            self.logger.error(f"更新参数失败: {str(e)}")
            raise

    def refresh_config_params(self) -> None:
        """刷新配置参数

        当配置文件更新后，重新从配置文件加载所有参数。
        这个方法应该在配置窗口保存参数后被调用。
        """
        try:
            # 重新加载配置实例
            from .default_config import reload_config

            reload_config()

            # 重新获取配置实例
            self.default_config = get_default_config()

            # 重新获取配置参数
            params_config = get_params()

            # 更新所有缓存的参数
            self.epsilon_CF = params_config.clustering_params.epsilon_CF
            self.epsilon_PW = params_config.clustering_params.epsilon_PW
            self.min_pts = params_config.clustering_params.min_pts

            # 更新识别参数
            self.pa_threshold = params_config.identification_params.pa_threshold
            self.dtoa_threshold = params_config.identification_params.dtoa_threshold
            self.pa_weight = params_config.identification_params.pa_weight
            self.dtoa_weight = params_config.identification_params.dtoa_weight
            self.threshold = params_config.identification_params.threshold

            self.pri_equal_doa_tolerance = params_config.merge_params.pri_equal.doa_tolerance
            self.pri_different_doa_tolerance = params_config.merge_params.pri_different.doa_tolerance
            self.pri_different_cf_tolerance = params_config.merge_params.pri_different.cf_tolerance
            self.pri_none_doa_tolerance = params_config.merge_params.pri_none.doa_tolerance

            # 更新参数指纹
            self.current_param_fingerprint = self._generate_param_fingerprint()

            self.logger.info("配置参数已刷新")

        except Exception as e:
            self.logger.error(f"刷新配置参数失败: {str(e)}")
            raise

    def _ensure_directories(self):
        """确保必要的目录存在

        创建并确保以下目录存在：
        - results: 结果保存目录
        - temp: 临时文件目录
        """
        try:
            # 创建结果目录
            self.results_dir.mkdir(exist_ok=True)
            # 创建临时目录
            self.temp_dir.mkdir(exist_ok=True)
            self.logger.debug("已确保必要目录存在")
        except Exception as e:
            self.logger.error(f"创建目录时出错: {str(e)}")

    def import_data(self, file_path: str) -> Tuple[bool, str]:
        """导入并处理雷达信号数据文件。

        在独立线程中异步加载和处理Excel格式的雷达信号数据文件。

        Args:
            file_path (str): Excel文件路径

        Returns:
            tuple: 包含两个元素：
                - bool: 是否成功启动导入处理
                - str: 状态消息或错误描述

        Raises:
            Exception: 创建工作线程失败时抛出

        """
        try:
            self.logger.info("开始导入数据...")
            self.process_started.emit()

            # 创建工作线程
            self.worker = DataWorker(file_path)
            self._workers.append(self.worker)  # 保持引用

            # 连接信号
            self.worker.finished.connect(self._on_import_finished)
            self.worker.start()

            return True, "正在导入数据..."

        except Exception as e:
            self.logger.error(f"创建工作线程失败: {str(e)}")
            return False, f"导入失败: {str(e)}"

    def _on_import_finished(self, success: bool, message: str, result: dict, data: object) -> None:
        """处理数据导入完成的回调。

        处理DataWorker导入数据完成后的结果，更新数据状态并发送相关信号。

        Args:
            success (bool): 数据导入是否成功
            message (str): 处理结果消息
            result (dict): 处理结果信息（包含total_pulses, time_range, filtered_pulses, band, slice_count）
            data (object): 导入的雷达信号数据

        Raises:
            Exception: 处理回调过程中出错
        """
        try:
            if success and data is not None:
                self.data = data
                # 更新processor的数据
                self.processor.data = data

                # 同步plotter配置
                if hasattr(self.processor, "plotter"):
                    self.plotter = self.processor.plotter
                    # 重新更新配置以确保同步
                    self.plotter.update_configs(data)

                self.data_ready.emit(True)
                # 更新切片信息（从result字典获取）
                band = result.get("band", "未知")
                slice_count = result.get("slice_count", 0)
                self.slice_info_updated1.emit(f"数据包位于{band}，")
                self.slice_info_updated2.emit(f"预计将获得{slice_count}个250ms切片")
                self.sliced_data_count_tmp = slice_count
            else:
                self.logger.error(f"数据导入失败: {message}")
                self.data_ready.emit(False)
        except Exception as e:
            self.logger.error(f"导入完成处理出错: {str(e)}")
            self.data_ready.emit(False)
        finally:
            # 发送完成信号
            self.process_finished.emit()
            # 清理工作线程
            if self.worker in self._workers:
                self._workers.remove(self.worker)
            self.worker = None

    def start_slicing(self):
        """启动数据切片处理线程。

        重置处理状态并在独立线程中执行数据切片操作。

        Args:
            None

        Returns:
            bool: 切片处理启动是否成功

        Raises:
            Exception: 创建或启动切片线程失败时抛出
        """
        try:
            # 重置所有相关状态
            self.current_slice_idx = -1
            self.valid_clusters = []
            self.final_cluster_results = {"slice_idx": 0, "clusters": None, "cf_dim_count": 0, "pw_dim_count": 0, "total_cluster_count": 0}

            # 确保聚类处理器状态重置
            self.cluster_processor = ClusterProcessor()

            # 创建并启动切片线程
            self.slice_worker = SliceWorker(self)
            self.slice_worker.slice_finished.connect(self._on_slice_finished)
            self.slice_worker.start()

            return True

        except Exception as e:
            self.logger.error(f"切片处理出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False

    def _on_slice_finished(self, success: bool) -> None:
        """处理切片完成的回调。

        处理切片操作完成后的结果，发送相关状态信号。

        Args:
            success (bool): 切片处理是否成功

        Returns:
            None
        """
        self.process_finished.emit()  # 发送处理完成信号
        if success:
            self.data_ready.emit(True)  # 通知UI数据已准备就绪
            self.slice_finished.emit(True)  # 发送切片完成信号
        else:
            self.slice_finished.emit(False)

    def process_first_slice(self) -> bool:
        """处理第一个数据切片。

        对第一个数据切片进行处理，包括数据检查、状态重置、图像生成等操作。

        Args:
            None

        Returns:
            bool: 切片处理是否成功

        Raises:
            Exception: 处理切片数据时出错
        """
        try:
            # 1. 数据有效性检查
            if self.sliced_data is None:
                self.logger.error("切片数据为空")
                return False

            # 2. 重置状态
            self.valid_clusters = []
            self.current_cluster_idx = -1

            # 3. 确保聚类处理器状态正确
            if not hasattr(self, "cluster_processor") or self.cluster_processor is None:
                self.logger.debug("重新初始化聚类处理器")
                self.cluster_processor = ClusterProcessor()

            # 4. 安全获取下一片数据
            if self.current_slice_idx < len(self.sliced_data) - 1:
                self.current_slice_idx += 1
                try:
                    current_slice = self.sliced_data[self.current_slice_idx]

                    # 5. 数据完整性检查
                    if current_slice is None or len(current_slice) == 0:
                        self.logger.error(f"切片 {self.current_slice_idx + 1} 数据无效")
                        return False

                    # 6. 设置数据到聚类处理器
                    self.cluster_processor.set_data(current_slice, self.current_slice_idx)

                    # 在绘制图像之前确保目录设置正确
                    if not hasattr(self.plotter, "save_dir") or self.plotter.save_dir is None:
                        self.logger.debug("重新设置绘图保存目录")
                        self.plotter.set_save_dir(str(self.results_dir))

                    if not hasattr(self.plotter, "temp_dir") or self.plotter.temp_dir is None:
                        self.logger.debug("重新设置绘图临时目录")
                        self.plotter.set_temp_dir(str(self.temp_dir))

                    # 确保plotter拥有时间范围信息
                    if hasattr(self.processor, "time_ranges") and self.processor.time_ranges:
                        self.plotter.set_slice_time_ranges(self.processor.time_ranges)

                    # 生成基础文件名
                    base_name = f"slice_{self.current_slice_idx + 1}"

                    # 7. 绘制切片图像，传递切片索引以确保时间范围一致性
                    image_paths = self.plotter.plot_slice(current_slice, base_name, self.current_slice_idx)
                    if image_paths:
                        # 发送处理开始信号
                        # self.process_started.emit()
                        # 发送图像路径，这会触发UI更新
                        self.slice_images_ready.emit(image_paths)
                        # 发送处理完成信号
                        # self.process_finished.emit()
                    else:
                        self.logger.warning("未能生成切片图像")

                    # 8. 重置识别相关状态
                    self.final_cluster_results = {
                        "slice_idx": self.current_slice_idx,
                        "clusters": None,
                        "cf_dim_count": 0,
                        "pw_dim_count": 0,
                        "total_cluster_count": 0,
                    }

                    return True

                except Exception as e:
                    self.logger.error(f"处理切片数据时出错: {str(e)}")
                    return False
            else:
                self.logger.info("已经是最后一片数据")
                return False

        except Exception as e:
            self.logger.error(f"处理下一片数据出错: {str(e)}")
            return False

    def set_save_dir(self, save_dir: str):
        """设置保存目录

        Args:
            save_dir (str): 保存目录路径
        """
        self.save_dir = save_dir

    def get_save_dir(self) -> str:
        """获取保存目录

        Returns:
            str: 保存目录路径
        """
        return self.save_dir

    def get_last_directory(self) -> str:
        """获取上次使用的目录路径

        Returns:
            str: 上次使用的目录路径，如果不存在则返回空字符串
        """
        # 从设置中读取上次保存的路径
        last_path = self.settings.value("last_file_path", "")
        if last_path and os.path.exists(os.path.dirname(last_path)):
            return os.path.dirname(last_path)
        return ""

    def update_last_file_path(self, file_path: str):
        """更新最后使用的文件路径

        Args:
            file_path (str): 新的文件路径
        """
        self.last_file_path = file_path

    def save_settings(self):
        """保存应用程序设置

        将最后使用的文件路径保存到QSettings中
        """
        if self.last_file_path:
            self.settings.setValue("last_file_path", self.last_file_path)

    def save_directory(self, file_path: str):
        """保存当前访问的目录

        Args:
            file_path (str): 当前文件路径
        """
        directory = str(Path(file_path).parent)
        self.settings.setValue("last_directory", directory)

    def validate_file(self, file_path: str) -> bool:
        """验证文件有效性

        Args:
            file_path (str): 待验证的文件路径

        Returns:
            bool: 文件是否有效
        """
        if not file_path:
            self.process_status.emit(False, "未选择文件")
            return False

        path = Path(file_path)
        if not path.exists():
            self.process_status.emit(False, "文件不存在")
            return False

        if path.suffix.lower() not in [".xlsx", ".xls"]:
            self.process_status.emit(False, "请选择Excel文件")
            return False

        # self.current_file_path = str(path)
        # 保存当前目录
        self.save_directory(file_path)
        return True

    def set_cluster_params(self, epsilon_CF: float, epsilon_PW: float, min_pts: int) -> None:
        """设置聚类参数。

        更新聚类算法的参数设置，并同步更新聚类处理器的参数。

        Args:
            epsilon_CF (float): CF维度的邻域半径
            epsilon_PW (float): PW维度的邻域半径
            min_pts (int): 最小点数

        Returns:
            None
        """
        self.epsilon_CF = epsilon_CF
        self.epsilon_PW = epsilon_PW
        self.min_pts = min_pts
        # 更新聚类处理器的参数
        self.cluster_processor.set_cluster_params(epsilon_CF, epsilon_PW, min_pts)
        # 更新参数指纹
        self.update_param_fingerprint()

    def set_identify_params(self, pa_threshold: float, dtoa_threshold: float, pa_weight: float, dtoa_weight: float, threshold: float) -> None:
        """设置识别参数

        Args:
            pa_threshold (float): PA判别门限
            dtoa_threshold (float): DTOA判别门限
            pa_weight (float): PA判别权重
            dtoa_weight (float): DTOA判别权重
            threshold (float): 联合判别门限
        """
        # 更新识别参数
        self.pa_threshold = pa_threshold
        self.dtoa_threshold = dtoa_threshold
        self.pa_weight = pa_weight
        self.dtoa_weight = dtoa_weight
        self.threshold = threshold
        # 更新聚类处理器的参数
        self.cluster_processor.set_identify_params(pa_threshold, dtoa_threshold, pa_weight, dtoa_weight, threshold)
        # 更新参数指纹
        self.update_param_fingerprint()

    def process_slice_images(self, slice_data: object) -> None:
        """处理切片数据并生成图像。

        根据输入的切片数据生成5维图像，并发送图像路径信号。

        Args:
            slice_data (object): 待处理的切片数据

        Returns:
            None

        Raises:
            Exception: 处理切片图像过程中出错
        """
        try:
            # 确保plotter已设置保存目录
            if not self.plotter.save_dir:
                self.plotter.set_save_dir("results")

            # 确保plotter拥有时间范围信息
            if hasattr(self.processor, "time_ranges") and self.processor.time_ranges:
                self.plotter.set_slice_time_ranges(self.processor.time_ranges)

            # 生成切片的5维图像，传递切片索引
            image_paths = self.plotter.plot_slice(slice_data, f"slice_{self.current_slice_idx + 1}", self.current_slice_idx)

            self.current_slice_images = image_paths
            self.slice_images_ready.emit(image_paths)

        except Exception as e:
            self.logger.error(f"处理切片图像出错: {str(e)}")  # 添加日志

    def show_next_slice(self) -> bool:
        """切换并显示下一个切片数据。

        切换到下一个切片，更新切片索引并处理新切片的图像数据。

        Args:
            None

        Returns:
            bool: 切片切换是否成功

        Raises:
            Exception: 切换切片过程中出错
        """
        try:
            self.logger.info(f"当前为切片{self.current_slice_idx + 1}, 总切片数: {len(self.sliced_data)}")
            if self.current_slice_idx < len(self.sliced_data) - 1:
                self.current_slice_idx += 1
                self.logger.info(f"切换到切片 {self.current_slice_idx + 1}")
                self.process_slice_images(self.sliced_data[self.current_slice_idx])
                return True
            return False
        except Exception as e:
            self.logger.error(f"切换切片出错: {str(e)}")
            return False

    def show_next_cluster(self) -> bool:
        """切换并显示下一个聚类结果。

        切换到下一个有效的聚类结果，更新聚类索引并发送相关信号。

        Args:
            None

        Returns:
            bool: 聚类结果切换是否成功

        Raises:
            Exception: 切换聚类结果过程中出错
        """
        try:
            if self.valid_clusters and self.current_cluster_idx < len(self.valid_clusters) - 1:
                self.current_cluster_idx += 1
                cluster_info = self.valid_clusters[self.current_cluster_idx]

                self.cluster_result_ready.emit(
                    cluster_info["dim_name"], str(cluster_info["cluster_dim_idx"]), str(cluster_info["total_cluster_count"]), cluster_info
                )

                # 同步参数到表格
                self.sync_params_to_table(cluster_info)
                return True
            return False

        except Exception as e:
            self.logger.error(f"显示下一类出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False

    def check_next_available(self) -> tuple[bool, bool]:
        """检查是否存在下一个切片和聚类结果。

        检查当前数据中是否还有未处理的切片和聚类结果。

        Args:
            None

        Returns:
            tuple[bool, bool]: 包含两个布尔值的元组
                - 第一个值表示是否有下一个切片
                - 第二个值表示是否有下一个聚类结果
        """
        has_next_slice = self.current_slice_idx < len(self.sliced_data) - 1
        has_next_cluster = self.valid_clusters and self.current_cluster_idx < len(self.valid_clusters) - 1
        return has_next_slice, has_next_cluster

    def _extract_cluster_parameters(self, cluster_info: dict) -> None:
        """提取聚类参数并发送更新信号。

        从聚类信息中提取各项参数，包括标签、置信度和信号特征参数，并发送表格更新信号。

        Args:
            cluster_info (dict): 包含预测结果和聚类数据的信息字典

        Returns:
            None

        Raises:
            KeyError: 访问字典中不存在的键时抛出
        """

        dtoa = np.diff(cluster_info["cluster_data"]["points"][:, 4]) * 1000  # 转换为us
        dtoa = np.append(dtoa, 0)  # 补齐长度
        # 调试用
        # if self.current_slice_idx == 4 and cluster_info['cluster_idx'] == 3:
        #     print(f"DTOA: {dtoa}")

        params = get_params()
        # 获取分组值
        cf_grouped_values = self.params_extractor.extract_grouped_values(
            cluster_info["cluster_data"]["points"][:, 0],
            eps=params.extraction_params.cf_extraction.eps,
            min_samples=params.extraction_params.cf_extraction.min_samples,
            threshold_ratio=params.extraction_params.cf_extraction.threshold_ratio,
        )
        pw_grouped_values = self.params_extractor.extract_grouped_values(
            cluster_info["cluster_data"]["points"][:, 1],
            eps=params.extraction_params.pw_extraction.eps,
            min_samples=params.extraction_params.pw_extraction.min_samples,
            threshold_ratio=params.extraction_params.pw_extraction.threshold_ratio,
        )
        pri_grouped_values = self.params_extractor.extract_grouped_values(
            dtoa,
            eps=params.extraction_params.pri_extraction.eps,
            min_samples=params.extraction_params.pri_extraction.min_samples,
            threshold_ratio=params.extraction_params.pri_extraction.threshold_ratio,
        )
        doa_grouped_values = sorted(cluster_info["cluster_data"]["points"][:, 2])
        doa_grouped_values = [np.mean(doa_grouped_values[1:-1])]
        # PRI后处理
        if pri_grouped_values:
            # 抑制谐波
            if len(pri_grouped_values) > 1:
                pri_grouped_values = self.params_extractor.filter_related_numbers(
                    pri_grouped_values, params.extraction_params.pri_extraction.harmonic_tolerance
                )
            # 单值过滤
            if len(pri_grouped_values) == 1:
                if pri_grouped_values[0] < params.extraction_params.pri_extraction.filter_threshold:
                    pri_grouped_values = []

        cluster_info["CF"] = cf_grouped_values
        cluster_info["PW"] = pw_grouped_values
        cluster_info["PRI"] = pri_grouped_values
        cluster_info["DOA"] = doa_grouped_values

    def sync_params_to_table(self, cluster_info: dict) -> None:
        """同步参数到表格

        Args:
            cluster_info (dict): 聚类信息字典
        """
        # 提取已有的参数
        params = {
            "pa_label": self.PA_LABEL_NAMES[cluster_info["prediction"]["pa_label"]],
            "pa_conf": f"{cluster_info['prediction']['pa_conf']:.4f}",
            "dtoa_label": self.DTOA_LABEL_NAMES[cluster_info["prediction"]["dtoa_label"]],
            "dtoa_conf": f"{cluster_info['prediction']['dtoa_conf']:.4f}",
            "joint_prob": f"{cluster_info['prediction']['joint_prob']:.4f}",
            "pa_dict": "\n".join([f"{self.PA_LABEL_NAMES[label]}: {conf:.4f}" for label, conf in cluster_info["prediction"]["pa_dict"].items()]),
            "dtoa_dict": "\n".join([f"{self.DTOA_LABEL_NAMES[label]}: {conf:.4f}" for label, conf in cluster_info["prediction"]["dtoa_dict"].items()]),
            "cf": ", ".join([f"{v:.0f}" for v in cluster_info["CF"]]),  # 载频，多值用逗号分隔
            "pw": f"{', '.join([f'{v:.1f}' for v in cluster_info['PW']])}",  # 脉宽，多值用逗号分隔
            "pri": f"{', '.join([f'{v:.1f}' for v in cluster_info['PRI']])}",  # PRI，多值用逗号分隔
            "doa": f"{np.mean(cluster_info['DOA']):.1f}",  # DOA取均值
        }

        # 发送表格更新信号
        self.table_data_ready.emit(params)

    def get_current_cluster(self) -> dict | None:
        """获取当前聚类数据。

        返回当前选中的聚类数据，如果没有有效的聚类数据则返回None。

        Args:
            None

        Returns:
            dict | None: 当前聚类数据字典，无有效数据时返回None
        """
        if self.valid_clusters and 0 <= self.current_cluster_idx < len(self.valid_clusters):
            return self.valid_clusters[self.current_cluster_idx]
        return None

    def start_identification(self) -> None:
        """启动信号识别处理线程。

        创建并启动识别工作线程，连接相关信号处理函数。

        Args:
            None

        Returns:
            None

        Raises:
            Exception: 创建或启动识别线程失败时抛出
        """
        try:
            # 创建并启动识别工作线程
            self.identify_worker = IdentifyWorker(self)

            # 连接信号
            self.identify_worker.identify_started.connect(self.process_started.emit)
            self.identify_worker.identify_finished.connect(
                lambda success, cluster_count, can_merge: self.identify_ready.emit(success, cluster_count, can_merge)
            )

            # 启动线程
            self.identify_worker.start()

        except Exception as e:
            self.logger.error(f"启动识别处理出错: {str(e)}")
            self.process_finished.emit()

    def _on_identification_finished(self, success: bool, can_merge: bool = False) -> None:
        """处理识别完成的回调。

        发送识别完成相关信号并清理工作线程。

        Args:
            success (bool): 识别过程是否成功
            can_merge (bool): 是否存在可合并的聚类

        Returns:
            None

        Raises:
            Exception: 处理回调过程中出错
        """
        try:
            # 发送识别完成信号
            self.identify_ready.emit(success, len(self.valid_clusters), can_merge)
            # 发送处理完成信号
            self.process_finished.emit()

            # 清理工作线程
            if self.identify_worker:
                self.identify_worker.deleteLater()
                self.identify_worker = None

        except Exception as e:
            self.logger.error(f"处理识别完成回调时出错: {str(e)}")

    def _process_identify_current_slice(self) -> bool:
        """识别当前切片的聚类结果

        对当前切片数据进行两阶段聚类和识别处理。处理顺序根据波段类型决定：
        - X波段：先PW后CF
        - 其他波段：先CF后PW

        Returns:
            bool: 识别处理是否成功

        Raises:
            Exception: 识别处理过程中出错
        """
        try:
            # 获取当前切片数据
            current_slice = self.sliced_data[self.current_slice_idx]

            # 确保配置同步
            # self.plotter.update_configs(current_slice)

            # 检测波段类型
            band_type = self.cluster_processor.detect_band(current_slice)

            # 确定处理顺序
            # dimensions = ["PW", "CF"] if band_type == "X波段" else ["CF", "PW"]
            dimensions = ["CF", "PW"] if band_type == "X波段" else ["CF", "PW"]

            # 重置处理状态
            self.valid_clusters = []
            self.current_cluster_idx = -1

            # 设置当前切片数据和时间范围
            self.cluster_processor.set_data([current_slice], self.current_slice_idx)
            self.cluster_processor.set_slice_time_ranges(self.processor.time_ranges)

            # 初始化处理数据
            current_data = current_slice
            recycled_data = []
            dim_idx = {"CF": 0, "PW": 0}
            cluster_count = 0

            # 按顺序处理每个维度
            for dimension in dimensions:
                success, cluster_result = self.cluster_processor.process_dimension(dimension, current_data)

                if success and cluster_result:
                    # 处理聚类结果
                    for cluster in cluster_result["clusters"]:
                        # 确保cluster包含必要的字段
                        cluster_data = {
                            "points": cluster["points"],
                            "time_ranges": self.cluster_processor.time_ranges,
                            "slice_idx": self.current_slice_idx,
                            "dim_name": dimension,
                            "cluster_idx": cluster_count + 1,
                        }

                        # 预测
                        success, pa_conf, dtoa_conf, pa_label, dtoa_label, pa_conf_dict, dtoa_conf_dict = self.predictor.predict(
                            cluster_data, self.pa_threshold, self.dtoa_threshold
                        )

                        if success:
                            # 提取有效雷达标签对应概率
                            pa_conf_tmp = pa_conf if pa_label != 5 else 0.0
                            dtoa_conf_tmp = dtoa_conf if dtoa_label != 5 else 0.0

                            # 计算联合概率
                            joint_prob = (pa_conf_tmp * self.pa_weight + dtoa_conf_tmp * self.dtoa_weight) / (self.pa_weight + self.dtoa_weight)

                            # 判断是否为有效雷达信号（贪婪策略）
                            is_valid = pa_label != 5 or dtoa_label != 5

                            # 雷达有效时，对于脉间参差类别的特殊判别
                            # if is_valid and dtoa_label == 1:
                            #     # 计算dtoa的集中度
                            #     dtoa = np.diff(cluster['points'][:, 4]) * 1000  # 转换为us

                            #     # 计算统计指标
                            #     dtoa_median = np.median(dtoa)
                            #     dtoa_min = np.min(dtoa)
                            #     dtoa_max = np.max(dtoa)

                            #     # 判断条件：
                            #     # 1. 数据范围不能超过1000us
                            #     # 2. 大部分数据应该在中位数/均值附近
                            #     data_range = dtoa_max - dtoa_min
                            #     is_range_valid = data_range <= 1000  # 范围阈值可调

                            #     # 计算在中位数一定范围内的数据比例
                            #     center_range_ratio = 0.35  # 可调35%
                            #     in_center_count = np.sum(np.abs(dtoa - dtoa_median) <= center_range_ratio * dtoa_median)
                            #     center_ratio = in_center_count / len(dtoa)
                            #     is_centered = center_ratio >= 0.7  # 比例阈值可调

                            #     # 综合判断
                            #     if not (is_range_valid or is_centered):
                            #         is_valid = False

                            # 生成图像
                            image_paths = self.plotter.plot_cluster(cluster, for_predict=False)

                            # 创建聚类信息
                            cluster_info = {
                                "dim_name": dimension,
                                "cluster_dim_idx": dim_idx[dimension] + 1,  # 通过识别的每个维度下的类别索引
                                "cluster_idx": len(self.valid_clusters) + 1,  # 通过识别的聚类索引
                                "total_cluster_count": cluster_count + 1,  # 当前维度聚类结果总数中的索引
                                "cluster_data": cluster,
                                "image_paths": image_paths,
                                "is_valid": is_valid,  # 保存是否为有效雷达信号
                                "prediction": {
                                    "pa_label": pa_label,
                                    "pa_conf": pa_conf,
                                    "dtoa_label": dtoa_label,
                                    "dtoa_conf": dtoa_conf,
                                    "joint_prob": joint_prob,
                                    "pa_dict": pa_conf_dict,
                                    "dtoa_dict": dtoa_conf_dict,
                                },
                            }
                            # 提取并更新参数
                            self._extract_cluster_parameters(cluster_info)

                            cluster_count += 1

                            # 处理无效数据
                            if not is_valid:
                                recycled_data.extend(cluster["points"].tolist())

                            # 保存聚类结果
                            # 在勾选了“展示所有结果”后，会导致没有通过识别的结聚类也被保存，进而影响到合并，使合并的结果包含了未通过识别的聚类，后续需要修改。
                            if not self.only_show_identify_result or is_valid:
                                dim_idx[dimension] += 1
                                self.valid_clusters.append(cluster_info)

                    # 更新待处理数据
                    unprocessed_data = cluster_result.get("unprocessed_points", [])
                    if not isinstance(unprocessed_data, list):
                        unprocessed_data = unprocessed_data.tolist()

                    # 合并回收数据和未聚类数据
                    if recycled_data and unprocessed_data:
                        current_data = np.vstack((recycled_data, unprocessed_data))
                    elif recycled_data:
                        current_data = recycled_data
                    else:
                        current_data = unprocessed_data

            # 更新最终结果
            self.final_cluster_results.update(
                {
                    "slice_idx": self.current_slice_idx + 1,
                    "clusters": self.valid_clusters,
                    "cf_dim_count": sum(1 for c in self.valid_clusters if c["dim_name"] == "CF"),
                    "pw_dim_count": sum(1 for c in self.valid_clusters if c["dim_name"] == "PW"),
                    "total_cluster_count": len(self.valid_clusters),
                }
            )

            # 添加聚类合并逻辑
            can_merge = self._check_can_merge()

            # 显示第一个结果
            if self.valid_clusters:
                self.current_cluster_idx = -1
                self.show_next_cluster()
                return True, can_merge

            return False, False

        except Exception as e:
            self.logger.error(f"识别处理出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False, False

    def cleanup(self) -> None:
        """清理所有资源并重置状态。

        停止所有工作线程，清空数据，重置处理器状态，重新设置目录，并发送清空信号。

        Args:
            None

        Returns:
            None

        Raises:
            Exception: 清理资源过程中出错
        """
        try:
            # 停止所有工作线程
            if hasattr(self, "_workers"):
                for worker in self._workers:
                    if worker and worker.isRunning():
                        worker.quit()
                        worker.wait()

            # 清空存储的数据
            self.sliced_data = None
            self.current_slice_idx = -1
            self.valid_clusters = []
            self.current_cluster_idx = -1
            self.merged_clusters = []  # 清空合并结果
            self.final_cluster_results = {"slice_idx": 0, "clusters": None, "cf_dim_count": 0, "pw_dim_count": 0, "total_cluster_count": 0}

            # 重置处理器状态
            if hasattr(self, "processor"):
                self.processor = DataProcessor()
                self.plotter = self.processor.plotter  # 更新plotter引用
            if hasattr(self, "cluster_processor"):
                self.cluster_processor = ClusterProcessor()

            # 确保目录存在并重新设置绘图器目录
            self._ensure_directories()
            if hasattr(self, "plotter"):
                self.plotter.set_save_dir(str(self.results_dir))
                self.plotter.set_temp_dir(str(self.temp_dir))

            # 发送清空信号
            self.slice_info_updated2.emit("预计将获得 0 个250ms切片")
            self.table_data_ready.emit({})

        except Exception as e:
            self.logger.error(f"清理资源时出错: {str(e)}")

    def reset_current_slice(self):
        """重置当前切片的处理结果"""
        try:
            if self.sliced_data is None or self.current_slice_idx < 0:
                self.logger.warning("没有可重置的切片数据")
                return False

            # 获取当前切片数据
            current_slice = self.sliced_data[self.current_slice_idx]

            # 重置聚类相关状态
            self.valid_clusters = []
            self.current_cluster_idx = -1
            self.merged_clusters = []  # 重置合并结果
            self.final_cluster_results = {"slice_idx": self.current_slice_idx, "clusters": None, "cf_dim_count": 0, "pw_dim_count": 0, "total_cluster_count": 0}

            # 重新初始化聚类处理器
            self.cluster_processor = ClusterProcessor()

            # 确保plotter拥有时间范围信息
            if hasattr(self.processor, "time_ranges") and self.processor.time_ranges:
                self.plotter.set_slice_time_ranges(self.processor.time_ranges)

            # 重新绘制原始切片图像
            base_name = f"slice_{self.current_slice_idx + 1}"
            image_paths = self.plotter.plot_slice(current_slice, base_name, self.current_slice_idx)

            if image_paths:
                # 发送图像更新信号
                self.slice_images_ready.emit(image_paths)
                # 更新切片信息
                # total_slices = len(self.sliced_data)
                # self.slice_info_updated.emit(f"当前切片: {self.current_slice_idx + 1}/{total_slices}")
                self.logger.info(f"切片 {self.current_slice_idx + 1} 已重置")
                return True

            return False

        except Exception as e:
            self.logger.error(f"重置当前切片时出错: {str(e)}")
            return False

    def _check_can_merge(self, merge_params=None):
        """检查是否存在可合并的聚类

        Args:
            merge_params (dict, optional): 合并参数，包含三个规则的参数设置

        Returns:
            bool: 如果存在可合并的聚类返回True，否则返回False
        """
        try:
            if not self.valid_clusters or len(self.valid_clusters) < 2:
                return False

            # 检查任意两个聚类是否可以合并
            for i in range(len(self.valid_clusters)):
                for j in range(i + 1, len(self.valid_clusters)):
                    if self._can_merge_clusters(self.valid_clusters[i], self.valid_clusters[j], merge_params):
                        return True

            return False

        except Exception as e:
            self.logger.error(f"检查聚类合并条件时出错: {str(e)}")
            return False

    def _can_merge_clusters_pri_equal(self, cluster1: Dict, cluster2: Dict, merge_params: Optional[Dict] = None) -> bool:
        """判断两个聚类是否可以基于PRI相同条件合并

        合并条件：PRI可以提取且存在相同值，DOA在指定范围内

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 从配置获取默认参数
            params_config = get_params()

            # 使用传入的参数或默认参数
            if merge_params is None:
                params = {
                    "pri_equal": {"doa_tolerance": params_config.merge_params.pri_equal.doa_tolerance},
                    "pri_different": {"cf_tolerance": params_config.merge_params.pri_different.cf_tolerance},
                }
            else:
                params = merge_params

            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都存在
            if not (pri1 and pri2):
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = params["pri_different"].get("cf_tolerance", params_config.merge_params.pri_different.cf_tolerance)

            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 检查是否有相同的PRI值
            pri_set1 = set(np.round(pri1, 1))  # 保留1位小数进行比较
            pri_set2 = set(np.round(pri2, 1))

            # 规则1: PRI相同且DOA在指定范围内，且时间交叠
            if pri_set1.intersection(pri_set2):
                doa_tolerance = params["pri_equal"].get("doa_tolerance", params_config.merge_params.pri_equal.doa_tolerance)
                if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI相同合并条件时出错: {str(e)}")
            return False

    def _can_merge_clusters_pri_different(self, cluster1: Dict, cluster2: Dict, merge_params: Optional[Dict] = None) -> bool:
        """判断两个聚类是否可以基于PRI不同条件合并

        合并条件：PRI可以提取但不存在相同值，DOA和CF在指定范围内

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 若输入的两个类别的DTOA识别结果都是常规雷达（即类别0），则不合并
            dtoa_label1 = cluster1.get("prediction", {}).get("dtoa_label", -1)
            dtoa_label2 = cluster2.get("prediction", {}).get("dtoa_label", -1)
            if dtoa_label1 == 0 and dtoa_label2 == 0:
                return False

            # 从配置获取默认参数
            params_config = get_params()

            # 使用传入的参数或默认参数
            if merge_params is None:
                params = {
                    "pri_different": {
                        "doa_tolerance": params_config.merge_params.pri_different.doa_tolerance,
                        "cf_tolerance": params_config.merge_params.pri_different.cf_tolerance,
                    }
                }
            else:
                params = merge_params

            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都存在
            if not (pri1 and pri2):
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = params["pri_different"].get("cf_tolerance", params_config.merge_params.pri_different.cf_tolerance)
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 检查是否有相同的PRI值
            pri_set1 = set(np.round(pri1, 1))  # 保留1位小数进行比较
            pri_set2 = set(np.round(pri2, 1))

            # 规则2: PRI不同但DOA和CF在指定范围内，且时间交叠
            if not pri_set1.intersection(pri_set2):
                doa_tolerance = params["pri_different"].get("doa_tolerance", params_config.merge_params.pri_different.doa_tolerance)
                if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI不同合并条件时出错: {str(e)}")
            return False

    def _can_merge_clusters_pri_none(self, cluster1: Dict, cluster2: Dict, merge_params: Optional[Dict] = None) -> bool:
        """判断两个聚类是否可以基于PRI无法提取条件合并

        合并条件：PRI无法提取，DOA在指定范围内，且TOA有相交部分

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 从配置获取默认参数
            params_config = get_params()

            # 使用传入的参数或默认参数
            if merge_params is None:
                params = {
                    "pri_none": {"doa_tolerance": params_config.merge_params.pri_none.doa_tolerance},
                    "pri_different": {"cf_tolerance": params_config.merge_params.pri_different.cf_tolerance},
                }
            else:
                params = merge_params

            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都不存在
            if pri1 or pri2:
                # print(f"pri1:{pri1},pri2:{pri2},pri不是都不存在")
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = params["pri_none"].get("cf_tolerance", params_config.merge_params.pri_different.cf_tolerance)
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 规则3：PRI全都不存在但DOA在指定范围内，且它们的TOA有相交部分
            doa_tolerance = params["pri_none"].get("doa_tolerance", params_config.merge_params.pri_none.doa_tolerance)
            if doa_diff <= doa_tolerance:
                # 检查TOA是否有相交部分
                if self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI无法提取合并条件时出错: {str(e)}")
            return False

    def _merge_valid_clusters(self, merge_params: Optional[Dict] = None) -> None:
        """合并有效聚类结果

        采用分层次合并策略：
        1. 先对所有类别执行合并条件一的判断：PRI可以提取且存在相同值
        2. 然后对剩余类别执行合并条件二的判断：PRI可以提取但不存在相同值
        3. 再对剩余类别执行合并条件三的判断：PRI无法提取

        Args:
            merge_params (dict, optional): 合并参数，包含三个规则的参数设置

        合并依据：
        1. PRI相同且DOA在指定范围内
        2. PRI不同但DOA和CF在指定范围内
        3. PRI不存在但DOA在指定范围内
        """
        try:
            if not self.valid_clusters:
                self.logger.info("没有有效聚类需要合并")
                return

            # 清空之前的合并结果
            self.merged_clusters = []

            # 创建聚类副本用于合并处理
            clusters_to_merge = self.valid_clusters.copy()
            merged_groups = []  # 存储合并组

            # 第一层：PRI相同条件合并
            self.logger.info("开始第一层合并：PRI相同条件")
            clusters_to_merge, level1_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_equal, merge_params)
            merged_groups.extend(level1_groups)

            # 第二层：PRI不同条件合并
            self.logger.info("开始第二层合并：PRI不同条件")
            clusters_to_merge, level2_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_different, merge_params)
            merged_groups.extend(level2_groups)

            # 第三层：PRI无法提取条件合并
            self.logger.info("开始第三层合并：PRI无法提取条件")
            clusters_to_merge, level3_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_none, merge_params)
            merged_groups.extend(level3_groups)

            # 处理合并组，生成合并后数据
            merge_index = 1
            for group in merged_groups:
                if len(group) > 1:  # 只处理需要合并的组
                    merged_data = self._create_merged_cluster(group, merge_index)
                    if merged_data:
                        self.merged_clusters.append(merged_data)
                        merge_index += 1

                        self.logger.info(f"合并了 {len(group)} 个聚类，合并索引: {merge_index - 1}")

            self.logger.info(f"聚类合并完成，共生成 {len(self.merged_clusters)} 个合并结果")

        except Exception as e:
            self.logger.error(f"聚类合并过程中出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")

    def _merge_clusters_by_condition(
        self, clusters_to_merge: List[dict], merge_condition_func: Callable, merge_params: Optional[Dict] = None
    ) -> Tuple[List[dict], List[List[dict]]]:
        """根据指定条件合并聚类

        Args:
            clusters_to_merge (list): 待合并的聚类列表
            merge_condition_func: 合并条件判断函数
            merge_params (dict, optional): 合并参数

        Returns:
            tuple: (剩余未合并的聚类列表, 合并组列表)
        """
        try:
            remaining_clusters = clusters_to_merge.copy()
            merged_groups = []

            # 贪婪合并策略
            while remaining_clusters:
                # 弹出第一个聚类作为种子
                seed_cluster = remaining_clusters.pop(0)
                current_group = [seed_cluster]

                # 贪婪扩展：重复查找可合并的聚类直到没有新的可加入
                found_new = True
                while found_new:
                    found_new = False
                    i = 0

                    # 遍历剩余聚类
                    while i < len(remaining_clusters):
                        candidate_cluster = remaining_clusters[i]

                        # 检查候选聚类是否可以与当前组中的任一聚类合并
                        can_merge_with_group = False
                        for group_cluster in current_group:
                            if merge_condition_func(group_cluster, candidate_cluster, merge_params):
                                can_merge_with_group = True
                                break

                        # 如果可以合并，加入组并从待处理列表中移除
                        if can_merge_with_group:
                            current_group.append(candidate_cluster)
                            remaining_clusters.pop(i)
                            found_new = True  # 标记找到新的可合并聚类
                            # 不增加i，因为列表长度已减少
                            self.logger.info("合并成功。")
                        else:
                            i += 1

                # 将完成的合并组加入结果
                merged_groups.append(current_group)

            # 提取未合并的聚类（长度为1的组）作为下一层的输入
            unmerged_clusters = []
            for group in merged_groups:
                if len(group) == 1:
                    unmerged_clusters.append(group[0])

            return unmerged_clusters, merged_groups

        except Exception as e:
            self.logger.error(f"按条件合并聚类时出错: {str(e)}")
            return clusters_to_merge, []

    def _can_merge_clusters(self, cluster1: Dict, cluster2: Dict, merge_params: Optional[Dict] = None) -> bool:
        """判断两个聚类是否可以合并

        Args:
            cluster1: 第一个聚类
            cluster2: 第二个聚类
            merge_params (dict, optional): 合并参数，包含三个规则的参数设置

        Returns:
            bool: 是否可以合并
        """
        try:
            # 从配置获取默认参数
            params_config = get_params()

            # 使用传入的参数或默认参数
            if merge_params is None:
                # 如果没有传入参数，构造默认参数字典
                params = {
                    "pri_equal": {"doa_tolerance": params_config.merge_params.pri_equal.doa_tolerance},
                    "pri_different": {
                        "doa_tolerance": params_config.merge_params.pri_different.doa_tolerance,
                        "cf_tolerance": params_config.merge_params.pri_different.cf_tolerance,
                    },
                    "pri_none": {"doa_tolerance": params_config.merge_params.pri_none.doa_tolerance},
                }
            else:
                params = merge_params

            # 获取聚类参数（使用正确的字段名）
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = params["pri_different"].get("cf_tolerance", params_config.merge_params.pri_different.cf_tolerance)
            self.logger.info(f"cf_tolerance: {cf_tolerance}")
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break
            if cf_diff:
                if pri1 and pri2:
                    # 检查是否有相同的PRI值
                    pri_set1 = set(np.round(pri1, 1))  # 保留1位小数进行比较
                    pri_set2 = set(np.round(pri2, 1))
                    # 规则1: PRI相同且DOA在指定范围内，且时间交叠
                    if pri_set1.intersection(pri_set2):
                        doa_tolerance = params["pri_equal"].get("doa_tolerance", params_config.merge_params.pri_equal.doa_tolerance)
                        self.logger.info(f"pri_equal.doa_tolerance: {doa_tolerance}")
                        if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                            return True
                    # 规则2: PRI不同但DOA和CF在指定范围内，且时间交叠
                    else:
                        doa_tolerance = params["pri_different"].get("doa_tolerance", params_config.merge_params.pri_different.doa_tolerance)
                        self.logger.info(f"pri_different.doa_tolerance: {doa_tolerance}")
                        if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                            return True
                # 规则3：PRI不全都存在但DOA在指定范围内，且它们的TOA有相交部分
                elif not (pri1 or pri2):
                    # else:
                    doa_tolerance = params["pri_none"].get("doa_tolerance", params_config.merge_params.pri_none.doa_tolerance)
                    self.logger.info(f"pri_none.doa_tolerance: {doa_tolerance}")
                    if doa_diff <= doa_tolerance:
                        # 检查TOA是否有相交部分
                        if self._check_toa_intersection(cluster1, cluster2):
                            return True

            return False

        except Exception as e:
            self.logger.error(f"判断聚类合并条件时出错: {str(e)}")
            return False

    def _check_toa_intersection(self, cluster1: Dict, cluster2: Dict) -> bool:
        """检查两个聚类的TOA时间范围是否有相交部分

        Args:
            cluster1 (dict): 第一个聚类数据
            cluster2 (dict): 第二个聚类数据

        Returns:
            bool: TOA时间范围是否有相交部分
        """
        try:
            # 获取聚类数据中的points数组
            cluster_data1 = cluster1.get("cluster_data", {})
            cluster_data2 = cluster2.get("cluster_data", {})

            points1 = cluster_data1.get("points", np.array([]))
            points2 = cluster_data2.get("points", np.array([]))

            if len(points1) == 0 or len(points2) == 0:
                return False

            # 提取TOA数据（第4列，索引为4）
            toa1 = points1[:, 4]
            toa2 = points2[:, 4]

            # 计算TOA时间范围
            toa1_min, toa1_max = np.min(toa1), np.max(toa1)
            toa2_min, toa2_max = np.min(toa2), np.max(toa2)

            # 检查时间范围是否有相交
            # 两个时间段相交的条件：max(start1, start2) < min(end1, end2)
            intersection_exists = max(toa1_min, toa2_min) < min(toa1_max, toa2_max)

            return intersection_exists

        except Exception as e:
            self.logger.error(f"检查TOA相交时出错: {str(e)}")
            return False

    def _create_merged_cluster(self, cluster_group, merge_index):
        """创建合并后的聚类数据

        Args:
            cluster_group: 要合并的聚类组
            merge_index: 合并索引

        Returns:
            dict: 合并后的数据结构
        """
        try:
            # 合并脉冲数据
            merged_pulse_data = []
            dim_list = []
            dim_idx_list = []

            for cluster in cluster_group:
                # 获取脉冲数据
                cluster_data = cluster.get("cluster_data", {})
                points = cluster_data.get("points", np.array([]))
                dim = cluster.get("dim_name", "unknown")
                dim_cluster_idx = cluster.get("total_cluster_count", "unknown")
                if len(points) > 0:
                    merged_pulse_data.append(points)
                    dim_list.append(dim)
                    dim_idx_list.append(dim_cluster_idx)

            # 提取参数
            self.logger.info(f"形状：{[np.shape(data) for data in merged_pulse_data]}")
            pulse_data = np.vstack([data for data in merged_pulse_data])
            self.logger.info(f"拼接后数据形状：{np.shape(pulse_data)}")
            pulse_data = pulse_data[np.argsort(pulse_data[:, 4])]
            merged_cf, merged_pw, merged_pri, merged_doa = self._extract_parameters_after_merge(pulse_data)

            # 创建合并后数据结构
            merged_data = {
                "cluster_data": merged_pulse_data,  # List[np.array]
                "CF": f"{', '.join([f'{v:.0f}' for v in merged_cf])}",
                "PW": f"{', '.join([f'{v:.1f}' for v in merged_pw])}",
                "DOA": f"{merged_doa:.1f}",  # DOA取均值
                "DTOA": f"{', '.join([f'{v:.1f}' for v in merged_pri])}",
                "index_merge": merge_index,
                "merge_count": len(cluster_group),
                "dim_name": dim_list,
                "dim_cluster_idx": dim_idx_list,
                "time_ranges": self.cluster_processor.time_ranges,
            }

            return merged_data

        except Exception as e:
            self.logger.error(f"创建合并聚类数据时出错: {str(e)}")
            return None

    def get_merged_clusters(self):
        """获取合并后的聚类数据

        Returns:
            list: 合并后的聚类数据列表
        """
        return self.merged_clusters

    def execute_merge_clusters(self, merge_params=None):
        """执行聚类合并操作

        供外部调用的公共方法，用于手动触发聚类合并。

        Args:
            merge_params (dict, optional): 合并参数，包含三个规则的参数设置
                格式: {
                    'pri_equal': {'doa_tolerance': float},
                    'pri_different': {'doa_tolerance': float, 'cf_tolerance': float},
                    'pri_none': {'doa_tolerance': float}
                }

        Returns:
            bool: 合并操作是否成功执行
        """
        try:
            if not self.valid_clusters:
                self.logger.warning("没有有效聚类可以合并")
                return False

            # 执行合并，传递参数
            self._merge_valid_clusters(merge_params)

            self.logger.info(f"聚类合并完成，共生成 {len(self.merged_clusters)} 个合并结果")
            return True

        except Exception as e:
            self.logger.error(f"执行聚类合并时出错: {str(e)}")
            return False

    def _extract_parameters_after_merge(self, pulse_data: list) -> tuple:
        """提取聚类参数并发送更新信号。

        从聚类信息中提取各项参数，包括标签、置信度和信号特征参数，并发送表格更新信号。

        Args:
            pulse_data (list): 原始脉冲数据

        Returns:
            tuple: 包含四个元素的元组
                - cf_grouped_values (list): 合并后的CF参数列表
                - pw_grouped_values (list): 合并后的PW参数列表
                - pri_grouped_values (list): 合并后的PRI参数列表
                - doa_range (float): 合并后的DOA参数范围

        Raises:
            KeyError: 访问字典中不存在的键时抛出
        """
        dtoa = np.diff(pulse_data[:, 4]) * 1000  # 转换为us
        dtoa = np.append(dtoa, 0)  # 补齐长度

        params = get_params()
        # 获取分组值
        cf_grouped_values = self.params_extractor.extract_grouped_values(
            pulse_data[:, 0],
            eps=params.extraction_params.cf_extraction.eps,
            min_samples=params.extraction_params.cf_extraction.min_samples,
            threshold_ratio=params.extraction_params.cf_extraction.threshold_ratio,
        )
        pw_grouped_values = self.params_extractor.extract_grouped_values(
            pulse_data[:, 1],
            eps=params.extraction_params.pw_extraction.eps,
            min_samples=params.extraction_params.pw_extraction.min_samples,
            threshold_ratio=params.extraction_params.pw_extraction.threshold_ratio,
        )
        pri_grouped_values = self.params_extractor.extract_grouped_values(
            dtoa,
            eps=params.extraction_params.pri_extraction.eps,
            min_samples=params.extraction_params.pri_extraction.min_samples,
            threshold_ratio=params.extraction_params.pri_extraction.threshold_ratio,
        )
        # 方位角特殊处理
        doa = sorted(pulse_data[:, 2])
        doa_value = np.mean(doa)
        # PRI后处理
        if pri_grouped_values:
            # 抑制谐波
            if len(pri_grouped_values) > 1:
                pri_grouped_values = self.params_extractor.filter_related_numbers(
                    pri_grouped_values, params.extraction_params.pri_extraction.harmonic_tolerance
                )
            # 单值过滤
            if len(pri_grouped_values) == 1:
                if pri_grouped_values[0] < params.extraction_params.pri_extraction.filter_threshold:
                    pri_grouped_values = []

        return cf_grouped_values, pw_grouped_values, pri_grouped_values, doa_value

    def set_display_mode(self, only_identified: bool):
        """设置显示模式"""
        self.only_show_identify_result = only_identified
        self.logger.info(f"显示模式已设置为: {'仅展示识别后结果' if only_identified else '展示所有结果'}")

    def redraw_current_slice(self, slice_num: int) -> bool:
        """重绘指定编号的切片并启动识别。

        根据给定的切片编号重新绘制切片图像，重置聚类状态，并启动识别处理。

        Args:
            slice_num (int): 目标切片编号（从1开始）

        Returns:
            bool: 重绘操作是否成功
                - True: 重绘成功并启动识别处理
                - False: 切片编号无效或重绘过程出错

        Raises:
            Exception: 重绘切片过程中出错
        """
        try:
            # 检查切片编号有效性
            if not self.sliced_data or slice_num < 1 or slice_num > len(self.sliced_data):
                self.logger.warning(f"无效的切片编号: {slice_num}")
                return False

            # 更新当前切片索引（切片编号从1开始，索引从0开始）
            self.current_slice_idx = slice_num - 1

            # 获取当前切片数据
            current_slice = self.sliced_data[self.current_slice_idx]

            # 确保使用正确的plotter实例
            if hasattr(self, "processor"):
                self.plotter = self.processor.plotter

            # 确保plotter拥有时间范围信息
            if hasattr(self.processor, "time_ranges") and self.processor.time_ranges:
                self.plotter.set_slice_time_ranges(self.processor.time_ranges)

            # 重新绘制原始切片图像
            base_name = f"slice_{slice_num}"
            image_paths = self.plotter.plot_slice(current_slice, base_name, self.current_slice_idx)

            if image_paths:
                # 发送图像更新信号
                self.slice_images_ready.emit(image_paths)

                # 重置聚类相关状态
                self.valid_clusters = []
                self.current_cluster_idx = -1

                # 创建并启动识别工作线程
                self.identify_worker = IdentifyWorker(self)

                # 连接identify_ready信号
                self.identify_worker.identify_started.connect(self.process_started.emit)
                self.identify_worker.identify_finished.connect(
                    lambda success, cluster_count, can_merge: self.identify_ready.emit(success, cluster_count, can_merge)
                )

                self.identify_worker.start()

                return True

            return False

        except Exception as e:
            self.logger.error(f"重绘当前切片时出错: {str(e)}")
            return False

    def _generate_param_fingerprint(self) -> str:
        """生成当前聚类、识别和合并参数的唯一指纹

        将所有参数组合成字符串并计算哈希值，用于唯一标识一组参数设置

        Returns:
            str: 参数指纹哈希值
        """
        import hashlib

        # 组合参数字符串（包含聚类、识别和合并参数）
        param_string = (
            f"CF{self.epsilon_CF}_PW{self.epsilon_PW}_MP{self.min_pts}_"
            f"PATH{self.pa_threshold}_DTOATH{self.dtoa_threshold}_"
            f"PA{self.pa_weight}_DTOA{self.dtoa_weight}_TH{self.threshold}_"
            f"PEDT{self.pri_equal_doa_tolerance}_PDDT{self.pri_different_doa_tolerance}_"
            f"PDCT{self.pri_different_cf_tolerance}_PNDT{self.pri_none_doa_tolerance}"
        )

        # 计算哈希值
        fingerprint = hashlib.md5(param_string.encode()).hexdigest()[:8]  # 取前8位作为简短指纹

        return fingerprint

    def is_current_slice_saved(self) -> bool:
        """检查当前切片是否已保存

        通过比较当前参数指纹与保存状态中的记录判断。

        Returns:
            bool: 当前切片是否已保存
        """
        try:
            # 如果没有切片数据，则返回False
            if not self.sliced_data or self.current_slice_idx >= len(self.sliced_data):
                return False

            # 获取当前切片和参数对应的键
            current_key = f"{self.current_slice_idx}_{self.current_param_fingerprint}"

            # 检查当前切片是否在保存状态中
            return self.saved_states.get(current_key, False)
        except Exception as e:
            self.logger.error(f"检查当前切片保存状态时出错: {str(e)}")
            return False

    def mark_current_slice_saved(self) -> None:
        """将当前切片在当前参数设置下标记为已保存

        更新保存状态哈希映射
        """
        # 生成当前切片和参数的唯一键
        key = f"{self.current_slice_idx}_{self.current_param_fingerprint}"

        # 更新保存状态
        self.saved_states[key] = True

    def update_param_fingerprint(self) -> bool:
        """更新当前参数指纹

        检查参数是否改变，如果改变则更新当前参数指纹

        Returns:
            bool: 参数是否发生变化
        """
        # 生成新的参数指纹
        new_fingerprint = self._generate_param_fingerprint()

        # 检查是否发生变化
        changed = new_fingerprint != self.current_param_fingerprint

        # 更新当前参数指纹
        self.current_param_fingerprint = new_fingerprint

        return changed

    def save_results(self, save_dir: str, only_valid: bool = False) -> Tuple[bool, str]:
        """保存识别结果到Excel文件

        Args:
            save_dir (str): 保存目录路径
            only_valid (bool, optional): 是否只保存有效的雷达信号结果。默认为False。

        Returns:
            Tuple[bool, str]: 是否成功，以及相关消息
        """
        try:
            self.logger.info(f"开始保存识别结果到目录: {save_dir}")

            # 检查是否存在识别结果
            if not hasattr(self, "valid_clusters") or not self.valid_clusters:
                return False, "没有可保存的识别结果"

            # 检查当前切片是否已保存过
            if self.is_current_slice_saved():
                return False, f"切片 {self.current_slice_idx + 1} 在当前参数设置下已经保存过"

            # 创建保存目录
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)

            # 从原始文件路径提取数据包名称
            if self.last_file_path:
                # 提取文件名并去掉扩展名
                data_package_name = os.path.splitext(os.path.basename(self.last_file_path))[0]
                # 包含参数指纹的文件名
                file_name = f"{data_package_name}_{self.current_param_fingerprint}_识别结果.xlsx"
            else:
                # 如果没有原始文件路径，使用默认名称
                file_name = f"识别结果_{self.current_param_fingerprint}.xlsx"

            file_path = os.path.join(save_dir, file_name)

            # 准备数据
            results_data = []

            # 遍历当前切片的识别结果
            current_slice_idx = self.current_slice_idx
            for cluster_idx, cluster_result in enumerate(self.valid_clusters):
                # 如果只保存有效结果，则检查是否为有效雷达信号
                if only_valid:
                    # 直接使用保存在聚类结果中的is_valid标志
                    is_valid = cluster_result.get("is_valid", False)

                    # 如果为无效结果且只保存有效结果，则跳过此条
                    if not is_valid:
                        continue

                # 提取需要保存的数据
                dim_name = cluster_result.get("dim_name", "")
                prediction = cluster_result.get("prediction", {})

                row_data = {
                    "切片索引": current_slice_idx + 1,
                    "雷达序号": cluster_idx + 1,
                    "聚类ID": cluster_result.get("total_cluster_count", 0),
                    "聚类维度": dim_name,
                    "载频/MHz": f"{', '.join([f'{v:.0f}' for v in cluster_result.get('CF', [])])}",  # 载频，多值用逗号分隔
                    "脉宽/us": f"{', '.join([f'{v:.1f}' for v in cluster_result.get('PW', [])])}",  # 脉宽，多值用逗号分隔
                    "DOA/°": f"{np.mean(cluster_result.get('DOA', [])):.0f}",  # DOA取均值
                    "PRI/us": f"{', '.join([f'{v:.1f}' for v in cluster_result.get('PRI', [])])}",  # PRI，多值用逗号分隔
                    "PA预测结果": self.PA_LABEL_NAMES.get(prediction.get("pa_label", 5), "未知"),
                    "PA预测概率": f"{'\n'.join([f'{self.PA_LABEL_NAMES[label]}: {conf:.4f}' for label, conf in prediction.get('pa_dict', {}).items()])}",
                    "DTOA预测结果": self.DTOA_LABEL_NAMES.get(prediction.get("dtoa_label", 4), "未知"),
                    "DTOA预测概率": f"{'\n'.join([f'{self.DTOA_LABEL_NAMES[label]}: {conf:.4f}' for label, conf in prediction.get('dtoa_dict', {}).items()])}",
                }
                results_data.append(row_data)

            # 创建DataFrame并保存
            if results_data:
                df = pd.DataFrame(results_data)

                # 准备参数信息表（包含聚类、识别和合并参数）
                params_info = {
                    "参数名": [
                        "epsilon_CF",
                        "epsilon_PW",
                        "min_pts",
                        "pa_threshold",
                        "dtoa_threshold",
                        "pa_weight",
                        "dtoa_weight",
                        "threshold",
                        "pri_equal_doa_tolerance",
                        "pri_different_doa_tolerance",
                        "pri_different_cf_tolerance",
                        "pri_none_doa_tolerance",
                    ],
                    "参数值": [
                        self.epsilon_CF,
                        self.epsilon_PW,
                        self.min_pts,
                        self.pa_threshold,
                        self.dtoa_threshold,
                        self.pa_weight,
                        self.dtoa_weight,
                        self.threshold,
                        self.pri_equal_doa_tolerance,
                        self.pri_different_doa_tolerance,
                        self.pri_different_cf_tolerance,
                        self.pri_none_doa_tolerance,
                    ],
                }
                params_df = pd.DataFrame(params_info)

                # 检查文件是否已存在
                if os.path.exists(file_path):
                    # 如果存在，读取现有数据
                    try:
                        with pd.ExcelWriter(file_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                            df.to_excel(writer, sheet_name="识别结果", index=False, startrow=writer.sheets["识别结果"].max_row, header=False)
                    except Exception as e:
                        self.logger.warning(f"追加到现有文件出错，将创建新文件: {str(e)}")
                        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                            df.to_excel(writer, sheet_name="识别结果", index=False)
                            params_df.to_excel(writer, sheet_name="参数信息", index=False)
                else:
                    # 创建新文件
                    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name="识别结果", index=False)
                        params_df.to_excel(writer, sheet_name="参数信息", index=False)

                # 标记当前切片为已保存
                self.mark_current_slice_saved()

                self.logger.info(f"识别结果已保存到: {file_path}")
                return True, f"成功保存{len(results_data)}条识别结果"
            else:
                return False, "没有有效的识别结果可保存"

        except Exception as e:
            self.logger.error(f"保存识别结果出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False, f"保存失败: {str(e)}"

    def _save_current_merge_result(self, save_dir: str, merged_data: dict) -> Tuple[bool, str]:
        """保存当前合并结果
        Args:
            save_dir (str): 保存目录
            merged_data (dict): 合并后的数据

        Returns:
            Tuple[bool, str]: 保存是否成功，以及提示信息
        """
        pass

    def full_speed_process(self):
        """全速处理方法

        开始全速处理流程，包括切片、聚类、识别、结果保存。
        使用线程进行后台处理，以避免阻塞UI。

        Returns:
            bool: 是否成功启动全速处理
        """
        # 检查必要条件
        if self.processor is None or self.processor.data is None or len(self.processor.data) == 0:
            self.logger.error("没有导入有效的雷达数据")
            return False

        if not hasattr(self, "save_dir") or self.save_dir is None or self.save_dir == "":
            self.logger.error("未设置保存目录")
            return False

        # 新建全速处理线程
        self.full_speed_worker = FullSpeedWorker(self)

        # 连接信号
        self.full_speed_worker.slice_started.connect(self._on_slice_started_fs)
        self.full_speed_worker.slice_finished.connect(self._on_slice_finished_fs)
        self.full_speed_worker.current_slice_finished.connect(self._on_current_slice_finished_fs)
        self.full_speed_worker.process_finished.connect(self._on_process_finished_fs)
        self.full_speed_worker.start_save.connect(self._on_start_save_fs)

        # 启动全速处理线程
        self.full_speed_worker.start()

        return True

    def _on_slice_started_fs(self):
        """全速处理切片开始信号"""
        self.logger.info("全速处理开始")
        # 向UI发送切片开始信号
        self.process_started_fs.emit()

    def _on_slice_finished_fs(self, success: bool, slice_count: int):
        """全速处理切片完成信号

        Args:
            success (bool): 切片处理是否成功
            slice_count (int): 切片数量
        """
        if success:
            self.logger.info(f"全速处理切片完成，共获取{slice_count}个切片")
            # 保存全速处理时的切片总数量，用来计算进度
            self.total_slice_count_fs = slice_count
            # 向UI发送切片完成信号
            self.slice_finished_fs.emit(True, slice_count)
        else:
            self.logger.error("全速处理切片失败")
            # 向UI发送切片失败信号
            self.slice_finished_fs.emit(False, 0)

    def _on_current_slice_finished_fs(self, slice_idx: int):
        """全速处理当前切片完成信号

        Args:
            success (bool): 当前切片处理是否成功
            slice_idx (int): 当前切片序号
        """
        # 计算进度百分比
        progress = int((slice_idx + 1) / self.total_slice_count_fs * 100)
        # 更新UI进度条
        self.progress_updated_fs.emit(progress)

    def _on_start_save_fs(self):
        """全速处理开始保存信号"""
        self.logger.info("开始保存识别结果...")
        # 向UI发送开始保存信号
        self.start_save_fs.emit()

    def _on_process_finished_fs(self, success: bool):
        """全速处理完成信号

        Args:
            success (bool): 全速处理是否成功
        """
        self.logger.info(f"全速处理{'成功' if success else '失败'}")
        # 向UI发送处理完成信号
        self.process_finished_fs.emit(success)
