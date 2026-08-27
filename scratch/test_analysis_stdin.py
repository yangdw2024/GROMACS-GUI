"""
测试所有分析命令的 stdin 修复
模拟 GromacsWorker 的执行方式（使用 PIPE 提供 stdin_input）
"""
import os
import sys
import subprocess
import numpy as np

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 准备数据
WORK_DIR = r"D:\YDW\Trae_Gromacs\test\test_simple"
TPR = os.path.join(WORK_DIR, "em.tpr")
EDR = os.path.join(WORK_DIR, "em.edr")
TRR = os.path.join(WORK_DIR, "em.trr")
GMX = r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\gmx.exe"

OUTPUT_DIR = r"D:\YDW\Trae_Gromacs\test\analysis_stdin_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_with_stdin(cmd, stdin_input, timeout=60):
    """模拟 GromacsWorker._run_single 的执行方式"""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True, text=True,
            timeout=timeout,
            cwd=WORK_DIR
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def test_energy():
    """测试能量分析 - 修复前: 失败 (No energy terms selected)"""
    print("\n=== 能量分析 ===")
    out = os.path.join(OUTPUT_DIR, "energy.xvg")
    cmd = [GMX, "energy", "-f", EDR, "-o", out]

    # 修复：sel为空时使用默认Potential
    energy_terms = "Potential"
    stdin_in = "\n".join(energy_terms.split()) + "\n0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        data = []
        with open(out) as f:
            for line in f:
                if not line.startswith(('#', '@')):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            data.append((float(parts[0]), float(parts[1])))
                        except:
                            pass
        print(f"  ✅ 成功 (数据点: {len(data)})")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_rmsd():
    """测试RMSD - 修复前: 失败 (等待组选择)"""
    print("\n=== RMSD分析 ===")
    out = os.path.join(OUTPUT_DIR, "rmsd.xvg")
    cmd = [GMX, "rms", "-s", TPR, "-f", TRR, "-o", out, "-tu", "ns"]
    stdin_in = "0\n0\n"  # 拟合组, 计算组

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_rmsf():
    """测试RMSF"""
    print("\n=== RMSF分析 ===")
    out = os.path.join(OUTPUT_DIR, "rmsf.xvg")
    cmd = [GMX, "rmsf", "-s", TPR, "-f", TRR, "-o", out, "-res"]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_gyrate():
    """测试回转半径"""
    print("\n=== 回转半径 ===")
    out = os.path.join(OUTPUT_DIR, "gyrate.xvg")
    cmd = [GMX, "gyrate", "-s", TPR, "-f", TRR, "-o", out]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_sasa():
    """测试SASA"""
    print("\n=== SASA分析 ===")
    out = os.path.join(OUTPUT_DIR, "sasa.xvg")
    cmd = [GMX, "sasa", "-s", TPR, "-f", TRR, "-o", out]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_density():
    """测试密度分析"""
    print("\n=== 密度分析 ===")
    out = os.path.join(OUTPUT_DIR, "density.xvg")
    cmd = [GMX, "density", "-s", TPR, "-f", TRR, "-o", out]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_msd():
    """测试均方位移 - 修复前: 失败 (Increase -trestart)"""
    print("\n=== MSD分析 ===")
    out = os.path.join(OUTPUT_DIR, "msd.xvg")
    cmd = [GMX, "msd", "-s", TPR, "-f", TRR, "-o", out, "-tu", "ns", "-trestart", "10"]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_distance():
    """测试距离分析"""
    print("\n=== 距离分析 ===")
    out = os.path.join(OUTPUT_DIR, "distance.xvg")
    cmd = [GMX, "distance", "-s", TPR, "-f", TRR, "-oav", out]
    stdin_in = "0\n0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_angle():
    """测试角度分析"""
    print("\n=== 角度分析 ===")
    out = os.path.join(OUTPUT_DIR, "angle.xvg")
    cmd = [GMX, "angle", "-s", TPR, "-f", TRR, "-ov", out]
    stdin_in = "0\n0\n0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_covar():
    """测试协方差矩阵"""
    print("\n=== 协方差矩阵 ===")
    covar_out = os.path.join(OUTPUT_DIR, "covar.xvg")
    cmd = [GMX, "covar", "-s", TPR, "-f", TRR, "-o", covar_out]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(covar_out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_principal():
    """测试主成分分析"""
    print("\n=== 主成分分析 ===")
    pc_out = os.path.join(OUTPUT_DIR, "pc.xvg")
    cmd = [GMX, "principal", "-s", TPR, "-f", TRR, "-o", pc_out]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(pc_out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_rdf():
    """测试RDF"""
    print("\n=== RDF分析 ===")
    out = os.path.join(OUTPUT_DIR, "rdf.xvg")
    cmd = [GMX, "rdf", "-s", TPR, "-f", TRR, "-o", out]
    stdin_in = "1\n1\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_hbond():
    """测试氢键"""
    print("\n=== 氢键分析 ===")
    out = os.path.join(OUTPUT_DIR, "hbond.xvg")
    cmd = [GMX, "hbond", "-s", TPR, "-f", TRR, "-num", out]
    stdin_in = "1\n1\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_saltbr():
    """测试盐桥"""
    print("\n=== 盐桥分析 ===")
    out = os.path.join(OUTPUT_DIR, "saltbr.xvg")
    cmd = [GMX, "saltbr", "-s", TPR, "-f", TRR, "-o", out]

    # saltbr 不需要stdin
    ok, out_text, err = run_with_stdin(cmd, None, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_cluster():
    """测试聚类"""
    print("\n=== 聚类分析 ===")
    out = os.path.join(OUTPUT_DIR, "cluster.xpm")
    cmd = [GMX, "cluster", "-s", TPR, "-f", TRR, "-o", out, "-method", "gromos", "-cutoff", "0.3", "-dista"]
    stdin_in = "0\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=120)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def test_pairdist():
    """测试配对距离"""
    print("\n=== 配对距离 ===")
    out = os.path.join(OUTPUT_DIR, "pairdist.xvg")
    cmd = [GMX, "pairdist", "-s", TPR, "-f", TRR, "-o", out, "-type", "min"]
    stdin_in = "1\n1\n"

    ok, out_text, err = run_with_stdin(cmd, stdin_in, timeout=60)
    if ok and os.path.exists(out):
        print(f"  ✅ 成功")
        return True
    else:
        print(f"  ❌ 失败: {err[-200:]}")
        return False


def main():
    print("=" * 60)
    print("  分析命令 stdin 修复验证测试")
    print("=" * 60)

    # 检查测试数据
    if not os.path.exists(TPR):
        print(f"❌ 测试TPR不存在: {TPR}")
        return False

    tests = [
        ("energy", test_energy),
        ("rms", test_rmsd),
        ("rmsf", test_rmsf),
        ("gyrate", test_gyrate),
        ("sasa", test_sasa),
        ("density", test_density),
        ("msd", test_msd),
        ("distance", test_distance),
        ("angle", test_angle),
        ("covar", test_covar),
        ("principal", test_principal),
        ("rdf", test_rdf),
        ("hbond", test_hbond),
        ("saltbr", test_saltbr),
        ("cluster", test_cluster),
        ("pairdist", test_pairdist),
    ]

    results = []
    for name, test_func in tests:
        try:
            ok = test_func()
            results.append((name, ok))
        except Exception as e:
            print(f"  ❌ {name} 异常: {str(e)}")
            results.append((name, False))

    # 总结
    print("\n" + "=" * 60)
    print("  测试总结")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    failed = total - passed
    print(f"总测试: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%")

    return failed == 0


if __name__ == "__main__":
    main()
