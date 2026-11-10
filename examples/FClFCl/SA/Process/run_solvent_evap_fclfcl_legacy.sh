#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "  FClFCl 溶剂蒸发脚本 (循环删除 CF)"
echo "======================================"

# 用法说明
usage() {
    echo "用法: bash run_solvent_evap_fclfcl.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --solvent        溶剂名称 (默认: CF)"
    echo "  --delete-num     每次删除数量 (默认: 100)"
    echo "  --atoms-per-solvent  每个溶剂分子原子数 (默认: 5)"
    echo "  --loops          删除轮数 (默认: auto 自动计算)"
    echo "  --start-loop     起始循环号 (默认: 1)"
    echo "  --input-gro      输入 gro 文件 (默认: FClFCl_npt2.gro)"
    echo "  --prefix         输出前缀 (默认: FClFCl_npt)"
    echo "  --top            拓扑文件 (默认: p4PM6-FClFCl-mix.top)"
    echo "  --mdp            MDP 文件 (默认: ydw-npt-remove.mdp)"
    echo ""
    echo "完整示例:"
    echo "  bash run_solvent_evap_fclfcl.sh --solvent CF --delete-num 100 --atoms-per-solvent 5 --loops 500"
    echo "  bash run_solvent_evap_fclfcl.sh --input-gro FClFCl_npt2.gro --prefix FClFCl_npt --top p4PM6-FClFCl-mix.top"
    echo ""
}

# 默认参数
SOLVENT_NAME="CF"
DELETE_NUM=100
ATOMS_PER_SOLVENT=5
LOOPS="auto"
START_LOOP=1
INPUT_GRO="FClFCl_npt2.gro"
PREFIX="FClFCl_npt"
TOP_FILE="p4PM6-FClFCl-mix.top"
MDP_FILE="ydw-npt-remove.mdp"

GMX="${GMX:-gmx}"
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
if command -v nvidia-smi >/dev/null 2>&1; then
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

# 确定初始输入文件
if [ "$START_LOOP" -eq 1 ]; then
    if [ ! -f "$INPUT_GRO" ]; then
        echo "错误: 初始输入文件 $INPUT_GRO 未找到！"
        exit 1
    fi
    CURRENT_GRO="$INPUT_GRO"
else
    PREV_LOOP=$((START_LOOP - 1))
    CURRENT_GRO="${PREFIX}_${PREV_LOOP}.gro"
    if [ ! -f "$CURRENT_GRO" ]; then
        echo "错误: 循环 $PREV_LOOP 的输出文件 $CURRENT_GRO 未找到！"
        exit 1
    fi
fi

# 获取当前溶剂分子数
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

export ATOMS_PER_SOLVENT

CURRENT_SOLVENT_COUNT=$(read_top_solvent_count "$TOP_FILE")

if [ -z "$CURRENT_SOLVENT_COUNT" ] || ! [[ "$CURRENT_SOLVENT_COUNT" =~ ^[0-9]+$ ]]; then
    echo "错误: 在 $TOP_FILE 中找不到有效的 $SOLVENT_NAME 分子数。"
    exit 1
fi

GRO_SOLVENT_ATOMS=$(count_gro_solvent_atoms "$CURRENT_GRO")
EXPECTED_SOLVENT_ATOMS=$((CURRENT_SOLVENT_COUNT * ATOMS_PER_SOLVENT))

if [ "$START_LOOP" -gt 1 ] && [ "$GRO_SOLVENT_ATOMS" -ne "$EXPECTED_SOLVENT_ATOMS" ] && [ -f "${PREFIX}_current.top" ]; then
    BACKUP_COUNT=$(read_top_solvent_count "${PREFIX}_current.top")
    if [ -n "$BACKUP_COUNT" ] && [ $((BACKUP_COUNT * ATOMS_PER_SOLVENT)) -eq "$GRO_SOLVENT_ATOMS" ]; then
        echo "检测到上次异常中断留下的拓扑计数偏差，从 ${PREFIX}_current.top 恢复拓扑文件..." | tee -a "$LOG_FILE"
        cp "${PREFIX}_current.top" "$TOP_FILE"
        CURRENT_SOLVENT_COUNT="$BACKUP_COUNT"
        EXPECTED_SOLVENT_ATOMS=$((CURRENT_SOLVENT_COUNT * ATOMS_PER_SOLVENT))
    fi
fi

if [ "$GRO_SOLVENT_ATOMS" -ne "$EXPECTED_SOLVENT_ATOMS" ]; then
    echo "错误: $CURRENT_GRO 中 $SOLVENT_NAME 原子数 ($GRO_SOLVENT_ATOMS) 与 $TOP_FILE 声明分子数 ($CURRENT_SOLVENT_COUNT * $ATOMS_PER_SOLVENT = $EXPECTED_SOLVENT_ATOMS) 不一致！" | tee -a "$LOG_FILE"
    exit 1
fi

echo "当前 $SOLVENT_NAME 分子数: $CURRENT_SOLVENT_COUNT" | tee -a "$LOG_FILE"

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

# 保存初始文件备份
if [ "$START_LOOP" -eq 1 ]; then
    cp "$INPUT_GRO" "${PREFIX}_original.gro"
    cp "$TOP_FILE" "${PREFIX}_original.top"
    echo "已备份初始文件" | tee -a "$LOG_FILE"
fi

# ==================== 开始溶剂蒸发循环 ====================
WORK_GRO="${PREFIX}_work.gro"
cp "$CURRENT_GRO" "$WORK_GRO"

loop=$START_LOOP
while [ "$loop" -le "$END_LOOP" ]; do
    # 计算本次删除数量
    CURRENT_DELETE_NUM=$DELETE_NUM
    if [ "$CURRENT_SOLVENT_COUNT" -lt "$CURRENT_DELETE_NUM" ]; then
        CURRENT_DELETE_NUM=$CURRENT_SOLVENT_COUNT
    fi

    if [ "$CURRENT_DELETE_NUM" -le 0 ]; then
        echo "循环 $loop: 已无 $SOLVENT_NAME 可删，停止。" | tee -a "$LOG_FILE"
        break
    fi

    echo ""
    echo "[循环 $loop/$END_LOOP] 删除 $CURRENT_DELETE_NUM 个 $SOLVENT_NAME..." | tee -a "$LOG_FILE"

    # 调用 delete_solvent.py 删除溶剂
    NEW_TOP="${TOP_FILE%.top}_new.top"
    echo "正在运行 delete_solvent.py..." | tee -a "$LOG_FILE"
    python3 delete_solvent.py \
        --solvent "$SOLVENT_NAME" \
        --delete-num "$CURRENT_DELETE_NUM" \
        --atoms-per-mol "$ATOMS_PER_SOLVENT" \
        --loop "$loop" \
        --input "$WORK_GRO" \
        --output "${PREFIX}_new.gro" \
        --topology "$TOP_FILE" \
        --topology-output "$NEW_TOP" \
        >> "$LOG_FILE" 2>&1 || {
            echo "错误: delete_solvent.py 在循环 $loop 中失败。" | tee -a "$LOG_FILE"
            exit 1
        }

    # 更新工作结构文件（拓扑待 mdrun 成功后提交，避免中断导致 GRO/TOP 失步）
    mv "${PREFIX}_new.gro" "$WORK_GRO"

    # 生成 tpr 并运行 NPT
    OUTBASE="${PREFIX}_${loop}"

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

    echo "正在运行 mdrun (100ps NPT)..." | tee -a "$LOG_FILE"
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

    # 检查输出
    if [ ! -f "${OUTBASE}.gro" ]; then
        echo "错误: ${OUTBASE}.gro 未生成。" | tee -a "$LOG_FILE"
        exit 1
    fi

    # 提交拓扑并备份结果
    mv "$NEW_TOP" "$TOP_FILE"
    cp "${OUTBASE}.gro" "${PREFIX}_current.gro"
    cp "$TOP_FILE" "${PREFIX}_current.top"

    # 更新溶剂计数
    CURRENT_SOLVENT_COUNT=$((CURRENT_SOLVENT_COUNT - CURRENT_DELETE_NUM))

    cat > "${PREFIX}_sa_state.json" <<EOF
{
  "completed_loop": $loop,
  "end_loop": $END_LOOP,
  "solvent": "$SOLVENT_NAME",
  "deleted_in_loop": $CURRENT_DELETE_NUM,
  "remaining_solvent": $CURRENT_SOLVENT_COUNT,
  "gro_file": "${OUTBASE}.gro",
  "top_file": "$TOP_FILE",
  "timestamp": "$(date -Iseconds 2>/dev/null || date)"
}
EOF

    echo "[循环 $loop 完成] 剩余 $CURRENT_SOLVENT_COUNT 个 $SOLVENT_NAME" | tee -a "$LOG_FILE"

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