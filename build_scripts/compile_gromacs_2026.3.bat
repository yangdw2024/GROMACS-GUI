@echo off
setlocal

echo [1/3] Setting up Visual Studio environment...
call "D:\Microsoft Visual Studio\VC\Auxiliary\Build\vcvars64.bat"

echo [2/3] Setting up CUDA environment...
set CUDA_PATH=D:\NVIDIA_CUDA_Toolkit
set PATH=D:\YDW\Trae_Gromacs\miniconda3\Library\bin;D:\NVIDIA_CUDA_Toolkit\bin;%PATH%
set LIB=D:\NVIDIA_CUDA_Toolkit\lib\x64;%LIB%
set INCLUDE=D:\NVIDIA_CUDA_Toolkit\include;%INCLUDE%

echo [3/3] Compiling GROMACS 2026.3...
cd /d "D:\YDW\Trae_Gromacs\gromacs\build-2026.3-AVX512-CUDA"

echo Starting build... This may take 30-60 minutes.
"D:\YDW\Trae_Gromacs\miniconda3\Library\bin\ninja.exe" install

echo.
echo Compilation complete. Exit code: %ERRORLEVEL%
endlocal
