#!/bin/bash
# WSL GROMACS 完整工作流程测试脚本
set -e

TEST_DIR=/mnt/d/YDW/WSL_Gromacs/test_run
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# 加载环境
export PATH=/usr/local/cuda-13.3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
GROMACS_ROOT=/mnt/d/YDW/WSL_Gromacs/install/gromacs-2026.3-AVX512-CUDA
export PATH=$GROMACS_ROOT/bin:$PATH
export LD_LIBRARY_PATH=$GROMACS_ROOT/lib:$LD_LIBRARY_PATH
export GMXDATA=$GROMACS_ROOT/share/gromacs

if [ -f "$GROMACS_ROOT/bin/GMXRC" ]; then
    source "$GROMACS_ROOT/bin/GMXRC"
fi

echo "=========================================="
echo "  GROMACS WSL 完整功能测试"
echo "=========================================="
echo ""
echo "测试目录: $TEST_DIR"
echo "GROMACS版本: $(gmx --version | grep 'GROMACS version:' | head -1)"
echo ""

# 创建简单的纯水盒子测试系统
echo "[Step 1/3] 创建水盒子系统..."
gmx solvate -cs spc216.gro -o water_box.gro -box 3 3 3 -maxsol 200 <<EOF

EOF
echo "[Step 1/3] 完成"

# 计算水分子数（每个水分子3个原子）
echo "[Step 2/3] 生成拓扑文件..."
WATER_COUNT=$(grep -c '^SOL' water_box.gro)
if [ "$WATER_COUNT" -eq 0 ]; then
    WATER_COUNT=200
else
    WATER_COUNT=$((WATER_COUNT / 3))
fi

cat > water.top <<EOF
#include "amber99sb-ildn.ff/forcefield.itp"
#include "amber99sb-ildn.ff/tip3p.itp"

[ system ]
Pure Water in a Box

[ molecules ]
SOL     $WATER_COUNT
EOF
echo "[Step 2/3] 完成"

# 创建能量最小化MDP
echo "[Step 3/3] 运行能量最小化..."
cat > em.mdp <<EOF
title       = Water box energy minimization
integrator  = steep
nsteps      = 500
dt          = 0.002

cutoff-scheme = Verlet
vdwtype     = Cut-off
rvdw        = 1.0
coulombtype = PME
rcoulomb    = 1.0
pbc         = xyz
EOF

gmx grompp -f em.mdp -c water_box.gro -p water.top -o em.tpr -maxwarn 2
gmx mdrun -deffnm em -nt 4
echo "[Step 3/3] 完成"

echo ""
echo "=========================================="
echo "  测试全部通过！"
echo "=========================================="
echo ""
echo "生成的文件:"
ls -lh "$TEST_DIR" | grep -E 'water_box.gro|water.top|em.tpr|em.log|em.gro|em.edr'
