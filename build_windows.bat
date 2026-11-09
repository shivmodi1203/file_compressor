@echo off
rem Builds dist\FileCompressor.exe. Run from this folder on a Windows machine.
setlocal

if not exist .venv (
    python -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat || exit /b 1

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed ^
    --name FileCompressor ^
    --icon file_compressor\resources\icon.ico ^
    --add-data "file_compressor\resources;file_compressor\resources" ^
    file_compressor\__main__.py || exit /b 1

echo.
echo Build complete: dist\FileCompressor.exe
