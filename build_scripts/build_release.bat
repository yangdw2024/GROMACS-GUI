@echo off
setlocal EnableDelayedExpansion

chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "SCRIPT_DIR=%SCRIPT_DIR%\.."
for /f "delims=" %%a in ("%SCRIPT_DIR%") do set "SCRIPT_DIR=%%~fa"

set "VERSION_CONFIG=%SCRIPT_DIR%\version.config"
if not exist "%VERSION_CONFIG%" (
    echo [ERROR] version.config not found: %VERSION_CONFIG%
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('powershell -Command "(Get-Content '%VERSION_CONFIG%' -Raw | ConvertFrom-Json).version_string"') do (
    set "APP_VERSION=%%a"
)

for /f "tokens=*" %%a in ('powershell -Command "(Get-Content '%VERSION_CONFIG%' -Raw | ConvertFrom-Json).product_name"') do (
    set "PRODUCT_NAME=%%a"
)

echo ============================================
echo %PRODUCT_NAME%
echo Version: %APP_VERSION%
echo ============================================
echo.

set "SOURCE_DIR=%SCRIPT_DIR%\source"
set "RELEASE_DIR=%SCRIPT_DIR%\release"
set "DIST_DIR=%SCRIPT_DIR%\dist"
set "ICON=%SCRIPT_DIR%\resources\app_icon.ico"
set "BUILD_LOG=%SCRIPT_DIR%\build.log"

echo [1/5] Pre-checks...

python --version >nul 2>&1
if errorlevel 1 (
    set "PYTHON_EXE=%SCRIPT_DIR%\miniconda3\python.exe"
    if not exist "%PYTHON_EXE%" (
        echo [ERROR] Python not found
        pause
        exit /b 1
    )
) else (
    set "PYTHON_EXE=python.exe"
)
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python environment abnormal
    pause
    exit /b 1
)
echo   [OK] Python

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    "%PYTHON_EXE%" -m pyinstaller --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] PyInstaller not installed
        pause
        exit /b 1
    )
    set "PYI_CMD_PREFIX=%PYTHON_EXE% -m pyinstaller"
) else (
    set "PYI_CMD_PREFIX=pyinstaller"
)
echo   [OK] PyInstaller

if not exist "%SOURCE_DIR%\gromacs_gui_v4.py" (
    echo [ERROR] Main file not found: %SOURCE_DIR%\gromacs_gui_v4.py
    pause
    exit /b 1
)
echo   [OK] Main file

if not exist "%SCRIPT_DIR%\resources" (
    echo [WARN] resources missing
    set "ICON="
)

if not exist "%SCRIPT_DIR%\gromacs" (
    echo [WARN] gromacs dir missing
)

echo.
echo [2/5] Cleaning old builds...
if exist "%RELEASE_DIR%" rd /S /Q "%RELEASE_DIR%"
if exist "%DIST_DIR%" rd /S /Q "%DIST_DIR%"
if exist "%SCRIPT_DIR%\build" rd /S /Q "%SCRIPT_DIR%\build"
if exist "%SOURCE_DIR%\build" rd /S /Q "%SOURCE_DIR%\build"
if exist "%SOURCE_DIR%\dist" rd /S /Q "%SOURCE_DIR%\dist"
if exist "%SOURCE_DIR%\*.spec" del /F /Q "%SOURCE_DIR%\*.spec"
mkdir "%RELEASE_DIR%" 2>nul
echo   [OK] Cleaned

echo.
echo [3/5] Creating version info...
powershell -Command "$v=Get-Content '%VERSION_CONFIG%' -Raw | ConvertFrom-Json; $v | ConvertTo-Json -Depth 10 | Out-File -Encoding UTF8 '%SOURCE_DIR%\version_info.json'"
echo   [OK] version_info.json

echo.
echo [4/5] Building (2-5 min)...
echo   Output: %RELEASE_DIR%\%PRODUCT_NAME%%APP_VERSION%.exe
echo   Log:    %BUILD_LOG%
echo.

cd /d "%SOURCE_DIR%"

set "PYI_CMD=%PYI_CMD_PREFIX% --noconfirm --onefile --windowed"
set "PYI_CMD=%PYI_CMD% --name %PRODUCT_NAME%%APP_VERSION%"
if exist "%ICON%" (
    set "PYI_CMD=%PYI_CMD% --icon %ICON%"
)
set "PYI_CMD=%PYI_CMD% --add-data version_info.json;."
set "PYI_CMD=%PYI_CMD% --add-data core;core"
set "PYI_CMD=%PYI_CMD% --add-data config;config"
set "PYI_CMD=%PYI_CMD% --add-data ..\resources;resources"
set "PYI_CMD=%PYI_CMD% --hidden-import=PyQt5.QtCore"
set "PYI_CMD=%PYI_CMD% --hidden-import=PyQt5.QtGui"
set "PYI_CMD=%PYI_CMD% --hidden-import=PyQt5.QtWidgets"
set "PYI_CMD=%PYI_CMD% --hidden-import=PyQt5.sip"
set "PYI_CMD=%PYI_CMD% --hidden-import=numpy"
set "PYI_CMD=%PYI_CMD% --hidden-import=psutil"
set "PYI_CMD=%PYI_CMD% --clean"
set "PYI_CMD=%PYI_CMD% --log-level WARN"
set "PYI_CMD=%PYI_CMD% gromacs_gui_v4.py"

echo Command: %PYI_CMD%
%PYI_CMD% > "%BUILD_LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    echo [ERROR] Log: %BUILD_LOG%
    echo.
    powershell -Command "Get-Content '%BUILD_LOG%' -Tail 20"
    pause
    exit /b 1
)

echo.
echo [5/5] Packaging...
if exist "%SOURCE_DIR%\dist\%PRODUCT_NAME%%APP_VERSION%.exe" (
    move /Y "%SOURCE_DIR%\dist\%PRODUCT_NAME%%APP_VERSION%.exe" "%RELEASE_DIR%\" >nul
    echo   [OK] exe output
) else (
    echo [ERROR] exe not found
    pause
    exit /b 1
)

echo   Copying config...
if exist "%SCRIPT_DIR%\source\config" (
    xcopy /E /I /Y "%SCRIPT_DIR%\source\config" "%RELEASE_DIR%\config" >nul 2>&1
) else if exist "%SCRIPT_DIR%\config" (
    xcopy /E /I /Y "%SCRIPT_DIR%\config" "%RELEASE_DIR%\config" >nul 2>&1
)
echo   Copying resources...
xcopy /E /I /Y "%SCRIPT_DIR%\resources" "%RELEASE_DIR%\resources" >nul 2>&1
echo   Copying docs...
copy /Y "%SCRIPT_DIR%\version.config" "%RELEASE_DIR%\" >nul
copy /Y "%SCRIPT_DIR%\说明书.md" "%RELEASE_DIR%\" >nul 2>&1

echo   Creating launcher...
(
echo @echo off
echo chcp 65001 ^>nul
echo set "APP_DIR=%%~dp0"
echo set "PATH=%%APP_DIR%%gromacs;%%PATH%%"
echo start "" "%%APP_DIR%%%PRODUCT_NAME%%APP_VERSION%.exe" %%*
) > "%RELEASE_DIR%\启动程序.bat"

if exist "%SOURCE_DIR%\build" rd /S /Q "%SOURCE_DIR%\build"
if exist "%SOURCE_DIR%\dist" rd /S /Q "%SOURCE_DIR%\dist"
if exist "%SOURCE_DIR%\*.spec" del /F /Q "%SOURCE_DIR%\*.spec"
if exist "%SCRIPT_DIR%\build" rd /S /Q "%SCRIPT_DIR%\build"

echo   Creating zip...
powershell -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%RELEASE_DIR%\..\%PRODUCT_NAME%%APP_VERSION%_Release.zip' -Force" >nul 2>&1

echo   Archiving backup...
set "BACKUP_DIR=%SCRIPT_DIR%\archives\release_backup"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%" 2>nul
for /f "tokens=*" %%t in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TIMESTAMP=%%t"
set "BACKUP_NAME=%PRODUCT_NAME%%APP_VERSION%_%TIMESTAMP%.zip"
powershell -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%BACKUP_DIR%\%BACKUP_NAME%' -Force" >nul 2>&1
if exist "%BACKUP_DIR%\%BACKUP_NAME%" (
    echo   [OK] Archived: %BACKUP_NAME%
) else (
    echo   [WARN] Archive failed
)

for /f "tokens=*" %%c in ('powershell -Command "(Get-Content '%VERSION_CONFIG%' -Raw | ConvertFrom-Json).backup_max_count"') do (
    set "BACKUP_MAX=%%c"
)
if not defined BACKUP_MAX set "BACKUP_MAX=5"
echo   Cleaning old backups (max %BACKUP_MAX%)...
powershell -Command "$files = Get-ChildItem '%BACKUP_DIR%\*.zip' | Sort-Object LastWriteTime -Descending; if ($files.Count -gt %BACKUP_MAX%) { $files | Select-Object -Skip %BACKUP_MAX% | Remove-Item -Force; Write-Output ('  Removed ' + ($files.Count - %BACKUP_MAX%) + ' old backups') } else { Write-Output '  No cleanup needed' }"

echo.
echo ============================================
echo Build complete!
echo ============================================
echo.
echo Output:
echo   exe: %RELEASE_DIR%\%PRODUCT_NAME%%APP_VERSION%.exe
echo   zip: %RELEASE_DIR%\..\%PRODUCT_NAME%%APP_VERSION%_Release.zip
echo   log: %BUILD_LOG%
echo.
echo Release dir:
echo   %RELEASE_DIR%\
echo     %PRODUCT_NAME%%APP_VERSION%.exe
echo     启动程序.bat
echo     version.config
echo     config\
echo     resources\
echo.
pause
