# -*- coding: utf-8 -*-
"""
路径管理模块

用于统一管理应用程序的资源路径和用户数据路径。
兼容开发环境和 PyInstaller 打包后的环境。
"""

import sys
import os
import shutil
from pathlib import Path

# 应用程序名称，用于创建用户数据目录
APP_NAME = "RadarIdentifySystem"

class Paths:
    """路径管理类"""
    
    @staticmethod
    def get_base_path() -> Path:
        """
        获取应用程序的基准路径。
        
        Returns:
            Path: 基准路径
            - 开发环境: 项目根目录
            - 打包环境: 
                - onedir模式: exe所在目录 或 _internal 目录 (如果存在)
                - onefile模式: sys._MEIPASS
        """
        if getattr(sys, 'frozen', False):
            # 打包环境
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller --onefile 模式
                return Path(sys._MEIPASS)
            else:
                # PyInstaller --onedir 模式
                exe_dir = Path(sys.executable).parent
                
                # 即使 _internal 目录存在，资源文件也位于根目录下
                # 因此直接返回 exe 所在目录作为基准路径
                return exe_dir
        else:
            # 开发环境: 当前文件在 common/paths.py，根目录是两级父目录
            return Path(__file__).resolve().parent.parent

    @staticmethod
    def get_resource_path(relative_path: str) -> Path:
        """
        获取只读资源的绝对路径。
        
        Args:
            relative_path (str): 相对路径，如 "resources/icons/app.ico"
            
        Returns:
            Path: 资源的绝对路径
        """
        return Paths.get_base_path() / relative_path

    @staticmethod
    def get_user_data_dir() -> Path:
        """
        获取用户数据目录。
        
        Returns:
            Path: 
            - 开发环境: 项目根目录
            - 打包环境: AppData/Local/RadarIdentifySystem
        """
        if getattr(sys, 'frozen', False):
            # 打包环境: 使用 AppData
            local_app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            user_data_dir = Path(local_app_data) / APP_NAME
        else:
            # 开发环境: 使用项目根目录
            user_data_dir = Paths.get_base_path()
        
        # 确保目录存在
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        return user_data_dir

    @staticmethod
    def get_config_dir(is_user: bool = True) -> Path:
        """
        获取配置目录。
        
        Args:
            is_user (bool): True 表示获取用户配置目录(AppData)，False 表示获取系统默认配置目录(Resources)
            
        Returns:
            Path: 配置目录路径
        """
        if is_user:
            path = Paths.get_user_data_dir() / "config"
            path.mkdir(parents=True, exist_ok=True)
            return path
        else:
            return Paths.get_resource_path("config")

    @staticmethod
    def get_log_dir() -> Path:
        """
        获取日志目录 (位于用户数据目录下)。
        
        Returns:
            Path: 日志目录路径
        """
        path = Paths.get_user_data_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_model_dir() -> Path:
        """
        获取模型目录 (只读资源)。
        
        Returns:
            Path: 模型目录路径
        """
        return Paths.get_resource_path("model_wm")

    @staticmethod
    def get_model_registry_path() -> Path:
        """
        获取模型注册表文件路径。
        
        模型注册表用于存储模型显示名称与实际文件名的映射关系。
        
        Returns:
            Path: 模型注册表 JSON 文件路径
        """
        return Paths.get_config_dir(is_user=True) / "model_registry.json"

    @staticmethod
    def ensure_user_config():
        """
        确保用户配置文件存在。
        将 default_params_user.json 和 default_params_system.json 都复制到用户配置目录。
        """
        user_config_dir = Paths.get_config_dir(is_user=True)
        resource_config_dir = Paths.get_config_dir(is_user=False)
        
        # 开发环境下，如果用户配置目录和资源目录相同，则无需复制
        if user_config_dir.resolve() == resource_config_dir.resolve():
            return
            
        # 需要确保存在的文件列表
        config_files = ["default_params_user.json", "default_params_system.json"]
        
        for filename in config_files:
            target_file = user_config_dir / filename
            
            # 如果目标文件已存在，跳过
            if target_file.exists():
                continue
                
            # 尝试从只读资源目录复制
            source_file = resource_config_dir / filename
            
            if source_file.exists():
                try:
                    shutil.copy2(source_file, target_file)
                    print(f"已初始化配置文件: {target_file} (从 {source_file} 复制)")
                except Exception as e:
                    print(f"初始化配置文件失败 {filename}: {e}")
            else:
                print(f"警告: 源配置文件不存在 {source_file}")
