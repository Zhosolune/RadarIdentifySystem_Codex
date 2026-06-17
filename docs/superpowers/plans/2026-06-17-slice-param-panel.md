# Slice 参数面板 UI 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将切片参数抽屉内容拆为独立面板，恢复两套导航入口，并加入不修改全局配置的 PA/DTOA 模型选择卡。

**Architecture:** `SliceInterface` 保留 `SlidingDrawer` 外壳，通过 `setContentWidget()` 挂载普通 `QWidget` 类型的 `SliceParamPanel`。面板持有自动识别、模型选择和导出路径卡；模型选择卡只保存实例状态并发出信号，控制器继续复用现有导航槽函数。

**Tech Stack:** Python 3.11、PyQt6、项目内 vendored qfluentwidgets、pytest。

---

## 文件职责

- `ui/components/model_selection_card.py`：枚举 PA/DTOA 模型，展示两个下拉框并保存实例级选择。
- `ui/components/slice_param_panel.py`：只负责抽屉内容区三类卡片的创建和布局。
- `ui/components/navigation_control_card.py`：右栏常驻操作卡和四个文字导航按钮。
- `ui/interfaces/slice_interface.py`：创建抽屉外壳、内容面板和触发关系，不再组装抽屉内部卡片。
- `ui/controllers/slice_controller.py`：让文字切片按钮复用已有切片导航槽函数。
- `ui/controllers/identify_controller.py`：让文字类别按钮复用已有类别导航槽函数。
- `tests/unit/test_model_selection_card.py`：锁定模型枚举、初值和实例局部状态。
- `tests/unit/test_slice_param_panel.py`：锁定参数面板卡片归属。
- `tests/unit/test_slice_interface.py`：锁定抽屉组合、宽度和新命名。
- `tests/unit/test_navigation_controls.py`：锁定两套导航入口连接同一控制器行为。

### Task 1: 实例级模型选择卡

**Files:**
- Create: `RadarIdentifySystem_PyQt6/ui/components/model_selection_card.py`
- Create: `RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py`

- [ ] **Step 1: 写入模型选择卡失败测试**

```python
"""模型选择卡实例状态测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import qconfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.app_config import appConfig
from ui.components.model_selection_card import ModelSelectionCard

_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_model_selection_is_local_to_card(monkeypatch) -> None:
    """切换模型时只更新卡片状态，不写入全局配置。"""
    _app()
    pa_paths = [r"C:\models\pa-default.onnx", r"C:\models\pa-session.onnx"]
    dtoa_paths = [r"C:\models\dtoa-default.onnx", r"C:\models\dtoa-session.onnx"]
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: pa_paths if model_type == "PA" else dtoa_paths,
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_path",
        lambda model_type: pa_paths[0] if model_type == "PA" else dtoa_paths[0],
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_display_name",
        lambda path, model_type: Path(path).stem,
    )
    original_pa = qconfig.get(appConfig.modelPaEnabledPath)
    original_dtoa = qconfig.get(appConfig.modelDtoaEnabledPath)

    card = ModelSelectionCard()
    card.pa_model_combo.setCurrentIndex(1)
    card.dtoa_model_combo.setCurrentIndex(1)

    assert card.selected_model_path("PA") == pa_paths[1]
    assert card.selected_model_path("DTOA") == dtoa_paths[1]
    assert qconfig.get(appConfig.modelPaEnabledPath) == original_pa
    assert qconfig.get(appConfig.modelDtoaEnabledPath) == original_dtoa
```

- [ ] **Step 2: 运行测试并确认因组件缺失而失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py -v`

Expected: FAIL，错误包含 `ModuleNotFoundError: No module named 'ui.components.model_selection_card'`。

- [ ] **Step 3: 实现最小模型选择卡**

实现 `ModelSelectionCard(ExpandGroupSettingCard)`，模块导入和核心逻辑如下：

```python
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, ExpandGroupSettingCard, FluentIcon

from app.model_bootstrap import (
    collect_available_model_files,
    get_display_name,
    get_enabled_model_path,
)


class ModelSelectionCard(ExpandGroupSettingCard):
    """保存当前切片页面 PA 与 DTOA 模型选择的设置卡。"""

    modelChanged = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建两个模型下拉框并复制当前全局默认选择。"""
        super().__init__(
            icon=FluentIcon.ROBOT,
            title="模型选择",
            content="为当前 Session 选择 PA 与 DTOA 模型",
            parent=parent,
        )
        self.setObjectName("modelSelectionCard")
        self._model_paths: dict[str, list[str]] = {}
        self._selected_paths: dict[str, str | None] = {"PA": None, "DTOA": None}
        self.pa_model_combo = self._create_model_combo("PA")
        self.dtoa_model_combo = self._create_model_combo("DTOA")
        self.addGroup(FluentIcon.APPLICATION, "PA 模型", None, self.pa_model_combo)
        self.addGroup(FluentIcon.APPLICATION, "DTOA 模型", None, self.dtoa_model_combo)

    def selected_model_path(self, model_type: str) -> str | None:
        """返回指定模型类型在当前卡片实例中的选择路径。

        Args:
            model_type: 模型类型，支持 ``PA`` 或 ``DTOA``，不区分大小写。

        Returns:
            当前实例选中的模型文件路径；没有可用模型时返回 ``None``。

        Raises:
            ValueError: 模型类型不是 ``PA`` 或 ``DTOA``。

        Example:
            >>> card = ModelSelectionCard()
            >>> card.selected_model_path("PA") is None or isinstance(card.selected_model_path("PA"), str)
            True
        """
        normalized_type = model_type.upper()
        if normalized_type not in self._selected_paths:
            raise ValueError(f"不支持的模型类型: {model_type}")
        return self._selected_paths[normalized_type]

    def _create_model_combo(self, model_type: str) -> ComboBox:
        """创建并初始化指定类型的模型下拉框。"""
        combo = ComboBox(self)
        model_paths = collect_available_model_files(model_type)
        self._model_paths[model_type] = model_paths
        combo.addItems([get_display_name(path, model_type) for path in model_paths])
        if not model_paths:
            combo.setEnabled(False)
            return combo

        enabled_path = get_enabled_model_path(model_type)
        selected_index = model_paths.index(enabled_path) if enabled_path in model_paths else 0
        combo.setCurrentIndex(selected_index)
        self._selected_paths[model_type] = model_paths[selected_index]
        combo.currentIndexChanged.connect(
            lambda index, current_type=model_type: self._on_model_changed(
                current_type,
                index,
            )
        )
        return combo

    def _on_model_changed(self, model_type: str, index: int) -> None:
        """将下拉框变化保存到当前卡片实例。"""
        model_paths = self._model_paths[model_type]
        if not 0 <= index < len(model_paths):
            return
        selected_path = model_paths[index]
        self._selected_paths[model_type] = selected_path
        self.modelChanged.emit(model_type, selected_path)
```

模块和类补充中文 Google 风格 docstring；构造函数准确说明只读取全局默认值、不产生全局写入。不得导入或调用 `qconfig.set()`、`set_enabled_model_path()`。

- [ ] **Step 4: 运行模型选择卡测试**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py -v`

Expected: PASS。

- [ ] **Step 5: 路径限定提交本任务**

```powershell
git add -- RadarIdentifySystem_PyQt6/ui/components/model_selection_card.py RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py
git commit --only -m "feat(ui): 添加实例级模型选择卡" -- RadarIdentifySystem_PyQt6/ui/components/model_selection_card.py RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py
```

### Task 2: 独立 SliceParamPanel 内容组件

**Files:**
- Create: `RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py`
- Create: `RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/components/__init__.py`

- [ ] **Step 1: 写入面板卡片归属失败测试**

```python
"""切片参数面板组件测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.components import SliceParamPanel
from ui.components.export_option_card import ExportOptionCard
from ui.components.model_selection_card import ModelSelectionCard

_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_slice_param_panel_owns_drawer_cards() -> None:
    """参数面板应集中持有抽屉中的三类卡片。"""
    _app()
    panel = SliceParamPanel()

    assert panel.auto_recognize_card.parent() is not None
    assert isinstance(panel.model_selection_card, ModelSelectionCard)
    assert isinstance(panel.export_path_card, ExportOptionCard)
```

- [ ] **Step 2: 运行测试并确认因导出缺失而失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py -v`

Expected: FAIL，错误包含 `ImportError: cannot import name 'SliceParamPanel'`。

- [ ] **Step 3: 实现普通 QWidget 参数面板**

创建 `SliceParamPanel(QWidget)`，构造函数内创建：

```python
self.auto_recognize_card = SwitchSettingCard(
    icon=FluentIcon.PLAY,
    title="自动识别",
    content="切换下一片时自动执行识别工作流",
    configItem=appConfig.autoRecognizeNextSlice,
    parent=self,
)
self.model_selection_card = ModelSelectionCard(self)
self.export_path_card = ExportOptionCard(self)
```

使用 `QVBoxLayout(self)`，边距为 `0`，间距为 `8`，按上述顺序加入三张卡片并在末尾加入 stretch。该类不继承 `SlidingDrawer`，不创建抽屉，不连接识别工作流。随后在 `ui/components/__init__.py` 导出 `ModelSelectionCard` 和 `SliceParamPanel`。

- [ ] **Step 4: 运行面板测试与模型卡回归**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py -v`

Expected: 2 tests PASS。

- [ ] **Step 5: 路径限定提交本任务**

```powershell
git add -- RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py RadarIdentifySystem_PyQt6/ui/components/__init__.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py
git commit --only -m "refactor(ui): 抽离切片参数面板内容" -- RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py RadarIdentifySystem_PyQt6/ui/components/__init__.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py
```

### Task 3: 抽屉组合与卡片迁移

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py`
- Modify: `RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py`

- [ ] **Step 1: 将抽屉组合契约改为失败测试**

把现有宽度测试更新为：

```python
def test_slice_param_panel_is_mounted_in_matching_drawer() -> None:
    """参数面板应挂载到与右栏同宽的独立抽屉中。"""
    _app()
    interface = SliceInterface()

    assert hasattr(interface, "slice_param_panel")
    assert hasattr(interface, "slice_param_drawer")
    assert not hasattr(interface, "slice_param_config")
    assert interface.slice_param_drawer.drawerSize() == interface.right_column.width()
    assert interface.slice_param_drawer.contentWidget() is interface.slice_param_panel
    assert not hasattr(interface.navigation_control_card, "auto_recognize_card")
    assert interface.slice_param_panel.export_path_card is not None
```

- [ ] **Step 2: 运行测试并确认旧结构导致失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py -v`

Expected: FAIL，首个失败断言为缺少 `slice_param_panel` 或 `slice_param_drawer`。

- [ ] **Step 3: 最小迁移抽屉和卡片**

在 `NavigationControlCard` 中删除 `auto_recognize_card` 的创建、布局和文档属性说明，保留现有主操作区。

在 `SliceInterface._create_right_column()` 中：

```python
self.navigation_control_card = NavigationControlCard(cards_group)
self.plot_option_card = PlotOptionCard(cards_group)
self.redraw_option_card = RedrawOptionCard(cards_group)

cards_group.addSettingCard(self.navigation_control_card)
cards_group.addSettingCard(self.plot_option_card)
cards_group.addSettingCard(self.redraw_option_card)

self.slice_param_drawer = SlidingDrawer(
    DrawerPosition.RIGHT,
    self.RIGHT_COLUMN_WIDTH,
    self,
    title="切片参数",
)
self.slice_param_panel = SliceParamPanel(self.slice_param_drawer)
self.slice_param_drawer.setContentWidget(self.slice_param_panel)
self.slice_param_drawer.setToggleButtonVisible(False)
self.slice_param_drawer.setTriggerWidget(
    self.navigation_control_card.drawer_options_button
)
self.navigation_control_card.drawer_options_button.clicked.connect(
    self.slice_param_drawer.toggle
)
```

删除 `SliceInterface` 中旧 `export_path_card` 创建、右栏卡片注册和抽屉占位标签布局。清理不再使用的导入，保留 `RIGHT_COLUMN_WIDTH` 单一宽度真相源。

- [ ] **Step 4: 运行抽屉与面板定向回归**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py RadarIdentifySystem_PyQt6/tests/unit/test_sliding_drawer.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 路径限定提交本任务**

```powershell
git add -- RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py
git commit --only -m "refactor(ui): 组合切片参数抽屉与独立面板" -- RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py
```

### Task 4: 恢复文字导航按钮并复用槽函数

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py`
- Create: `RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py`

- [ ] **Step 1: 写入双入口连接失败测试**

测试用 `monkeypatch` 在创建 `SliceInterface` 前替换四个控制器槽函数为计数函数；测试模块导入和用例完整内容如下：

```python
"""切片页面双入口导航连接测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.controllers.identify_controller import IdentifyController
from ui.controllers.slice_controller import SliceController
from ui.interfaces.slice_interface import SliceInterface

_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_graphic_and_text_navigation_buttons_share_controller_slots(monkeypatch) -> None:
    """图形和文字导航按钮应触发同一组控制器槽函数。"""
    _app()
    calls = {"prev_slice": 0, "next_slice": 0, "prev_cluster": 0, "next_cluster": 0}

    def count(name: str) -> Callable[[object], None]:
        """创建记录指定槽函数调用次数的替代函数。"""
        def slot(controller: object) -> None:
            """记录一次控制器槽函数调用。"""
            calls[name] += 1
        return slot

    monkeypatch.setattr(SliceController, "_on_prev_slice", count("prev_slice"))
    monkeypatch.setattr(SliceController, "_on_next_slice", count("next_slice"))
    monkeypatch.setattr(IdentifyController, "_on_prev_cluster", count("prev_cluster"))
    monkeypatch.setattr(IdentifyController, "_on_next_cluster", count("next_cluster"))
    interface = SliceInterface()

    interface.prev_slice_button.click()
    interface.navigation_control_card.prev_slice_button.click()
    interface.next_slice_button.click()
    interface.navigation_control_card.next_slice_button.click()
    interface.prev_cluster_button.click()
    interface.navigation_control_card.prev_cluster_button.click()
    interface.next_cluster_button.click()
    interface.navigation_control_card.next_cluster_button.click()

    assert calls == {
        "prev_slice": 2,
        "next_slice": 2,
        "prev_cluster": 2,
        "next_cluster": 2,
    }
```

- [ ] **Step 2: 运行测试并确认文字按钮缺失导致失败**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py -v`

Expected: FAIL，错误包含 `NavigationControlCard` 缺少 `prev_slice_button`。

- [ ] **Step 3: 恢复按钮并连接已有槽函数**

在 `NavigationControlCard.__init__()` 中创建：

```python
self.prev_slice_button = PushButton(CustomIcon.CHEVRONS_LEFT, "上一片", self)
self.prev_cluster_button = PushButton(CustomIcon.CHEVRON_LEFT, "上一类", self)
self.next_cluster_button = PushButton(CustomIcon.CHEVRON_RIGHT, "下一类", self)
self.next_slice_button = PushButton(CustomIcon.CHEVRONS_RIGHT, "下一片", self)
```

导航行按“上一片、上一类、重置当前切片、下一类、下一片”的顺序加入按钮。`SliceController._connect_signals()` 新增文字切片按钮到现有 `_on_prev_slice`/`_on_next_slice` 的连接；`IdentifyController._connect_signals()` 新增文字类别按钮到现有 `_on_prev_cluster`/`_on_next_cluster` 的连接。不新增转发槽函数。

- [ ] **Step 4: 运行导航测试和全部相关回归**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_interface.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py RadarIdentifySystem_PyQt6/tests/unit/test_model_selection_card.py RadarIdentifySystem_PyQt6/tests/unit/test_sliding_drawer.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 路径限定提交本任务**

```powershell
git add -- RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py
git commit --only -m "feat(ui): 恢复切片和类别文字导航按钮" -- RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py
```

### Task 5: 文档与最终验证

**Files:**
- Modify: `docs/operateLog.md`

- [ ] **Step 1: 运行语法编译检查**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m compileall RadarIdentifySystem_PyQt6/ui/components/model_selection_card.py RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py`

Expected: 退出码为 0，不出现 `SyntaxError`。

- [ ] **Step 2: 运行完整单元测试目录**

Run: `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit -v`

Expected: 全部 PASS；若存在与本次无关的基线失败，记录准确测试名和错误，不宣称完整通过。

- [ ] **Step 3: 更新操作日志**

在 `docs/operateLog.md` 当前条目中勾选完成项，列出实际影响文件、测试命令及其结果；如果 Qt 运行态未执行，明确记录“仅完成语法级/单元测试验证”。

- [ ] **Step 4: 检查差异和意外文件**

Run: `git diff --check; git status --short`

Expected: `git diff --check` 无错误；状态中不出现计划外的新文件，原有用户修改保持不变。

- [ ] **Step 5: 路径限定提交操作日志**

```powershell
git add -- docs/operateLog.md
git commit --only -m "docs: 记录切片参数面板重构结果" -- docs/operateLog.md
```
