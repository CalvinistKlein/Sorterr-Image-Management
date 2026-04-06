import re
import eel
import os
import sys
import shutil
import json
from PIL import Image, ExifTags
import base64
from io import BytesIO
from datetime import datetime
import threading
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
METADATA_FILENAME = '.sorterr_metadata.json'
CACHE_DIR_NAME = '.sorterr_cache'

# Global state
current_root = os.getcwd()
metadata = {}
cache_progress = {'total': 0, 'done': 0, 'pre_cached': 0, 'running': False}

def get_cache_dir(root):
    return os.path.join(root, CACHE_DIR_NAME)

def get_thumb_cache_path(root, filename):
    return os.path.join(get_cache_dir(root), 'thumbs', filename + '.jpg')

def get_preview_cache_path(root, filename):
    return os.path.join(get_cache_dir(root), 'previews', filename + '.jpg')

def ensure_cache_dirs(root):
    os.makedirs(os.path.join(get_cache_dir(root), 'thumbs'), exist_ok=True)
    os.makedirs(os.path.join(get_cache_dir(root), 'previews'), exist_ok=True)

def get_metadata_path(root):
    return os.path.join(root, METADATA_FILENAME)

def load_metadata(root):
    global metadata
    path = get_metadata_path(root)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                metadata = json.load(f)
        except Exception:
            metadata = {}
    else:
        metadata = {}

def save_metadata(root):
    path = get_metadata_path(root)
    try:
        with open(path, 'w') as f:
            json.dump(metadata, f, indent=4)
    except Exception:
        pass

def write_xmp_sidecar(image_path, rating, color):
    """Write or surgically update an XMP sidecar with rating and color label for interoperability."""
    # Write both standard styles: image.xmp (Lightroom) and image.ext.xmp (Darktable)
    base = os.path.splitext(image_path)[0]
    sidecars = [base + ".xmp", image_path + ".xmp"]
    
    xmp_label = color if color != "None" else ""
    # Map colors to Urgency (Darktable)
    color_map = {"Red": 1, "Yellow": 2, "Green": 3, "Blue": 4, "Purple": 5}
    urgency = color_map.get(color, 0)
    
    def update_xmp_content(content, rating, label, urgency):
        # 1. Ensure namespaces are there
        desc_pattern = re.compile(r'(<rdf:Description[^>]*?)(/?>)', re.IGNORECASE | re.DOTALL)
        match = desc_pattern.search(content)
        if not match: return content # Fallback
        
        header, closer = match.groups()
        
        # Add namespaces if missing
        if 'xmlns:xmp=' not in header: header += '\n    xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        if 'xmlns:photoshop=' not in header: header += '\n    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"'
        
        # 2. Update Attributes (Rating, Label, Urgency)
        for attr, val in [('xmp:Rating', rating), ('xmp:Label', label), ('photoshop:Urgency', urgency)]:
            attr_pattern = re.compile(rf'{attr}="[^"]*"')
            if attr_pattern.search(header):
                header = attr_pattern.sub(f'{attr}="{val}"', header)
            else:
                header += f'\n   {attr}="{val}"'
        
        return content[:match.start()] + header + closer + content[match.end():]

    minimal_template = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
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
<?xpacket end="w"?>"""

    for sc_path in sidecars:
        try:
            if os.path.exists(sc_path):
                with open(sc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = update_xmp_content(content, rating, xmp_label, urgency)
                with open(sc_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
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
            rgb = raw.postprocess(use_camera_wb=True, half_size=True)
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

def background_precache(root, image_paths):
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
        if not cache_progress['running']:
            break
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

# --- Flask image server (runs on port 8081) ---
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

    # Generate and cache on-the-fly
    try:
        ensure_cache_dirs(current_root)
        img = open_image(filepath)
        img.thumbnail(THUMBNAIL_SIZE)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        resp = Response(buf.getvalue(), mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
    except Exception as e:
        print(f"Image serve error: {e}")
        return Response('Error', status=500)

def start_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    flask_app.run(host='localhost', port=8081, threaded=True)

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
        current_root = folder_path
        load_metadata(current_root)
        # Stop any running pre-cache
        cache_progress['running'] = False
        return current_root
    return None

@eel.expose
def get_image_list():
    load_metadata(current_root)
    image_list = []

    folders = [('', 'Unsorted'), ('Picks', 'Pick'), ('Rejects', 'Reject')]
    all_paths = []
    for folder, status in folders:
        folder_full_path = os.path.join(current_root, folder) if folder else current_root
        if not os.path.exists(folder_full_path):
            continue
        try:
            dir_contents = os.listdir(folder_full_path)
        except PermissionError:
            continue

        for f in dir_contents:
            if f.startswith('.') or f.startswith('._'):
                continue
            full_path = os.path.join(folder_full_path, f)
            try:
                if os.path.isfile(full_path) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                    mdata = metadata.get(f, {})
                    # Use cached timestamp if available, else file mtime
                    timestamp = mdata.get('timestamp', os.path.getmtime(full_path))
                    image_list.append({
                        "filename": f,
                        "path": full_path,
                        "rating": mdata.get("rating", 0),
                        "color": mdata.get("color", "None"),
                        "status": status,
                        "timestamp": timestamp
                    })
                    all_paths.append(full_path)
            except Exception:
                pass

    # Set total synchronously before launching thread so the poll sees it immediately
    cache_progress['total'] = len(all_paths)
    cache_progress['done'] = 0
    cache_progress['pre_cached'] = 0
    cache_progress['running'] = True

    # Kick off background pre-cache (only thumbnails)
    t = threading.Thread(target=background_precache, args=(current_root, all_paths), daemon=True)
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
    if category not in ['Picks', 'Rejects']:
        return None
    target_dir = os.path.join(current_root, category)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    try:
        new_path = os.path.join(target_dir, filename)
        # Handle duplicate filenames — avoid silent overwrite
        if os.path.exists(new_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(new_path):
                new_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                counter += 1
        if os.path.exists(current_path):
            shutil.move(current_path, new_path)
            
            # Sync metadata to XMP sidecars
            mdata = metadata.get(filename, {})
            write_xmp_sidecar(new_path, mdata.get('rating', 0), mdata.get('color', 'None'))

            # Move existing XMP files if they exist
            for ext in [".xmp", os.path.splitext(filename)[1] + ".xmp"]:
                old_xmp = os.path.splitext(current_path)[0] + ext if ext == ".xmp" else current_path + ".xmp"
                if os.path.exists(old_xmp):
                    new_xmp = os.path.splitext(new_path)[0] + ext if ext == ".xmp" else new_path + ".xmp"
                    try:
                        shutil.move(old_xmp, new_xmp)
                    except Exception:
                        pass
            
            return new_path
        return None
    except Exception as e:
        print(f"Move error: {e}")
        return None

@eel.expose
def restore_image(filename, current_path):
    """Move an image back to unsorted root from Picks or Rejects."""
    try:
        if not os.path.exists(current_path):
            return None
        target_path = os.path.join(current_root, filename)
        # Handle duplicate filenames in root
        if os.path.exists(target_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(current_root, f"{base}_{counter}{ext}")
                counter += 1
        shutil.move(current_path, target_path)
        
        # Move associated XMP files back to root
        for ext in [".xmp", os.path.splitext(filename)[1] + ".xmp"]:
            old_xmp = os.path.splitext(current_path)[0] + ext if ext == ".xmp" else current_path + ".xmp"
            if os.path.exists(old_xmp):
                new_xmp = os.path.splitext(target_path)[0] + ext if ext == ".xmp" else target_path + ".xmp"
                try:
                    shutil.move(old_xmp, new_xmp)
                except Exception:
                    pass

        return target_path
    except Exception as e:
        print(f"Restore error: {e}")
        return None

@eel.expose
def set_star_rating(filename, rating):
    load_metadata(current_root)
    if filename not in metadata:
        metadata[filename] = {}
    metadata[filename]['rating'] = rating
    save_metadata(current_root)
    
    # Sync to XMP (need full path)
    # Find image in current_root or Picks/Rejects
    for folder in ['', 'Picks', 'Rejects']:
        potential_path = os.path.join(current_root, folder, filename) if folder else os.path.join(current_root, filename)
        if os.path.exists(potential_path):
            write_xmp_sidecar(potential_path, rating, metadata[filename].get('color', 'None'))
            break

    return True

@eel.expose
def set_color_tag(filename, color):
    load_metadata(current_root)
    if filename not in metadata:
        metadata[filename] = {}
    metadata[filename]['color'] = color
    save_metadata(current_root)
    
    # Sync to XMP
    for folder in ['', 'Picks', 'Rejects']:
        potential_path = os.path.join(current_root, folder, filename) if folder else os.path.join(current_root, filename)
        if os.path.exists(potential_path):
            write_xmp_sidecar(potential_path, metadata[filename].get('rating', 0), color)
            break

    return True

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
        eel.start('index.html', mode='chrome', port=8080,
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
            subprocess.Popen([firefox_path, 'http://localhost:8080/index.html'])
        threading.Thread(target=_open_firefox, daemon=True).start()
        eel.start('index.html', mode=None, host='localhost', port=8080)
        return

    # Try Chromium as a last Chromium-based option
    import shutil
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    if chromium:
        print(f"Launching with Chromium: {chromium}")
        eel.browsers.set_path('chrome', chromium)
        eel.start('index.html', mode='chrome', port=8080,
                  cmdline_args=['--start-fullscreen'])
        return

    # Final fallback: open system default browser as a tab
    print("No supported browser found — opening system default browser.")
    import threading, time
    def _open_default():
        time.sleep(1.5)
        _wbr.open('http://localhost:8080/index.html')
    threading.Thread(target=_open_default, daemon=True).start()
    eel.start('index.html', mode=None, host='localhost', port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    try:
        _start_app()
    except (SystemExit, KeyboardInterrupt):
        print("Application closed.")
