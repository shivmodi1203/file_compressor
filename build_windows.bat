@echo off
rem Builds the Windows installer and portable zip into release\. Run from this folder.
rem The installer step needs Inno Setup 6.3+ (https://jrsoftware.org/isdl.php).
setlocal

if not exist .venv (
    python -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat || exit /b 1

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || exit /b 1

python tools\build.py || exit /b 1
