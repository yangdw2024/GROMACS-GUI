@echo off
echo ============================================
echo 编译 GROMACS 2026.3 AVX-512 + CUDA + PLUMED
echo ============================================
echo.

setlocal enabledelayedexpansion

set "GMX_SOURCE=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3"
set "GMX_BUILD=D:\YDW\Trae_Gromacs\gromacs\build-2026.3-AVX512-CUDA-PLUMED"
set "GMX_INSTALL=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED"

echo 源目录: %GMX_SOURCE%
echo 构建目录: %GMX_BUILD%
echo 安装目录: %GMX_INSTALL%
echo.

if not exist "%GMX_BUILD%" mkdir "%GMX_BUILD%"
cd /d "%GMX_BUILD%"

echo ============================================
echo 配置环境变量
echo ============================================

set "PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64;D:\Windows Kits\10\bin\10.0.26100.0\x64;D:\Windows Kits\10\bin\x64;"
set "LIB=D:\NVIDIA_CUDA_Toolkit\lib\x64;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\lib\x64;D:\Windows Kits\10\lib\10.0.26100.0\um\x64;D:\Windows Kits\10\lib\10.0.26100.0\ucrt\x64;"
set "INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\include;D:\Windows Kits\10\include\10.0.26100.0\ucrt;D:\Windows Kits\10\include\10.0.26100.0\um;D:\Windows Kits\10\include\10.0.26100.0\shared;"

echo ============================================
echo 运行CMake配置
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\cmake.exe" ^
  "%GMX_SOURCE%" ^
  -G "Ninja" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGMX_SIMD=AVX_512 ^
  -DGMX_GPU=CUDA ^
  -DCMAKE_CUDA_ARCHITECTURES="89;90" ^
  -DGMX_FFT_LIBRARY=fftpack ^
  -DGMX_BUILD_SHARED_LIBS=OFF ^
  -DGMX_MPI=OFF ^
  -DGMX_OPENMP=ON ^
  -DGMX_HWLOC=OFF ^
  -DGMX_USE_PLUMED=ON ^
  -DCMAKE_INSTALL_PREFIX="%GMX_INSTALL%"

if %errorlevel% neq 0 (
    echo CMake配置失败
    pause
    exit /b %errorlevel%
)

echo ============================================
echo 开始编译
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" -j 8

if %errorlevel% neq 0 (
    echo 编译失败
    pause
    exit /b %errorlevel%
)

echo ============================================
echo 安装
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" install

if %errorlevel% neq 0 (
    echo 安装失败
    pause
    exit /b %errorlevel%
)

echo ============================================
echo 复制CUDA DLL
echo ============================================

xcopy /Y "D:\NVIDIA_CUDA_Toolkit\bin\x64\*.dll" "%GMX_INSTALL%\bin\"

echo ============================================
echo 复制dl.dll和libplumedKernel.dll (PLUMED需要)
echo ============================================

copy /Y "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.1-plumed-CUDA\bin\dl.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.1-plumed-CUDA\bin\fftw3f.dll" "%GMX_INSTALL%\bin\"

echo ============================================
echo 编译完成！
echo ============================================
echo 安装目录: %GMX_INSTALL%
echo.
"%GMX_INSTALL%\bin\gmx.exe" --version
pause