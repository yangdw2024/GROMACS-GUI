@echo off
chcp 65001 >nul
cd /d "D:\YDW\Trae_Gromacs"
set PIP_CACHE_DIR=D:\YDW\Trae_Gromacs\miniconda3\pip_cache
set TEMP=D:\YDW\Trae_Gromacs\temp
set TMP=D:\YDW\Trae_Gromacs\temp
if not exist "D:\YDW\Trae_Gromacs\miniconda3\pip_cache" mkdir "D:\YDW\Trae_Gromacs\miniconda3\pip_cache"
if not exist "D:\YDW\Trae_Gromacs\temp" mkdir "D:\YDW\Trae_Gromacs\temp"

for /f "tokens=*" %%a in ('powershell -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; (Get-Content 'D:\YDW\Trae_Gromacs\version.config' -Encoding UTF8 | ConvertFrom-Json).display_name"') do (
    set "APP_NAME=%%a"
)
for /f "tokens=*" %%a in ('powershell -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; (Get-Content 'D:\YDW\Trae_Gromacs\version.config' -Encoding UTF8 | ConvertFrom-Json).full_version"') do (
    set "APP_VERSION=%%a"
)

echo ============================================
echo   %APP_NAME% %APP_VERSION%
echo   Starting from source code...
echo ============================================
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
"D:\YDW\Trae_Gromacs\miniconda3\python.exe" "D:\YDW\Trae_Gromacs\source\gromacs_gui_v4.py"
pause