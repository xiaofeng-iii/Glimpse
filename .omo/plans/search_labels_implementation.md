# Search Labels Implementation Plan

## Goal
Implement the accepted search result source labeling and filtering design for Glimpse.
Users should be able to run one combined search and understand why each memory matched:
- OCR/text match badge: `[OCR]`
- Semantic/vector match badge: `[语义]`
- Both sources matched: `[OCR][语义]`

The search toolbar should also expose source filtering:
- `综合结果` (hybrid combined results)
- `仅看 OCR` (text/OCR results only)
- `仅看语义` (vector/semantic results only)

## Scope
Expected code areas:
- `db/sqlite_manager.py`
- `services/search_service.py`
- `ui/main_window.py`
- `tests/unit/services/test_search_service.py`

Do not add new runtime dependencies.

## TODOs
1. [ ] Add non-persistent `match_sources` metadata to `MemoryRecord` in `db/sqlite_manager.py` - expect search results can carry `OCR` and/or `语义` labels without DB schema changes
2. [ ] Extend `SearchService.search()` with `source_filter` support in `services/search_service.py` - expect `all`, `ocr`, and `semantic` modes to route to hybrid/text/vector searches correctly
3. [ ] Annotate hybrid/text/vector search results with source badges in `services/search_service.py` - expect hybrid merged records to contain `match_sources` reflecting actual source membership
4. [ ] Add search source filter UI in `MainWindow` in `ui/main_window.py` - expect combo box options `综合结果`, `仅看 OCR`, `仅看语义` near the search input and search refresh on change
5. [ ] Render source badge prefixes in memory list rows in `ui/main_window.py` - expect rows show `[OCR]`, `[语义]`, or `[OCR][语义]` before timestamp only when `match_sources` is present
6. [ ] Add/update tests for source filters and badge metadata in `tests/unit/services/test_search_service.py` - expect tests cover hybrid both-source labels, OCR-only filter, semantic-only filter, and empty-query no-badge behavior

## Acceptance Criteria
- Search results returned from `SearchService.search(query, source_filter="all")` include accurate `match_sources` metadata.
- `source_filter="ocr"` returns OCR/text matches only and labels them `OCR`.
- `source_filter="semantic"` returns semantic/vector matches only and labels them `语义`.
- Empty search/recent memories do not show any badge prefix.
- Main window includes source filter choices: `综合结果`, `仅看 OCR`, `仅看语义`.
- Changing the source filter refreshes search results immediately.
- Memory list rows use text prefixes exactly: `[OCR]`, `[语义]`, `[OCR][语义]`.
- Existing search behavior remains backward compatible for callers that do not pass `source_filter`.

## Verification Commands
Run from `5.25Glimpse/` using the project conda environment:
```powershell
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/services/test_search_service.py -q
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit -q
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests -x -q
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m py_compile db/sqlite_manager.py services/search_service.py ui/main_window.py
```

## Implementation Notes
- Prefer `field(default_factory=list)` for `MemoryRecord.match_sources` so the list is safe per record.
- `match_sources` is runtime metadata only; do not persist it or alter SQLite tables.
- Preserve existing search limit behavior.
- Prefer stable internal filter values: `all`, `ocr`, `semantic`.
- UI display labels should remain Chinese-friendly: `综合结果`, `仅看 OCR`, `仅看语义`.
- Use `getattr(memory, "match_sources", [])` when rendering for backward compatibility with mocks or older objects.
- If vector search is unavailable and hybrid falls back to text, returned records should carry `OCR` only.

## Final Verification Wave
F1. [x] Oracle review: verify implementation matches accepted design and labels exactly — VERDICT: APPROVE
F2. [x] Code-quality review: verify minimal scope, no schema churn, no duplicated merge logic issues — VERDICT: APPROVE
F3. [x] Test review: verify meaningful tests cover source metadata and UI rendering/filter behavior — VERDICT: APPROVE
F4. [x] Hands-on QA review: run app/search flow or targeted UI verification and confirm badges/filter refresh work — VERDICT: APPROVE
