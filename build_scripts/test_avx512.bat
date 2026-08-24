cd /d "d:\YDW\Trae_Gromacs\test\test_simple"

echo === Testing gromacs-2026.3-AVX512-CUDA ===
"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA\bin\gmx.exe" grompp -f em.mdp -c processed.gro -p topol.top -o em_test1.tpr -maxwarn 2
if %errorlevel% neq 0 echo grompp FAILED & goto end
echo grompp SUCCESS

"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA\bin\gmx.exe" mdrun -s em_test1.tpr -deffnm em_test1 -nt 4 -gpu_id 0 -nb gpu -pme cpu
if %errorlevel% neq 0 echo mdrun FAILED & goto end
echo mdrun SUCCESS

echo.
echo === Testing gromacs-2026.3-AVX512-CUDA-sm120 ===
"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120\bin\gmx.exe" grompp -f em.mdp -c processed.gro -p topol.top -o em_test2.tpr -maxwarn 2
if %errorlevel% neq 0 echo grompp FAILED & goto end
echo grompp SUCCESS

"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120\bin\gmx.exe" mdrun -s em_test2.tpr -deffnm em_test2 -nt 4 -gpu_id 0 -nb gpu -pme cpu
if %errorlevel% neq 0 echo mdrun FAILED & goto end
echo mdrun SUCCESS

echo.
echo === Testing gromacs-2026.3-AVX512-CUDA-PLUMED ===
"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED\bin\gmx.exe" grompp -f em.mdp -c processed.gro -p topol.top -o em_test3.tpr -maxwarn 2
if %errorlevel% neq 0 echo grompp FAILED & goto end
echo grompp SUCCESS

"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED\bin\gmx.exe" mdrun -s em_test3.tpr -deffnm em_test3 -nt 4 -gpu_id 0 -nb gpu -pme cpu
if %errorlevel% neq 0 echo mdrun FAILED & goto end
echo mdrun SUCCESS

echo.
echo === ALL TESTS PASSED ===
:end
pause