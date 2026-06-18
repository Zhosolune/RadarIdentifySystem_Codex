# 聚类参数链路同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `app_config.py` 中拆分后的 CF/PW 最小点数和新增 DOA 参数同步到核心参数对象、运行时组装器和识别聚类流程。

**Architecture:** `ClusteringParams` 增加 `min_pts_cf`、`min_pts_pw`、`eps_doa`、`min_pts_doa`、`clip_threshold_doa` 字段；`runtime.get_clustering_params()` 从新配置项读取这些字段；`IdentifyWorker` 在 CF/PW 两级聚类中分别使用 `min_pts_cf` 与 `min_pts_pw`。DOA 参数只进入参数对象和日志快照，暂不参与聚类算法。

**Tech Stack:** Python 3.12、dataclasses、PyQt6 配置系统、pytest。

---

### Task 1: 参数模型和运行时组装器

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/core/models/algorithm_params.py`
- Modify: `RadarIdentifySystem_PyQt6/runtime/algorithm_params.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_runtime_algorithm_params.py`

- [x] **Step 1: 写失败测试**

新增测试断言 `get_clustering_params()` 返回 `min_pts_cf`、`min_pts_pw`、`eps_doa`、`min_pts_doa`、`clip_threshold_doa`，且不再依赖旧 `algorithmMinPts`。

- [x] **Step 2: 运行测试确认失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_runtime_algorithm_params.py -v`

Expected: FAIL，当前 `ClusteringParams` 缺少新字段或运行时读取旧配置项。

- [x] **Step 3: 最小实现**

更新 `ClusteringParams` 字段和文档；更新 `get_clustering_params()` 读取 `algorithmMinPtsCF`、`algorithmMinPtsPW`、`algorithmEpsilonDOA`、`algorithmMinPtsDOA`、`algorithmClipThresholdDOA`。

- [x] **Step 4: 运行测试确认通过**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_runtime_algorithm_params.py -v`

Expected: PASS。

### Task 2: 识别聚类流程消费新字段

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/runtime/threading/identify_worker.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_identify_worker_clustering_params.py`

- [x] **Step 1: 写失败测试**

通过 monkeypatch `process_dimension_clustering()` 和 `recognize_clusters()`，断言 CF 阶段收到 `min_pts_cf`，PW 阶段收到 `min_pts_pw`。

- [x] **Step 2: 运行测试确认失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_identify_worker_clustering_params.py -v`

Expected: FAIL，当前 CF/PW 都使用旧 `min_pts`。

- [x] **Step 3: 最小实现**

更新日志快照字段；CF 聚类传 `cluster_params.min_pts_cf`，PW 聚类传 `cluster_params.min_pts_pw`；DOA 参数只记录，不调用 DOA 聚类。

- [x] **Step 4: 运行相关测试和语法检查**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_runtime_algorithm_params.py RadarIdentifySystem_PyQt6/tests/unit/test_identify_worker_clustering_params.py -v`

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m compileall -q RadarIdentifySystem_PyQt6/core/models/algorithm_params.py RadarIdentifySystem_PyQt6/runtime/algorithm_params.py RadarIdentifySystem_PyQt6/runtime/threading/identify_worker.py`

Expected: PASS / exit code 0。
