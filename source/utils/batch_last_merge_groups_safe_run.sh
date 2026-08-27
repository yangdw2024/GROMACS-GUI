#!/usr/bin/env bash
set -euo pipefail

GMX=${GMX:-/d/YDW/Trae_Gromacs/gromacs/gromacs-2026.3-AVX512-CUDA-sm120-final2/bin/gmx.exe}

# 输出格式：pdb 或 gro
FMT="${1:-pdb}"

if [[ "$FMT" != "pdb" && "$FMT" != "gro" ]]; then
    echo "错误: 第一个参数只能是 pdb 或 gro"
    echo "用法: bash batch_last_merge_groups_safe.sh pdb"
    exit 1
fi

MERGED_NAME="MERGED"
OUTDIR="last_${FMT}_${MERGED_NAME}"
ALL_OUT="all_last_frames_${MERGED_NAME}.${FMT}"
LOGDIR="merge_logs"
WORKDIR="./merge_work_${MERGED_NAME}"

mkdir -p "$OUTDIR" "$LOGDIR" "$WORKDIR"

# ======== 这里写死你要合并的组 ========
GROUPS=("L8B" "CF" "DIO")
# ====================================

merge_ndx_py="$WORKDIR/merge_ndx_groups.py"
cat > "$merge_ndx_py" <<'PY'
import sys

infile = sys.argv[1]
outfile = sys.argv[2]
wanted = ["L8B", "CF", "DIO"]

groups = {}
current = None

with open(infile, "r") as f:
    for line in f:
        s = line.strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1].strip()
            groups[current] = []
        else:
            if current is None:
                continue
            groups[current].extend(int(x) for x in s.split())

missing = [g for g in wanted if g not in groups]
if missing:
    print("缺少组: " + ", ".join(missing), file=sys.stderr)
    print("当前可用组: " + ", ".join(groups.keys()), file=sys.stderr)
    sys.exit(2)

merged = sorted(set(i for g in wanted for i in groups[g]))

with open(outfile, "w") as f:
    for gname, atoms in groups.items():
        f.write(f"[ {gname} ]\n")
        for i in range(0, len(atoms), 15):
            f.write(" ".join(str(x) for x in atoms[i:i+15]) + "\n")
    f.write("[ MERGED ]\n")
    for i in range(0, len(merged), 15):
        f.write(" ".join(str(x) for x in merged[i:i+15]) + "\n")
PY

concat_pdb_py="$WORKDIR/concat_pdb_models.py"
cat > "$concat_pdb_py" <<'PY'
import sys
from pathlib import Path

out = Path(sys.argv[1])
frames = [Path(x) for x in sys.argv[2:]]

with out.open("w") as fout:
    for model_id, p in enumerate(frames, start=1):
        fout.write(f"MODEL     {model_id}\n")
        with p.open("r") as fin:
            for line in fin:
                rec = line[:6].strip()
                if rec in {"ATOM", "HETATM", "TER"}:
                    fout.write(line)
        fout.write("ENDMDL\n")
    fout.write("END\n")
PY

frames=()

while IFS= read -r trr; do
    [[ -f "$trr" ]] || continue
    base="${trr%.xtc}"
    tpr="${base}.tpr"

    if [[ ! -f "$tpr" ]]; then
        echo "跳过 $base: 找不到 ${tpr}"
        continue
    fi

    default_ndx="$WORKDIR/${base}_default.ndx"
    merged_ndx="$WORKDIR/${base}_merged.ndx"
    make_ndx_log="$LOGDIR/${base}_make_ndx.log"
    merge_log="$LOGDIR/${base}_merge_groups.log"
    trjconv_log="$LOGDIR/${base}_trjconv.log"

    printf 'q\n' | "$GMX" make_ndx -f "$tpr" -o "$default_ndx" >"$make_ndx_log" 2>&1 || {
        echo "错误: $base 生成默认 index 失败，见 $make_ndx_log"
        exit 1
    }

    python "$merge_ndx_py" "$default_ndx" "$merged_ndx" >"$merge_log" 2>&1 || {
        echo "错误: $base 合并组失败，见 $merge_log"
        exit 1
    }

    if ! grep -q '^\[ MERGED \]' "$merged_ndx"; then
        echo "错误: $base 没有成功生成 [ MERGED ] 组，见 $merge_log"
        exit 1
    fi

    out="${OUTDIR}/${base}_${MERGED_NAME}_last.${FMT}"

    printf '%s\n' "$MERGED_NAME" | "$GMX" trjconv \
        -f "$trr" \
        -s "$tpr" \
        -n "$merged_ndx" \
        -dump 999999999 \
        -pbc mol \
        -ur compact \
        -o "$out" >"$trjconv_log" 2>&1 || {
        echo "错误: $base 提取最后一帧失败，见 $trjconv_log"
        exit 1
    }

    frames+=("$out")
    echo "完成: $trr -> $out"
done < <(printf '%s\n' evap_*.xtc | sort -V)

if [[ ${#frames[@]} -eq 0 ]]; then
    echo "错误: 没有成功提取任何最后一帧"
    exit 1
fi

if [[ "$FMT" == "pdb" ]]; then
    python3 "$concat_pdb_py" "$ALL_OUT" "${frames[@]}"
else
    cat "${frames[@]}" > "$ALL_OUT"
fi

echo "单帧输出目录: $OUTDIR"
echo "总汇文件: $ALL_OUT"
echo "日志目录: $LOGDIR"