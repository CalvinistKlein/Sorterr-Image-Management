let allImages = [];
let filteredImages = [];
let currentIndex = 0;
let currentFilter = 'All';
let currentSort = 'time';
let currentDir = '';
let pickerPath = '';
let currentLayout = 'single';
let layoutSize = 1;
let timeGroupingActive = false;
let burstGroupingActive = false;
let actionInProgress = false;
let flaskPort = 8081;

// Browser-side image preload cache
const preloadCache = new Map();
let PRELOAD_AHEAD = parseInt(localStorage.getItem('sorterr_preload_ahead') || '3', 10);
const PRELOAD_BEHIND = 1;
let SMART_COLLECT_GAP = parseInt(localStorage.getItem('sorterr_smart_gap') || '10', 10);
let BURST_GAP = parseFloat(localStorage.getItem('sorterr_burst_gap') || '1.0');
let BURST_MIN_COUNT = parseInt(localStorage.getItem('sorterr_burst_min_count') || '3', 10);

function preloadUrl(url) {
    if (!url || preloadCache.has(url)) return;
    const img = new Image();
    img.src = url;
    preloadCache.set(url, img);
    // Evict entries based on distance to currentIndex if cache grows too large
    if (preloadCache.size > 20) {
        let furthestKey = null;
        let maxDist = -1;
        for (const [key, value] of preloadCache.entries()) {
            const idx = filteredImages.findIndex(img => key.includes(encodeURIComponent(img.path)));
            if (idx === -1) {
                preloadCache.delete(key);
                return;
            }
            const dist = Math.abs(idx - currentIndex);
            if (dist > maxDist) { maxDist = dist; furthestKey = key; }
        }
        if (furthestKey) preloadCache.delete(furthestKey);
    }
}

function preloadAdjacent(centerIndex) {
    for (let offset = -PRELOAD_BEHIND; offset <= PRELOAD_AHEAD; offset++) {
        const idx = centerIndex + offset;
        if (idx >= 0 && idx < filteredImages.length) {
            const url = `http://localhost:${flaskPort}/image?path=${encodeURIComponent(filteredImages[idx].path)}`;
            preloadUrl(url);
        }
    }
}

// Keybinds State
const defaultKeybinds = {
    prevImage: ['arrowleft', 'a'],
    nextImage: ['arrowright', 'd'],
    pick: ['arrowup', 'w'],
    reject: ['arrowdown', 's'],
    prevLayout: ['q'],
    nextLayout: ['e'],
    openPicker: ['o'],
    reloadFolder: ['r']
};
// Clone default to handle missing keys defensively over time
let keybinds = { ...defaultKeybinds };
try {
    const saved = JSON.parse(localStorage.getItem('sorterr_keybinds'));
    if (saved) keybinds = { ...defaultKeybinds, ...saved };
} catch (e) { console.error("Could not load setting", e); }
let activeKeybindAction = null;

// UI Elements
const previewContainer = document.getElementById('image-grid');
const mainImages = [
    document.getElementById('main-image-0'), document.getElementById('main-image-1'),
    document.getElementById('main-image-2'), document.getElementById('main-image-3')
];
const thumbnailsTrack = document.getElementById('thumbnails-track');
const filenameLabel = document.getElementById('filename');
const counterLabel = document.getElementById('counter');
const statusTag = document.getElementById('status-tag');
const currentDirLabel = document.getElementById('current-dir-label');
const actionOverlay = document.getElementById('action-overlay');
const actionText = document.getElementById('action-text');
const noImages = document.getElementById('no-images');

const stars = document.querySelectorAll('.star');
const colorDots = document.querySelectorAll('.color-dot');
const layoutBtns = document.querySelectorAll('.layout-btn');
const timeGroupingBtn = document.getElementById('time-grouping-btn');
const burstGroupingBtn = document.getElementById('burst-grouping-btn');

const settingsModal = document.getElementById('settings-modal');
const keybindInputs = document.querySelectorAll('.keybind-input');

async function init() {
    console.log("Initializing Sorterr...");
    try { flaskPort = await eel.get_flask_port()(); } catch(e) { console.error("Could not get Flask port", e); }
    // Don't auto-load — show empty state until user picks a folder
    noImages.classList.remove('hidden');
    previewContainer.classList.add('hidden');
    document.getElementById('welcome-screen').classList.remove('hidden');
    document.getElementById('empty-folder-screen').classList.add('hidden');
    renderKeybindsUI();
    renderRecentProjects();
}

// Server-side settings persistence (R9 fix)
async function loadServerSettings() {
    try {
        const settings = await eel.load_settings()();
        if (settings) {
            if (settings.keybinds) { keybinds = { ...defaultKeybinds, ...settings.keybinds }; renderKeybindsUI(); }
            if (settings.preload_ahead !== undefined) { PRELOAD_AHEAD = settings.preload_ahead; }
            if (settings.smart_gap !== undefined) { SMART_COLLECT_GAP = settings.smart_gap; }
            if (settings.burst_gap !== undefined) { BURST_GAP = settings.burst_gap; }
            if (settings.burst_min_count !== undefined) { BURST_MIN_COUNT = settings.burst_min_count; }
            if (settings.raw_quality !== undefined) { rawQualityCheckbox.checked = settings.raw_quality; eel.set_raw_half_size(!settings.raw_quality)(); }
            // Sync UI sliders/inputs
            const syncUI = (sliderId, inputId, val) => {
                const s = document.getElementById(sliderId); const i = document.getElementById(inputId);
                if (s) s.value = val; if (i) i.value = val;
            };
            syncUI('preload-count-slider', 'preload-count-input', PRELOAD_AHEAD);
            syncUI('smart-gap-slider', 'smart-gap-input', SMART_COLLECT_GAP);
            syncUI('burst-window-slider', 'burst-window-input', BURST_GAP);
            syncUI('burst-count-slider', 'burst-count-input', BURST_MIN_COUNT);
        }
    } catch(e) { console.error("Could not load server settings", e); }
}

function persistSettings() {
    const settings = {
        keybinds: keybinds,
        preload_ahead: PRELOAD_AHEAD,
        smart_gap: SMART_COLLECT_GAP,
        burst_gap: BURST_GAP,
        burst_min_count: BURST_MIN_COUNT,
        raw_quality: rawQualityCheckbox.checked
    };
    // Save to both localStorage (immediate) and server (durable)
    localStorage.setItem('sorterr_keybinds', JSON.stringify(keybinds));
    localStorage.setItem('sorterr_preload_ahead', PRELOAD_AHEAD);
    localStorage.setItem('sorterr_smart_gap', SMART_COLLECT_GAP);
    localStorage.setItem('sorterr_burst_gap', BURST_GAP);
    localStorage.setItem('sorterr_burst_min_count', BURST_MIN_COUNT);
    localStorage.setItem('sorterr_raw_quality', rawQualityCheckbox.checked);
    try { eel.save_settings(settings)(); } catch(e) { /* server may not be ready yet */ }
}

// Recent Projects
const MAX_RECENTS = 8;
function getRecents() {
    try { return JSON.parse(localStorage.getItem('sorterr_recents') || '[]'); }
    catch(e) { return []; }
}
function saveRecents(list) { localStorage.setItem('sorterr_recents', JSON.stringify(list)); }

function addRecent(folderPath) {
    let recents = getRecents().filter(r => r.path !== folderPath);
    recents.unshift({ path: folderPath, date: new Date().toLocaleDateString() });
    if (recents.length > MAX_RECENTS) recents = recents.slice(0, MAX_RECENTS);
    saveRecents(recents);
    renderRecentProjects();
}

function clearRecents() {
    if (confirm("Clear all recent project history?")) {
        localStorage.removeItem('sorterr_recents');
        renderRecentProjects();
    }
}

function removeRecent(path) {
    let recents = getRecents().filter(r => r.path !== path);
    saveRecents(recents);
    renderRecentProjects();
}

function renderRecentProjects() {
    const list = document.getElementById('recent-projects-list');
    const noMsg = document.getElementById('no-recents-msg');
    const clearBtn = document.getElementById('clear-recents-btn');
    const recents = getRecents();
    list.innerHTML = '';
    
    if (recents.length === 0) { 
        noMsg.style.display = ''; 
        clearBtn.classList.add('hidden');
        return; 
    }
    
    noMsg.style.display = 'none';
    clearBtn.classList.remove('hidden');
    clearBtn.onclick = clearRecents;

    recents.forEach(r => {
        const item = document.createElement('div');
        item.className = 'recent-item';
        // Show just the folder name prominently, full path as title
        const name = r.path.split(/[\/\\]/).filter(Boolean).pop();
        item.title = r.path;
        // Bug #10 fix: build via DOM to avoid XSS from folder paths
        const icon = document.createElement('span');
        icon.style.fontSize = '1rem'; icon.textContent = '📁';
        const pathDiv = document.createElement('div');
        pathDiv.className = 'recent-item-path';
        pathDiv.textContent = name;
        const sub = document.createElement('span');
        sub.style.cssText = 'font-size:0.7rem;color:var(--text-secondary)';
        sub.textContent = r.path;
        pathDiv.appendChild(document.createElement('br'));
        pathDiv.appendChild(sub);
        const dateSpan = document.createElement('span');
        dateSpan.className = 'recent-item-date'; dateSpan.textContent = r.date;
        const removeBtn = document.createElement('button');
        removeBtn.className = 'recent-item-remove'; removeBtn.title = 'Remove from recents'; removeBtn.textContent = '✕';
        item.append(icon, pathDiv, dateSpan, removeBtn);
        item.querySelector('.recent-item-remove').onclick = (e) => {
            e.stopPropagation();
            removeRecent(r.path);
        };
        item.onclick = () => openRecentFolder(r.path);
        list.appendChild(item);
    });
}

async function openRecentFolder(folderPath) {
    const confirmed = await eel.set_current_folder(folderPath)();
    if (confirmed) {
        currentDir = confirmed;
        currentDirLabel.textContent = currentDir;
        pickerPath = currentDir;
        currentIndex = 0;
        await loadServerSettings();
        loadImages();
        addRecent(confirmed);
    } else {
        alert(`Folder not found: ${folderPath}`);
        removeRecent(folderPath);
    }
}

async function loadImages() {
    allImages = await eel.get_image_list()();
    applyFilters();
    pollCacheProgress();
}

async function pollCacheProgress() {
    const cacheGroup = document.getElementById('cache-group');
    const cacheBar = document.getElementById('cache-bar');
    const cacheLabel = document.getElementById('cache-label');

    // Short initial delay to let the background thread initialise
    await new Promise(r => setTimeout(r, 200));

    const tick = async () => {
        const p = await eel.get_cache_progress()();
        if (!p || p.total === 0) { cacheGroup.style.display = 'none'; return; }

        const needsGen = p.total - (p.pre_cached || 0);

        if (needsGen === 0 && !p.running) {
            // All images were already cached from a previous session
            cacheGroup.style.display = '';
            cacheBar.style.width = '100%';
            cacheLabel.textContent = `✓ ${p.total} loaded from cache`;
            setTimeout(() => { cacheGroup.style.display = 'none'; }, 2500);
            return;
        }

        const pct = Math.round((p.done / p.total) * 100);
        cacheGroup.style.display = '';
        cacheBar.style.width = pct + '%';
        cacheLabel.textContent = `${p.done} / ${p.total} (${pct}%)`;

        if (p.running) {
            setTimeout(tick, 400);
        } else {
            cacheLabel.textContent = `✓ ${p.total} cached`;
            setTimeout(() => { cacheGroup.style.display = 'none'; }, 3000);
        }
    };
    tick();
}

// Picker
async function openPicker() { 
    const selectedFolder = await eel.open_system_folder_dialog()();
    if (selectedFolder) {
        const confirmed = await eel.set_current_folder(selectedFolder)();
        if (confirmed) {
            currentDir = confirmed;
            currentDirLabel.textContent = currentDir;
            pickerPath = currentDir;
            currentIndex = 0;
            await loadServerSettings();
            loadImages();
            addRecent(confirmed);
        } else {
            alert('⚠ Could not open folder — check permissions.');
        }
    }
}
async function confirmFolder() { /* Deprecated */ }
function closePicker() { /* Deprecated */ }

// Settings & Keybinds
function openSettings() { settingsModal.classList.remove('hidden'); }
function closeSettings() { 
    settingsModal.classList.add('hidden'); 
    activeKeybindAction = null;
    renderKeybindsUI();
}
function saveKeybinds() { persistSettings(); }

function formatKeyText(k) {
    if (k.startsWith('arrow')) return k.replace('arrow', '');
    if (k === ' ') return 'Space';
    return k;
}

function renderKeybindsUI() {
    keybindInputs.forEach(btn => {
        const action = btn.dataset.action;
        if (keybinds[action] && keybinds[action].length > 0) {
            btn.textContent = keybinds[action].map(formatKeyText).join(', ').toUpperCase();
        } else {
            btn.textContent = 'UNBOUND';
        }
        btn.classList.remove('listening');
    });
}

keybindInputs.forEach(btn => {
    btn.onclick = () => {
        renderKeybindsUI(); // reset others
        activeKeybindAction = btn.dataset.action;
        btn.textContent = "Press Key...";
        btn.classList.add('listening');
    };
});

document.getElementById('reset-keybinds-btn').onclick = () => {
    keybinds = { ...defaultKeybinds };
    saveKeybinds();
    renderKeybindsUI();
};

// Helper for Bi-directional sync between Slider and Number Input
function setupSyncGroup(sliderId, inputId, storageKey, isFloat, initialValue, onUpdate) {
    const slider = document.getElementById(sliderId);
    const input = document.getElementById(inputId);
    if (!slider || !input) return;

    // Set initial values
    slider.value = initialValue;
    input.value = initialValue;

    const update = (val) => {
        const parsed = isFloat ? parseFloat(val) : parseInt(val, 10);
        slider.value = parsed;
        input.value = parsed;
        localStorage.setItem(storageKey, parsed);
        onUpdate(parsed);
    };

    slider.oninput = (e) => update(e.target.value);
    input.onchange = (e) => update(e.target.value);
}

// Initialize Sync Groups
setupSyncGroup('preload-count-slider', 'preload-count-input', 'sorterr_preload_ahead', false, PRELOAD_AHEAD, (val) => {
    PRELOAD_AHEAD = val;
    persistSettings();
});

setupSyncGroup('smart-gap-slider', 'smart-gap-input', 'sorterr_smart_gap', false, SMART_COLLECT_GAP, (val) => {
    SMART_COLLECT_GAP = val;
    if (timeGroupingActive) renderThumbnails();
    persistSettings();
});

setupSyncGroup('burst-window-slider', 'burst-window-input', 'sorterr_burst_gap', true, BURST_GAP, (val) => {
    BURST_GAP = val;
    if (burstGroupingActive) renderThumbnails();
    persistSettings();
});

setupSyncGroup('burst-count-slider', 'burst-count-input', 'sorterr_burst_min_count', false, BURST_MIN_COUNT, (val) => {
    BURST_MIN_COUNT = val;
    if (burstGroupingActive) renderThumbnails();
    persistSettings();
});

const rawQualityCheckbox = document.getElementById('raw-quality-checkbox');
const storedRawQuality = localStorage.getItem('sorterr_raw_quality');
if (storedRawQuality !== null) {
    rawQualityCheckbox.checked = storedRawQuality === 'true';
}
eel.set_raw_half_size(!rawQualityCheckbox.checked)();

rawQualityCheckbox.addEventListener('change', async (e) => {
    const isHighQuality = e.target.checked;
    eel.set_raw_half_size(!isHighQuality)();
    persistSettings();
    if (confirm("Clear cache to apply this quality change to already-viewed images? (May take a moment to regenerate previews)")) {
        await eel.clear_cache()();
        preloadCache.clear();
        if (currentDir) loadImages();
    }
});

// Filters & Sort
function applyFilters() {
    if (currentFilter === 'All') filteredImages = [...allImages];
    else filteredImages = allImages.filter(img => img.status === currentFilter);

    if (timeGroupingActive || burstGroupingActive) { currentSort = 'time'; document.getElementById('sort-order').value = 'time'; }

    if (currentSort === 'name') filteredImages.sort((a, b) => a.filename.localeCompare(b.filename));
    else if (currentSort === 'rating') filteredImages.sort((a, b) => b.rating - a.rating);
    else if (currentSort === 'time') filteredImages.sort((a, b) => a.timestamp - b.timestamp);

    renderThumbnails();
    
    if (filteredImages.length === 0) {
        noImages.classList.remove('hidden');
        previewContainer.classList.add('hidden');
        if (currentDir) {
            document.getElementById('welcome-screen').classList.add('hidden');
            document.getElementById('empty-folder-screen').classList.remove('hidden');
        }
        filenameLabel.textContent = '-';
        counterLabel.textContent = '0 / 0';
        updateUIForImage(null);
    } else {
        noImages.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        if (currentIndex >= filteredImages.length) currentIndex = 0;
        loadImageGroup(currentIndex);
    }
}

function getIndicatorHtml(img) {
    let statusClass = 'unsorted';
    if (img.status === 'Pick') statusClass = 'pick';
    else if (img.status === 'Reject') statusClass = 'reject';

    let colorHtml = '';
    if (img.color && img.color !== 'None') {
        colorHtml = `<div class="color-tag-indicator ${img.color.toLowerCase()}">${img.color}</div>`;
    }

    let starsHtml = '';
    if (img.rating > 0) {
        starsHtml = `<div class="stars-rank-indicator">${'★'.repeat(img.rating)}</div>`;
    }

    return {
        status: `<div class="status-circle ${statusClass}"></div>`,
        color: colorHtml,
        stars: starsHtml
    };
}

function updateIndicatorsForImage(index) {
    if (index < 0 || index >= filteredImages.length) return;
    const img = filteredImages[index];
    const indicators = getIndicatorHtml(img);

    // Update thumbnail
    const thumb = document.getElementById(`thumb-${index}`);
    if (thumb) {
        thumb.querySelector('.status-indicator-overlay').innerHTML = indicators.status;
        thumb.querySelector('.color-indicator-overlay').innerHTML = indicators.color;
        thumb.querySelector('.stars-indicator-overlay').innerHTML = indicators.stars;
    }

    // Update main preview if it's currently showing this image
    // Find which wrap is showing this index
    for (let i = 0; i < layoutSize; i++) {
        if (currentIndex + i === index) {
            const wrapper = mainImages[i].parentElement;
            wrapper.querySelector('.status-indicator-overlay').innerHTML = indicators.status;
            wrapper.querySelector('.color-indicator-overlay').innerHTML = indicators.color;
            wrapper.querySelector('.stars-indicator-overlay').innerHTML = indicators.stars;
        }
    }
}

function renderThumbnails() {
    thumbnailsTrack.innerHTML = '';
    
    // Pre-calculate burst clusters for Min Count filtering
    const burstMap = new Map(); // filename -> groupSize
    if (burstGroupingActive) {
        let currentCluster = [];
        for (let i = 0; i < filteredImages.length; i++) {
            const img = filteredImages[i];
            const prevImg = filteredImages[i-1];
            const gap = prevImg ? img.timestamp - prevImg.timestamp : Infinity;
            
            if (gap <= BURST_GAP) {
                currentCluster.push(img.filename);
            } else {
                if (currentCluster.length >= BURST_MIN_COUNT) {
                    currentCluster.forEach(fn => burstMap.set(fn, currentCluster.length));
                }
                currentCluster = [img.filename];
            }
        }
        if (currentCluster.length >= BURST_MIN_COUNT) {
            currentCluster.forEach(fn => burstMap.set(fn, currentCluster.length));
        }
    }

    let lastTime = null;
    filteredImages.forEach((img, index) => {
        const gap = (lastTime !== null) ? img.timestamp - lastTime : null;

        // High-priority: Time Grouping Divider (Scene Change - Yellow)
        if (timeGroupingActive && gap !== null && (gap > SMART_COLLECT_GAP)) {
            const divider = document.createElement('div');
            divider.className = 'group-divider time-group';
            thumbnailsTrack.appendChild(divider);
        } 
        
        // Secondary: Burst Grouping Divider (Blue)
        // Only show if both photos are part of a valid burst sequence (meets MIN_COUNT)
        if (burstGroupingActive && gap !== null && (gap <= BURST_GAP) && burstMap.has(img.filename)) {
            const divider = document.createElement('div');
            divider.className = 'group-divider burst-group';
            thumbnailsTrack.appendChild(divider);
        }
        
        lastTime = img.timestamp;
        
        const item = document.createElement('div');
        item.className = 'thumbnail-item'; item.id = `thumb-${index}`;
        item.setAttribute('data-color', img.color);
        item.onclick = () => loadImageGroup(index);
        
        const thumbImg = document.createElement('img');
        thumbImg.loading = 'lazy';
        thumbImg.src = `http://localhost:${flaskPort}/thumb?path=${encodeURIComponent(img.path)}`;
        item.appendChild(thumbImg);

        const indicators = getIndicatorHtml(img);
        
        const statusOverlay = document.createElement('div');
        statusOverlay.className = 'status-indicator-overlay top-right';
        statusOverlay.innerHTML = indicators.status;
        item.appendChild(statusOverlay);

        const colorOverlay = document.createElement('div');
        colorOverlay.className = 'color-indicator-overlay bottom-left';
        colorOverlay.innerHTML = indicators.color;
        item.appendChild(colorOverlay);

        const starsOverlay = document.createElement('div');
        starsOverlay.className = 'stars-indicator-overlay bottom-right';
        starsOverlay.innerHTML = indicators.stars;
        item.appendChild(starsOverlay);

        thumbnailsTrack.appendChild(item);
    });
}

async function loadImageGroup(index) {
    if (index < 0 || index >= filteredImages.length) return;
    document.querySelectorAll('.thumbnail-item.active').forEach(el => el.classList.remove('active'));
    currentIndex = index;

    for (let i = 0; i < 4; i++) {
        const targetIndex = currentIndex + i;
        if (i < layoutSize && targetIndex < filteredImages.length) {
            const currentImg = filteredImages[targetIndex];
            const newThumb = document.getElementById(`thumb-${targetIndex}`);
            if (newThumb) {
                newThumb.classList.add('active');
                if (i === 0) newThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }
            const url = `http://localhost:${flaskPort}/image?path=${encodeURIComponent(currentImg.path)}`;
            // If preloaded and complete, swap instantly; otherwise assign and let browser load
            const cached = preloadCache.get(url);
            if (cached && cached.complete && cached.naturalWidth > 0) {
                mainImages[i].src = cached.src;
            } else {
                mainImages[i].src = url;
            }
            mainImages[i].parentElement.style.visibility = 'visible';

            // Update indicators for preview
            const indicators = getIndicatorHtml(currentImg);
            const wrapper = mainImages[i].parentElement;
            wrapper.querySelector('.status-indicator-overlay').innerHTML = indicators.status;
            wrapper.querySelector('.color-indicator-overlay').innerHTML = indicators.color;
            wrapper.querySelector('.stars-indicator-overlay').innerHTML = indicators.stars;

            if (i === 0) updateUIForImage(currentImg);
        } else {
            mainImages[i].src = '';
            mainImages[i].parentElement.style.visibility = 'hidden';
        }
    }
    // Preload neighbours in background
    preloadAdjacent(currentIndex);
}

function updateLayout(layout) {
    currentLayout = layout;
    layoutBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.layout === layout));
    previewContainer.className = `layout-${layout}`;
    if (layout === 'single') layoutSize = 1; else if (layout === 'split') layoutSize = 2; else layoutSize = 4;
    loadImageGroup(currentIndex);
}

// Data Updates
async function updateUIForImage(img) {
    if (!img) {
        updateStars(0); updateColorDot('None');
        // Bug #15 fix: reset all stale text labels
        filenameLabel.textContent = '-';
        statusTag.textContent = '-';
        counterLabel.textContent = '0 / 0';
        document.getElementById('exif-camera').textContent = '-';
        document.getElementById('exif-settings').textContent = '-';
        document.getElementById('exif-date').textContent = '-';
        return;
    }
    filenameLabel.textContent = img.filename; statusTag.textContent = img.status;
    const pct = (((currentIndex + 1) / filteredImages.length) * 100).toFixed(2);
    const endIdx = Math.min(currentIndex + layoutSize, filteredImages.length);
    counterLabel.textContent = layoutSize === 1 ? `${currentIndex + 1} / ${filteredImages.length} (${pct}%)` : `${currentIndex + 1}-${endIdx} / ${filteredImages.length} (${pct}%)`;
    updateSortingProgress();
    
    updateStars(img.rating); updateColorDot(img.color);
    
    const exif = await eel.get_exif(img.path)();
    if (exif) {
        document.getElementById('exif-camera').textContent = `${exif.Make || ''} ${exif.Model || ''}`.trim() || 'Unknown';
        document.getElementById('exif-settings').textContent = `${exif.FNumber ? `f/${exif.FNumber}` : ''} ${exif.ExposureTime ? `${exif.ExposureTime}s` : ''} ${exif.ISOSpeedRatings ? `ISO${exif.ISOSpeedRatings}` : ''} ${exif.FocalLength ? `${exif.FocalLength}mm` : ''}`.trim() || 'No Data';
        document.getElementById('exif-date').textContent = exif.DateTimeOriginal || 'No Data';
    } else {
        document.getElementById('exif-camera').textContent = 'No Data';
        document.getElementById('exif-settings').textContent = 'No Data';
        document.getElementById('exif-date').textContent = 'No Data';
    }
}

function updateStars(rating) { stars.forEach(s => s.classList.toggle('active', parseInt(s.dataset.value) <= rating)); }
function updateColorDot(color) { colorDots.forEach(d => d.classList.toggle('active', d.dataset.color === color)); }

let ratingDebounceTimer = null;
async function setRating(rating) {
    if (filteredImages.length === 0) return;
    const img = filteredImages[currentIndex];
    const newRating = img.rating === rating ? 0 : rating;
    
    // Optimistic UI update
    img.rating = newRating; updateStars(newRating);
    const master = allImages.find(i => i.fingerprint === img.fingerprint); if (master) master.rating = newRating;
    updateIndicatorsForImage(currentIndex);
    
    // Capture values now — closure must not reference stale `img` after navigation
    const targetFingerprint = img.fingerprint;
    const targetRating = newRating;
    clearTimeout(ratingDebounceTimer);
    ratingDebounceTimer = setTimeout(async () => {
        await eel.set_star_rating(targetFingerprint, targetRating)();
    }, 250);
}

let colorDebounceTimer = null;
async function setColor(color) {
    if (filteredImages.length === 0) return;
    const img = filteredImages[currentIndex];
    
    // Optimistic UI update
    img.color = color; updateColorDot(color);
    const master = allImages.find(i => i.fingerprint === img.fingerprint); if (master) master.color = color;
    const thumb = document.getElementById(`thumb-${currentIndex}`);
    if (thumb) thumb.setAttribute('data-color', color);
    updateIndicatorsForImage(currentIndex);
    
    // Capture values now
    const targetFingerprint = img.fingerprint;
    const targetColor = color;
    clearTimeout(colorDebounceTimer);
    colorDebounceTimer = setTimeout(async () => {
        await eel.set_color_tag(targetFingerprint, targetColor)();
    }, 250);
}

async function handleRestore() {
    if (actionInProgress || filteredImages.length === 0) return;
    const img = filteredImages[currentIndex];
    if (img.status === 'Unsorted') return;
    actionInProgress = true;
    try {
        const oldUrl = `http://localhost:${flaskPort}/image?path=${encodeURIComponent(img.path)}`;
        const newPath = await eel.restore_image(img.filename, img.path)();
        if (newPath) {
            preloadCache.delete(oldUrl);
            showFeedback('RESTORED');
            img.path = newPath; img.status = 'Unsorted';
            const master = allImages.find(i => i.fingerprint === img.fingerprint);
            if (master) { master.path = newPath; master.status = 'Unsorted'; }
            applyFilters();
            updateSortingProgress();
        }
    } finally { actionInProgress = false; }
}

async function handleAction(category) {
    if (actionInProgress || filteredImages.length === 0) return;
    const img = filteredImages[currentIndex];
    actionInProgress = true;
    try {
        const oldUrl = `http://localhost:${flaskPort}/image?path=${encodeURIComponent(img.path)}`;
        const result = await eel.move_image(img.filename, img.path, category)();
        if (result) {
            preloadCache.delete(oldUrl);
            showFeedback(category === 'Picks' ? 'PICKED' : 'REJECTED');
            const oldFilename = img.filename;
            img.path = result.path;
            img.filename = result.filename;
            img.status = category === 'Picks' ? 'Pick' : 'Reject';
            const master = allImages.find(i => i.fingerprint === img.fingerprint);
            if (master) { master.path = result.path; master.filename = result.filename; master.status = img.status; }
            if (currentIndex < filteredImages.length - 1) currentIndex++;
            applyFilters();
            updateSortingProgress();
        }
    } finally { actionInProgress = false; }
}

async function handleUndo() {
    if (actionInProgress) return;
    actionInProgress = true;
    try {
        const result = await eel.undo_last_action()();
        if (result) {
            showFeedback('UNDONE');
            await loadImages();
            updateSortingProgress();
        } else {
            showFeedback('NOTHING TO UNDO');
        }
    } finally { actionInProgress = false; }
}

function updateSortingProgress() {
    const total = allImages.length;
    const sorted = allImages.filter(img => img.status !== 'Unsorted').length;
    const pct = total > 0 ? ((sorted / total) * 100).toFixed(2) : '0.00';
    const el = document.getElementById('sort-progress');
    if (el) el.textContent = `${sorted} / ${total} (${pct}%)`;
}
function showFeedback(text) { actionOverlay.classList.remove('hidden'); actionText.textContent = text; setTimeout(() => actionOverlay.classList.add('hidden'), 500); }

// Event Listeners
document.getElementById('open-picker-btn').onclick = openPicker;
document.getElementById('welcome-open-btn').onclick = openPicker;
document.getElementById('viewer-pick-btn').onclick = () => handleAction('Picks');
document.getElementById('viewer-reject-btn').onclick = () => handleAction('Rejects');
document.getElementById('viewer-restore-btn').onclick = handleRestore;
document.getElementById('settings-btn').onclick = openSettings;
document.getElementById('close-settings-btn').onclick = closeSettings;

document.getElementById('prev-img-btn').onclick = () => { if (currentIndex > 0) loadImageGroup(Math.max(0, currentIndex - layoutSize)); };
document.getElementById('next-img-btn').onclick = () => { if (currentIndex + layoutSize < filteredImages.length) loadImageGroup(currentIndex + layoutSize); };

document.getElementById('scroll-left-btn').onclick = () => thumbnailsTrack.scrollBy({ left: -200, behavior: 'smooth' });
document.getElementById('scroll-right-btn').onclick = () => thumbnailsTrack.scrollBy({ left: 200, behavior: 'smooth' });
document.getElementById('reload-folder-btn').onclick = () => { if (currentDir) loadImages(); };

// Touch Swiping Support (Issue #24)
let touchStartX = 0;
let touchEndX = 0;

previewContainer.addEventListener('touchstart', e => {
    touchStartX = e.changedTouches[0].screenX;
}, { passive: true });

previewContainer.addEventListener('touchend', e => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
}, { passive: true });

function handleSwipe() {
    const swipeThreshold = 50;
    const diff = touchEndX - touchStartX;
    if (Math.abs(diff) < swipeThreshold) return;

    if (diff > 0) {
        // Swipe Right -> Previous
        if (currentIndex > 0) loadImageGroup(Math.max(0, currentIndex - layoutSize));
    } else {
        // Swipe Left -> Next
        if (currentIndex + layoutSize < filteredImages.length) loadImageGroup(currentIndex + layoutSize);
    }
}

document.querySelectorAll('.filter-btn:not(#smart-collection-btn):not(#reset-keybinds-btn)').forEach(btn => {
    btn.onclick = () => {
        document.querySelector('.filter-btn.active')?.classList.remove('active');
        btn.classList.add('active'); currentFilter = btn.dataset.filter; currentIndex = 0; applyFilters();
    };
});

document.getElementById('sort-order').onchange = (e) => { currentSort = e.target.value; timeGroupingActive = false; burstGroupingActive = false; timeGroupingBtn.classList.remove('active'); burstGroupingBtn.classList.remove('active'); applyFilters(); };
timeGroupingBtn.onclick = () => { timeGroupingActive = !timeGroupingActive; timeGroupingBtn.classList.toggle('active', timeGroupingActive); applyFilters(); };
burstGroupingBtn.onclick = () => { burstGroupingActive = !burstGroupingActive; burstGroupingBtn.classList.toggle('active', burstGroupingActive); applyFilters(); };
layoutBtns.forEach(btn => btn.onclick = () => updateLayout(btn.dataset.layout));
stars.forEach(s => s.onclick = () => setRating(parseInt(s.dataset.value)));
colorDots.forEach(d => d.onclick = () => setColor(d.dataset.color));

document.addEventListener('keydown', (e) => {
    const key = e.key.toLowerCase();
    
    // Remapper Mode Interception
    if (activeKeybindAction) {
        e.preventDefault();
        if (key === 'escape') {
            activeKeybindAction = null;
            renderKeybindsUI();
            return;
        }
        keybinds[activeKeybindAction] = [key]; // Override with new key
        saveKeybinds();
        activeKeybindAction = null;
        renderKeybindsUI();
        return;
    }

    // Modal close handling
    if (!settingsModal.classList.contains('hidden')) { if (key === 'escape') closeSettings(); return; }

    // Ctrl+Z / Cmd+Z: Undo last action
    if ((e.ctrlKey || e.metaKey) && key === 'z') {
        e.preventDefault();
        handleUndo();
        return;
    }

    // Alt+Up/Down: undo pick/reject (restore to unsorted)
    if (e.altKey && filteredImages.length > 0) {
        if (e.key === 'ArrowUp') { e.preventDefault(); if (filteredImages[currentIndex]?.status === 'Pick') handleRestore(); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); if (filteredImages[currentIndex]?.status === 'Reject') handleRestore(); return; }
    }

    // Dynamic keybind matches
    if (keybinds.openPicker.includes(key)) { openPicker(); return; }
    if (keybinds.reloadFolder.includes(key)) { if (currentDir) loadImages(); return; }
    if (filteredImages.length === 0) return;
    
    if (keybinds.prevImage.includes(key)) { if (currentIndex > 0) loadImageGroup(Math.max(0, currentIndex - layoutSize)); return; }
    if (keybinds.nextImage.includes(key)) { if (currentIndex + layoutSize < filteredImages.length) loadImageGroup(currentIndex + layoutSize); return; }
    if (keybinds.pick.includes(key)) { handleAction('Picks'); return; }
    if (keybinds.reject.includes(key)) { handleAction('Rejects'); return; }
    
    if (keybinds.prevLayout.includes(key)) {
        const layoutList = ['single', 'split', 'grid'];
        const cycleIdx = layoutList.indexOf(currentLayout);
        if (cycleIdx > 0) updateLayout(layoutList[cycleIdx - 1]);
        return;
    }
    if (keybinds.nextLayout.includes(key)) {
        const layoutList = ['single', 'split', 'grid'];
        const cycleIdx = layoutList.indexOf(currentLayout);
        if (cycleIdx < 2) updateLayout(layoutList[cycleIdx + 1]);
        return;
    }

    // Fixed keys
    if (e.key >= '1' && e.key <= '5') { setRating(parseInt(e.key)); return; }
    const colorMap = {'6':'Red', '7':'Yellow', '8':'Green', '9':'Blue', '0':'Purple', '`':'None'};
    if (colorMap[e.key]) { setColor(colorMap[e.key]); return; }
});

init();
