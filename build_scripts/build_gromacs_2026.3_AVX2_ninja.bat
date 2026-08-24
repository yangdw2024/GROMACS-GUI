@echo off
setlocal

echo [1/4] Setting up Visual Studio environment...
call "D:\Microsoft Visual Studio\VC\Auxiliary\Build\vcvars64.bat"

echo [2/4] Setting up CUDA environment...
set CUDA_PATH=D:\NVIDIA_CUDA_Toolkit
set PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;%PATH%
set LIB=D:\NVIDIA_CUDA_Toolkit\lib\x64;%LIB%
set INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;%INCLUDE%

echo [3/4] Setting up build directory...
cd /d "D:\YDW\Trae_Gromacs\gromacs"
if exist "build-2026.3-AVX2-CUDA" rmdir /s /q "build-2026.3-AVX2-CUDA"
if not exist "build-2026.3-AVX2-CUDA" mkdir build-2026.3-AVX2-CUDA
cd build-2026.3-AVX2-CUDA

echo [4/4] Running CMake configuration with Ninja (AVX2_256)...
"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\cmake.exe" ^
  "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3" ^
  -G "Ninja" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGMX_SIMD=AVX2_256 ^
  -DGMX_GPU=CUDA ^
  -DCMAKE_CUDA_ARCHITECTURES="89;90" ^
  -DGMX_FFT_LIBRARY=fftpack ^
  -DGMX_BUILD_SHARED_LIBS=OFF ^
  -DGMX_MPI=OFF ^
  -DGMX_OPENMP=ON ^
  -DGMX_HWLOC=OFF ^
  -DGMX_USE_PLUMED=OFF ^
  -DCMAKE_INSTALL_PREFIX="D:/YDW/Trae_Gromacs/gromacs/gromacs-2026.3-AVX2-CUDA"

echo.
echo CMake configuration complete. Exit code: %ERRORLEVEL%
endlocal
pause