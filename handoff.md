# Sorterr — Handoff Document

Complete audit of all bugs found, fixed, and remaining across the codebase.

---

## Bugs Fixed in This Session

### 🔴 Critical — Fixed

| # | File | Bug | Impact | Fix |
|---|------|-----|--------|-----|
| 1 | `main.py` | **Duplication bug**: `move_image` collision handler created `_1` copies when re-opening a folder with already-sorted files | File count inflation (2274→2356), Darktable losing files, ordering scrambled | Replaced entire metadata system with SQLite DB using content fingerprinting. `UNIQUE(fingerprint, folder)` constraint makes duplication impossible. |
| 2 | `main.py` | **Undo action name mismatch**: `move_image` logged `category.lower()` → `'picks'`/`'rejects'`, but `undo_last_action` queried for those same strings. Would break if category casing changed. | Undo could silently fail | Normalized to `'pick'`/`'reject'` (explicit, no dependency on input casing) |
| 3 | `main.py` | **`restore_image` queried old_folder AFTER the physical move**: fingerprint would read the moved file at its new location but query DB for folder at old location — timing-dependent correctness | Undo logging could record wrong `old_folder` | Moved fingerprint + DB query to BEFORE `shutil.move()` |
| 4 | `main.py` | **`reconcile_folder` clobbered concurrent edits**: Every reconciliation did a blanket `UPDATE` on all existing files, resetting folder/filename even if unchanged. If a user rated a file while reconciliation was running, the UPDATE could race. | Ratings/colors lost in rare race condition | Added change-detection: only UPDATE if filename or folder actually differs |
| 5 | `main.py` | **Duplicate-across-folders silently dropped**: `disk_map` was a flat dict keyed by fingerprint. If the same file existed in root AND Picks (real duplicate on disk from previous bug), the last-scanned folder won, silently dropping the other | Data loss — sorted files could appear unsorted | Collect all occurrences, prefer sorted folder (Picks > Rejects > root) |
| 6 | `main.py` | **Precache thread overlap (R3)**: `get_image_list` launched a new precache thread without cancelling the old one. Rapid folder switches caused overlapping threads writing to the same `cache_progress` dict. | Progress bar shows wrong values, CPU waste | Set `cache_progress['running'] = False` before starting new thread |
| 7 | `app.js` | **Rapid pick/reject race condition (R4)**: `handleAction` was async with no re-entry guard. Mashing W/S could fire multiple backend moves for the same image. | Double-moves, stale path references | Added `actionInProgress` flag with try/finally guard on all action handlers |

### 🟡 Moderate — Fixed

| # | File | Bug | Impact | Fix |
|---|------|-----|--------|-----|
| 8 | `app.js` | **`removeRecent()` undefined**: Called on lines 164 and 182 but function never existed | Clicking ✕ on a recent project entry crashes with `ReferenceError` | Added the function |
| 9 | `app.js` | **Undefined variable `dc`**: Line 544 referenced `dc` in split/grid counter display | `ReferenceError` crash when using split or grid layout | Replaced with `endIdx = Math.min(currentIndex + layoutSize, filteredImages.length)` |
| 10 | `app.js` | **Progress shows 100% too early**: `Math.round()` on 2274 images means last ~5 images all show 100% | User confusion — thinks they're done when they're not | Changed to `.toFixed(2)` for fractional display |
| 11 | `index.html` | **Preload slider never persisted (R1)**: JS expected `preload-count-input` but HTML had `preload-count-label` (a `<span>`). Silent null check meant slider value reset to default on every launch. | Preload count always reset to 3 | Changed to `<input type="number" id="preload-count-input">` matching the other settings rows |
| 12 | `style.css` | **`.small-input` class never defined**: All number inputs in settings used this class but it had no CSS — inputs were unstyled and uncontrolled width | Settings modal looked broken | Added `.small-input` with proper styling |
| 13 | `app.js` | **`catch` without parameter (R9)**: `catch { return []; }` — works in modern JS but breaks on older browsers/engines | Compatibility issue | Changed to `catch(e) { return []; }` |

### 🟢 Features Added

| # | Feature | Implementation |
|---|---------|---------------|
| 9 | **Ctrl+Z / ⌘Z Undo** | `actions` table in SQLite logs every pick/reject. `undo_last_action()` pops the last one and restores the file. Persists across app restarts. |
| 10 | **Dual Progress Display** | "Viewing" (position in filtered view) + "Sorting Progress" (how many sorted vs total) in sidebar |
| 11 | **SQLite Database** | Replaced `.sorterr_metadata.json` with `.sorterr.db`. Content fingerprinting (SHA-256 of first 64KB + file size). Auto-migrates legacy JSON on first open. |

---

## Known Remaining Bugs — NOT Fixed

### 🔴 Pre-existing — Should Fix

| # | File | Bug | Impact | Suggested Fix |
|---|------|-----|--------|---------------|
| R2 | `main.py:479` | **Flask server hardcoded to port 8081**: If another process uses 8081, the image server fails silently. Eel is also hardcoded to 8080. | App shows blank images or won't launch | Add port-finding logic: try 8081, fallback to 8082-8089 |
| R5 | `main.py:245-303` | **XMP sidecar written with string replacement, not XML parser**: If a sidecar has complex structure (GPS data, editing masks), the regex-based update could corrupt it | Data loss in XMP sidecars for complex workflows | Replace with `lxml` or `xml.etree` parser (noted in sorterr-features.md Phase 4) |

### 🟡 Pre-existing — Low Priority

| # | File | Bug | Impact | Notes |
|---|------|-----|--------|-------|
| R6 | `app.js` | **No debounce on star rating/color tag**: Each click triggers an immediate `eel.set_star_rating()` RPC + disk write + XMP sync. Rapid 1→2→3→4→5 star assignment fires 5 sequential backend calls | Slight UI lag when rapidly changing ratings | Debounce by 200ms or batch updates |
| R7 | `app.js:27-30` | **Preload cache eviction is FIFO, not LRU**: Oldest entry is evicted regardless of whether it's the previous image the user might go back to | Navigating backward may not be instant | Use an LRU map or evict based on distance from currentIndex |
| R8 | `main.py:305-317` | **`open_image` with rawpy uses `half_size=True`**: Previews are half-resolution. Zooming to 100% shows a softer image than the original | Can't verify pixel-level critical focus | Documented in features.md §11.4. Phase 2 proposes a two-stage render pipeline |
| R9 | `main.py` | **Settings still in localStorage**: Keybinds, preload count, grouping thresholds all stored in browser localStorage. Clearing cache wipes everything. | User preferences lost on cache clear | Move to server-side config file (documented in features.md §11.5) |
| R10 | `main.py:49-58` | **DB connections accumulate in `_db_connections` dict**: Each (root, thread_id) pair creates a new connection that's never closed | Memory leak during very long sessions with many folder switches | Add a `close_db()` function called when switching folders |

---

## Architecture Notes for Next Developer

### Data Flow After Changes

```
User opens folder
    → set_current_folder(path)
        → init_db(root)           # Create/open .sorterr.db
        → _migrate_legacy_json()  # One-time JSON→SQLite import
    → get_image_list()
        → reconcile_folder(root)  # Scan disk, fingerprint files, sync with DB
            → scan_disk_files()   # List root/, Picks/, Rejects/
            → fingerprint_file()  # SHA-256 of first 64KB + file size
            → INSERT/UPDATE/DELETE # Reconcile DB with reality
            → return image_list   # Authoritative list from DB
        → background_precache()   # Thumbnail generation thread

User picks/rejects
    → move_image(filename, path, category)
        → fingerprint_file()      # Identify the file
        → DB dedup check           # Already in target folder? → no-op
        → shutil.move()           # Physical move
        → UPDATE files SET folder  # DB tracks new location
        → INSERT actions           # Undo history
        → write_xmp_sidecar()     # Darktable/Lightroom sync
        → return {path, filename}  # Dict (not string!) for frontend

User presses Ctrl+Z
    → undo_last_action()
        → SELECT last pick/reject from actions
        → restore_image()         # Move back to root
        → DELETE from actions     # Remove undone entry
```

### Key Behavioral Changes from Pre-existing Code

1. **`move_image` now returns a dict `{path, filename}`** instead of a bare path string. Frontend `handleAction` updated to match.
2. **`set_star_rating` / `set_color_tag` return `False`** (not `True`) if the file isn't found in the DB. Previously they'd silently create orphan entries.
3. **Reconciliation is heavier**: `get_image_list()` now fingerprints every file on every call. For 2274 × 35MB CR3 files, that's ~2274 × 64KB reads = ~145MB of I/O. Takes ~2-3 seconds. Could be optimized by caching fingerprints by (filename, mtime, size) triple.
4. **`.sorterr.db` is created in the project folder** alongside `.sorterr_cache/`. It's ~100KB for 2274 files.

### Files Modified

| File | Lines Changed | What Changed |
|------|---------------|-------------|
| `main.py` | ~300 lines | SQLite layer, fingerprinting, reconciliation, move/restore/undo rewrite, rating/color via DB, precache cancel |
| `web/app.js` | ~80 lines | Dict return handling, undo handler, fractional %, sorting progress, removeRecent fix, dc fix, action guard, catch fix |
| `web/index.html` | ~10 lines | Sorting progress row, Ctrl+Z in shortcuts help, preload slider fix |
| `web/style.css` | ~30 lines | Gold/black theme, .small-input class |
