@echo off
setlocal EnableDelayedExpansion

:: 使用GBK编码避免中文乱码
chcp 936 >nul 2>&1

title GROMACS GUI 打包工具

:: 获取脚本所在目录（处理中文路径和空格）
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ============================================
echo GROMACS GUI v4.2 打包工具
echo ============================================
echo.

:: 定义目录
set "SOURCE_DIR=%SCRIPT_DIR%\source"
set "DIST_DIR=%SCRIPT_DIR%\dist"
set "ICON=%SCRIPT_DIR%\resources\app_icon.ico"
set "BUILD_LOG=%SCRIPT_DIR%\build.log"

:: 前置校验
echo [1/5] 执行前置校验...

:: 校验Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python未安装或未添加到PATH环境变量
    echo     请先安装Python 3.10+并添加到系统PATH
    pause
    exit /b 1
)
echo   [OK] Python环境正常

:: 校验PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [X] PyInstaller未安装
    echo     请先执行: pip install pyinstaller
    pause
    exit /b 1
)
echo   [OK] PyInstaller已安装

:: 校验主程序文件
if not exist "%SOURCE_DIR%\gromacs_gui_v4.py" (
    echo [X] 主程序文件不存在: %SOURCE_DIR%\gromacs_gui_v4.py
    pause
    exit /b 1
)
echo   [OK] 主程序文件存在

:: 清理旧构建文件
echo.
echo [2/5] 清理旧构建文件...
if exist "%DIST_DIR%" rd /S /Q "%DIST_DIR%"
if exist "%SCRIPT_DIR%\build" rd /S /Q "%SCRIPT_DIR%\build"
if exist "%SOURCE_DIR%\build" rd /S /Q "%SOURCE_DIR%\build"
if exist "%SOURCE_DIR%\dist" rd /S /Q "%SOURCE_DIR%\dist"
if exist "%SOURCE_DIR%\*.spec" del /F /Q "%SOURCE_DIR%\*.spec"
if exist "%SCRIPT_DIR%\build" rd /S /Q "%SCRIPT_DIR%\build"
mkdir "%DIST_DIR%" 2>nul
echo   [OK] 清理完成

:: 执行打包
echo.
echo [3/5] 正在编译打包（需要2-5分钟）...
echo   输出目录: %DIST_DIR%
echo   日志文件: %BUILD_LOG%
echo.

cd /d "%SOURCE_DIR%"

:: 构建PyInstaller命令
set "PYI_CMD=pyinstaller --noconfirm --onefile --windowed"
set "PYI_CMD=!PYI_CMD! --name GROMACS_GUI_v42"
if exist "%ICON%" (
    set "PYI_CMD=!PYI_CMD! --icon "%ICON%""
)
set "PYI_CMD=!PYI_CMD! --hidden-import=PyQt5.QtCore"
set "PYI_CMD=!PYI_CMD! --hidden-import=PyQt5.QtGui"
set "PYI_CMD=!PYI_CMD! --hidden-import=PyQt5.QtWidgets"
set "PYI_CMD=!PYI_CMD! --hidden-import=PyQt5.sip"
set "PYI_CMD=!PYI_CMD! --hidden-import=numpy"
set "PYI_CMD=!PYI_CMD! --hidden-import=psutil"
set "PYI_CMD=!PYI_CMD! --clean"
set "PYI_CMD=!PYI_CMD! --log-level WARN"
set "PYI_CMD=!PYI_CMD! gromacs_gui_v4.py"

echo 执行命令: !PYI_CMD!
echo.
!PYI_CMD! > "%BUILD_LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo [X] 打包失败！
    echo [X] 详细日志: %BUILD_LOG%
    echo.
    echo [错误摘要]:
    powershell -Command "Get-Content '%BUILD_LOG%' -Tail 20"
    pause
    exit /b 1
)

:: 移动输出文件
echo.
echo [4/5] 整理打包产物...
if exist "%SOURCE_DIR%\dist\GROMACS_GUI_v42.exe" (
    move /Y "%SOURCE_DIR%\dist\GROMACS_GUI_v42.exe" "%DIST_DIR%\GROMACS_GUI_v4.2.exe" >nul
    echo   [OK] 可执行文件已输出
) else (
    echo [X] 未找到打包输出的exe文件
    echo [X] 请检查日志: %BUILD_LOG%
    pause
    exit /b 1
)

:: 复制必要文件
echo   复制资源文件...
if exist "%SCRIPT_DIR%\resources" (
    xcopy /E /I /Y "%SCRIPT_DIR%\resources" "%DIST_DIR%\resources" >nul 2>&1
)
if exist "%SCRIPT_DIR%\config" (
    xcopy /E /I /Y "%SCRIPT_DIR%\config" "%DIST_DIR%\config" >nul 2>&1
)

:: 复制GROMACS版本（可选）
echo   复制GROMACS版本...
if exist "%SCRIPT_DIR%\gromacs" (
    for /d %%G in ("%SCRIPT_DIR%\gromacs\*") do (
        if exist "%%G\bin\gmx.exe" (
            xcopy /E /I /Y "%%G" "%DIST_DIR%\gromacs\%%~nG" >nul 2>&1
        )
    )
)

:: 创建启动脚本
echo   创建启动脚本...
(
echo @echo off
echo chcp 65001 ^>nul
echo set "APP_DIR=%%~dp0"
echo set "PATH=%%APP_DIR%%gromacs\gromacs-2026.3-AVX512-CUDA-sm120-fixed\bin;%%PATH%%"
echo start "" "%%APP_DIR%%GROMACS_GUI_v4.2.exe" %%*
) > "%DIST_DIR%\启动程序.bat"

:: 清理临时文件
if exist "%SOURCE_DIR%\build" rd /S /Q "%SOURCE_DIR%\build"
if exist "%SOURCE_DIR%\dist" rd /S /Q "%SOURCE_DIR%\dist"
if exist "%SOURCE_DIR%\*.spec" del /F /Q "%SOURCE_DIR%\*.spec"
if exist "%SCRIPT_DIR%\build" rd /S /Q "%SCRIPT_DIR%\build"

:: 创建压缩包
echo   创建发布压缩包...
powershell -Command "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%DIST_DIR%\..\GROMACS_GUI_v4.2_Release.zip' -Force" >nul 2>&1

:: 输出结果
echo.
echo ============================================
echo 打包完成！
echo ============================================
echo.
echo 输出文件:
echo   - %DIST_DIR%\GROMACS_GUI_v4.2.exe
echo   - %DIST_DIR%\..\GROMACS_GUI_v4.2_Release.zip
echo   - %BUILD_LOG%
echo.
pause