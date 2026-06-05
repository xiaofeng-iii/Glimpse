# Glimpse AI Session Guide

This file is the shared starting point for new AI coding sessions. Keep it short, factual, and durable. Temporary plans, prompts, tool notes, and session scratch files should stay out of Git.

## Product In One Sentence

Glimpse is a desktop memory assistant: a user captures the screen, the app summarizes visual meaning, stores the result locally, and lets the user search those memories later.

## First Principles

- Preserve the current local-memory pipeline: capture -> AI summary -> embedding -> SQLite + ChromaDB -> search/UI.
- Keep user data local by default. Runtime data belongs under `GlimpseData/`, not in the repo.
- Prefer dependency injection through `container.get(...)`. Avoid introducing new module-level global instances.
- Treat UI, services, storage, and capture as separate layers. Cross layers through existing services/signals instead of shortcut imports.
- Make behavior robust when AI credentials are missing. Search/browse should still work with saved data.
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
3. `services/memory_service.py` orchestrates AI summary, embeddings, and persistence.
4. `db/sqlite_manager.py` stores memory metadata, summary text, optional recognized text, and FTS search data.
5. `db/chroma_manager.py` stores vector-search data.
6. `services/search_service.py` combines exact and semantic search results.
7. UI renders list/detail state and hides placeholder app names such as empty strings or `unknown`.

OCR engine code still exists in `services/ocr_engine.py` and is registered in `container.py`, but the current `MemoryService` implementation does not call it. If OCR is re-enabled, update this guide and the relevant memory-service tests together.

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
- `.codex/`, `.opencode/`, `.cursor/`, `.windsurf/`, `.claude/`
- prompt scratch files and one-off AI helper scripts
- runtime data under `GlimpseData/`

Keep `AGENTS.md` tracked. It is the one generic document meant for the next AI session.

## Testing

Run focused tests for the area you changed. Useful defaults:

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
