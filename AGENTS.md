# Glimpse AI Session Guide

This file is the shared starting point for new AI coding sessions. Keep it short, factual, and durable. Temporary plans, prompts, tool notes, and session scratch files should stay out of Git.

## Product In One Sentence

Glimpse is a desktop memory assistant: a user captures the screen, the app summarizes visual meaning, stores the result locally, and lets the user search those memories later.

## First Principles

- Preserve the current local-memory pipeline: capture -> local OCR -> AI summary
  or OCR fallback -> SQLite (`PENDING`) -> embedding + ChromaDB -> final sync
  status -> search/UI.
- Keep user data local by default. Runtime data belongs under `GlimpseData/`, not in the repo.
- Prefer dependency injection through `container.get(...)`. Avoid introducing new module-level global instances.
- Treat UI, services, storage, and capture as separate layers. Cross layers through existing services/signals instead of shortcut imports.
- Make behavior robust when AI credentials are missing. OCR-only memory creation,
  search, and browse should still work.
- Do not commit AI session artifacts. Keep only this guide as the repo-level instruction file for future sessions.

## Environment

Use the existing conda environment:

```powershell
conda activate glimpse
python main.py
```

For non-interactive commands, prefer:

```powershell
conda run -n glimpse python -m pytest tests/unit -v
conda run -n glimpse python -m py_compile main.py container.py
```

The project is developed on Windows with a Tauri/Vue desktop shell and a Python API backend. The configured Python is expected to be `Python 3.10.x` inside the `glimpse` environment.

## Documentation Placement

- Put durable product, architecture, workflow, API-boundary, and testing
  documentation under `docs/`. Keep the active set small and link it from
  `docs/README.md`.
- Keep short, durable AI working rules in this `AGENTS.md`. Put detailed
  reusable agent context under `docs/agents/`, starting from
  `docs/agents/README.md`.
- Put one-off analysis, generated reports, render output, prompts, and session
  scratch files under the project-root `.tmp/` or the system temp directory.
  Delete them when the task ends; never place them in `docs/` or in the parent
  workspace directory.
- Keep tool indexes and caches such as `.codegraph/` at the project root and
  out of Git.
- Do not create documentation in `E:\project\Glimpse\`; the repository root is
  `E:\project\Glimpse\Glimpse\`.
- Before adding a new document, prefer updating an existing source of truth.
  Archive superseded historical material under `docs/archive/` and label it
  clearly.

## Runtime Entry Points

- `main.py`: default source launcher. Loads `.env`, points Tauri at the current Python interpreter, and starts the Vue + Tauri desktop shell.
- `main_legacy_qt.py`: legacy PySide6 desktop entry kept for fallback/debugging.
- `main_api.py`: FastAPI backend entry used by the Tauri shell and browser development flow.
- `container.py`: service registry and lifecycle owner. Add shared services here instead of constructing them ad hoc from UI code.
- `glimpse-frontend/`: Vue 3 + Tauri desktop frontend.
- `ui/main_window.py`: legacy Qt desktop experience, memory list, search box, screenshot actions, tray/window behavior.
- `ui/settings_dialog.py`: legacy Qt settings dialog, including AI, OCR, screenshot, cluster, and hotkeys.

## Core Flow

1. Screenshot is captured by `core/capture.py`.
2. Cluster mode, if enabled, buffers multiple screenshots in `core/cluster_buffer.py`.
3. `services/memory_service.py` runs local OCR before optional AI summarization;
   without AI credentials it falls back to the recognized text.
4. `db/sqlite_manager.py` first stores the fact record with `PENDING` sync status,
   including summary text, recognized text, metadata, and FTS data.
5. `services/memory_service.py` embeds the summary plus recognized text,
   `db/chroma_manager.py` writes the derived vector index, and SQLite records
   `SYNCED` or `FAILED`.
6. `services/search_service.py` combines text search (FTS with substring
   fallback) and semantic results.
7. UI renders list/detail state, reacts to WebSocket updates, and hides
   placeholder app names such as empty strings or `unknown`.

OCR is enabled before AI summarization through the injected `OCREngine`.
`services/ocr_engine.py` uses RapidOCR 3.9.2 with the bundled
PP-OCRv6-small detection/recognition models and ONNX Runtime CPU. OCR failures
must not prevent a memory from being saved. Historical rows are processed only
through the manual maintenance backfill; never add automatic startup backfill.

## Important Conventions

- Settings live in `GlimpseData/config/settings.json` and are managed by `config/settings_manager.py`.
- Paths should come from `config/path_manager.py`; avoid writing generated data beside source files.
- Global hotkeys are handled by `services/keyboard_manager.py`; settings dialogs should not let saved global hotkeys fire while editing shortcuts.
- `Escape` clears search in the main window. It is not a configurable global hotkey.
- AI providers are OpenAI-compatible. Provider/base URL/model/timeout settings belong under the `ai` settings section.
- Chinese search needs fallback behavior because SQLite FTS does not tokenize Chinese reliably.

## What To Ignore

These are intentionally ignored or should remain untracked:

- `.omo/`
- `docs/superpowers/`
- `.codex/`, `.opencode/`, `.cursor/`, `.windsurf/`
- prompt scratch files and one-off AI helper scripts
- `.tmp/` and tool indexes such as `.codegraph/`
- runtime data under `GlimpseData/`

Keep `AGENTS.md` tracked. It is the one generic document meant for the next AI session.

## Testing

默认只做与当前改动直接相关的最小验证，不自动运行全量测试。细小的视觉、间距、
颜色或文案调整无需测试；前端改动以确认受影响页面能够渲染、显示无明显错误为主，
只有涉及组件行为、状态逻辑或构建链路时才补充直接相关的检查。后端改动只运行受影响
模块的最小单元或 API 测试，必要时再补充直接相关的集成检查。完整测试套件、完整前端
测试或安装包验证仅在用户明确要求时运行。交付时说明实际运行和跳过的验证。

按上述边界选择改动范围内的 focused tests。Useful defaults:

```powershell
conda run -n glimpse python -m pytest tests/unit/config/test_settings_manager.py tests/unit/services/test_keyboard_manager.py -v
conda run -n glimpse python -m pytest tests/unit/services/test_ai_client.py tests/unit/services/test_ocr_engine.py tests/unit/core/test_capture.py -v
conda run -n glimpse python -m pytest tests/unit -v
```

When touching Qt UI, also run the app manually in the `glimpse` environment and check the affected workflow.

## Git Hygiene

- Keep commits functional and small.
- Existing style: English type before the colon, Chinese subject after it, for example `fix: 修复快捷键监听与应用名占位显示`.
- Do not rewrite or discard user changes unless explicitly asked.
- If removing tracked AI artifacts, use `git rm --cached` so local scratch files are not deleted.

## Release Completion

- A formal release is not complete when the tag, Workflow, or installer build merely succeeds.
- After the GitHub Release exists, follow the post-release procedure in `docs/RELEASE.md` and replace the generated notes via `gh release edit vX.Y.Z --notes-file ...`.
- For a formal release, build the notes from the previous formal tag through the current formal tag; intervening preview releases may be used as reference, but do not change that range. For a preview release, use the nearest preceding formal or preview tag through the current preview tag. Keep only user-visible results, use the three Chinese sections, keep each item to one sentence of at most 30 Chinese characters, and include the compare link.
- Read the Release back from GitHub and verify its body, release status, installer, and checksum before reporting the release complete.



以暗猜接口为耻，以认真查阅为荣
以模糊执行为耻，以寻求确认为荣
以盲想业务为耻，以人类确认为荣
以创造接口为耻，以复用现有为荣
以跳过验证为耻，以主动测试为荣
以破坏架构为耻，以遵循规范为荣
以假装理解为耻，以诚实无知为菜
以盲目修改为耻，以谨慎重构为荣

Shame in guessing APIs, Honor in careful research.
Shame in vague execution, Honor in seeking confirmation.
Shame in assuming business logic, Honor in human verification.
Shame in creating interfaces, Honor in reusing existing ones.
Shame in skipping validation, Honor in proactive testing.
Shame in breaking architecture, Honor in following specifications.
Shame in pretending to understand, Honor in honest ignorance.
Shame in blind modification, Honor in careful refactoring.

