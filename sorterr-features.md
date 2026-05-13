# Sorterr: Exhaustive Feature Review & Recreation Blueprint

## 1. Executive Summary
Sorterr is a specialized, high-performance desktop application designed specifically for professional photographers and media managers who need to cull (sort, select, and reject) massive volumes of high-resolution images. Built entirely around the philosophy of speed and seamless interaction, the application strips away complex editing tools to focus exclusively on rapid decision-making. By pre-loading images, providing instant keyboard-driven actions, and natively supporting professional camera formats, Sorterr allows users to process thousands of photos in a fraction of the time required by traditional file browsers or heavy editing suites.

---

## 2. Core Philosophy & The Culling Workflow
The entire application is built to support a specific, highly optimized workflow:
*   **Ingestion:** The user selects a root folder containing raw, unsorted images directly from an SD card or hard drive.
*   **Rapid Review:** Using only the keyboard, the user navigates through the images. The system guarantees that the next image is instantly visible without any loading screens.
*   **Categorization:** Images are marked as "Picks" (keepers) or "Rejects" (deletions). The application physically organizes the files into corresponding sub-folders in real-time, keeping the primary workspace clean.
*   **Deep Inspection:** When absolute sharpness or detail is required, the user zooms into the image to verify critical focus (e.g., ensuring a subject's eye is perfectly sharp).
*   **Refinement:** After the initial pass, the user filters the view to show only "Picks," applying star ratings and color tags to identify the absolute best shots for final editing.

---

## 3. Primary Interface & Navigation Mechanics
The user interface is minimalist, dedicating maximum screen real estate to the images themselves. It consists of four primary zones:

### 3.1 The Top Control Bar
*   **Workspace Selection:** A prominent button allows users to open their operating system's native folder browser to select a new gallery.
*   **View Filters:** A toggle group that instantly filters the main viewport. Users can choose to see "All" images, only "Unsorted" images, only "Picks," or only "Rejects."
*   **Smart Grouping Toggles:** Buttons to activate or deactivate "Time Grouping" and "Burst Grouping" logic (detailed in Section 8).
*   **Layout Selection:** Icons to switch the main viewport between Single, Split, and Grid modes.
*   **Sort Order Dropdown:** Allows sorting the current view by Capture Time, File Name, or Star Rating.
*   **Settings Access:** A gear icon that opens the customization modal.

### 3.2 The Main Viewport
*   This is the dynamic canvas where images are rendered. It adapts based on the chosen Layout Mode.
*   It supports overlaid, semi-transparent buttons for mouse-driven users (Pick, Restore, Reject) that appear when hovering over an image.
*   It handles all mouse-driven zooming and panning interactions.

### 3.3 The Information Heads-Up Display (HUD)
*   Located on the right side of the screen, this panel provides constant contextual information.
*   **Directory Path:** Shows the absolute location of the currently active folder.
*   **Active Filename:** Displays the exact name and extension of the currently focused image.
*   **Sorting Progress:** A counter (e.g., "45 / 1200") showing exactly how far along the user is in the current folder, alongside a percentage for immediate context.
*   **Current Status:** Text explicitly stating if the active image is Unsorted, a Pick, or a Reject.

### 3.4 The Thumbnail Strip (Footer)
*   A horizontally scrolling filmstrip at the bottom of the screen.
*   Displays miniature versions of all images in the current filtered view.
*   The currently active image is highlighted.
*   Users can click any thumbnail to instantly jump to that image in the main viewport.
*   Visual dividers (colored vertical lines) appear here when Smart Grouping is active.

---

## 4. Advanced Image Zooming & Deep Inspection
To accommodate the need for critical focus verification, Sorterr includes a robust, high-performance zooming engine tailored for high-resolution media.

### 4.1 Smooth Scroll Zoom
*   Users can place their cursor over any part of the image in the main viewport and use their mouse scroll wheel (or trackpad scroll gesture) to zoom in and out dynamically.
*   The zoom anchors perfectly to the cursor's position, allowing the user to immediately magnify a specific detail (like a face in a crowd) without needing to pan afterward.

### 4.2 Click-and-Drag Panning
*   Once an image is magnified beyond the bounds of the viewport, the cursor transforms into a "grab" icon.
*   Users can click and hold to drag the image smoothly in any direction, exploring the magnified details.
*   The panning is optimized to be entirely fluid, with zero stuttering even on massive RAW files.

### 4.3 1:1 Pixel Mapping (100% Zoom Shortcut)
*   A dedicated keyboard shortcut instantly snaps the image to a 100% (1:1) pixel scale, centered on the current cursor location.
*   Pressing the shortcut again instantly snaps the image back to "Fit to Screen" mode.

### 4.4 Synchronized Multi-Zoom (Compare Mode)
*   When utilizing the "Split View" layout (two images side-by-side), the zooming engine links both viewports.
*   If the user zooms into the left eye of a subject in the first image, the second image automatically zooms and pans to the exact same relative coordinate.
*   This feature is critical for comparing two nearly identical burst shots to determine which one achieved perfect critical focus.

---

## 5. Layout Modes in Detail
The application adapts to different stages of the culling process through three distinct layout modes, easily cycled via keyboard shortcuts.

### 5.1 Single View
*   **Purpose:** Deep, distraction-free inspection of individual images.
*   **Behavior:** The active image scales to fill the maximum available bounds of the viewport while maintaining its native aspect ratio.
*   **Navigation:** Pressing 'Next' instantly replaces the current image with the next one in the sequence.

### 5.2 Split View (2-Up)
*   **Purpose:** Direct comparison of two sequential images, heavily utilized when reviewing action bursts or bracketed exposures.
*   **Behavior:** The screen splits vertically. The active image is displayed on the left, and the immediately following image is displayed on the right.
*   **Navigation:** Pressing 'Next' shifts the right image to the left pane, and loads a new image into the right pane, creating a rolling comparison.
*   **Interaction:** Culling actions (Pick/Reject) apply specifically to the currently "active" pane (indicated by a subtle highlight).

### 5.3 Grid View (4-Up)
*   **Purpose:** Rapid elimination of obvious bad shots (out of focus, bad lighting, floor shots) and gaining a broad overview of a scene.
*   **Behavior:** The viewport divides into a 2x2 grid, displaying four sequential images simultaneously.
*   **Navigation:** Pressing 'Next' advances the entire grid by four new images (page-turning style).

---

## 6. The Culling Engine & Categorization
The core mechanical loop of Sorterr is the categorization of files. This process is designed to be destructive in organization, but non-destructive to the actual files.

### 6.1 The "Pick" Action
*   **Trigger:** Executed via keyboard (default: Up Arrow or 'W') or by clicking the overlaid "Pick" button.
*   **Execution:** The system physically moves the file from its current location into a dedicated "Picks" sub-folder within the root directory.
*   **Feedback:** A large, momentary visual overlay flashes "PICKED" on the screen. The image receives a green status badge on its thumbnail.
*   **Progression:** If configured, the app immediately advances to the next image to maintain flow state.

### 6.2 The "Reject" Action
*   **Trigger:** Executed via keyboard (default: Down Arrow or 'S') or the overlaid "Reject" button.
*   **Execution:** The file is moved into a dedicated "Rejects" sub-folder.
*   **Feedback:** A red "REJECTED" overlay flashes. The thumbnail receives a red status badge.

### 6.3 The "Restore" Action
*   **Trigger:** Executed via a modifier key combination (default: Alt+Up/Down) or the "Restore" button.
*   **Execution:** Instantly reverses a Pick or Reject action. The file is moved out of the sub-folder and placed back into the root directory.
*   **Feedback:** A grey "RESTORED" overlay flashes. The status badges are removed, returning the image to a pristine "Unsorted" state.

---

## 7. Metadata, Ratings, and Synchronization
Beyond binary picking and rejecting, the application provides granular organization tools that seamlessly integrate with professional post-production software.

### 7.1 Star Ratings
*   Users can assign a rank from 1 to 5 stars to any image using the numeric keys (1-5).
*   The rating is immediately reflected visually via star icons overlaid on the thumbnail and main preview.
*   Ratings act as toggles: if an image is currently rated 4 stars, pressing '4' again removes the rating entirely (setting it to 0).

### 7.2 Color Tags
*   Users can categorize images by intent using standard color labels: Red (6), Yellow (7), Green (8), Blue (9), and Purple (0).
*   A colored dot appears in the bottom-left corner of the image's thumbnail and preview.
*   Pressing the backtick key (`) instantly clears the color tag.

### 7.3 Universal Sidecar Synchronization
*   Every time a user assigns a rating, a color tag, or moves an image, the application silently generates or updates a "Sidecar" file alongside the original image.
*   These sidecar files contain the organizational data formatted in an industry-standard way.
*   **The Benefit:** When the user eventually imports their "Picks" folder into an editor like Adobe Lightroom or Darktable, all of the star ratings and color tags assigned in Sorterr are automatically recognized and applied. The user never loses their sorting work when transitioning between applications.

### 7.4 EXIF Data Extraction
*   The HUD automatically reads the internal hardware metadata (EXIF) embedded within the active image.
*   It decodes complex information into human-readable text, displaying the exact camera body used, the lens focal length, aperture, shutter speed, ISO, and the precise timestamp of capture.

---

## 8. Smart Grouping & Visual Cues
To help users parse folders containing thousands of images, the application analyzes the capture timestamps to provide intelligent visual context.

### 8.1 Time-Based Grouping (Scene Detection)
*   Users can define a "Time Gap" threshold (e.g., 30 seconds).
*   The application analyzes the chronological sequence of the images. If it detects a gap between two photos that exceeds the threshold, it assumes the photographer moved to a new location or started a new scene.
*   It places a prominent Yellow vertical divider line in the thumbnail strip at this exact break point, allowing the user to visually anticipate a complete change of scenery.

### 8.2 Burst Grouping (Action Detection)
*   Users can define a "Burst Window" (e.g., 1.0 second) and a "Minimum Count" (e.g., 3 images).
*   The application scans for clusters of images taken in rapid succession that meet these criteria.
*   It places a Blue vertical divider line around these clusters. This tells the user: "The next 5 photos are essentially the same split-second moment; you only need to pick the one with the sharpest focus, and reject the rest."

---

## 9. The Zero-Lag Rendering Engine (Functional Description)
The speed of Sorterr is derived from an aggressive, predictive background processing system.

### 9.1 Background Thumbnail Generation
*   The moment a folder is selected, a silent background engine begins scanning every supported image file.
*   It generates lightweight miniature versions of every image and stores them in a hidden, temporary cache folder.
*   A subtle progress bar in the HUD shows this generation progress. Because it happens in the background, the user can begin culling the first few images immediately, while the rest of the folder is processed silently.

### 9.2 Predictive Preloading (The "Look-Ahead" Cache)
*   The application maintains a rolling "window" of memory surrounding the user's current position.
*   If the user is looking at Image 10, the system automatically loads Images 11, 12, 13 (configurable look-ahead) and Image 9 (look-behind) into the computer's fastest memory tier.
*   When the user presses 'Next', Image 11 is already fully loaded and appears instantaneously. The system then drops Image 9 from memory and silently loads Image 14 in the background.
*   This predictive engine completely masks the time it takes to decode massive, complex RAW files.

### 9.3 Professional Format Support
*   The system includes a dedicated decoding engine capable of reading proprietary camera manufacturer formats without requiring the user to install third-party codecs or operating system extensions.
*   It automatically applies native camera white balance and color profiles to ensure the previews look natural and accurate to the scene.

---

## 10. Customization & Accessibility
Sorterr is designed to adapt to the user's established muscle memory, not the other way around.

### 10.1 The Keybind Remapper
*   Accessible via the Settings modal, every primary action (Next, Previous, Pick, Reject, Cycle Layouts, Open Folder) can be custom-mapped.
*   The interface utilizes a "listening" state: the user clicks the action they want to change, the UI prompts them to "Press Key," and the very next key they touch is instantly mapped to that action.
*   It supports complex keys, including arrows, letters, and non-standard symbols.
*   A "Reset to Defaults" button is always available to revert to the factory configuration safely.

### 10.2 Threshold Sliders
*   The Settings modal provides interactive sliders to adjust the core engine variables.
*   Users can dial in the exact number of images the Predictive Preloader should hold in memory (balancing speed against system RAM usage).
*   Users can adjust the exact seconds and image counts required to trigger the Time and Burst Smart Grouping dividers.
*   All slider adjustments are applied and saved instantly without requiring a restart.

---

## 11. Known Operational Caveats & Limitations
While highly optimized, the current architecture has several structural limitations that users must navigate:

### 11.1 Duplicate Naming Conflicts & Metadata Loss
*   **The Scenario:** A user imports photos from two different cameras into the same folder, resulting in two distinct images both named `DSC_0001.JPG`.
*   **The Issue:** When moving these files into the "Picks" folder, the operating system would normally overwrite one file with the other. Sorterr prevents this by intelligently renaming the second file to `DSC_0001_1.JPG` during the move.
*   **The Caveat:** The application's internal metadata tracking system organizes ratings and tags based strictly on the *original filename*. Because the physical file was renamed during the move, the tracking system loses the connection. The file is safely moved, but any star ratings or color tags applied before the move are silently orphaned and lost.

### 11.2 Infinite Metadata Bloat ("Ghost Entries")
*   **The Scenario:** A user opens a folder of 1,000 images, rates several of them, and then decides to delete 500 of those images using their computer's standard file explorer (outside of Sorterr).
*   **The Issue:** Sorterr's hidden tracking file does not synchronize backward with the file system. It retains the ratings and tags for all 1,000 images forever, even though 500 of them no longer exist. Over months of heavy use and file management, these hidden tracking files can become bloated with obsolete data.

### 11.3 Fixed Communication Channels (Port Conflicts)
*   **The Architecture:** Sorterr is uniquely built as two separate programs running invisibly in tandem: a display interface and a high-speed file delivery engine. They communicate using specific, hardcoded internal addresses on the computer.
*   **The Issue:** If the user happens to have another application running (like a web development tool, a local server, or even another instance of Sorterr that crashed) that is currently occupying those specific addresses, Sorterr will silently fail to launch, presenting the user with a blank screen or a connection error, requiring manual troubleshooting.

### 11.4 Preview Resolution vs. Critical Focus
*   **The Architecture:** To achieve its zero-lag navigation guarantee when dealing with massive 50+ megapixel RAW files, the decoding engine processes the files at exactly half of their native resolution.
*   **The Issue:** While this makes the application incredibly fast and the images look fantastic when fit to the screen, zooming in to 100% reveals a softer, lower-resolution image than the original file contains. This makes it difficult for a professional to confidently verify exact pixel-level critical focus without relying on slower, heavier editing software.

### 11.5 Settings Volatility
*   **The Architecture:** Sorterr leverages standard internet browser technology to render its highly responsive interface. Consequently, it saves user preferences (keybinds, smart grouping thresholds, and recent project history) in the browser's temporary storage cache.
*   **The Issue:** If the user routinely clears their browser history and cache for privacy reasons, or runs system optimization software (like CCleaner), Sorterr's settings are completely wiped out, returning the application to a factory-fresh state on the next launch.

### 11.6 Rigid Extensibility (XMP Handling)
*   **The Architecture:** When generating the synchronization sidecar files, Sorterr uses a rigid, text-replacement method rather than understanding the complex structural language of the file.
*   **The Issue:** While fast and perfectly functional for Sorterr's own data, if the image already had a highly complex sidecar file attached to it (containing GPS data, copyright information, or advanced editing masks), Sorterr's rigid updating method risks corrupting the formatting of that external data.

---

## 12. The "Next Generation" Blueprint (Recreation Plan)
To evolve Sorterr from a highly functional utility into a flawless, enterprise-grade professional tool, the entire architecture must be rebuilt to address current limitations while expanding its core capabilities.

### Phase 1: Absolute Data Integrity & Stability Redesign
*   **Advanced File Fingerprinting (Replacing Filename Tracking):** The foundational data structure must be completely rewritten. Instead of tracking data by a fragile filename, the system will calculate a unique digital fingerprint (hash) based on the file's contents and absolute location. This guarantees that files can be renamed, moved, or duplicated without ever losing their associated ratings, tags, or culling status.
*   **System-Level Configuration Architecture:** All user settings, keybinds, and historical data will be aggressively migrated out of volatile browser storage and secured in a dedicated, system-level configuration file located in the user's permanent application data directory. This ensures preferences survive browser clearings, uninstalls, and system updates.
*   **Dynamic Resource Allocation Engine:** The startup sequence will be completely overhauled. Instead of relying on fixed communication channels, the application will actively scan the computer's network environment upon launch, automatically locating and securing safe, unused channels. This will eliminate "address in use" launch failures entirely.

### Phase 2: Professional Image Pipeline Upgrades
*   **Two-Stage High-Fidelity Rendering System:** To solve the "Preview Resolution vs. Critical Focus" dilemma without sacrificing speed, the rendering pipeline will be split into two parallel tracks.
    1.  **Track 1 (Instantaneous):** Loads the lightning-fast, half-resolution preview exactly as it does now to maintain the zero-lag navigation guarantee.
    2.  **Track 2 (Silent Upgrade):** The moment the fast preview is displayed, a background process begins decoding the full, 100% native resolution image. If the user decides to zoom in, the system instantly swaps the fast preview for the high-fidelity render, allowing for perfect, pixel-peeping focus verification.
*   **Dedicated Worker Pools:** The background processing engine (which generates thumbnails and sidecars) will be isolated into a dedicated, multi-lane "worker pool." This ensures that no matter how massive the folder or how complex the RAW files, the primary user interface never drops a frame or experiences a micro-stutter.

### Phase 3: Workflow, Efficiency, & Interaction Enhancements
*   **Synchronized Multi-Zoom & Pan (Compare Mode 2.0):** The zooming engine will be heavily upgraded to support complex, multi-viewport synchronization. While in Split or Grid view, a user zooming into the bottom-right corner of one image will cause all other visible images to zoom and pan to the exact same relative coordinates simultaneously. This is the ultimate tool for comparing focus points across a high-speed burst sequence.
*   **Advanced Parameter Search & Filtering Engine:** The simple toggle filters will be replaced with a robust query engine. Users will be able to stack logic to filter their workspace (e.g., "Show me only images with a Green Tag AND 4+ stars AND captured on a Tuesday AND with an ISO over 1600").
*   **Frictionless Onboarding (Drag-and-Drop):** The operating system integration will be enhanced to allow users to bypass the interface entirely. Dragging a folder of images directly from the desktop onto the Sorterr application icon or window will instantly launch the app and begin the caching process.
*   **Auto-Advance Flow States:** A highly requested user preference will be introduced to dictate the mechanical flow of culling. When enabled, the application will automatically jump to the next consecutive image the instant a "Pick" or "Reject" action is registered, physically removing one keystroke from every decision made and dramatically increasing overall processing speed.

### Phase 4: Aesthetic, Interface, & Extensibility Refinement
*   **Comprehensive Native Theme Engine:** The user interface will be upgraded to support a full CSS-variable driven theme engine. This will provide seamless integration with the user's operating system preferences, natively supporting Dark Mode, Light Mode, and critical High-Contrast accessibility modes, reducing eye strain during marathon culling sessions.
*   **Hardware-Accelerated Fluid Animations:** The jarring, instantaneous layout cuts will be replaced with subtle, hardware-accelerated animations. Transitioning from a Grid view to a Single view will smoothly animate the selected image to fill the screen. Thumbnails will scroll with momentum, and feedback overlays will fade organically, providing a significantly more premium, cohesive, and modern user experience.
*   **Intelligent XML Parsing for Sidecars:** The rigid text-replacement method for updating sidecar files will be replaced with a full, intelligent XML parsing library. This ensures that Sorterr can safely inject its ratings and tags into existing, highly complex sidecar files (containing GPS, copyright, or advanced masking data) without any risk of corrupting the external data structures.
