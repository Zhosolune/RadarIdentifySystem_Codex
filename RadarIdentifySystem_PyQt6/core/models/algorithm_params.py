"""核心算法参数数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClusteringParams:
    """聚类算法参数。

    功能描述：
        封装 CF/PW 级联聚类流程使用的全部输入参数，作为聚类算法的稳定
        参数契约对象，避免在调用链上持续扩展长参数列表。

    Attributes:
        eps_cf (float): CF 维度 DBSCAN 邻域半径。
        eps_pw (float): PW 维度 DBSCAN 邻域半径。
        min_pts (int): DBSCAN 核心点最小样本数。
        min_cluster_size (int): 聚类有效判定的最小点数。
    """

    eps_cf: float = 2.0
    eps_pw: float = 0.2
    min_pts: int = 1
    min_cluster_size: int = 8


@dataclass(frozen=True, slots=True)
class RecognitionParams:
    """识别算法参数。

    功能描述：
        封装识别阶段使用的业务参数，供后续识别工作流与核心算法共享统一
        的参数契约。

    Attributes:
        tolerance (float): 识别匹配容差。
        min_confidence (float): 最低置信度阈值。
        max_candidates (int): 最大候选结果数量。
    """

    tolerance: float = 0.5
    min_confidence: float = 0.8
    max_candidates: int = 5


@dataclass(frozen=True, slots=True)
class ExtractParams:
    """参数提取算法参数。

    功能描述：
        封装参数提取阶段使用的控制参数，供后续提取逻辑统一消费。

    Attributes:
        step (int): 提取步长。
        smooth_window (int): 平滑窗口大小。
        outlier_threshold (float): 离群值判定阈值。
    """

    step: int = 1
    smooth_window: int = 5
    outlier_threshold: float = 3.0


@dataclass(frozen=True, slots=True)
class MergeParams:
    """合并算法参数。

    功能描述：
        封装聚类结果合并阶段的业务参数，供后续合并规则与工作流共享。

    Attributes:
        time_decay (float): 时间衰减系数。
        sim_threshold (float): 相似度阈值。
        max_extrapolate (int): 最大外推步数。
        pri_equal_doa_tolerance (float): 等 PRI 合并时的 DOA 容差。
    """

    time_decay: float = 0.9
    sim_threshold: float = 0.8
    max_extrapolate: int = 3
    pri_equal_doa_tolerance: float = 20.0


@dataclass(frozen=True, slots=True)
class ModelImageConfig:
    """模型输入图像参数契约。

    功能描述：
        定义 PA/DTOA 模型推理所需的二值散点图像尺寸与坐标范围常量。
        严格对应旧版 `plot_manager.PlotConfig`，确保模型的视觉输入特征完全一致。

    Attributes:
        y_min (float): 图像纵轴下界。
        y_max (float): 图像纵轴上界。
        width (int): 图像宽度（像素）。
        height (int): 图像高度（像素）。
    """

    y_min: float
    y_max: float
    width: int
    height: int


# PA 模型输入图像参数（400×80，PA 幅度 40~120 dB）
PA_IMAGE_CONFIG = ModelImageConfig(
    y_min=40,
    y_max=120,
    width=400,
    height=80,
)

# DTOA 模型输入图像参数（500×250，DTOA 0~3000 us，运行时动态可升至 4000 us）
DTOA_IMAGE_CONFIG = ModelImageConfig(
    y_min=0,
    y_max=3000,
    width=500,
    height=250,
)

# DTOA 动态 y_max 升级阈值配置
# 当 DTOA 落在 [3000, 4000] us 区间的点数超过此阈值时，自动将 y_max 升至 4000 us
DTOA_YMAX_UPSCALE_UPPER = 4000         # 升级后的纵轴上界
DTOA_YMAX_UPSCALE_COUNT_MIN = 10       # 升级所需的最小点数（绝对）
DTOA_YMAX_UPSCALE_RATIO = 0.2          # 升级所需的最小点数比例（相对总点数）
