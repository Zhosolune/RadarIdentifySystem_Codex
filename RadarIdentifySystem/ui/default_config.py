# -*- coding: utf-8 -*-
"""
默认配置管理模块

提供系统默认参数的管理功能，支持配置的保存、加载和重置。
使用JSON文件存储配置信息，提供通用的参数获取和设置方法。
配置实体对象提供直接属性访问，get_param方法用于获取用户输入值并以配置文件值作为默认值。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy
from cores.log_manager import LogManager
import shutil
from common.paths import Paths


class ClusteringParams:
    """聚类参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.epsilon_CF = data["epsilon_CF"]
        self.epsilon_PW = data["epsilon_PW"]
        self.min_pts = data["min_pts"]


class IdentificationParams:
    """识别参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.pa_threshold = data["pa_threshold"]
        self.dtoa_threshold = data["dtoa_threshold"]
        self.pa_weight = data["pa_weight"]
        self.dtoa_weight = data["dtoa_weight"]
        self.threshold = data["threshold"]


class PriEqualParams:
    """PRI相等参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.doa_tolerance = data["doa_tolerance"]


class PriDifferentParams:
    """PRI不同参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.doa_tolerance = data["doa_tolerance"]
        self.cf_tolerance = data["cf_tolerance"]


class PriNoneParams:
    """PRI无法提取参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.doa_tolerance = data["doa_tolerance"]


class CfExtractionParams:
    """CF参数提取配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.eps = data["eps"]
        self.min_samples = data["min_samples"]
        self.threshold_ratio = data["threshold_ratio"]


class PwExtractionParams:
    """PW参数提取配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.eps = data["eps"]
        self.min_samples = data["min_samples"]
        self.threshold_ratio = data["threshold_ratio"]


class PriExtractionParams:
    """PRI参数提取配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.eps = data["eps"]
        self.min_samples = data["min_samples"]
        self.threshold_ratio = data["threshold_ratio"]
        self.filter_threshold = data["filter_threshold"]
        self.harmonic_tolerance = data.get("harmonic_tolerance", 0.2)


class ExtractionParams:
    """参数提取配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.cf_extraction = CfExtractionParams(data["cf_extraction"])
        self.pw_extraction = PwExtractionParams(data["pw_extraction"])
        self.pri_extraction = PriExtractionParams(data["pri_extraction"])


class MergeParams:
    """合并参数配置类"""

    def __init__(self, data: Dict[str, Any]):
        self.pri_equal = PriEqualParams(data["pri_equal"])
        self.pri_different = PriDifferentParams(data["pri_different"])
        self.pri_none = PriNoneParams(data["pri_none"])


class ExportParams:
    """导出参数配置类
    
    管理导出对话框的配置项，包括导出路径、波段导出方式和大文件切分方式。
    """

    def __init__(self, data: Dict[str, Any]):
        self.export_path = data.get("export_path", "")
        self.band_export_mode = data.get("band_export_mode", 0)
        self.file_split_mode = data.get("file_split_mode", 2)
        self.file_split_size_mb = data.get("file_split_size_mb", 100)
        self.file_split_count = data.get("file_split_count", 10)


class ConfigParams:
    """配置参数实体类

    保持JSON的嵌套层级结构，提供对所有参数的分组访问。
    初始化时严格检查JSON文件的完整性，缺少任何参数都会导致初始化失败。
    """

    def __init__(self, config_data: Dict[str, Any]):
        """从配置数据初始化配置参数

        Args:
            config_data (Dict[str, Any]): 配置数据字典

        Raises:
            KeyError: 当配置数据缺少必需的参数时
            TypeError: 当参数类型不正确时
        """
        # 创建嵌套的配置对象，保持JSON结构
        self.clustering_params = ClusteringParams(config_data["clustering_params"])
        self.identification_params = IdentificationParams(
            config_data["identification_params"]
        )
        self.extraction_params = ExtractionParams(config_data["extraction_params"])
        self.merge_params = MergeParams(config_data["merge_params"])
        self.export_params = ExportParams(config_data.get("export_params", {}))


class DefaultConfig:
    """默认配置管理类

    负责管理系统的默认参数配置，支持从JSON文件加载、保存和重置配置。

    配置加载策略：
    1. 软件启动时优先读取default_params_user.json
    2. 如果user.json不存在，则读取default_params_system.json
    3. 将读取的配置数据初始化为ConfigParams实体

    配置更新策略：
    1. config_window保存时立即更新实体内容
    2. 同时更新default_params_user.json文件
    3. 其他输入框使用get_param方法获取实时参数，以配置文件值作为保护
    """

    def __init__(self):
        """初始化默认配置管理器"""
        self.logger = LogManager()

        # 确保用户配置文件存在
        Paths.ensure_user_config()

        # 配置文件路径 - 系统配置也从用户目录读取（如果用户需要修改系统默认配置）
        # 或者保持系统配置从资源目录读取（作为只读基准），但根据你的要求，现在改为读写目录
        self.system_config_file = Paths.get_config_dir(is_user=True) / "default_params_system.json"
        self.user_config_file = Paths.get_config_dir(is_user=True) / "default_params_user.json"

        # 配置实体对象（公开访问）
        self.params: ConfigParams

        # 加载配置并初始化实体
        self._load_and_init_config()

    def _load_and_init_config(self) -> None:
        """加载配置文件并初始化配置实体

        按照以下策略加载配置：
        1. 优先读取default_params_user.json
        2. 如果user.json不存在，则读取default_params_system.json
        3. 将读取的配置数据初始化为ConfigParams实体
        4. 检测设备掩码，不匹配时清空设备相关数据

        Raises:
            FileNotFoundError: 当配置文件不存在时
            json.JSONDecodeError: 当配置文件格式错误时
            KeyError: 当配置文件缺少必需参数时
        """
        try:
            config_data = None

            # 优先读取用户配置文件
            if self.user_config_file.exists():
                with open(self.user_config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                self.logger.info(f"已加载用户配置文件: {self.user_config_file}")
            # 如果用户配置不存在，读取系统配置文件
            elif self.system_config_file.exists():
                with open(self.system_config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                self.logger.info(
                    f"用户配置不存在，已加载系统配置文件: {self.system_config_file}"
                )
            else:
                error_msg = f"配置文件不存在: {self.user_config_file} 和 {self.system_config_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # 保存配置数据
            self._user_config = config_data

            # 检测设备掩码
            self._check_device_mask()

            # 初始化配置实体对象
            self.params = ConfigParams(self._user_config)
            self.logger.info("配置实体对象初始化成功")

        except (
            json.JSONDecodeError,
            FileNotFoundError,
            PermissionError,
            KeyError,
        ) as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            raise

    def _get_device_mask(self) -> str:
        """生成当前设备的唯一掩码

        使用机器名称+MAC地址生成唯一标识

        Returns:
            str: 设备掩码
        """
        import socket
        import uuid
        import hashlib

        try:
            # 获取机器名称
            hostname = socket.gethostname()

            # 获取MAC地址
            mac = uuid.getnode()
            mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))

            # 组合并生成哈希
            device_info = f"{hostname}_{mac_str}"
            mask = hashlib.md5(device_info.encode()).hexdigest()[:16]

            return mask
        except Exception as e:
            self.logger.error(f"获取设备掩码失败: {str(e)}")
            return ""

    def _check_device_mask(self) -> None:
        """检测设备掩码

        1. 保存当前设备掩码到user.json
        2. 检测system.json中掩码是否有值
           - 若没有值，则填入当前设备掩码
           - 若有值，则比较两个值是否相同
        3. 若不同，则清空user.json中的数据库目录和导入文件信息
        """
        try:
            current_mask = self._get_device_mask()

            # 读取system.json中的掩码
            system_mask = ""
            if self.system_config_file.exists():
                with open(self.system_config_file, "r", encoding="utf-8") as f:
                    system_config = json.load(f)
                    system_mask = system_config.get("device_mask", "")

            if not system_mask:
                # system.json中没有掩码，填入当前设备掩码
                if self.system_config_file.exists():
                    with open(self.system_config_file, "r", encoding="utf-8") as f:
                        system_config = json.load(f)
                    system_config["device_mask"] = current_mask
                    with open(self.system_config_file, "w", encoding="utf-8") as f:
                        json.dump(system_config, f, indent=2, ensure_ascii=False)
                    self.logger.info(f"已将设备掩码写入system.json: {current_mask}")
            elif system_mask != current_mask:
                # 设备掩码不匹配，清空用户配置中的设备相关数据
                self.logger.warning(f"设备掩码不匹配 (system: {system_mask}, 当前: {current_mask})，清空导入数据")
                self._user_config["database_paths"] = []
                self._user_config["import_files"] = {}
                self._user_config["excluded_files"] = []

            # 更新user.json中的设备掩码
            self._user_config["device_mask"] = current_mask
            self._save_user_config()

        except Exception as e:
            self.logger.error(f"检测设备掩码失败: {str(e)}")

    def _save_user_config(self) -> None:
        """保存用户配置到文件

        将当前用户配置保存到用户配置文件中。
        """
        try:
            with open(self.user_config_file, "w", encoding="utf-8") as f:
                json.dump(self._user_config, f, indent=2, ensure_ascii=False)
            # self.logger.info(f"用户配置已保存到: {self.user_config_file}")
        except Exception as e:
            self.logger.error(f"保存用户配置失败: {str(e)}")
            raise

    def reset_to_defaults(self) -> bool:
        """重置用户配置为系统默认值

        Returns:
            bool: 重置是否成功
        """
        try:
            # 读取系统配置文件
            with open(self.system_config_file, "r", encoding="utf-8") as f:
                system_config = json.load(f)

            # 深拷贝系统配置到用户配置
            self._user_config = deepcopy(system_config)

            # 保存重置后的配置
            self._save_user_config()

            # 重新创建配置实体对象
            self.params = ConfigParams(self._user_config)

            self.logger.info("用户配置已重置为默认值")
            return True

        except Exception as e:
            self.logger.error(f"重置配置失败: {str(e)}")
            return False

    def get_param(self, user_input_value: Any, config_param_path: str) -> Any:
        """获取参数值

        获取用户输入的值，如果用户输入值为None或无效，则返回配置文件中的默认值。
        当在config_window.py以外的地方使用时，使用default_params_user.json进行保护。

        Args:
            user_input_value (Any): 用户输入的值（来自界面输入框）
            config_param_path (str): 配置文件中的参数路径，使用点号分隔，如 'clustering_params.epsilon_CF'

        Returns:
            Any: 如果用户输入值有效则返回用户输入值，否则返回配置文件中的默认值

        Examples:
            >>> config.get_param(user_input, 'clustering_params.epsilon_CF')
            # 如果user_input有效则返回user_input，否则返回配置文件中的epsilon_CF值
        """
        try:
            # 如果用户输入值有效，直接返回
            if user_input_value is not None and str(user_input_value).strip() != "":
                return user_input_value

            # 否则从用户配置文件获取默认值（用于保护）
            # 重新读取用户配置文件以确保获取最新值
            try:
                with open(self.user_config_file, "r", encoding="utf-8") as f:
                    current_user_config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                # 如果用户配置文件不存在或损坏，使用内存中的配置
                current_user_config = self._user_config

            keys = config_param_path.split(".")
            value = current_user_config

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    self.logger.warning(f"配置参数路径不存在: {config_param_path}")
                    return None

            return value
        except Exception as e:
            self.logger.error(f"获取参数失败 {config_param_path}: {str(e)}")
            return None

    def set_param(self, param_path: str, value: Any) -> bool:
        """设置参数值

        修改用户配置中的参数值并自动保存到文件。

        Args:
            param_path (str): 参数路径，使用点号分隔
            value (Any): 参数值

        Returns:
            bool: 设置是否成功
        """
        try:
            keys = param_path.split(".")
            config = self._user_config

            # 导航到目标位置
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # 设置值
            config[keys[-1]] = value

            # 自动保存用户配置
            self._save_user_config()

            # 重新创建配置实体对象
            self.params = ConfigParams(self._user_config)

            return True
        except Exception as e:
            self.logger.error(f"设置参数失败 {param_path}: {str(e)}")
            return False

    def get_all_params(self) -> Dict[str, Any]:
        """获取所有用户参数

        Returns:
            Dict[str, Any]: 包含所有用户参数的字典
        """
        return deepcopy(self._user_config)

    def update_params(self, params: Dict[str, Any]) -> bool:
        """批量更新参数

        批量更新用户配置中的多个参数，最后统一保存。

        Args:
            params (Dict[str, Any]): 参数字典，键为参数路径，值为参数值

        Returns:
            bool: 更新是否成功
        """
        try:
            for param_path, value in params.items():
                keys = param_path.split(".")
                config = self._user_config

                # 导航到目标位置
                for key in keys[:-1]:
                    if key not in config:
                        config[key] = {}
                    config = config[key]

                # 设置值
                config[keys[-1]] = value

            # 批量更新完成后统一保存
            self._save_user_config()

            # 重新创建配置实体对象
            self.params = ConfigParams(self._user_config)

            return True

        except Exception as e:
            self.logger.error(f"批量更新参数失败: {str(e)}")
            return False

    def save_config(self) -> bool:
        """保存当前用户配置到文件

        Returns:
            bool: 保存是否成功
        """
        try:
            self._save_user_config()
            return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {str(e)}")
            return False

    def get_database_paths(self) -> list:
        """获取数据库目录路径列表

        Returns:
            list: 数据库目录路径列表
        """
        return self._user_config.get("database_paths", [])

    def add_database_path(self, path: str) -> bool:
        """添加数据库目录路径

        Args:
            path (str): 目录路径

        Returns:
            bool: 添加是否成功
        """
        try:
            if "database_paths" not in self._user_config:
                self._user_config["database_paths"] = []

            # 检查路径是否已存在
            if path in self._user_config["database_paths"]:
                self.logger.warning(f"目录路径已存在: {path}")
                return False

            self._user_config["database_paths"].append(path)
            self._save_user_config()
            self.logger.info(f"已添加数据库目录: {path}")
            return True
        except Exception as e:
            self.logger.error(f"添加数据库目录失败: {str(e)}")
            return False

    def remove_database_path(self, path: str) -> bool:
        """移除数据库目录路径

        Args:
            path (str): 目录路径

        Returns:
            bool: 移除是否成功
        """
        try:
            if "database_paths" not in self._user_config:
                return False

            if path in self._user_config["database_paths"]:
                self._user_config["database_paths"].remove(path)
                self._save_user_config()
                self.logger.info(f"已移除数据库目录: {path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"移除数据库目录失败: {str(e)}")
            return False

    def get_import_files(self, file_type: str) -> list:
        """获取导入文件列表

        Args:
            file_type: 文件类型 (Excel, Bin, MAT)

        Returns:
            list: 文件路径列表
        """
        try:
            if "import_files" not in self._user_config:
                self._user_config["import_files"] = {}
            return self._user_config["import_files"].get(file_type, [])
        except Exception as e:
            self.logger.error(f"获取导入文件列表失败: {str(e)}")
            return []

    def set_import_files(self, file_type: str, files: list) -> bool:
        """设置导入文件列表

        Args:
            file_type: 文件类型 (Excel, Bin, MAT)
            files: 文件路径列表

        Returns:
            bool: 是否成功
        """
        try:
            if "import_files" not in self._user_config:
                self._user_config["import_files"] = {}
            self._user_config["import_files"][file_type] = files
            self._save_user_config()
            return True
        except Exception as e:
            self.logger.error(f"设置导入文件列表失败: {str(e)}")
            return False

    def get_excluded_files(self) -> list:
        """获取被移除的文件列表（刷新时不会添加）

        Returns:
            list: 被排除的文件路径列表
        """
        try:
            return self._user_config.get("excluded_files", [])
        except Exception as e:
            self.logger.error(f"获取排除文件列表失败: {str(e)}")
            return []

    def add_excluded_file(self, file_path: str) -> bool:
        """添加文件到排除列表

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否成功
        """
        try:
            if "excluded_files" not in self._user_config:
                self._user_config["excluded_files"] = []
            if file_path not in self._user_config["excluded_files"]:
                self._user_config["excluded_files"].append(file_path)
                self._save_user_config()
            return True
        except Exception as e:
            self.logger.error(f"添加排除文件失败: {str(e)}")
            return False

    def clear_excluded_files(self) -> bool:
        """清空排除文件列表

        Returns:
            bool: 是否成功
        """
        try:
            self._user_config["excluded_files"] = []
            self._save_user_config()
            return True
        except Exception as e:
            self.logger.error(f"清空排除文件列表失败: {str(e)}")
            return False


    def update_config_from_window(self, config_data: Dict[str, Any]) -> bool:
        """从config_window更新配置

        当用户在config_window.py中编辑并保存配置时调用此方法。
        即刻更新实体内容，然后更新default_params_user.json文件。

        Args:
            config_data: 新的配置数据

        Returns:
            bool: 更新是否成功
        """
        try:
            # 更新内存中的用户配置
            self._user_config = config_data

            # 即刻更新实体内容
            self.params = ConfigParams(config_data)

            # 同步更新配置文件
            self._save_user_config()

            self.logger.info("配置已从config_window更新")
            return True

        except Exception as e:
            self.logger.error(f"从config_window更新配置失败: {str(e)}")
            return False

    def reset_param(self, param_path: str) -> bool:
        """重置单个参数为系统默认值

        Args:
            param_path (str): 参数路径

        Returns:
            bool: 重置是否成功
        """
        try:
            default_value = self._get_system_param(param_path)
            if default_value is not None:
                return self.set_param(param_path, default_value)
            return False
        except Exception as e:
            self.logger.error(f"重置参数失败: {str(e)}")
            return False

    def _get_system_param(self, param_path: str) -> Any:
        """从系统配置获取参数值

        Args:
            param_path (str): 参数路径

        Returns:
            Any: 系统默认参数值
        """
        try:
            # 读取系统配置文件
            with open(self.system_config_file, "r", encoding="utf-8") as f:
                system_config = json.load(f)

            keys = param_path.split(".")
            value = system_config

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return value
        except Exception:
            return None


# 全局配置实例
_default_config_instance: Optional[DefaultConfig] = None


def get_default_config() -> DefaultConfig:
    """获取默认配置实例（单例模式）

    Returns:
        DefaultConfig: 默认配置实例
    """
    global _default_config_instance
    if _default_config_instance is None:
        _default_config_instance = DefaultConfig()
    return _default_config_instance


def get_params() -> ConfigParams:
    """直接获取配置参数实例（便捷方法）

    这是一个便捷方法，外部类可以直接调用此函数获取params单例，
    而无需先调用get_default_config()再访问params属性。

    Returns:
        ConfigParams: 配置参数实例

    Example:
        >>> from ui.default_config import get_params
        >>> params = get_params()
        >>> epsilon_cf = params.clustering_params.epsilon_CF
    """
    return get_default_config().params


def reload_config() -> None:
    """重新加载配置

    重新创建DefaultConfig实例，用于配置文件更新后的重新加载。
    """
    global _default_config_instance
    _default_config_instance = None
    get_default_config()
