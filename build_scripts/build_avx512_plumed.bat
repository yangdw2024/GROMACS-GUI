@echo off
echo ============================================
echo Build GROMACS 2026.3 AVX-512 + CUDA + PLUMED
echo ============================================
echo.

setlocal enabledelayedexpansion

set "GMX_SOURCE=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3"
set "GMX_BUILD=D:\YDW\Trae_Gromacs\gromacs\build-2026.3-AVX512-CUDA-PLUMED"
set "GMX_INSTALL=D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED"

echo Source: %GMX_SOURCE%
echo Build: %GMX_BUILD%
echo Install: %GMX_INSTALL%
echo.

if exist "%GMX_BUILD%" rmdir /s /q "%GMX_BUILD%"
mkdir "%GMX_BUILD%"
cd /d "%GMX_BUILD%"

echo ============================================
echo Setting Visual Studio environment...
echo ============================================
call "D:\Microsoft Visual Studio\VC\Auxiliary\Build\vcvars64.bat"

echo ============================================
echo Setting CUDA environment...
echo ============================================
set CUDA_PATH=D:\NVIDIA_CUDA_Toolkit
set "PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;%PATH%"
set "LIB=D:\YDW\Trae_Gromacs;D:\NVIDIA_CUDA_Toolkit\lib\x64;%LIB%"
set "INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;%INCLUDE%"

echo ============================================
echo CMake Configuration
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
  -DGMX_USE_PLUMED=ON ^
  -DCMAKE_C_FLAGS_RELEASE="/arch:AVX512" ^
  -DCMAKE_CXX_FLAGS_RELEASE="/arch:AVX512" ^
  -DCMAKE_INSTALL_PREFIX="%GMX_INSTALL%"

if %errorlevel% neq 0 (
    echo CMake failed
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Building...
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" -j 8

if %errorlevel% neq 0 (
    echo Build failed
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Installing...
echo ============================================

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" install

if %errorlevel% neq 0 (
    echo Install failed
    pause
    exit /b %errorlevel%
)

echo ============================================
echo Copy CUDA DLLs
echo ============================================

xcopy /Y "D:\NVIDIA_CUDA_Toolkit\bin\x64\*.dll" "%GMX_INSTALL%\bin\"

echo ============================================
echo Copy PLUMED dependencies
echo ============================================

copy /Y "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.1-plumed-CUDA\bin\dl.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libplumedKernel.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libdl.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libfftw3-3.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libgcc_s_seh-1.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libstdc++-6.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\libwinpthread-1.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\archives\libplumed\libplumedKernel.dll\zlib1.dll" "%GMX_INSTALL%\bin\"
copy /Y "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.1-plumed-CUDA\bin\fftw3f.dll" "%GMX_INSTALL%\bin\"

echo ============================================
echo Done!
echo ============================================
echo Install dir: %GMX_INSTALL%
echo.
"%GMX_INSTALL%\bin\gmx.exe" --version
pause
