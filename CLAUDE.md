# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dual-project codebase for a radar signal multi-dimensional parameter joint intelligent sorting system (雷达信号多维参数联合智能分选系统):

- **`RadarIdentifySystem/`** — Legacy PyQt5 version (frozen, do not modify)
- **`RadarIdentifySystem_PyQt6/`** — Active PyQt6 refactored version, all new work happens here

## Commands

```bash
# Run the application (from RadarIdentifySystem_PyQt6/)
python main.py

# Run unit tests
python -m pytest tests/unit/ -v
python -m pytest tests/unit/test_core_clustering.py -v   # single test file

# Install dependencies
pip install -r requirements.txt
```

Python >= 3.12 required. Windows 10/11 only.

## Architecture (PyQt6 version)

Strict layered architecture with enforced dependency direction:

```
ui → runtime → core
ui → app       (only global capabilities: config/log/signal_bus/style)
runtime → infra
infra → core
```

**`core` is forbidden from depending on ui/app/infra/runtime.** It contains pure business logic and algorithms with no Qt or UI imports.

### Layers

| Layer | Directory | Role |
|-------|-----------|------|
| `app/` | Lifecycle, config, signal_bus, logging, styles | Application shell |
| `core/` | Pure algorithms & data models | Business logic (no Qt) |
| `infra/` | Third-party adapters (plotting, parsers, ONNX, storage) | Integration |
| `runtime/` | Workflow orchestration, workers, events | Process control |
| `ui/` | Views, components, controllers, adapters | Display only |
| `utils/` | General-purpose utilities | No business semantics |

### Key Architectural Patterns

**ProcessingSession** (`core/models/processing_session.py`) — Central data carrier (not a manager). Holds all pipeline outputs from import through export. Stages progress linearly: `CREATED → IMPORTED → PREPROCESSED → SLICED → CLUSTERED → RECOGNIZED → MERGED → EXPORTED`. Stage failures do not advance the stage; completed stage outputs are never cleared by failures.

**Signal Bus** (`app/signal_bus.py`) — Global singleton `_SignalBus` decouples components. All cross-module events flow through it. Events must carry `session_id`; large objects go via session lookup, not event payloads.

**Workflow/Worker Separation** — `runtime/workflows/` orchestrates thread lifecycle and writes session state; `runtime/threading/` workers run computation on QThread. Only workflows write `session.*_result` and `session.stage` — UI never writes session directly.

**Controllers** (`ui/controllers/`) — MVP Presenters that bridge UI to workflows. UI slot functions must live here, not in interface or component classes.

### Data Pipeline

```
Excel/Bin/MAT → ImportWorker → PulseBatch [CF, PW, DOA, PA, TOA]
  → preprocess (PA cleaning, TOA flip fix) → SliceWorker (time-window slicing)
  → infra/plotting/facades (rasterize to QImage, synchronous) → IdentifyWorker (DBSCAN clustering)
  → recognition (ONNX inference, stub) → merge (stub) → export
```
Recognition and merge stages are 0-byte stubs (not yet implemented). Rendering uses synchronous facade calls (no worker thread); the render workflow/cache was intentionally removed.

**PulseBatch columns** (`core/models/pulse_batch.py`): COL_CF=0, COL_PW=1, COL_DOA=2, COL_PA=3, COL_TOA=4

### Rendering

`infra/plotting/` — `facades.py` provides high-level API (`render_slice_images`, `render_cluster_images`), delegating to `engine.py` rasterization. 5 dimensions rendered per slice: CF, PW, PA, DTOA, DOA. Band-specific Y-axis ranges defined in `infra/plotting/utils.py`.

## Mandatory Constraints

1. **No business logic in UI layer** — algorithms, state management, and business decisions belong in `core/` or `runtime/`
2. **Workers must live in `runtime/threading/`**, never in `core/`
3. **All workflow+threading code under `runtime/`** — workflows and workers must be siblings
4. **Config single entry point** — `app/app_config.py`, persisted to `config/config.json`. No second config system
5. **UI must not call `core/`/`infra/` directly** — go through `runtime/workflows/` and `ui/controllers/`
6. **Complex composite UI must be extracted** to `ui/components/` as named component instances; page-level code must not inline assemblies or create anonymous core display components in loops
7. **Logging** — write logs at key nodes (stage start/finish/fail). Prefix format: `[session:{id}] [stage:{name}]`
8. **Inline comments** — required, written in Simplified Chinese, concise "verb + object" style (e.g., "获取当前目录", "发射xx信号", "创建xx线程")
9. **signal_bus** — use for all cross-module signal communication; no direct signal wiring between UI and workers

## Implementation Notes

- **`runtime/events/` is planned but empty.** Current event data classes live in `app/events.py` (`ImportFinishedEvent`, `SliceReadyEvent`, `IdentifyProgressEvent`, etc.). Future work should move them to `runtime/events.py` per the architecture spec.
- **`core/recognition.py` and `core/merge.py` are 0-byte stubs.** The pipeline currently stops at clustering + display.
- **`core/params_extract.py`** provides `extract_grouped_values()` used by clustering to pull parameters from config.
- **`infra/onnx/`, `infra/storage/`, `infra/packaging/`** are empty directories — ONNX inference, export, and packaging are not yet built.
- **`openpyxl`** is a transitive dependency (pandas `.read_excel()` needs it for `.xlsx`) but is not in `requirements.txt` — install separately if Excel import fails.
- **`.trae/rules/`** contains additional AI IDE guidance split into four files: directory baseline + constraints, code standards, AI behavior rules, and session/event contracts. Read these if modifying architecture boundaries, adding stages, or changing the event model.

## Key Dependencies

- PyQt6 + PyQt6-Fluent-Widgets (UI framework, `FluentWindow` base class)
- scikit-learn (DBSCAN clustering)
- onnxruntime (neural network inference, not yet wired)
- numpy, pandas (data handling)
- matplotlib (plotting backend)
