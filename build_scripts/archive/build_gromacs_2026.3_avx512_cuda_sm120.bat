@echo off
chcp 65001 >nul
echo ============================================
echo Build GROMACS 2026.3 AVX-512 + CUDA (sm_120)
echo ============================================
echo.

setlocal enabledelayedexpansion

set "GMX_SOURCE=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3"
set "GMX_BUILD=D:\YDW\Trae_Gromacs\gromacs\build-2026.3-AVX512-CUDA-sm120"
set "GMX_INSTALL=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120"

echo Source: %GMX_SOURCE%
echo Build:  %GMX_BUILD%
echo Install: %GMX_INSTALL%
echo.

if not exist "%GMX_BUILD%" mkdir "%GMX_BUILD%"
cd /d "%GMX_BUILD%"

echo ============================================
echo Environment setup
echo ============================================

set "PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64;D:\Windows Kits\10\bin\10.0.26100.0\x64;D:\Windows Kits\10\bin\x64;"
set "LIB=D:\NVIDIA_CUDA_Toolkit\lib\x64;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\lib\x64;D:\Windows Kits\10\lib\10.0.26100.0\um\x64;D:\Windows Kits\10\lib\10.0.26100.0\ucrt\x64;"
set "INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;D:\Microsoft Visual Studio\VC\Tools\MSVC\14.51.36231\include;D:\Windows Kits\10\include\10.0.26100.0\ucrt;D:\Windows Kits\10\include\10.0.26100.0\um;D:\Windows Kits\10\include\10.0.26100.0\shared;"

echo ============================================
echo CMake configure
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\cmake.exe" ^
  "%GMX_SOURCE%" ^
  -G "Ninja" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGMX_SIMD=AVX_512 ^
  -DGMX_GPU=CUDA ^
  -DCMAKE_CUDA_ARCHITECTURES="89;90;120" ^
  -DGMX_FFT_LIBRARY=fftpack ^
  -DGMX_BUILD_SHARED_LIBS=OFF ^
  -DGMX_MPI=OFF ^
  -DGMX_OPENMP=ON ^
  -DGMX_HWLOC=OFF ^
  -DGMX_USE_PLUMED=OFF ^
  -DCMAKE_INSTALL_PREFIX="%GMX_INSTALL%"

if %errorlevel% neq 0 (
    echo CMake configure FAILED
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Build (16 threads)
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" -j 16

if %errorlevel% neq 0 (
    echo Build FAILED
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Install
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" install

if %errorlevel% neq 0 (
    echo Install FAILED
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Copy CUDA DLLs
echo ============================================

xcopy /Y "D:\NVIDIA_CUDA_Toolkit\bin\x64\*.dll" "%GMX_INSTALL%\bin\"

echo ============================================
echo Build complete!
echo ============================================
echo Install dir: %GMX_INSTALL%
echo.
"%GMX_INSTALL%\bin\gmx.exe" --version
pause
