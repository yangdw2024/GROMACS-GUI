cd "d:\YDW\Trae_Gromacs\test\test_water_system"

Write-Host "=== Testing gromacs-2026.3-AVX512-CUDA-sm120 (CPU only) ==="
& "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120\bin\gmx.exe" mdrun -s em_test2.tpr -deffnm em_test2_cpu -nt 4
if ($LASTEXITCODE -ne 0) { Write-Host "mdrun CPU FAILED"; exit }
Write-Host "mdrun CPU SUCCESS"

Write-Host ""
Write-Host "=== Testing gromacs-2026.3-AVX512-CUDA-sm120 (GPU) ==="
& "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120\bin\gmx.exe" mdrun -s em_test2.tpr -deffnm em_test2_gpu -nt 4 -gpu_id 0 -nb gpu -pme cpu
if ($LASTEXITCODE -ne 0) { Write-Host "mdrun GPU FAILED"; exit }
Write-Host "mdrun GPU SUCCESS"

Write-Host ""
Write-Host "=== TEST COMPLETED ==="