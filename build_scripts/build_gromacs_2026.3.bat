@echo off
setlocal

echo [1/3] Setting up Visual Studio environment...
call "D:\Microsoft Visual Studio\VC\Auxiliary\Build\vcvars64.bat"

echo [2/3] Setting up CUDA environment...
set CUDA_PATH=D:\NVIDIA_CUDA_Toolkit
set PATH=D:\NVIDIA_CUDA_Toolkit\bin;%PATH%
set LIB=D:\NVIDIA_CUDA_Toolkit\lib\x64;%LIB%
set INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;%INCLUDE%

echo [3/3] Running CMake configuration...
cd /d "D:\YDW\Trae_Gromacs\gromacs\build-2026.3-AVX512-CUDA"

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\cmake.exe" ^
  "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3" ^
  -G "Visual Studio 18 2026" ^
  -A x64 ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGMX_SIMD=AVX_512 ^
  -DGMX_GPU=CUDA ^
  -DCMAKE_CUDA_ARCHITECTURES="89;90;100;120" ^
  -DGMX_FFT_LIBRARY=fftw3 ^
  -DGMX_BUILD_OWN_FFTW=ON ^
  -DGMX_BUILD_SHARED_LIBS=OFF ^
  -DGMX_MPI=OFF ^
  -DGMX_OPENMP=ON ^
  -DGMX_HWLOC=OFF ^
  -DCMAKE_INSTALL_PREFIX="D:/YDW/Trae_Gromacs/gromacs/gromacs-2026.3-AVX512-CUDA"

echo.
echo CMake configuration complete. Exit code: %ERRORLEVEL%
endlocal
