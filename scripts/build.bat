pushd "%~dp0.."
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate virtual environment.
    echo Run setup first: python -m venv venv ^& venv\Scripts\activate ^& pip install eel pillow rawpy imageio numpy flask exifread pyinstaller
    pause
    exit /b 1
)

echo [1/2] Installing/verifying PyInstaller...
pip install pyinstaller -q

echo [2/2] Building Sorterr-v1.4.exe...
pyinstaller --onefile --windowed ^
    --add-data "web;web" ^
    --collect-all rawpy ^
    --collect-all exifread ^
    --name "Sorterr-v1.4" ^
    --icon "web\favicon.ico" ^
    main.py 2>nul || ^
pyinstaller --onefile --windowed ^
    --add-data "web;web" ^
    --collect-all rawpy ^
    --collect-all exifread ^
    --name "Sorterr-v1.4" ^
    main.py

echo.
echo ============================================================
echo  Build complete! Your exe is in the dist\ folder.
echo ============================================================
popd
