# Cluster Screenshot Feature Plan

## Wave 1 (Parallel - No Dependencies)

### Task 1: DB Schema & Record Update
- File: db/sqlite_manager.py
- Add `extra_images TEXT` column to `memories` table (ALTER TABLE or CREATE TABLE IF NOT EXISTS with new schema + migration check)
- Update `MemoryRecord` dataclass with `extra_images: Optional[str] = None`
- Update `from_row`, `insert_memory` to handle the new field
- QA: DB initializes without errors

### Task 2: AIClient analyze_images
- File: services/ai_client.py
- Add `analyze_images(image_paths: List[str], prompt: str, stream_callback=None)` 
- Build content array with multiple `image_url` entries before text prompt
- QA: Constructs valid OpenAI payload with N images

### Task 3: Settings Schema Expansion
- File: config/settings_manager.py
- Add `cluster` section with `cluster_mode`, `cluster_auto_submit`, `cluster_max_images`, `cluster_timeout`
- Add validation `_validate_cluster`
- Add `cluster` to `SETTINGS_SCHEMA`
- QA: Defaults load correctly

### Task 4: CaptureManager Debounce Bypass
- File: core/capture.py
- Add `force_bypass_debounce: bool = False` to `capture_fullscreen`
- Skip cooldown check when True
- QA: Bypass works

## Wave 2 (Parallel - Depends on Wave 1)

### Task 5: ClusterBuffer Service (core/cluster_buffer.py)
- QObject with QTimer, state machine (IDLE, COLLECTING)
- Methods: add_image, flush, discard
- Signals: flushed(list), discarded(), state_changed(str, int, int)
- Auto-flush on timeout or max images

### Task 6: MemoryService Cluster Support (services/memory_service.py)
- Add `create_cluster_memory_async(image_paths, app_name, ...)`
- OCR all images, call `analyze_images`, save with extra_images JSON

### Task 7: SettingsDialog UI Update (ui/settings_dialog.py)
- New tab: 集群模式
- Controls: toggle (master), toggle (auto submit), spinbox (max 1-10), spinbox (timeout 1-10s)

## Wave 3

### Task 8: Container Registration (container.py)
- Register ClusterBuffer singleton with SettingsManager injection

## Wave 4

### Task 9: MainWindow Integration (ui/main_window.py)
- Route screenshots through ClusterBuffer when cluster_mode ON
- Status bar: show collected count, countdown, [立即提交] [取消] buttons
- Bypass debounce for cluster member screenshots
- Connect flush to create_cluster_memory_async

## Wave 5

### Task 10: Testing
- test_cluster_buffer.py (state machine)
- Integration test for full cluster pipeline
