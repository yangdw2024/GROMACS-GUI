@echo off
setlocal

echo [1/5] Setting up Visual Studio environment...
call "D:\Microsoft Visual Studio\VC\Auxiliary\Build\vcvars64.bat"

echo [2/5] Setting up CUDA environment...
set CUDA_PATH=D:\NVIDIA_CUDA_Toolkit
set PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;%PATH%

echo [3/5] Setting up build directory...
cd /d "D:\YDW\Trae_Gromacs\gromacs"
if exist "build-2026.3-AVX512-CUDA-sm120-final2" rmdir /s /q "build-2026.3-AVX512-CUDA-sm120-final2"
mkdir build-2026.3-AVX512-CUDA-sm120-final2
cd build-2026.3-AVX512-CUDA-sm120-final2

echo [4/5] Running CMake configuration with Ninja...
"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\cmake.exe" ^
  "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3" ^
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
  -DCMAKE_C_FLAGS_RELEASE="/arch:AVX512" ^
  -DCMAKE_CXX_FLAGS_RELEASE="/arch:AVX512" ^
  -DCMAKE_INSTALL_PREFIX="D:/YDW/Trae_Gromacs/gromacs/gromacs-2026.3-AVX512-CUDA-sm120-final2"

echo.
echo CMake configuration complete. Exit code: %ERRORLEVEL%
if %errorlevel% neq 0 (
    pause
    exit /b %errorlevel%
)

echo [5/5] Building and installing...
"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" -j 8
if %errorlevel% neq 0 (
    echo Build failed
    pause
    exit /b %errorlevel%
)

"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" install
if %errorlevel% neq 0 (
    echo Install failed
    pause
    exit /b %errorlevel%
)

xcopy /Y "D:\NVIDIA_CUDA_Toolkit\bin\x64\*.dll" "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\"

echo.
echo Build complete!
"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\gmx.exe" --version
pause