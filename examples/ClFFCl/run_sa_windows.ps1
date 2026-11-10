# ClFFCl SA溶剂蒸发流程 (Windows PowerShell版)
# 注意：运行前请确保已安装Python和GROMACS

# 设置参数
$GMX = "gmx"          # GROMACS命令（如果不在PATH中，需要完整路径如 "C:\Program Files\GROMACS\bin\gmx.exe"）
$PYTHON = "python"    # Python命令
$WORK_DIR = Get-Location
$PREFIX = "ClFFCl"

# 初始文件
$INIT_GRO = "${PREFIX}_npt2.gro"
$INIT_TOP = "p4PM6-ClFFCl-mix.top"
$MDP_FILE = "ydw-npt-sa.mdp"

# 参数设置
$LOOPS = 500          # 蒸发轮数
$DELETE_NUM = 100     # 每轮删除的CF分子数
$ATOMS_PER_CF = 5     # 每个CF分子的原子数
$SOLVENT_NAME = "CF"

# 当前文件
$CURRENT_GRO = $INIT_GRO
$CURRENT_TOP = $INIT_TOP

function Get-TopSolventCount([string]$TopPath, [string]$Solvent) {
    if (-not (Test-Path $TopPath)) {
        throw "拓扑文件不存在: $TopPath"
    }
    $inMolecules = $false
    foreach ($line in Get-Content $TopPath -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[\s*([^\]]+?)\s*\]') {
            $inMolecules = ($Matches[1].Trim().ToLower() -eq 'molecules')
            continue
        }
        if ($inMolecules -and $trimmed -and -not $trimmed.StartsWith(';')) {
            $codePart = ($trimmed -split ';', 2)[0].Trim()
            $parts = $codePart -split '\s+'
            if ($parts.Count -ge 2 -and $parts[0] -eq $Solvent) {
                return [int]$parts[1]
            }
        }
    }
    throw "在 $TopPath 的 [ molecules ] 中未找到溶剂 $Solvent"
}

function Get-GroSolventAtomCount([string]$GroPath, [string]$Solvent) {
    $lines = Get-Content $GroPath -Encoding UTF8
    if ($lines.Count -lt 3) {
        throw "GRO 文件行数不足: $GroPath"
    }
    $numAtoms = [int]($lines[1].Trim())
    if ($lines.Count - 3 -ne $numAtoms) {
        throw "GRO 头部原子数 ($numAtoms) 与实际原子行数 ($($lines.Count - 3)) 不一致: $GroPath"
    }
    $cnt = 0
    for ($idx = 2; $idx -lt (2 + $numAtoms); $idx++) {
        $line = $lines[$idx]
        if ($line.Length -ge 10 -and $line.Substring(5, 5).Trim() -eq $Solvent) {
            $cnt++
        }
    }
    return $cnt
}

foreach ($reqFile in @($CURRENT_GRO, $CURRENT_TOP, $MDP_FILE, "delete_solvent.py")) {
    if (-not (Test-Path $reqFile)) {
        Write-Host "错误: 必需文件未找到: $reqFile" -ForegroundColor Red
        exit 1
    }
}

$CURRENT_SOLVENT_COUNT = Get-TopSolventCount -TopPath $CURRENT_TOP -Solvent $SOLVENT_NAME
$GRO_SOLVENT_ATOMS = Get-GroSolventAtomCount -GroPath $CURRENT_GRO -Solvent $SOLVENT_NAME
$EXPECTED_SOLVENT_ATOMS = $CURRENT_SOLVENT_COUNT * $ATOMS_PER_CF

if ($GRO_SOLVENT_ATOMS -ne $EXPECTED_SOLVENT_ATOMS) {
    Write-Host "错误: $CURRENT_GRO 中 $SOLVENT_NAME 原子数 ($GRO_SOLVENT_ATOMS) 与 $CURRENT_TOP 声明分子数 ($CURRENT_SOLVENT_COUNT * $ATOMS_PER_CF = $EXPECTED_SOLVENT_ATOMS) 不一致！" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ClFFCl SA溶剂蒸发流程 (Windows PowerShell)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "工作目录: $WORK_DIR"
Write-Host "当前 $SOLVENT_NAME 分子数: $CURRENT_SOLVENT_COUNT"
Write-Host "循环次数: $LOOPS"
Write-Host "每轮删除: $DELETE_NUM 个CF分子"
Write-Host ""

for ($i = 1; $i -le $LOOPS; $i++) {
    $CURRENT_DELETE_NUM = [Math]::Min($DELETE_NUM, $CURRENT_SOLVENT_COUNT)
    if ($CURRENT_DELETE_NUM -le 0) {
        Write-Host "循环 $i : 已无 $SOLVENT_NAME 可删，停止。" -ForegroundColor Yellow
        break
    }

    Write-Host "------------ 第 $i / $LOOPS 轮 ------------" -ForegroundColor Yellow

    # 输出文件
    $DEL_GRO = "${PREFIX}_sa_${i}_del.gro"
    $OUT_GRO = "${PREFIX}_sa_$i.gro"
    $OUT_TOP = "${PREFIX}_sa_$i.top"
    $TPR_FILE = "${PREFIX}_sa_$i.tpr"

    Write-Host "Step 1: 删除 $CURRENT_DELETE_NUM 个CF分子..." -ForegroundColor Green

    & $PYTHON delete_solvent.py `
        --solvent $SOLVENT_NAME `
        --delete-num $CURRENT_DELETE_NUM `
        --atoms-per-mol $ATOMS_PER_CF `
        --loop $i `
        --input $CURRENT_GRO `
        --output $DEL_GRO `
        --topology $CURRENT_TOP `
        --topology-output $OUT_TOP

    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 删除溶剂失败！" -ForegroundColor Red
        exit 1
    }

    Write-Host "Step 2: grompp预处理..." -ForegroundColor Green

    & $GMX grompp -f $MDP_FILE -c $DEL_GRO -p $OUT_TOP -o $TPR_FILE -maxwarn 200

    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: grompp失败！" -ForegroundColor Red
        exit 1
    }

    Write-Host "Step 3: mdrun运行模拟..." -ForegroundColor Green

    & $GMX mdrun -v -deffnm "${PREFIX}_sa_$i" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu

    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: mdrun失败！" -ForegroundColor Red
        exit 1
    }

    if (-not (Test-Path $OUT_GRO)) {
        Write-Host "错误: $OUT_GRO 未生成！" -ForegroundColor Red
        exit 1
    }

    Remove-Item $DEL_GRO -Force -ErrorAction SilentlyContinue

    # 更新当前文件为下一轮输入
    $CURRENT_GRO = $OUT_GRO
    $CURRENT_TOP = $OUT_TOP
    $CURRENT_SOLVENT_COUNT = $CURRENT_SOLVENT_COUNT - $CURRENT_DELETE_NUM

    Copy-Item $CURRENT_GRO "${PREFIX}_sa_current.gro" -Force
    Copy-Item $CURRENT_TOP "${PREFIX}_sa_current.top" -Force

    $stateObj = [ordered]@{
        completed_loop    = $i
        end_loop          = $LOOPS
        solvent           = $SOLVENT_NAME
        deleted_in_loop   = $CURRENT_DELETE_NUM
        remaining_solvent = $CURRENT_SOLVENT_COUNT
        gro_file          = $CURRENT_GRO
        top_file          = $CURRENT_TOP
        timestamp         = (Get-Date).ToString("o")
    }
    $stateObj | ConvertTo-Json | Set-Content -Path "${PREFIX}_sa_state.json" -Encoding UTF8

    Write-Host "第 $i 轮完成！剩余 $CURRENT_SOLVENT_COUNT 个 $SOLVENT_NAME" -ForegroundColor Green
    Write-Host ""
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SA溶剂蒸发流程完成！" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "最终文件:"
Write-Host "  GRO: $CURRENT_GRO"
Write-Host "  TOP: $CURRENT_TOP"
