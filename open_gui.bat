@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 video_to_gif_gui.py
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python video_to_gif_gui.py
    goto :eof
)

echo Python was not found. Install Python 3 and try again.
pause
