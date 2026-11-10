#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "  ClFFCl 溶剂蒸发脚本 (循环删除 CF) [Corrected]"
echo "======================================"

# 用法说明
usage() {
    echo "用法: bash run_solvent_evap_clffcl.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --solvent        溶剂名称 (默认: CF)"
    echo "  --delete-num     每次删除数量 (默认: 100)"
    echo "  --atoms-per-solvent  每个溶剂分子原子数 (默认: 5)"
    echo "  --loops          删除轮数 (默认: auto 自动计算)"
    echo "  --start-loop     起始循环号 (默认: 1)"
    echo "  --input-gro      输入 gro 文件 (默认: ClFFCl_npt2.gro)"
    echo "  --prefix         输出前缀 (默认: ClFFCl_npt)"
    echo "  --top            拓扑文件 (默认: p4PM6-ClFFCl-mix.top)"
    echo "  --mdp            MDP 文件 (默认: ydw-npt-sa.mdp)"
    echo ""
    echo "完整示例:"
    echo "  bash run_solvent_evap_clffcl.sh --solvent CF --delete-num 100 --atoms-per-solvent 5 --loops 500"
    echo "  bash run_solvent_evap_clffcl.sh --input-gro ClFFCl_npt2.gro --prefix ClFFCl_npt --top p4PM6-ClFFCl-mix.top"
    echo ""
}

# 默认参数
SOLVENT_NAME="CF"
DELETE_NUM=100
ATOMS_PER_SOLVENT=5
LOOPS="auto"
START_LOOP=1
INPUT_GRO="ClFFCl_npt2.gro"
PREFIX="ClFFCl_npt"
TOP_FILE="p4PM6-ClFFCl-mix.top"
MDP_FILE="ydw-npt-sa.mdp"

GMX="${GMX:-gmx}"
PYTHON="${PYTHON:-$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)}"
MAXWARN="${MAXWARN:-200}"
NT="${NT:-16}"
GPU_ID="${GPU_ID:-0}"

# ==================== 解析参数 ====================
POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --solvent)
            SOLVENT_NAME="$2"
            shift 2
            ;;
        --delete-num)
            DELETE_NUM="$2"
            shift 2
            ;;
        --atoms-per-solvent)
            ATOMS_PER_SOLVENT="$2"
            shift 2
            ;;
        --loops)
            LOOPS="$2"
            shift 2
            ;;
        --start-loop)
            START_LOOP="$2"
            shift 2
            ;;
        --input-gro)
            INPUT_GRO="$2"
            shift 2
            ;;
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --top)
            TOP_FILE="$2"
            shift 2
            ;;
        --mdp)
            MDP_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

# ==================== GPU 设置 ====================
echo ""
echo "[GPU 设置]"
if [ "${FORCE_CPU:-0}" != "1" ] && command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=index,name,memory.free --format=csv,noheader >/dev/null 2>&1; then
    echo "检测到 NVIDIA GPU，查看可用 GPU："
    nvidia-smi --query-gpu=index,name,memory.free --format=csv,noheader 2>/dev/null || echo "无法获取 GPU 信息"

    if [ -z "${CUDA_VISIBLE_DEVICES:-}" ]; then
        export CUDA_VISIBLE_DEVICES="${GPU_ID}"
        echo "已设置 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
    else
        echo "使用现有 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
    fi
else
    echo "警告: 未检测到 NVIDIA GPU，将使用 CPU 运行"
fi

echo "检查 GROMACS 是否可用..."
if ! command -v "$GMX" >/dev/null 2>&1; then
    echo "错误: GROMACS (gmx) 未在 PATH 中找到。"
    exit 1
fi

# ==================== 参数验证 ====================
echo ""
echo "======================================"
echo "  溶剂蒸发参数"
echo "======================================"
echo "溶剂名称: $SOLVENT_NAME"
echo "每次删除数量: $DELETE_NUM"
echo "每个溶剂原子数: $ATOMS_PER_SOLVENT"
echo "目标循环数: $LOOPS"
echo "起始循环号: $START_LOOP"
echo "输入文件: $INPUT_GRO"
echo "输出前缀: $PREFIX"
echo "拓扑文件: $TOP_FILE"
echo "MDP 文件: $MDP_FILE"
echo "======================================"

# 检查必需文件
for file in "$TOP_FILE" "$MDP_FILE" "delete_solvent.py"; do
    if [ ! -f "$file" ]; then
        echo "错误: $file 未找到！"
        exit 1
    fi
done

# 设置工作目录
WORK_DIR="$(pwd)"
LOG_DIR="logs_evap_${PREFIX}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/evap_summary.log"

echo "溶剂蒸发开始于 $(date)" > "$LOG_FILE"
echo "参数设置: solvent=$SOLVENT_NAME, delete_num=$DELETE_NUM, atoms=$ATOMS_PER_SOLVENT" >> "$LOG_FILE"

# 辅助函数：读取 TOP 中目标溶剂分子数
read_top_solvent_count() {
    awk '
        /^\[[[:space:]]*molecules[[:space:]]*\]/ {flag=1; next}
        /^\[/ {flag=0; next}
        flag && /^[[:space:]]*($|;)/ {next}
        flag {
            sub(/;.*/, "")
            if ($1=="'"$SOLVENT_NAME"'") {print $2; exit}
        }
    ' "$1" | tr -d '[:space:]'
}

# 辅助函数：统计 GRO 中目标溶剂原子数
count_gro_solvent_atoms() {
    awk -v s="$SOLVENT_NAME" '
        NR==2 {natoms=$1+0; next}
        NR>2 && NR<=2+natoms {
            res=substr($0,6,5)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", res)
            if (res==s) c++
        }
        END {print c+0}
    ' "$1"
}

# 辅助函数：校验 GRO 文件结构完整性（头部声明原子数 == 实际原子行数，且存在非空盒子行）
verify_gro_complete() {
    awk '
        NR==2 {natoms=$1+0}
        END {
            if (NR < 3) exit 1
            if (NR - 3 != natoms) exit 2
            if (length($0) == 0) exit 3
        }
    ' "$1"
}

# 辅助函数：检查 GRO 是否包含速度列（列宽 >= 68），用于核对 MDP continuation=yes / gen_vel=no
has_gro_velocities() {
    awk '
        NR==2 {natoms=$1+0; next}
        NR==3 && natoms>0 {
            line=$0
            sub(/\r$/, "", line)
            if (length(line) >= 68) print "yes"; else print "no"
            exit
        }
        END { if (natoms==0) print "yes" }
    ' "$1"
}

# 辅助函数：解析第 K 轮的输入 GRO 与输入 TOP（连续运行与断点续跑共用同一规则）
resolve_loop_inputs() {
    local target_loop="$1"
    if [ "$target_loop" -eq 1 ]; then
        RESOLVED_IN_GRO="$INPUT_GRO"
        if [ -f "${PREFIX}_original.top" ]; then
            RESOLVED_IN_TOP="${PREFIX}_original.top"
        else
            RESOLVED_IN_TOP="$TOP_FILE"
        fi
    else
        local prev_loop=$((target_loop - 1))
        RESOLVED_IN_GRO="${PREFIX}_${prev_loop}.gro"
        if [ -f "${PREFIX}_${prev_loop}.top" ]; then
            RESOLVED_IN_TOP="${PREFIX}_${prev_loop}.top"
        elif [ -f "${PREFIX}_current.top" ]; then
            RESOLVED_IN_TOP="${PREFIX}_current.top"
        else
            RESOLVED_IN_TOP="$TOP_FILE"
        fi
    fi
}

export ATOMS_PER_SOLVENT

# 保存初始文件备份（仅在 START_LOOP=1 且尚未创建备份或首次启动时）
if [ "$START_LOOP" -eq 1 ]; then
    if [ ! -f "$INPUT_GRO" ]; then
        echo "错误: 初始输入文件 $INPUT_GRO 未找到！"
        exit 1
    fi
    cp "$INPUT_GRO" "${PREFIX}_original.gro"
    cp "$TOP_FILE" "${PREFIX}_original.top"
    echo "已备份初始文件: ${PREFIX}_original.gro, ${PREFIX}_original.top" | tee -a "$LOG_FILE"
fi

# 统一解析起始轮次的输入结构与输入拓扑
resolve_loop_inputs "$START_LOOP"
CURRENT_GRO="$RESOLVED_IN_GRO"
CURRENT_TOP_SOURCE="$RESOLVED_IN_TOP"

if [ ! -f "$CURRENT_GRO" ]; then
    echo "错误: 起始循环 $START_LOOP 所需的输入结构文件 $CURRENT_GRO 未找到！" | tee -a "$LOG_FILE"
    exit 1
fi

if ! verify_gro_complete "$CURRENT_GRO"; then
    echo "错误: 输入结构文件 $CURRENT_GRO 不完整或原子行数与头部声明不符！" | tee -a "$LOG_FILE"
    exit 1
fi

CURRENT_SOLVENT_COUNT=$(read_top_solvent_count "$CURRENT_TOP_SOURCE")

if [ -z "$CURRENT_SOLVENT_COUNT" ] || ! [[ "$CURRENT_SOLVENT_COUNT" =~ ^[0-9]+$ ]]; then
    echo "错误: 在 $CURRENT_TOP_SOURCE 中找不到有效的 $SOLVENT_NAME 分子数。" | tee -a "$LOG_FILE"
    exit 1
fi

GRO_SOLVENT_ATOMS=$(count_gro_solvent_atoms "$CURRENT_GRO")
EXPECTED_SOLVENT_ATOMS=$((CURRENT_SOLVENT_COUNT * ATOMS_PER_SOLVENT))

# 若断点续跑时回退拓扑计数与上一轮完成结构不一致，尝试其他可用拓扑版本对账
if [ "$START_LOOP" -gt 1 ] && [ "$GRO_SOLVENT_ATOMS" -ne "$EXPECTED_SOLVENT_ATOMS" ]; then
    for cand_top in "${PREFIX}_$((START_LOOP - 1)).top" "${PREFIX}_current.top" "$TOP_FILE"; do
        if [ -f "$cand_top" ]; then
            CAND_COUNT=$(read_top_solvent_count "$cand_top")
            if [ -n "$CAND_COUNT" ] && [ $((CAND_COUNT * ATOMS_PER_SOLVENT)) -eq "$GRO_SOLVENT_ATOMS" ]; then
                echo "从 $cand_top 匹配恢复第 $((START_LOOP - 1)) 轮拓扑状态..." | tee -a "$LOG_FILE"
                CURRENT_TOP_SOURCE="$cand_top"
                CURRENT_SOLVENT_COUNT="$CAND_COUNT"
                EXPECTED_SOLVENT_ATOMS=$((CURRENT_SOLVENT_COUNT * ATOMS_PER_SOLVENT))
                break
            fi
        fi
    done
fi

if [ "$GRO_SOLVENT_ATOMS" -ne "$EXPECTED_SOLVENT_ATOMS" ]; then
    echo "错误: $CURRENT_GRO 中 $SOLVENT_NAME 原子数 ($GRO_SOLVENT_ATOMS) 与拓扑 $CURRENT_TOP_SOURCE 声明分子数 ($CURRENT_SOLVENT_COUNT * $ATOMS_PER_SOLVENT = $EXPECTED_SOLVENT_ATOMS) 不一致！拒绝执行以防止重复删除或跳轮。" | tee -a "$LOG_FILE"
    exit 1
fi

# 同步主 TOP_FILE 为已验证的起始拓扑版本
if [ "$CURRENT_TOP_SOURCE" != "$TOP_FILE" ]; then
    cp "$CURRENT_TOP_SOURCE" "$TOP_FILE"
fi

echo "当前 $SOLVENT_NAME 分子数: $CURRENT_SOLVENT_COUNT (来源结构: $CURRENT_GRO, 来源拓扑: $CURRENT_TOP_SOURCE)" | tee -a "$LOG_FILE"

# 计算循环次数
if [ "$LOOPS" = "auto" ]; then
    if [ $CURRENT_SOLVENT_COUNT -eq 0 ]; then
        echo "溶剂数量已为 0，无需继续删除。"
        exit 0
    fi
    END_LOOP=$(( (CURRENT_SOLVENT_COUNT + DELETE_NUM - 1) / DELETE_NUM ))
    if [ "$START_LOOP" -gt 1 ]; then
        END_LOOP=$((START_LOOP - 1 + END_LOOP))
    fi
else
    END_LOOP="$LOOPS"
fi

echo "将运行循环: $START_LOOP 到 $END_LOOP" | tee -a "$LOG_FILE"

# ==================== 开始溶剂蒸发循环 (Corrected: 逐轮继承 NPT 输出结构) ====================
WORK_GRO="${PREFIX}_work.gro"
cp "$CURRENT_GRO" "$WORK_GRO"

loop=$START_LOOP
while [ "$loop" -le "$END_LOOP" ]; do
    # 每一轮统一通过 resolve_loop_inputs 获取上一轮已完成的 NPT 结构与对应拓扑
    resolve_loop_inputs "$loop"
    LOOP_IN_GRO="$RESOLVED_IN_GRO"
    LOOP_IN_TOP="$RESOLVED_IN_TOP"

    if [ ! -f "$LOOP_IN_GRO" ] || ! verify_gro_complete "$LOOP_IN_GRO"; then
        echo "错误: 循环 $loop 的输入结构 $LOOP_IN_GRO 缺失或不完整！" | tee -a "$LOG_FILE"
        exit 1
    fi

    LOOP_TOP_COUNT=$(read_top_solvent_count "$LOOP_IN_TOP")
    LOOP_GRO_ATOMS=$(count_gro_solvent_atoms "$LOOP_IN_GRO")
    if [ "$LOOP_TOP_COUNT" != "$CURRENT_SOLVENT_COUNT" ] || [ "$LOOP_GRO_ATOMS" -ne $((CURRENT_SOLVENT_COUNT * ATOMS_PER_SOLVENT)) ]; then
        echo "错误: 循环 $loop 开始前检测到 GRO/TOP 状态失步 (GRO 溶剂原子=$LOOP_GRO_ATOMS, TOP 溶剂分子=$LOOP_TOP_COUNT, 预期分子=$CURRENT_SOLVENT_COUNT)！" | tee -a "$LOG_FILE"
        exit 1
    fi

    # 计算本次删除数量
    CURRENT_DELETE_NUM=$DELETE_NUM
    if [ "$CURRENT_SOLVENT_COUNT" -lt "$CURRENT_DELETE_NUM" ]; then
        CURRENT_DELETE_NUM=$CURRENT_SOLVENT_COUNT
    fi

    if [ "$CURRENT_DELETE_NUM" -le 0 ]; then
        echo "循环 $loop: 已无 $SOLVENT_NAME 可删，停止。" | tee -a "$LOG_FILE"
        break
    fi

    OUTBASE="${PREFIX}_${loop}"
    NEW_TOP="${OUTBASE}_pending.top"
    LOOP_TOP="${OUTBASE}.top"

    echo ""
    echo "[循环 $loop/$END_LOOP] 输入结构: $LOOP_IN_GRO | 删除 $CURRENT_DELETE_NUM 个 $SOLVENT_NAME..." | tee -a "$LOG_FILE"

    # 调用 delete_solvent.py 从上一轮 NPT 结束结构 LOOP_IN_GRO 删除溶剂
    echo "正在运行 delete_solvent.py..." | tee -a "$LOG_FILE"
    "$PYTHON" delete_solvent.py \
        --solvent "$SOLVENT_NAME" \
        --delete-num "$CURRENT_DELETE_NUM" \
        --atoms-per-mol "$ATOMS_PER_SOLVENT" \
        --loop "$loop" \
        --input "$LOOP_IN_GRO" \
        --output "${PREFIX}_new.gro" \
        --topology "$LOOP_IN_TOP" \
        --topology-output "$NEW_TOP" \
        >> "$LOG_FILE" 2>&1 || {
            echo "错误: delete_solvent.py 在循环 $loop 中失败。" | tee -a "$LOG_FILE"
            exit 1
        }

    # 更新本轮 grompp 使用的工作结构文件
    mv "${PREFIX}_new.gro" "$WORK_GRO"

    # 清理本轮可能残留的旧输出与不匹配的 checkpoint（禁止跨轮复用原子数不同的 cpt）
    rm -f "${OUTBASE}.gro" "${OUTBASE}.tpr" "${OUTBASE}.cpt" "${OUTBASE}_prev.cpt"

    echo "正在运行 grompp..." | tee -a "$LOG_FILE"
    "$GMX" grompp \
        -f "$MDP_FILE" \
        -c "$WORK_GRO" \
        -p "$NEW_TOP" \
        -o "${OUTBASE}.tpr" \
        -maxwarn "$MAXWARN" \
        >> "$LOG_FILE" 2>&1 || {
            echo "错误: grompp 在循环 $loop 中失败。" | tee -a "$LOG_FILE"
            exit 1
        }

    # 新一轮删除分子后原子数已改变，直接从本轮新 tpr 启动 mdrun（不传上一轮 -cpi）
    echo "正在运行 mdrun (10ps NPT)..." | tee -a "$LOG_FILE"
    if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then
        "$GMX" mdrun \
            -v -deffnm "$OUTBASE" \
            -nt "$NT" -pin on -pinstride 1 \
            -bonded gpu -update gpu -gpu_id "$GPU_ID" \
            >> "$LOG_FILE" 2>&1 || {
                echo "错误: mdrun 在循环 $loop 中失败。" | tee -a "$LOG_FILE"
                exit 1
            }
    else
        "$GMX" mdrun \
            -v -deffnm "$OUTBASE" \
            -nt "$NT" -pin on -pinstride 1 \
            >> "$LOG_FILE" 2>&1 || {
                echo "错误: mdrun 在循环 $loop 中失败。" | tee -a "$LOG_FILE"
                exit 1
            }
    fi

    # 验证 mdrun 输出结构存在且完整
    if [ ! -f "${OUTBASE}.gro" ] || ! verify_gro_complete "${OUTBASE}.gro"; then
        echo "错误: ${OUTBASE}.gro 未生成或文件不完整。" | tee -a "$LOG_FILE"
        exit 1
    fi

    EXPECTED_AFTER_ATOMS=$(( (CURRENT_SOLVENT_COUNT - CURRENT_DELETE_NUM) * ATOMS_PER_SOLVENT ))
    ACTUAL_AFTER_ATOMS=$(count_gro_solvent_atoms "${OUTBASE}.gro")
    if [ "$ACTUAL_AFTER_ATOMS" -ne "$EXPECTED_AFTER_ATOMS" ]; then
        echo "错误: ${OUTBASE}.gro 中 $SOLVENT_NAME 原子数 ($ACTUAL_AFTER_ATOMS) 与预期 ($EXPECTED_AFTER_ATOMS) 不符！" | tee -a "$LOG_FILE"
        exit 1
    fi

    VEL_PRESENT=$(has_gro_velocities "${OUTBASE}.gro")

    # mdrun 验证通过后，正式提交本轮拓扑版本、更新 WORK_GRO 为本轮 NPT 输出结构并备份
    mv "$NEW_TOP" "$LOOP_TOP"
    cp "$LOOP_TOP" "$TOP_FILE"
    cp "${OUTBASE}.gro" "$WORK_GRO"
    cp "${OUTBASE}.gro" "${PREFIX}_current.gro"
    cp "$LOOP_TOP" "${PREFIX}_current.top"

    # 更新溶剂计数
    CURRENT_SOLVENT_COUNT=$((CURRENT_SOLVENT_COUNT - CURRENT_DELETE_NUM))

    cat > "${PREFIX}_sa_state.json" <<EOF
{
  "workflow_version": "Corrected",
  "completed_loop": $loop,
  "end_loop": $END_LOOP,
  "solvent": "$SOLVENT_NAME",
  "deleted_in_loop": $CURRENT_DELETE_NUM,
  "remaining_solvent": $CURRENT_SOLVENT_COUNT,
  "input_gro": "$LOOP_IN_GRO",
  "input_top": "$LOOP_IN_TOP",
  "gro_file": "${OUTBASE}.gro",
  "loop_top_file": "$LOOP_TOP",
  "top_file": "$TOP_FILE",
  "velocities_present": "$VEL_PRESENT",
  "timestamp": "$(date -Iseconds 2>/dev/null || date)"
}
EOF

    echo "[循环 $loop 完成] 输出: ${OUTBASE}.gro (速度列: $VEL_PRESENT) | 拓扑: $LOOP_TOP | 剩余 $CURRENT_SOLVENT_COUNT 个 $SOLVENT_NAME" | tee -a "$LOG_FILE"

    loop=$((loop + 1))
done

# ==================== 完成 ====================
echo ""
echo "======================================"
echo "  溶剂蒸发完成！"
echo "======================================"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
echo "最终结构: ${PREFIX}_current.gro" | tee -a "$LOG_FILE"
echo "最终拓扑: ${PREFIX}_current.top" | tee -a "$LOG_FILE"
echo "完成循环数: $((loop - START_LOOP)) 轮" | tee -a "$LOG_FILE"
echo "日志目录: $LOG_DIR"
