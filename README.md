# Sorterr

> **Professional photo culling, built for speed.**

Sorterr is a fast, keyboard-driven desktop application for sorting and culling large photo libraries. Built with Python and a browser-based UI powered by [Eel](https://github.com/python-eel/Eel), it runs locally with no cloud dependency and works with every major image format — including RAW files.

---

## Downloads

| Platform | Link |
|---|---|
| **Windows** | [Download Sorterr-v1.4.exe](https://github.com/CalvinistKlein/Sorterr-Image-Management/releases/latest) |
| **Linux (AppImage)** | [Download Sorterr-v1.4-x86_64.AppImage](https://github.com/CalvinistKlein/Sorterr-Image-Management/releases/latest) |

---

---

## Features

- **Instant navigation** — browser-side preload cache ensures near-zero loading delay between images
- **RAW support** — reads CR2, NEF, ARW, DNG, ORF, RW2, RAF, CR3 via `rawpy`
- **One-key culling** — pick or reject with arrow keys; restore to unsorted with `Alt+↑/↓`
- **Native file browser** — directly select internal OS folders and external USB drives for culling
- **Visual indicators** — status circle (green/red/grey), color badge, and star rank overlaid on every thumbnail and preview
- **Star ratings** — 1–5 stars, togglable (click the active star to clear)
- **Color tags** — Red, Yellow, Green, Blue, Purple; assignable by keyboard shortcut
- **Time & Burst Grouping** — group images by custom time gaps or rapid-fire bursts
- **Multiple layout modes** — Single, Split (2-up), Grid (4-up)
- **Thumbnail caching** — background pre-generation with live progress bar
- **EXIF metadata panel** — camera, settings (f-stop, shutter, ISO, focal length), and date
- **Recent projects** — quick reopen from the welcome screen
- **Remappable keybinds** — fully configurable from the settings panel
- **Viewer action buttons** — hover over any preview to reveal Pick / Restore / Reject buttons

---

## Screenshots

> Open the app and select a folder to get started.

---

## Installation

### Requirements

- Python 3.10+
- Linux, macOS, or Windows
- A supported browser (see below)

### Supported Browsers

Sorterr auto-detects and launches the best available browser in this order:

| Priority | Browser | Mode |
|---|---|---|
| 1st | **Brave** | App window (fullscreen, recommended) |
| 2nd | **Chromium** | App window (fullscreen) |
| 3rd | **Firefox** | Browser tab |
| Fallback | System default | Browser tab |

> **Brave is the recommended browser** for the best experience (app-window mode, no Chrome required).

### Quick Start (from source)

```bash
git clone https://github.com/yourname/sorterr.git
cd sorterr

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

Or use the provided launch scripts:

```bash
# Linux / macOS
chmod +x run.sh
./run.sh

# Windows
run.bat     # (to be created)
```

### Dependencies

| Package | Purpose |
|---|---|
| `eel` | Python↔JS bridge + embedded browser |
| `Pillow` | Image decoding and thumbnail generation |
| `Flask` | Local image HTTP server (port 8081) |
| `rawpy` | RAW file decoding |
| `exifread` | EXIF metadata extraction |
| `imageio`, `numpy` | Required by rawpy |

---

## Building a Standalone Executable

### Linux / macOS

```bash
chmod +x scripts/build.sh
./scripts/build.sh
# Output: dist/Sorterr
```

### Windows

```bat
scripts\build.bat
:: Output: dist\Sorterr.exe
```

Both scripts use [PyInstaller](https://pyinstaller.org) to bundle everything into a single binary.

---

## Usage

### Workflow

1. **Open a folder** — click *Select Folder* or press `O`
2. **Navigate** — use arrow keys (or WASD) to move between images
3. **Cull** — press `↑` / `W` to **pick**, `↓` / `S` to **reject**
4. **Restore** — press `Alt+↑` or `Alt+↓` to move an image back to unsorted
5. **Rate** — press `1`–`5` to set a star rating; press the same number again to clear it
6. **Tag** — press `6`–`0` to assign a color tag; `` ` `` to clear

Picked images are moved to a `Picks/` subfolder. Rejected images go to `Rejects/`. Both operations are non-destructive and fully reversible via **Restore**.

### Keyboard Shortcuts

| Action | Default Key(s) |
|---|---|
| Previous image | `←` / `A` |
| Next image | `→` / `D` |
| Pick | `↑` / `W` |
| Reject | `↓` / `S` |
| Restore to unsorted | `Alt+↑` (un-pick) · `Alt+↓` (un-reject) |
| Open folder picker | `O` |
| Cycle layout backward | `Q` |
| Cycle layout forward | `E` |
| Star ratings | `1` `2` `3` `4` `5` |
| Color tags | `6`=Red · `7`=Yellow · `8`=Green · `9`=Blue · `0`=Purple |
| Clear color tag | `` ` `` |

> All navigation keybinds (except star/color shortcuts) are remappable from the ⚙ Settings panel.

### Folder Structure

After culling, your photo directory will look like this:

```
MyPhotos/
├── Picks/
│   └── DSC0042.jpg
├── Rejects/
│   └── DSC0001.jpg
├── DSC0002.jpg          ← still unsorted
├── .sorterr_cache/      ← thumbnail/preview cache (auto-managed)
└── .sorterr_metadata.json  ← ratings and color tags (per folder)
```

---

## Architecture

Sorterr uses a dual-server architecture:

| Component | Technology | Port |
|---|---|---|
| UI shell | [Eel](https://github.com/python-eel/Eel) (Chromium/browser) | 8080 |
| Image server | Flask | 8081 |
| Backend logic | Python | — |
| Frontend | Vanilla HTML/CSS/JS | — |

**Image pipeline:**
1. Thumbnails are pre-generated in a background thread on folder open
2. Full previews are generated on-demand and cached to disk
3. The browser-side preload cache prefetches adjacent images ahead of navigation

---

## Configuration

Settings are persisted in `localStorage` under the `sorterr_*` keys:

| Key | Description |
|---|---|
| `sorterr_keybinds` | Custom keybind map |
| `sorterr_recents` | Recent project paths (up to 8) |
| `sorterr_preload_ahead` | Number of images to preload ahead (default: 3) |

Per-folder metadata (ratings, color tags) is stored in `.sorterr_metadata.json` inside each photo directory.

---

## Supported Formats

| Type | Extensions |
|---|---|
| Standard | `.jpg` `.jpeg` `.png` `.webp` `.tiff` `.bmp` |
| RAW | `.cr2` `.cr3` `.nef` `.arw` `.dng` `.orf` `.rw2` `.raf` |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Pull requests are welcome. Please open an issue first to discuss any significant change.
