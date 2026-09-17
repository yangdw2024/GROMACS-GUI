#!/usr/bin/env python3
"""
等效于 batch_last_merge_groups_safe.sh 的 Python 实现
用于从 evap_*.xtc 中提取最后一帧，合并指定组，输出为 pdb/gro

用法: python batch_last_merge_groups_run.py pdb
"""
import os
import sys
import subprocess
import glob
import shutil

# ================= 配置（常量，无副作用） =================
GMX = r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\gmx.exe"
WORKDIR = r"D:\YDW\Trae_gromacs_data\003"
GROUPS = ["L8B", "CF", "DIO"]  # 要合并的组
MERGED_NAME = "MERGED"
# ========================================================


def run_cmd(cmd, cwd=None, input_text=None, timeout=300):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd or WORKDIR
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "超时"
    except Exception as e:
        return False, "", str(e)


def merge_ndx_groups(infile, outfile, wanted):
    """合并索引文件中的指定组"""
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
        print(f"  缺少组: {', '.join(missing)}")
        print(f"  当前可用组: {', '.join(groups.keys())}")
        return False

    merged = sorted(set(i for g in wanted for i in groups[g]))

    with open(outfile, "w") as f:
        for gname, atoms in groups.items():
            f.write(f"[ {gname} ]\n")
            for i in range(0, len(atoms), 15):
                f.write(" ".join(str(x) for x in atoms[i:i+15]) + "\n")
        f.write("[ MERGED ]\n")
        for i in range(0, len(merged), 15):
            f.write(" ".join(str(x) for x in merged[i:i+15]) + "\n")
    return True


def concat_pdb_models(outpath, frames):
    """将多个 PDB 文件合并为一个多 MODEL 的 PDB"""
    with open(outpath, "w") as fout:
        for model_id, p in enumerate(frames, start=1):
            fout.write(f"MODEL     {model_id}\n")
            with open(p, "r") as fin:
                for line in fin:
                    rec = line[:6].strip()
                    if rec in {"ATOM", "HETATM", "TER"}:
                        fout.write(line)
            fout.write("ENDMDL\n")
        fout.write("END\n")


def main():
    FMT = sys.argv[1] if len(sys.argv) > 1 else "pdb"
    OUTDIR = os.path.join(WORKDIR, f"last_{FMT}_{MERGED_NAME}")
    ALL_OUT = os.path.join(WORKDIR, f"all_last_frames_{MERGED_NAME}.{FMT}")
    LOGDIR = os.path.join(WORKDIR, "merge_logs")
    TMPDIR = os.path.join(WORKDIR, f"merge_work_{MERGED_NAME}")

    if FMT not in ("pdb", "gro"):
        print("错误: 第一个参数只能是 pdb 或 gro")
        print("用法: python batch_last_merge_groups_run.py pdb")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    os.makedirs(TMPDIR, exist_ok=True)

    # 查找所有 evap_*.xtc 文件
    xtc_files_all = sorted(glob.glob(os.path.join(WORKDIR, "evap_*.xtc")))
    print(f"找到 {len(xtc_files_all)} 个 xtc 文件")
    # 先处理前5个验证流程，如需全部处理请删除下行
    xtc_files = xtc_files_all[:5]
    print(f"本次处理前 {len(xtc_files)} 个文件")
    sys.stdout.flush()

    frames = []

    for xtc_path in xtc_files:
        base = os.path.splitext(os.path.basename(xtc_path))[0]
        tpr_path = os.path.join(WORKDIR, f"{base}.tpr")
        print(f"\n处理: {base}")
        sys.stdout.flush()

        if not os.path.exists(tpr_path):
            print(f"  跳过: 找不到 {tpr_path}")
            sys.stdout.flush()
            continue

        default_ndx = os.path.join(TMPDIR, f"{base}_default.ndx")
        merged_ndx = os.path.join(TMPDIR, f"{base}_merged.ndx")
        make_ndx_log = os.path.join(LOGDIR, f"{base}_make_ndx.log")
        merge_log = os.path.join(LOGDIR, f"{base}_merge_groups.log")
        trjconv_log = os.path.join(LOGDIR, f"{base}_trjconv.log")

        # Step 1: make_ndx
        print(f"  Step1: make_ndx ...", end=" ")
        sys.stdout.flush()
        ok, out, err = run_cmd(
            [GMX, "make_ndx", "-f", tpr_path, "-o", default_ndx],
            input_text="q\n", timeout=60
        )
        if not ok:
            print("失败")
            print(f"  日志: {make_ndx_log}")
            with open(make_ndx_log, "w") as f:
                f.write(out + "\n" + err)
            continue
        print("OK")
        sys.stdout.flush()
        with open(make_ndx_log, "w") as f:
            f.write(out + "\n" + err)

        # Step 2: merge groups
        print(f"  Step2: merge groups ...", end=" ")
        sys.stdout.flush()
        success = merge_ndx_groups(default_ndx, merged_ndx, GROUPS)
        if not success:
            print("失败")
            sys.stdout.flush()
            continue
        print("OK")
        sys.stdout.flush()

        # Step 3: trjconv 提取最后一帧
        print(f"  Step3: trjconv 提取最后一帧 ...", end=" ")
        sys.stdout.flush()
        out_path = os.path.join(OUTDIR, f"{base}_{MERGED_NAME}_last.{FMT}")
        ok, out, err = run_cmd(
            [GMX, "trjconv",
             "-f", xtc_path,
             "-s", tpr_path,
             "-n", merged_ndx,
             "-dump", "999999999",
             "-pbc", "mol",
             "-ur", "compact",
             "-o", out_path],
            input_text=f"{MERGED_NAME}\n", timeout=120
        )
        if not ok:
            print("失败")
            print(f"  stderr: {err[:300]}")
            with open(trjconv_log, "w") as f:
                f.write(out + "\n" + err)
            continue
        print("OK")
        sys.stdout.flush()
        with open(trjconv_log, "w") as f:
            f.write(out + "\n" + err)

        frames.append(out_path)
        print(f"  完成 -> {out_path}")
        sys.stdout.flush()

    if len(frames) == 0:
        print("错误: 没有成功提取任何最后一帧")
        sys.exit(1)

    # Step 4: 合并所有帧
    if FMT == "pdb":
        concat_pdb_models(ALL_OUT, frames)
    else:
        with open(ALL_OUT, "wb") as fout:
            for fpath in frames:
                with open(fpath, "rb") as fin:
                    shutil.copyfileobj(fin, fout)

    print(f"\n单帧输出目录: {OUTDIR}")
    print(f"总汇文件: {ALL_OUT}")
    print(f"日志目录: {LOGDIR}")
    print(f"成功处理: {len(frames)} / {len(xtc_files)}")


if __name__ == "__main__":
    main()
