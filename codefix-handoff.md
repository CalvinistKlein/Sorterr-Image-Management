# Sorterr — Codefix Handoff

Complete audit of all bugs found, fixed, and remaining across the codebase.

---

## Bugs Fixed — Previous Session

### 🔴 Critical — Fixed

| # | File | Bug | Impact | Fix |
|---|------|-----|--------|-----|
| 1 | `main.py` | Duplication bug – `move_image` collision handler created `_1` copies when re-opening a folder with already-sorted files. | File count inflation, Darktable losing files, ordering scrambled. | Replaced entire metadata system with SQLite DB using content fingerprinting. `UNIQUE(fingerprint, folder)` constraint makes duplication impossible. |
| 2 | `main.py` | Undo action name mismatch (`category.lower()` → `'picks'`/`'rejects'`). | Undo could silently fail. | Normalized to explicit `'pick'`/`'reject'`. |
| 3 | `main.py` | `restore_image` queried old_folder **after** the physical move. | Undo logging could record wrong `old_folder`. | Moved fingerprint + DB query to **before** `shutil.move()`. |
| 4 | `main.py` | `reconcile_folder` clobbered concurrent edits with blanket UPDATE. | Ratings/colors lost in rare race condition. | Added change-detection: only UPDATE if filename or folder actually differs. |
| 5 | `main.py` | Duplicate-across-folders silently dropped from flat dict. | Data loss — sorted files could appear unsorted. | Collect all occurrences, prefer sorted folder (`Picks > Rejects > root`). |
| 6 | `main.py` | Precache thread overlap on rapid folder switches. | Progress bar shows wrong values, CPU waste. | Set `cache_progress['running'] = False` before starting new thread. |
| 7 | `app.js` | Rapid pick/reject race condition — no re-entry guard on `handleAction`. | Double-moves, stale path references. | Added `actionInProgress` flag with try/finally guard. |

### 🟡 Moderate — Fixed

| # | File | Bug | Impact | Fix |
|---|------|-----|--------|-----|
| 8 | `app.js` | `removeRecent()` undefined — called but never implemented. | Clicking ✕ on a recent project entry crashes with `ReferenceError`. | Implemented the function. |
| 9 | `app.js` | Undefined variable `dc` in split/grid counter display. | `ReferenceError` crash in split or grid layout. | Replaced with `endIdx = Math.min(currentIndex + layoutSize, filteredImages.length)`. |
| 10 | `app.js` | Progress shows 100% too early due to `Math.round()`. | User confusion — thinks done when ~5 images remain. | Changed to `.toFixed(2)` for fractional display. |
| 11 | `index.html` | Preload slider never persisted — JS expected `preload-count-input` but HTML had `preload-count-label`. | Preload count always reset to 3. | Changed to `<input type="number" id="preload-count-input">`. |
| 12 | `style.css` | `.small-input` class never defined — number inputs unstyled. | Settings modal looked broken. | Added `.small-input` with proper styling. |
| 13 | `app.js` | `catch` without parameter — breaks on older browsers/engines. | Compatibility issue. | Changed to `catch(e) { … }`. |

---

## Bugs Fixed — This Session

### Previously Documented as "Remaining" — Verified Fixed

These bugs were listed as unfixed in the prior handoff but were already resolved in the codebase. Confirmed and closed:

| # | Bug | Status | Evidence |
|---|-----|--------|----------|
| R2 | Flask/Eel hardcoded to port 8081/8080 | ✅ **Fixed** | `find_open_port()` at `main.py:47-55` dynamically finds available ports 8080–8099. |
| R5 | XMP sidecar written with string replacement, not XML parser | ✅ **Fixed** | `write_xmp_sidecar()` at `main.py:282-354` uses `xml.etree.ElementTree` with proper namespace handling and graceful fallback on parse errors. |
| R6 | No debounce on star rating/color tag | ✅ **Fixed** | `ratingDebounceTimer` and `colorDebounceTimer` with 250ms debounce at `app.js:597-636`. |
| R7 | Preload cache eviction is FIFO, not LRU | ✅ **Fixed** | `preloadUrl()` at `app.js:23-43` evicts the entry **furthest from currentIndex**, not the oldest. |
| R8 | `open_image` always uses `half_size=True` | ✅ **Fixed** | `RAW_HALF_SIZE` is now a configurable global toggled by the "High Quality RAW Preview" checkbox in Settings. `set_raw_half_size()` at `main.py:586-589`. |
| R10 | DB connections accumulate and are never closed | ✅ **Fixed** | `release_folder_dbs()` at `main.py:73-82` closes all connections for the old root, called from `set_current_folder()` at `main.py:572-573`. |

### Newly Fixed in This Session

| # | File | Bug | Impact | Fix |
|---|------|-----|--------|-----|
| R9 | `app.js` / `main.py` | **Settings stored only in localStorage** — clearing browser cache wipes all keybinds, preload count, grouping thresholds, RAW quality preference. | User preferences lost on cache clear. | Added `save_settings()` / `load_settings()` eel-exposed functions that persist to `.sorterr_settings.json` in the project folder. Frontend calls `persistSettings()` on every settings change (dual-write to localStorage + server). Settings are loaded from server when opening a folder. |
| N1 | `app.js:722` | **Filter button null reference crash** — `document.querySelector('.filter-btn.active').classList.remove('active')` throws if no filter button has the `active` class. | TypeError crash when clicking filter buttons in edge cases. | Added optional chaining: `?.classList.remove('active')`. |
| N2 | `main.py:501-528` | **On-the-fly thumbnails not cached to disk** — `serve_thumb` generated thumbnails into a BytesIO buffer but never wrote them to the cache directory. Repeat requests regenerated from scratch until the background precache thread caught up. | Unnecessary CPU/memory waste, slower thumbnail loading for uncached images. | Changed to use `generate_thumb_to_file()` which saves to disk cache, then serves with `send_file()`. |
| N3 | `main.py` & `app.js` | **Identity Bug via Filename** — `set_star_rating` and `set_color_tag` queried by filename, which isn't unique across folders. | Metadata applied to the wrong file if duplicate filenames existed. | Changed frontend to track images by `fingerprint` and passed `fingerprint` to Eel backend calls instead of `filename`. |
| N4 | `main.py` & `app.js` | **RAW Quality Cache Staleness** — Toggling "High Quality RAW Preview" didn't clear the disk cache. | Setting change had no apparent effect on already-viewed images. | Added `clear_cache()` Python function and an interactive confirmation prompt when toggling the setting to dynamically wipe cache. |
| N5 | `index.html` & `app.js` | **Empty Folder Welcome Trap** — Opening a completely empty folder showed the initial "Welcome" screen. | Confusing UX. | Separated `#welcome-screen` from `#empty-folder-screen` and updated routing logic in `applyFilters`. |
| N6 | `main.py` | **Background Precache Race Condition** — Thread didn't check if file still existed before attempting thumbnail generation. | Precache thread could crash with `FileNotFoundError` if user moved an image while it was queued. | Added `os.path.exists()` check in thread loop to gracefully skip moved files and adjust progress counters. |

---

## Known Remaining Issues

### 🟢 All Previously Known Bugs Are Now Fixed

No critical or moderate bugs remain in the codebase. The items below are **enhancement opportunities**, not bugs:

| # | Category | Description | Priority |
|---|----------|-------------|----------|
| E1 | Performance | `reconcile_folder` fingerprints every file on every call (~145MB I/O for 2274 CR3s). Could cache fingerprints by `(filename, mtime, size)` triple. | Low |
| E2 | UX | Recent projects list stored in localStorage only (not in server-side settings). Could be lost on cache clear. | Low |
| E3 | Performance | Preload cache eviction does O(n×m) `findIndex` scan. Could use a reverse index map for O(1) lookups. | Low |

---

## Architecture Notes for Next Developer

### Data Flow

```
User opens folder
    → set_current_folder(path)
        → release_folder_dbs(old_root)  # Close old DB connections
        → init_db(root)                 # Create/open .sorterr.db
        → _migrate_legacy_json()        # One-time JSON→SQLite import
    → loadServerSettings()              # Load .sorterr_settings.json
    → get_image_list()
        → reconcile_folder(root)        # Scan disk, fingerprint, sync DB
        → background_precache()         # Thumbnail generation thread

User picks/rejects
    → move_image(filename, path, category)
        → fingerprint_file()            # Identify the file
        → DB dedup check                # Already in target? → no-op
        → shutil.move()                 # Physical move
        → UPDATE files SET folder       # DB tracks new location
        → INSERT actions                # Undo history
        → write_xmp_sidecar()           # Darktable/Lightroom sync (via ElementTree)
        → return {path, filename}       # Dict for frontend

User changes settings
    → persistSettings()
        → localStorage (immediate fallback)
        → eel.save_settings() → .sorterr_settings.json (durable)

User presses Ctrl+Z
    → undo_last_action()
        → SELECT last pick/reject from actions
        → restore_image()
        → DELETE from actions
```

### Files Modified

| File | Changes | What Changed |
|------|---------|-------------|
| `main.py` | +45 lines | `save_settings()`, `clear_cache()`, `serve_thumb` persistence, `fingerprint` identity tracking, precache thread race fix. |
| `web/app.js` | +65 lines | Server-side settings logic, `fingerprint` object matching, UI caching controls, empty folder UX split. |
| `web/index.html` | +4 lines | Added `#empty-folder-screen` separate from welcome screen. |

---

*Generated on 2026-05-12 by Antigravity.*
