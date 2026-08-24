cd "d:\YDW\Trae_Gromacs\test\test_water_system"

Write-Host "=== Testing gromacs-2026.3-AVX512-CUDA-sm120-fixed ==="
& "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-fixed\bin\gmx.exe" --version

Write-Host ""
Write-Host "--- grompp ---"
& "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-fixed\bin\gmx.exe" grompp -f em.mdp -c water_box.gro -p test_top.top -o em_test_fixed.tpr -maxwarn 2
if ($LASTEXITCODE -ne 0) { Write-Host "grompp FAILED"; exit }
Write-Host "grompp SUCCESS"

Write-Host ""
Write-Host "--- mdrun GPU ---"
& "D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-fixed\bin\gmx.exe" mdrun -s em_test_fixed.tpr -deffnm em_test_fixed -nt 4 -gpu_id 0 -nb gpu -pme cpu
if ($LASTEXITCODE -ne 0) { Write-Host "mdrun GPU FAILED"; exit }
Write-Host "mdrun GPU SUCCESS"

Write-Host ""
Write-Host "=== TEST PASSED ==="