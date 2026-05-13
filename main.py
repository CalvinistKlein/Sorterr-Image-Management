import re
import eel
import os
import sys
import shutil
import json
import sqlite3
import hashlib
from PIL import Image, ExifTags
import base64
from io import BytesIO
from datetime import datetime
import threading
import socket
import xml.etree.ElementTree as ET
from flask import Flask, request, Response, send_file
import exifread
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

# Configuration
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp', '.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.cr3'}
RAW_EXTENSIONS = {'.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.cr3'}
THUMBNAIL_SIZE = (200, 200)
PREVIEW_SIZE = (1920, 1080)
LEGACY_METADATA_FILENAME = '.sorterr_metadata.json'
DB_FILENAME = '.sorterr.db'
CACHE_DIR_NAME = '.sorterr_cache'
SETTINGS_FILENAME = '.sorterr_settings.json'

# Global state
VERSION = "3.0"
current_root = os.getcwd()
cache_progress = {'total': 0, 'done': 0, 'pre_cached': 0, 'running': False}
current_run_id = 0
_db_connections = {}  # root -> sqlite3.Connection
_db_lock = threading.Lock()
RAW_HALF_SIZE = True

def find_open_port(start_port, max_port=8099):
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return start_port

FLASK_PORT = find_open_port(8081)
EEL_PORT = find_open_port(8080)

# ─── SQLite Database Layer ───────────────────────────────────────────

def get_db_path(root):
    return os.path.join(root, DB_FILENAME)

def get_db(root):
    """Get or create a thread-safe SQLite connection for the given root."""
    tid = threading.current_thread().ident
    key = (root, tid)
    if key not in _db_connections:
        conn = sqlite3.connect(get_db_path(root), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')  # Safe for concurrent reads
        _db_connections[key] = conn
    return _db_connections[key]

def release_folder_dbs(root):
    """Close and release all SQLite connections for a given folder."""
    with _db_lock:
        to_delete = [k for k in _db_connections.keys() if k[0] == root]
        for k in to_delete:
            try:
                _db_connections[k].close()
            except Exception:
                pass
            del _db_connections[k]

def init_db(root):
    """Create tables if they don't exist, and migrate from legacy JSON if needed."""
    db = get_db(root)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            filename    TEXT NOT NULL,
            folder      TEXT NOT NULL DEFAULT '',
            rating      INTEGER DEFAULT 0,
            color       TEXT DEFAULT 'None',
            timestamp   REAL DEFAULT 0,
            file_size   INTEGER DEFAULT 0,
            first_seen  TEXT,
            UNIQUE(fingerprint, folder)
        );
        CREATE TABLE IF NOT EXISTS actions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            action      TEXT NOT NULL,
            old_folder  TEXT,
            new_folder  TEXT,
            old_value   TEXT,
            new_value   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_files_fingerprint ON files(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder);
    ''')
    db.commit()
    _migrate_legacy_json(root, db)

def _migrate_legacy_json(root, db):
    """One-time migration from .sorterr_metadata.json to SQLite."""
    json_path = os.path.join(root, LEGACY_METADATA_FILENAME)
    if not os.path.exists(json_path):
        return
    # Only migrate if DB is empty
    count = db.execute('SELECT COUNT(*) FROM files').fetchone()[0]
    if count > 0:
        return
    try:
        with open(json_path, 'r') as f:
            legacy = json.load(f)
        print(f"Migrating {len(legacy)} entries from legacy JSON to SQLite...")
        # We'll match these by filename during the reconciliation pass
        # Store them temporarily so reconcile_folder can apply them
        db.execute('CREATE TABLE IF NOT EXISTS _legacy_import (filename TEXT PRIMARY KEY, rating INTEGER, color TEXT, timestamp REAL)')
        for fname, mdata in legacy.items():
            db.execute('INSERT OR IGNORE INTO _legacy_import (filename, rating, color, timestamp) VALUES (?,?,?,?)',
                      (fname, mdata.get('rating', 0), mdata.get('color', 'None'), mdata.get('timestamp', 0)))
        db.commit()
        print("Legacy migration staged. Will apply during folder reconciliation.")
    except Exception as e:
        print(f"Legacy migration error: {e}")

def fingerprint_file(filepath):
    """Fast content fingerprint: SHA-256 of first 64KB + file size.
    ~1ms per file even on 35MB CR3s. Unique for camera output files."""
    h = hashlib.sha256()
    try:
        size = os.path.getsize(filepath)
        h.update(str(size).encode())
        # Include filename in hash to prevent collisions if size + header match
        h.update(os.path.basename(filepath).encode())
        with open(filepath, 'rb') as f:
            h.update(f.read(65536))
        return h.hexdigest()
    except Exception as e:
        print(f"Fingerprint error for {filepath}: {e}")
        return None

def scan_disk_files(root):
    """Scan root, Picks/, Rejects/ and return list of (path, folder, filename)."""
    results = []
    folders = [('', 'Unsorted'), ('Picks', 'Pick'), ('Rejects', 'Reject')]
    for folder, _status in folders:
        folder_full = os.path.join(root, folder) if folder else root
        if not os.path.exists(folder_full):
            continue
        try:
            for f in os.listdir(folder_full):
                if f.startswith('.') or f.startswith('._'):
                    continue
                full_path = os.path.join(folder_full, f)
                if os.path.isfile(full_path) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                    # folder key: '' for root, 'Picks', 'Rejects'
                    folder_key = folder if folder else ''
                    results.append((full_path, folder_key, f))
        except PermissionError:
            continue
    return results

def reconcile_folder(root):
    """Sync disk state with DB. Returns the authoritative image list."""
    db = get_db(root)
    disk_files = scan_disk_files(root)

    # Fingerprint all disk files
    # A file may exist in multiple folders (true disk duplicate).
    # Collect ALL occurrences, then pick the best one per fingerprint.
    disk_all = {}  # fingerprint -> list of (path, folder, filename)
    for path, folder, filename in disk_files:
        fp = fingerprint_file(path)
        if fp:
            if fp not in disk_all:
                disk_all[fp] = []
            disk_all[fp].append((path, folder, filename))

    # Prefer the sorted folder (Picks/Rejects) over root — that's the user's intent
    folder_priority = {'Picks': 0, 'Rejects': 1, '': 2}
    disk_map = {}  # fingerprint -> (path, folder, filename) — best occurrence
    for fp, occurrences in disk_all.items():
        occurrences.sort(key=lambda x: folder_priority.get(x[1], 99))
        disk_map[fp] = occurrences[0]

    # Get existing DB fingerprints
    db_rows = {row['fingerprint']: dict(row) for row in db.execute('SELECT * FROM files')}

    # Check for legacy import data
    has_legacy = False
    legacy_data = {}
    try:
        for row in db.execute('SELECT * FROM _legacy_import'):
            legacy_data[row['filename']] = dict(row)
        has_legacy = True
    except Exception:
        pass

    # Insert new files
    for fp, (path, folder, filename) in disk_map.items():
        if fp not in db_rows:
            exif_data, timestamp = extract_exif(path)
            rating = 0
            color = 'None'
            # Apply legacy metadata if available
            if has_legacy and filename in legacy_data:
                rating = legacy_data[filename].get('rating', 0) or 0
                color = legacy_data[filename].get('color', 'None') or 'None'
                ts = legacy_data[filename].get('timestamp', 0)
                if ts and ts > 0:
                    timestamp = ts
            try:
                db.execute(
                    'INSERT INTO files (fingerprint, filename, folder, rating, color, timestamp, file_size, first_seen) VALUES (?,?,?,?,?,?,?,?)',
                    (fp, filename, folder, rating, color, timestamp, os.path.getsize(path), datetime.now().isoformat())
                )
            except sqlite3.IntegrityError:
                # UNIQUE constraint — file already in this folder, skip
                pass

    # Update existing files only if folder/filename changed (avoid clobbering concurrent edits)
    for fp, (path, folder, filename) in disk_map.items():
        if fp in db_rows:
            old = db_rows[fp]
            if old['filename'] != filename or old['folder'] != folder:
                db.execute('UPDATE files SET filename=?, folder=? WHERE fingerprint=?',
                          (filename, folder, fp))

    # Prune files no longer on disk
    disk_fps = set(disk_map.keys())
    for fp in set(db_rows.keys()) - disk_fps:
        db.execute('DELETE FROM files WHERE fingerprint=?', (fp,))

    # Clean up legacy import table if it exists
    if has_legacy:
        try:
            db.execute('DROP TABLE IF EXISTS _legacy_import')
        except Exception:
            pass

    db.commit()

    # Return the authoritative list
    folder_status = {'': 'Unsorted', 'Picks': 'Pick', 'Rejects': 'Reject'}
    image_list = []
    for row in db.execute('SELECT * FROM files ORDER BY timestamp'):
        r = dict(row)
        folder_key = r['folder']
        folder_path = os.path.join(root, folder_key) if folder_key else root
        r['path'] = os.path.join(folder_path, r['filename'])
        r['status'] = folder_status.get(folder_key, 'Unsorted')
        image_list.append(r)
    return image_list

# ─── Cache helpers ───────────────────────────────────────────────────

def get_cache_dir(root):
    return os.path.join(root, CACHE_DIR_NAME)

def get_thumb_cache_path(root, filename):
    return os.path.join(get_cache_dir(root), 'thumbs', filename + '.jpg')

def get_preview_cache_path(root, filename):
    return os.path.join(get_cache_dir(root), 'previews', filename + '.jpg')

def ensure_cache_dirs(root):
    os.makedirs(os.path.join(get_cache_dir(root), 'thumbs'), exist_ok=True)
    os.makedirs(os.path.join(get_cache_dir(root), 'previews'), exist_ok=True)

def write_xmp_sidecar(image_path, rating, color):
    """Write or surgically update an XMP sidecar with rating and color label using ElementTree."""
    base = os.path.splitext(image_path)[0]
    sidecars = [base + ".xmp", image_path + ".xmp"]
    
    xmp_label = color if color != "None" else ""
    color_map = {"Red": 1, "Yellow": 2, "Green": 3, "Blue": 4, "Purple": 5}
    urgency = color_map.get(color, 0)
    
    # Register namespaces
    ET.register_namespace("x", "adobe:ns:meta/")
    ET.register_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    ET.register_namespace("xmp", "http://ns.adobe.com/xap/1.0/")
    ET.register_namespace("photoshop", "http://ns.adobe.com/photoshop/1.0/")

    ns = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'xmp': 'http://ns.adobe.com/xap/1.0/',
        'photoshop': 'http://ns.adobe.com/photoshop/1.0/'
    }

    minimal_template = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Sorterr XMP Sync">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
   xmp:Rating="{rating}"
   xmp:Label="{xmp_label}"
   photoshop:Urgency="{urgency}"/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

    for sc_path in sidecars:
        try:
            if os.path.exists(sc_path):
                with open(sc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                header_match = re.search(r'<\?xpacket begin.*?id=.*?\?>', content)
                footer_match = re.search(r'<\?xpacket end=.*?\?>', content)
                header = header_match.group(0) if header_match else '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
                footer = footer_match.group(0) if footer_match else '<?xpacket end="w"?>'

                # ElementTree ignores ProcessingInstructions during parse, but we want to strip them
                # if they interfere. Usually ET.fromstring handles it fine if it's well-formed XML.
                # However, <?xpacket> is technically a PI before the root.
                # It's safer to strip them before parsing.
                xml_body = re.sub(r'<\?xpacket.*?\?>', '', content).strip()
                
                try:
                    tree = ET.fromstring(xml_body)
                    desc = tree.find('.//rdf:Description', ns)
                    if desc is not None:
                        desc.set('{http://ns.adobe.com/xap/1.0/}Rating', str(rating))
                        desc.set('{http://ns.adobe.com/xap/1.0/}Label', str(xmp_label))
                        desc.set('{http://ns.adobe.com/photoshop/1.0/}Urgency', str(urgency))
                    
                    xml_str = ET.tostring(tree, encoding='unicode')
                    new_content = f"{header}\n{xml_str}\n{footer}"
                    
                    with open(sc_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except ET.ParseError:
                    # If XML is malformed, fall back to writing the minimal template
                    with open(sc_path, "w", encoding="utf-8") as f:
                        f.write(minimal_template)
            else:
                with open(sc_path, "w", encoding="utf-8") as f:
                    f.write(minimal_template)
        except Exception as e:
            print(f"XMP Sync Error {sc_path}: {e}")

def open_image(filepath):
    """Open any image (including RAW) as a PIL Image."""
    ext = os.path.splitext(filepath)[1].lower()
    if HAS_RAWPY and ext in RAW_EXTENSIONS:
        with rawpy.imread(filepath) as raw:
            rgb = raw.postprocess(use_camera_wb=True, half_size=RAW_HALF_SIZE)
        img = Image.fromarray(rgb)
    else:
        img = Image.open(filepath)
        img = img.convert("RGB") if img.mode in ("RGBA", "P", "L", "CMYK") else img
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

def generate_thumb_to_file(src_path, dest_path):
    img = open_image(src_path)
    img.thumbnail(THUMBNAIL_SIZE)
    img.save(dest_path, format="JPEG", quality=75, optimize=True)

def generate_preview_to_file(src_path, dest_path):
    img = open_image(src_path)
    img.thumbnail(PREVIEW_SIZE)
    img.save(dest_path, format="JPEG", quality=85, optimize=True)

def background_precache(root, image_paths, run_id):
    """Pre-generate all thumbnails in background. Previews generated lazily."""
    global cache_progress
    ensure_cache_dirs(root)

    # Count pre-existing cached files up front
    already_cached = sum(
        1 for p in image_paths
        if os.path.exists(get_thumb_cache_path(root, os.path.basename(p)))
    )
    cache_progress['pre_cached'] = already_cached
    cache_progress['done'] = already_cached  # Start from already-done count
    cache_progress['running'] = True

    for src_path in image_paths:
        if current_run_id != run_id or not cache_progress['running']:
            break
        
        if not os.path.exists(src_path):
            cache_progress['total'] -= 1
            continue
            
        filename = os.path.basename(src_path)
        thumb_path = get_thumb_cache_path(root, filename)
        if not os.path.exists(thumb_path):
            try:
                generate_thumb_to_file(src_path, thumb_path)
            except Exception as e:
                print(f"Thumb cache error {filename}: {e}")
            cache_progress['done'] += 1  # Only count newly generated thumbnails

    # Ensure done == total when finished
    cache_progress['done'] = cache_progress['total']
    cache_progress['running'] = False
    print(f"Pre-cache complete: {cache_progress['total']} thumbnails ('{already_cached}' were pre-existing).")

# EXIF using exifread (works for JPEG, TIFF, and all RAW formats)
def parse_ratio(s):
    """Convert exifread ratio strings like '50/1' or '18/5' to a clean decimal."""
    if s and '/' in s:
        try:
            parts = s.split('/')
            val = float(parts[0]) / float(parts[1])
            return str(int(val)) if val == int(val) else f"{val:.1f}"
        except Exception:
            pass
    return s

def extract_exif(image_path):
    result = {}
    timestamp = 0

    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal', details=False)

        def tag_str(key):
            v = tags.get(key)
            return str(v) if v else None

        # Camera
        make = tag_str('Image Make') or tag_str('EXIF Make')
        model = tag_str('Image Model') or tag_str('EXIF Model')
        if make: result['Make'] = make
        if model: result['Model'] = model

        # Settings
        fnumber = tag_str('EXIF FNumber')
        exposure = tag_str('EXIF ExposureTime')
        iso = tag_str('EXIF ISOSpeedRatings')
        focal = tag_str('EXIF FocalLength')
        if fnumber: result['FNumber'] = parse_ratio(fnumber)
        if exposure: result['ExposureTime'] = exposure
        if iso: result['ISOSpeedRatings'] = iso
        if focal: result['FocalLength'] = parse_ratio(focal)  # Bug #11 fix: render as decimal

        # Date
        date_str = tag_str('EXIF DateTimeOriginal') or tag_str('Image DateTime')
        if date_str:
            result['DateTimeOriginal'] = date_str
            try:
                dt_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                timestamp = dt_obj.timestamp()
            except ValueError:
                pass

    except Exception as e:
        print(f"EXIF error for {image_path}: {e}")

    if timestamp == 0:
        try:
            timestamp = os.path.getmtime(image_path)
        except Exception:
            pass

    return result, timestamp

# --- Flask image server (runs dynamically) ---
flask_app = Flask(__name__)

@flask_app.route('/image')
def serve_image():
    filepath = request.args.get('path', '')
    if not filepath or not os.path.exists(filepath):
        return Response('Not found', status=404)

    filename = os.path.basename(filepath)
    preview_path = get_preview_cache_path(current_root, filename)

    # Check cache first
    if os.path.exists(preview_path):
        resp = send_file(preview_path, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp

    # Generate and cache
    try:
        ensure_cache_dirs(current_root)
        generate_preview_to_file(filepath, preview_path)
        resp = send_file(preview_path, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
    except Exception as e:
        print(f"Preview error for {filepath}: {e}")
        return Response('Error', status=500)

@flask_app.route('/thumb')
def serve_thumb():
    filepath = request.args.get('path', '')
    if not filepath or not os.path.exists(filepath):
        return Response('Not found', status=404)

    filename = os.path.basename(filepath)
    thumb_path = get_thumb_cache_path(current_root, filename)

    # Check cache first
    if os.path.exists(thumb_path):
        resp = send_file(thumb_path, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp

    # Generate, save to disk cache, then serve
    try:
        ensure_cache_dirs(current_root)
        generate_thumb_to_file(filepath, thumb_path)
        resp = send_file(thumb_path, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
    except Exception as e:
        print(f"Image serve error: {e}")
        return Response('Error', status=500)

def start_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print(f"Starting Flask server on port {FLASK_PORT}")
    flask_app.run(host='localhost', port=FLASK_PORT, threaded=True)

# -------------------------------------------------

@eel.expose
def open_system_folder_dialog():
    # Linux: Use zenity for a native Nautilus picker without needing python3-tk
    if sys.platform.startswith('linux'):
        import subprocess
        try:
            # --file-selection --directory triggers the native folder picker
            result = subprocess.run(['zenity', '--file-selection', '--directory', '--title=Select Gallery Folder'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            print(f"Zenity error: {e}")

    # macOS: Use osascript to trigger native folder picker, avoids Tkinter crash
    if sys.platform == 'darwin':
        import subprocess
        try:
            cmd = [
                'osascript', 
                '-e', 'tell application "System Events" to activate', 
                '-e', 'tell application "System Events" to return POSIX path of (choose folder with prompt "Select Gallery Folder")'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            print(f"osascript error: {e}")

    # Windows / Fallback: Use tkinter
    if HAS_TKINTER:
        try:
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', 1)
            folder_path = filedialog.askdirectory()
            root.destroy()
            return folder_path if folder_path else None
        except Exception as e:
            print(f"Tkinter error: {e}")
    
    print("No native folder picker available (neither Zenity nor Tkinter found).")
    return None

@eel.expose
def set_current_folder(folder_path):
    global current_root, cache_progress
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        if current_root and current_root != folder_path:
            release_folder_dbs(current_root)
        current_root = folder_path
        init_db(current_root)
        # Stop any running pre-cache
        cache_progress['running'] = False
        return current_root
    return None

@eel.expose
def get_flask_port():
    return FLASK_PORT

@eel.expose
def set_raw_half_size(is_half_size):
    global RAW_HALF_SIZE
    RAW_HALF_SIZE = is_half_size
    return True

@eel.expose
def save_settings(settings_dict):
    """Persist user settings to a JSON file in the project folder."""
    if not current_root:
        return False
    settings_path = os.path.join(current_root, SETTINGS_FILENAME)
    try:
        # Merge with existing settings to avoid clobbering unrelated keys
        existing = {}
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                existing = json.load(f)
        existing.update(settings_dict)
        with open(settings_path, 'w') as f:
            json.dump(existing, f, indent=2)
        return True
    except Exception as e:
        print(f"Save settings error: {e}")
        return False

@eel.expose
def load_settings():
    """Load user settings from the project folder's JSON file."""
    if not current_root:
        return None
    settings_path = os.path.join(current_root, SETTINGS_FILENAME)
    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Load settings error: {e}")
    return None

@eel.expose
def clear_cache():
    """Delete and recreate the cache directory."""
    if not current_root:
        return
    cache_dir = get_cache_dir(current_root)
    try:
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        ensure_cache_dirs(current_root)
    except Exception as e:
        print(f"Clear cache error: {e}")

@eel.expose
def get_image_list():
    global current_run_id
    image_list = reconcile_folder(current_root)
    all_paths = [img['path'] for img in image_list]

    # Cancel any running pre-cache from a previous folder load (R3 fix)
    cache_progress['running'] = False

    # Set total synchronously before launching thread so the poll sees it immediately
    cache_progress['total'] = len(all_paths)
    cache_progress['done'] = 0
    cache_progress['pre_cached'] = 0
    cache_progress['running'] = True

    current_run_id += 1
    run_id = current_run_id

    # Kick off background pre-cache (only thumbnails)
    t = threading.Thread(target=background_precache, args=(current_root, all_paths, run_id), daemon=True)
    t.start()

    return image_list

@eel.expose
def get_cache_progress():
    return cache_progress

@eel.expose
def get_exif(path):
    exif, _ = extract_exif(path)
    return exif

@eel.expose
def move_image(filename, current_path, category):
    """Move an image to Picks or Rejects, with fingerprint-based dedup."""
    if category not in ['Picks', 'Rejects']:
        return None
    if not os.path.exists(current_path):
        return None

    fp = fingerprint_file(current_path)
    if not fp:
        return None

    db = get_db(current_root)
    target_dir = os.path.join(current_root, category)
    os.makedirs(target_dir, exist_ok=True)

    # Check if this exact file is already in the target folder (dedup)
    existing = db.execute('SELECT filename FROM files WHERE fingerprint=? AND folder=?', (fp, category)).fetchone()
    if existing:
        # Already there — no-op, return existing path
        existing_path = os.path.join(target_dir, existing['filename'])
        return {'path': existing_path, 'filename': existing['filename']}

    # Determine the old folder for undo logging
    old_row = db.execute('SELECT folder FROM files WHERE fingerprint=?', (fp,)).fetchone()
    old_folder = old_row['folder'] if old_row else ''

    # Physical move with collision handling for genuinely different files
    target_path = os.path.join(target_dir, filename)
    if os.path.exists(target_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(current_path, target_path)
    except Exception as e:
        print(f"Move error: {e}")
        return None

    actual_filename = os.path.basename(target_path)

    # Update DB
    db.execute('UPDATE files SET filename=?, folder=? WHERE fingerprint=?',
              (actual_filename, category, fp))

    # Log action for undo
    db.execute('INSERT INTO actions (fingerprint, action, old_folder, new_folder) VALUES (?,?,?,?)',
              (fp, 'pick' if category == 'Picks' else 'reject', old_folder, category))
    db.commit()

    # Sync XMP sidecar (and others)
    row = db.execute('SELECT rating, color FROM files WHERE fingerprint=?', (fp,)).fetchone()
    write_xmp_sidecar(target_path, row['rating'] if row else 0, row['color'] if row else 'None')
    _move_sidecar_files(current_path, target_path, filename)

    return {'path': target_path, 'filename': actual_filename}

def _move_sidecar_files(old_path, new_path, filename):
    """Move associated sidecar files (XMP, PP3, DOP) alongside the image."""
    SIDECARS = [".xmp", ".pp3", ".dop"]
    base_ext = os.path.splitext(filename)[1]
    
    for ext in SIDECARS:
        possible_old = [
            os.path.splitext(old_path)[0] + ext,  # image.xmp
            old_path + ext                        # image.CR3.xmp
        ]
        possible_new = [
            os.path.splitext(new_path)[0] + ext,
            new_path + ext
        ]
        
        for old_sidecar, new_sidecar in zip(possible_old, possible_new):
            if os.path.exists(old_sidecar):
                try:
                    shutil.move(old_sidecar, new_sidecar)
                except Exception:
                    pass

@eel.expose
def restore_image(filename, current_path):
    """Move an image back to unsorted root from Picks or Rejects."""
    try:
        if not os.path.exists(current_path):
            return None

        # Fingerprint BEFORE the move (file must exist at current_path)
        fp = fingerprint_file(current_path)
        db = get_db(current_root)

        # Query old folder BEFORE the move
        old_folder = ''
        if fp:
            old_row = db.execute('SELECT folder FROM files WHERE fingerprint=?', (fp,)).fetchone()
            old_folder = old_row['folder'] if old_row else ''

        target_path = os.path.join(current_root, filename)
        # Handle duplicate filenames in root
        if os.path.exists(target_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(current_root, f"{base}_{counter}{ext}")
                counter += 1
        shutil.move(current_path, target_path)

        actual_filename = os.path.basename(target_path)

        # Update DB
        if fp:
            db.execute('UPDATE files SET filename=?, folder=? WHERE fingerprint=?',
                      (actual_filename, '', fp))
            # Log restore action
            db.execute('INSERT INTO actions (fingerprint, action, old_folder, new_folder) VALUES (?,?,?,?)',
                      (fp, 'restore', old_folder, ''))
            db.commit()

        # Move associated sidecar files back to root
        _move_sidecar_files(current_path, target_path, filename)

        return target_path
    except Exception as e:
        print(f"Restore error: {e}")
        return None

@eel.expose
def set_star_rating(fingerprint, rating):
    db = get_db(current_root)

    # Find the file by unique fingerprint
    row = db.execute('SELECT folder, color, filename FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
    if not row:
        return False

    db.execute('UPDATE files SET rating=? WHERE fingerprint=?', (rating, fingerprint))
    db.commit()

    # Sync to XMP
    folder_path = os.path.join(current_root, row['folder']) if row['folder'] else current_root
    image_path = os.path.join(folder_path, row['filename'])
    if os.path.exists(image_path):
        write_xmp_sidecar(image_path, rating, row['color'])

    return True

@eel.expose
def set_color_tag(fingerprint, color):
    db = get_db(current_root)

    # Find the file by unique fingerprint
    row = db.execute('SELECT folder, rating, filename FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
    if not row:
        return False

    db.execute('UPDATE files SET color=? WHERE fingerprint=?', (color, fingerprint))
    db.commit()

    # Sync to XMP
    folder_path = os.path.join(current_root, row['folder']) if row['folder'] else current_root
    image_path = os.path.join(folder_path, row['filename'])
    if os.path.exists(image_path):
        write_xmp_sidecar(image_path, row['rating'], color)

    return True

@eel.expose
def undo_last_action():
    """Undo the last pick/reject action by restoring the file to unsorted."""
    db = get_db(current_root)
    last = db.execute(
        "SELECT * FROM actions WHERE action IN ('pick','reject') ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not last:
        return None

    fp = last['fingerprint']
    file_row = db.execute('SELECT filename, folder FROM files WHERE fingerprint=?', (fp,)).fetchone()
    if not file_row:
        # Remove orphaned action
        db.execute('DELETE FROM actions WHERE id=?', (last['id'],))
        db.commit()
        return None

    # Build current path
    folder_path = os.path.join(current_root, file_row['folder']) if file_row['folder'] else current_root
    current_path = os.path.join(folder_path, file_row['filename'])

    if not os.path.exists(current_path):
        db.execute('DELETE FROM actions WHERE id=?', (last['id'],))
        db.commit()
        return None

    # Restore to root
    result = restore_image(file_row['filename'], current_path)

    if result:
        # Remove the undone action from history
        db.execute('DELETE FROM actions WHERE id=?', (last['id'],))
        db.commit()

    return result

# Initialize Eel - resolve web path for both dev and PyInstaller frozen builds
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

eel.init(os.path.join(base_path, 'web'))

def _find_brave():
    """Return the Brave browser executable path, or None."""
    candidates = []
    if sys.platform.startswith('win'):
        candidates = [
            os.path.expandvars(r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe'),
            os.path.expandvars(r'%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe'),
            os.path.expandvars(r'%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe'),
        ]
    elif sys.platform == 'darwin':
        candidates = ['/Applications/Brave Browser.app/Contents/MacOS/Brave Browser']
    else:  # Linux
        candidates = ['/usr/bin/brave', '/usr/bin/brave-browser', '/usr/local/bin/brave',
                      '/snap/bin/brave', '/opt/brave.com/brave/brave-browser']
    for path in candidates:
        if os.path.exists(path):
            return path
    import shutil
    for name in ('brave', 'brave-browser'):
        found = shutil.which(name)
        if found:
            return found
    return None

def _find_firefox():
    """Return the Firefox executable path, or None."""
    candidates = []
    if sys.platform.startswith('win'):
        candidates = [
            os.path.expandvars(r'%PROGRAMFILES%\Mozilla Firefox\firefox.exe'),
            os.path.expandvars(r'%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Mozilla Firefox\firefox.exe'),
        ]
    elif sys.platform == 'darwin':
        candidates = ['/Applications/Firefox.app/Contents/MacOS/firefox']
    else:
        candidates = ['/usr/bin/firefox', '/usr/bin/firefox-esr', '/usr/local/bin/firefox',
                      '/snap/bin/firefox']
    for path in candidates:
        if os.path.exists(path):
            return path
    import shutil
    found = shutil.which('firefox')
    return found or None

def _start_app():
    """Launch the Eel UI, preferring Brave then Firefox then system default."""
    import webbrowser as _wbr

    brave_path = _find_brave()
    firefox_path = _find_firefox()

    if brave_path:
        print(f"Launching with Brave: {brave_path}")
        eel.browsers.set_path('chrome', brave_path)
        eel.start('index.html', mode='chrome', port=EEL_PORT,
                  cmdline_args=['--start-fullscreen'])
        return

    # Firefox: eel cannot run Firefox in --app mode, so we run eel as a
    # plain server and open a regular browser tab.
    if firefox_path:
        print(f"Launching with Firefox: {firefox_path}")
        import threading, time
        def _open_firefox():
            time.sleep(1.5)  # Give eel server a moment to bind
            import subprocess
            subprocess.Popen([firefox_path, f'http://localhost:{EEL_PORT}/index.html'])
        threading.Thread(target=_open_firefox, daemon=True).start()
        eel.start('index.html', mode=None, host='localhost', port=EEL_PORT)
        return

    # Try Chromium as a last Chromium-based option
    import shutil
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    if chromium:
        print(f"Launching with Chromium: {chromium}")
        eel.browsers.set_path('chrome', chromium)
        eel.start('index.html', mode='chrome', port=EEL_PORT,
                  cmdline_args=['--start-fullscreen'])
        return

    # Final fallback: open system default browser as a tab
    print("No supported browser found — opening system default browser.")
    import threading, time
    def _open_default():
        time.sleep(1.5)
        _wbr.open(f'http://localhost:{EEL_PORT}/index.html')
    threading.Thread(target=_open_default, daemon=True).start()
    eel.start('index.html', mode=None, host='localhost', port=EEL_PORT)

if __name__ == "__main__":
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    try:
        _start_app()
    except (SystemExit, KeyboardInterrupt):
        print("Application closed.")
