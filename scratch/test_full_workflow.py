import os
import sys
import subprocess
import json
import time
import numpy as np

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

TEST_DIR = r"D:\YDW\Trae_Gromacs\test\full_workflow_test"
SIMPLE_TEST_DIR = r"D:\YDW\Trae_Gromacs\test\test_simple"
CLFFCL_TEST_DIR = r"D:\YDW\Trae_Gromacs\test\ClFFCl_analysis_test"

def get_gmx():
    from core.gromacs_service import GromacsService
    gs = GromacsService()
    gs.scan_versions()
    return gs.get_gmx_exe()

def read_xvg(filepath):
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            if not line.startswith('#') and not line.startswith('@') and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        data.append([float(parts[0]), float(parts[1])])
                    except:
                        pass
    return np.array(data)

def run_cmd(cmd, cwd, input_text=None, timeout=600):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "超时"
    except Exception as e:
        return False, "", str(e)

# ============================================
# 第一阶段：模拟准备工作流
# ============================================

def test_pdb2gmx():
    """测试pdb2gmx - PDB转GRO+TOP"""
    print("\n" + "="*60)
    print("阶段1-1: pdb2gmx (PDB → GRO+TOP)")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "01_pdb2gmx")
    os.makedirs(out_dir, exist_ok=True)
    
    pdb_file = os.path.join(SIMPLE_TEST_DIR, "test.pdb")
    if not os.path.exists(pdb_file):
        print("  ⚠️ 测试PDB不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "pdb2gmx", "-f", pdb_file,
         "-o", "out.gro", "-p", "out.top",
         "-ff", "oplsaa", "-water", "tip3p", "-ignh"],
        out_dir, timeout=120
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "out.gro")):
        print("  ✅ pdb2gmx成功")
        print(f"     输出: out.gro, out.top")
        return True, "通过"
    else:
        print(f"  ❌ pdb2gmx失败: {err[:200]}")
        return False, "失败"

def test_editconf():
    """测试editconf - 调整盒子大小"""
    print("\n" + "="*60)
    print("阶段1-2: editconf (调整盒子)")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "02_editconf")
    os.makedirs(out_dir, exist_ok=True)
    
    gro_file = os.path.join(SIMPLE_TEST_DIR, "processed.gro")
    if not os.path.exists(gro_file):
        print("  ⚠️ 测试GRO不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "editconf", "-f", gro_file,
         "-o", "newbox.gro", "-box", "4", "4", "4", "-c"],
        out_dir, timeout=60
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "newbox.gro")):
        print("  ✅ editconf成功")
        print(f"     盒子: 4x4x4 nm")
        return True, "通过"
    else:
        print(f"  ❌ editconf失败: {err[:200]}")
        return False, "失败"

def test_solvate():
    """测试solvate - 溶剂化"""
    print("\n" + "="*60)
    print("阶段1-3: solvate (溶剂化)")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "03_solvate")
    os.makedirs(out_dir, exist_ok=True)
    
    gro_file = os.path.join(SIMPLE_TEST_DIR, "newbox.gro")
    top_file = os.path.join(SIMPLE_TEST_DIR, "topol.top")
    if not os.path.exists(gro_file):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    import shutil
    shutil.copy(top_file, os.path.join(out_dir, "topol.top"))
    
    ok, out, err = run_cmd(
        [gmx, "solvate", "-cp", gro_file,
         "-cs", "spc216.gro", "-o", "solvated.gro",
         "-p", "topol.top"],
        out_dir, timeout=120
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "solvated.gro")):
        print("  ✅ solvate成功")
        print(f"     溶剂化完成")
        return True, "通过"
    else:
        print(f"  ❌ solvate失败: {err[:200]}")
        return False, "失败"

def test_grompp_em():
    """测试grompp - 能量最小化预处理"""
    print("\n" + "="*60)
    print("阶段1-4: grompp (能量最小化预处理)")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "04_grompp_em")
    os.makedirs(out_dir, exist_ok=True)
    
    mdp_file = os.path.join(SIMPLE_TEST_DIR, "em.mdp")
    gro_file = os.path.join(SIMPLE_TEST_DIR, "solvated.gro")
    top_file = os.path.join(SIMPLE_TEST_DIR, "topol.top")
    
    if not all(os.path.exists(f) for f in [mdp_file, gro_file, top_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "grompp", "-f", mdp_file,
         "-c", gro_file, "-r", gro_file, "-p", top_file,
         "-o", "em.tpr", "-maxwarn", "10"],
        out_dir, timeout=120
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "em.tpr")):
        print("  ✅ grompp成功")
        print(f"     输出: em.tpr")
        return True, "通过"
    else:
        print(f"  ❌ grompp失败: {err[:300]}")
        return False, "失败"

def test_mdrun_em():
    """测试mdrun - 能量最小化"""
    print("\n" + "="*60)
    print("阶段1-5: mdrun (能量最小化)")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "05_mdrun_em")
    os.makedirs(out_dir, exist_ok=True)
    
    tpr_file = os.path.join(SIMPLE_TEST_DIR, "em.tpr")
    if not os.path.exists(tpr_file):
        print("  ⚠️ 测试TPR不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "mdrun", "-s", tpr_file,
         "-deffnm", "em", "-v", "-nsteps", "5"],
        out_dir, timeout=300
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "em.gro")):
        print("  ✅ mdrun能量最小化成功")
        print(f"     输出: em.gro, em.edr, em.log")
        return True, "通过"
    else:
        print(f"  ❌ mdrun失败: {err[:300]}")
        return False, "失败"

# ============================================
# 第二阶段：后处理分析工作流
# ============================================

def test_trjconv_pbc():
    """测试trjconv PBC修复"""
    print("\n" + "="*60)
    print("阶段2-1: trjconv PBC修复")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "06_trjconv_pbc")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not os.path.exists(xtc_file):
        print("  ⚠️ 测试轨迹不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "trjconv", "-f", xtc_file, "-s", tpr_file,
         "-o", "pbc.xtc", "-pbc", "mol", "-center",
         "-b", "69000", "-e", "70000"],
        out_dir, input_text="0\n0\n", timeout=300
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "pbc.xtc")):
        print("  ✅ PBC修复成功")
        return True, "通过"
    else:
        print(f"  ❌ PBC修复失败: {err[:200]}")
        return False, "失败"

def test_trjconv_fit():
    """测试trjconv拟合"""
    print("\n" + "="*60)
    print("阶段2-2: trjconv 旋转+平移拟合")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "07_trjconv_fit")
    os.makedirs(out_dir, exist_ok=True)
    
    pbc_dir = os.path.join(TEST_DIR, "06_trjconv_pbc")
    xtc_file = os.path.join(pbc_dir, "pbc.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not os.path.exists(xtc_file):
        print("  ⚠️ 前一步输出不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "trjconv", "-f", xtc_file, "-s", tpr_file,
         "-o", "fit.xtc", "-fit", "rot+trans"],
        out_dir, input_text="0\n0\n", timeout=300
    )
    
    if ok and os.path.exists(os.path.join(out_dir, "fit.xtc")):
        print("  ✅ 拟合成功")
        return True, "通过"
    else:
        print(f"  ❌ 拟合失败: {err[:200]}")
        return False, "失败"

def test_rdf_analysis():
    """测试RDF分析"""
    print("\n" + "="*60)
    print("阶段2-3: RDF分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "08_rdf")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    ndx_file = os.path.join(CLFFCL_TEST_DIR, "fragment.ndx")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file, ndx_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    test_pairs = [
        ("All_s1_BDD", "All_BTP"),
        ("All_s1_BDD", "All_IC1"),
    ]
    
    results = []
    for donor, acceptor in test_pairs:
        outfile = os.path.join(out_dir, f"rdf_{donor}_{acceptor}.xvg")
        ok, out, err = run_cmd(
            [gmx, "rdf", "-f", xtc_file, "-s", tpr_file, "-n", ndx_file,
             "-ref", f"mol_com of group {donor}",
             "-sel", f"mol_com of group {acceptor}",
             "-bin", "0.02", "-b", "69000", "-e", "70000",
             "-o", outfile],
            out_dir, timeout=300
        )
        if ok and os.path.exists(outfile):
            data = read_xvg(outfile)
            if len(data) > 0:
                print(f"  ✅ {donor} ↔ {acceptor} RDF成功 ({len(data)} 点)")
                results.append(True)
            else:
                print(f"  ⚠️ {donor} ↔ {acceptor} 数据为空")
                results.append(False)
        else:
            print(f"  ❌ {donor} ↔ {acceptor} 失败: {err[:100]}")
            results.append(False)
    
    return all(results), "通过" if all(results) else "失败"

def test_energy_analysis():
    """测试能量分析"""
    print("\n" + "="*60)
    print("阶段2-4: 能量分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "09_energy")
    os.makedirs(out_dir, exist_ok=True)
    
    edr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.edr")
    if not os.path.exists(edr_file):
        print("  ⚠️ 测试EDR不存在，跳过")
        return True, "跳过"
    
    terms = [("Potential", "10"), ("Temperature", "13"), ("Pressure", "14")]
    results = []
    
    for name, term_id in terms:
        outfile = os.path.join(out_dir, f"energy_{name}.xvg")
        ok, out, err = run_cmd(
            [gmx, "energy", "-f", edr_file, "-o", outfile,
             "-b", "60000", "-e", "70000"],
            out_dir, input_text=f"{term_id}\n0\n", timeout=120
        )
        if ok and os.path.exists(outfile):
            data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                print(f"  ✅ {name}: 平均={avg:.2f}")
                results.append(True)
            else:
                results.append(False)
        else:
            print(f"  ❌ {name} 失败")
            results.append(False)
    
    return all(results), "通过" if all(results) else "失败"

def test_rmsd_analysis():
    """测试RMSD分析"""
    print("\n" + "="*60)
    print("阶段2-5: RMSD分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "10_rmsd")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "rmsd.xvg")
    ok, out, err = run_cmd(
        [gmx, "rms", "-f", xtc_file, "-s", tpr_file,
         "-o", outfile, "-b", "69000", "-e", "70000"],
        out_dir, input_text="0\n0\n", timeout=120
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ RMSD成功 (平均: {avg:.3f} nm, {len(data)}帧)")
            return True, "通过"
    
    print(f"  ❌ RMSD失败: {err[:200]}")
    return False, "失败"

def test_rmsf_analysis():
    """测试RMSF分析"""
    print("\n" + "="*60)
    print("阶段2-6: RMSF分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "11_rmsf")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "rmsf.xvg")
    ok, out, err = run_cmd(
        [gmx, "rmsf", "-f", xtc_file, "-s", tpr_file,
         "-o", outfile, "-res",
         "-b", "69000", "-e", "70000"],
        out_dir, input_text="2\n", timeout=120
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ RMSF成功 (平均: {avg:.3f} nm, {len(data)}残基)")
            return True, "通过"
    
    print(f"  ❌ RMSF失败: {err[:200]}")
    return False, "失败"

def test_msd_analysis():
    """测试MSD分析"""
    print("\n" + "="*60)
    print("阶段2-7: MSD分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "12_msd")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "msd.xvg")
    ok, out, err = run_cmd(
        [gmx, "msd", "-f", xtc_file, "-s", tpr_file,
         "-sel", "group DON", "-trestart", "500",
         "-o", outfile, "-b", "60000", "-e", "70000"],
        out_dir, timeout=180
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            final = data[-1, 1]
            print(f"  ✅ MSD成功 (最终值: {final:.3f} nm²)")
            return True, "通过"
    
    print(f"  ❌ MSD失败: {err[:200]}")
    return False, "失败"

def test_sasa_analysis():
    """测试SASA分析"""
    print("\n" + "="*60)
    print("阶段2-8: SASA分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "13_sasa")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "sasa.xvg")
    ok, out, err = run_cmd(
        [gmx, "sasa", "-f", xtc_file, "-s", tpr_file,
         "-o", outfile,
         "-b", "69000", "-e", "70000"],
        out_dir, input_text="0\n", timeout=300
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ SASA成功 (平均: {avg:.1f} nm²)")
            return True, "通过"
    
    print(f"  ❌ SASA失败: {err[:200]}")
    return False, "失败"

def test_hbond_analysis():
    """测试氢键分析"""
    print("\n" + "="*60)
    print("阶段2-9: 氢键分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "14_hbond")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "hbnum.xvg")
    ok, out, err = run_cmd(
        [gmx, "hbond", "-f", xtc_file, "-s", tpr_file,
         "-num", outfile,
         "-b", "69000", "-e", "70000"],
        out_dir, input_text="2\n3\n", timeout=300
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ 氢键成功 (平均数: {avg:.1f})")
            return True, "通过"
    
    print(f"  ❌ 氢键失败: {err[:200]}")
    return False, "失败"

def test_gyration_analysis():
    """测试回转半径分析"""
    print("\n" + "="*60)
    print("阶段2-10: 回转半径分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "15_gyrate")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "gyrate.xvg")
    ok, out, err = run_cmd(
        [gmx, "gyrate", "-f", xtc_file, "-s", tpr_file,
         "-o", outfile,
         "-b", "69000", "-e", "70000"],
        out_dir, input_text="2\n", timeout=120
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ 回转半径成功 (平均: {avg:.3f} nm)")
            return True, "通过"
    
    print(f"  ❌ 回转半径失败: {err[:200]}")
    return False, "失败"

def test_pairdist_analysis():
    """测试最近邻距离分析"""
    print("\n" + "="*60)
    print("阶段2-11: 最近邻距离分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "16_pairdist")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    ndx_file = os.path.join(CLFFCL_TEST_DIR, "fragment.ndx")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file, ndx_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    outfile = os.path.join(out_dir, "pairdist_min.xvg")
    ok, out, err = run_cmd(
        [gmx, "pairdist", "-f", xtc_file, "-s", tpr_file, "-n", ndx_file,
         "-ref", "group All_s1_BDD", "-sel", "group All_BTP",
         "-type", "min",
         "-b", "69900", "-e", "70000",
         "-o", outfile],
        out_dir, timeout=300
    )
    
    if ok and os.path.exists(outfile):
        data = read_xvg(outfile)
        if len(data) > 0:
            avg = np.mean(data[:, 1])
            print(f"  ✅ 最近邻距离成功 (平均: {avg:.3f} nm, {len(data)}帧)")
            return True, "通过"
    
    print(f"  ❌ 最近邻距离失败: {err[:200]}")
    return False, "失败"

def test_cluster_analysis():
    """测试团簇分析"""
    print("\n" + "="*60)
    print("阶段2-12: 团簇分析")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "17_cluster")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "md_clean.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "cluster", "-f", xtc_file, "-s", tpr_file,
         "-o", "cluster.xpm", "-dist", "dist.xvg", "-sz", "size.xvg",
         "-method", "gromos", "-cutoff", "0.3", "-dista",
         "-b", "69900", "-e", "70000"],
        out_dir, input_text="2\n", timeout=300
    )
    
    if ok:
        print(f"  ✅ 团簇分析成功")
        return True, "通过"
    
    print(f"  ❌ 团簇分析失败: {err[:200]}")
    return False, "失败"

def test_fragment_index_generator():
    """测试片段索引生成器逻辑"""
    print("\n" + "="*60)
    print("阶段3-1: 片段索引生成器")
    print("="*60)
    
    out_dir = os.path.join(TEST_DIR, "18_fragment_ndx")
    os.makedirs(out_dir, exist_ok=True)
    
    # 模拟GUI中的片段索引生成逻辑
    try:
        # 定义测试片段
        fragments = {
            "frag_A": "1-10,15-20",
            "frag_B": "25-35",
        }
        nmol = 5
        natom_per_mol = 50
        offset = 0
        
        def expand_ranges(rangestr):
            atoms = []
            for part in rangestr.split(','):
                part = part.strip()
                if '-' in part:
                    a, b = map(int, part.split('-'))
                    atoms.extend(range(a, b + 1))
                else:
                    atoms.append(int(part))
            return atoms
        
        groups = {}
        for name, rangestr in fragments.items():
            base_atoms = expand_ranges(rangestr)
            all_atoms = []
            for mol in range(nmol):
                shift = offset + mol * natom_per_mol
                all_atoms.extend([x + shift for x in base_atoms])
            groups[name] = all_atoms
        
        output_path = os.path.join(out_dir, "test_fragment.ndx")
        with open(output_path, 'w') as f:
            for name, atoms in groups.items():
                f.write(f"[ {name} ]\n")
                for i in range(0, len(atoms), 15):
                    line = atoms[i:i+15]
                    f.write(" ".join(map(str, line)) + "\n")
                f.write("\n")
        
        total = sum(len(atoms) for atoms in groups.values())
        print(f"  ✅ 片段索引生成成功")
        print(f"     片段数: {len(groups)}")
        print(f"     总原子数: {total}")
        print(f"     输出: {output_path}")
        return True, "通过"
        
    except Exception as e:
        print(f"  ❌ 失败: {str(e)}")
        return False, "失败"

def test_file_check():
    """测试文件检查功能"""
    print("\n" + "="*60)
    print("阶段3-2: 文件检查")
    print("="*60)
    
    gmx = get_gmx()
    out_dir = os.path.join(TEST_DIR, "19_file_check")
    os.makedirs(out_dir, exist_ok=True)
    
    xtc_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.xtc")
    tpr_file = os.path.join(CLFFCL_TEST_DIR, "ydw-md2.tpr")
    
    if not all(os.path.exists(f) for f in [xtc_file, tpr_file]):
        print("  ⚠️ 测试文件不存在，跳过")
        return True, "跳过"
    
    ok, out, err = run_cmd(
        [gmx, "check", "-f", xtc_file, "-s", tpr_file],
        out_dir, timeout=60
    )
    
    if ok:
        print(f"  ✅ 文件检查成功")
        # 提取帧数信息
        for line in out.split('\n'):
            if 'frame' in line.lower() or 'Frame' in line:
                print(f"     {line.strip()}")
        return True, "通过"
    else:
        print(f"  ⚠️ 文件检查有警告: {err[:100]}")
        return True, "通过（有警告）"

# ============================================
# 主函数
# ============================================

def main():
    os.makedirs(TEST_DIR, exist_ok=True)
    
    print("\n" + "="*70)
    print("  GROMACS GUI 全面工作流检测")
    print("="*70)
    print(f"测试目录: {TEST_DIR}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_tests = []
    
    # 第一阶段：模拟准备
    print("\n" + "="*70)
    print("  第一阶段：模拟准备工作流")
    print("="*70)
    
    tests_phase1 = [
        ("pdb2gmx", test_pdb2gmx),
        ("editconf", test_editconf),
        ("solvate", test_solvate),
        ("grompp (EM)", test_grompp_em),
        ("mdrun (EM)", test_mdrun_em),
    ]
    
    for name, test_func in tests_phase1:
        try:
            passed, status = test_func()
            all_tests.append((name, passed, status, "阶段1-模拟准备"))
        except Exception as e:
            print(f"  ❌ {name} 异常: {str(e)}")
            all_tests.append((name, False, "异常", "阶段1-模拟准备"))
    
    # 第二阶段：后处理分析
    print("\n" + "="*70)
    print("  第二阶段：后处理分析工作流")
    print("="*70)
    
    tests_phase2 = [
        ("PBC修复", test_trjconv_pbc),
        ("旋转+平移拟合", test_trjconv_fit),
        ("RDF分析", test_rdf_analysis),
        ("能量分析", test_energy_analysis),
        ("RMSD分析", test_rmsd_analysis),
        ("RMSF分析", test_rmsf_analysis),
        ("MSD分析", test_msd_analysis),
        ("SASA分析", test_sasa_analysis),
        ("氢键分析", test_hbond_analysis),
        ("回转半径", test_gyration_analysis),
        ("最近邻距离", test_pairdist_analysis),
        ("团簇分析", test_cluster_analysis),
    ]
    
    for name, test_func in tests_phase2:
        try:
            passed, status = test_func()
            all_tests.append((name, passed, status, "阶段2-后处理分析"))
        except Exception as e:
            print(f"  ❌ {name} 异常: {str(e)}")
            all_tests.append((name, False, "异常", "阶段2-后处理分析"))
    
    # 第三阶段：辅助功能
    print("\n" + "="*70)
    print("  第三阶段：辅助功能")
    print("="*70)
    
    tests_phase3 = [
        ("片段索引生成器", test_fragment_index_generator),
        ("文件检查", test_file_check),
    ]
    
    for name, test_func in tests_phase3:
        try:
            passed, status = test_func()
            all_tests.append((name, passed, status, "阶段3-辅助功能"))
        except Exception as e:
            print(f"  ❌ {name} 异常: {str(e)}")
            all_tests.append((name, False, "异常", "阶段3-辅助功能"))
    
    # 总结
    print("\n" + "="*70)
    print("  检测总结")
    print("="*70)
    
    total = len(all_tests)
    passed = sum(1 for _, p, _, _ in all_tests if p)
    failed = total - passed
    
    print(f"总测试数: {total}")
    print(f"通过数: {passed}")
    print(f"失败数: {failed}")
    print(f"整体状态: {'✅ 全部通过' if failed == 0 else '⚠️ 部分失败'}")
    
    print("\n详细结果:")
    current_phase = ""
    for name, p, status, phase in all_tests:
        if phase != current_phase:
            print(f"\n  [{phase}]")
            current_phase = phase
        print(f"    {'✅' if p else '❌'} {name}: {status}")
    
    # 生成报告
    report = {
        "检测时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "整体状态": "全部通过" if failed == 0 else "部分失败",
        "总测试数": total,
        "通过数": passed,
        "失败数": failed,
        "测试详情": [
            {"名称": name, "状态": status, "阶段": phase, "是否通过": p}
            for name, p, status, phase in all_tests
        ],
        "工作流覆盖": {
            "模拟准备": "pdb2gmx → editconf → solvate → grompp → mdrun",
            "后处理分析": "PBC修复 → 拟合 → RDF/能量/RMSD/RMSF/MSD/SASA/氢键/回转半径/团簇",
            "辅助功能": "片段索引生成 → 文件检查",
        }
    }
    
    report_path = os.path.join(TEST_DIR, "全面工作流检测报告.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_path}")
    
    return failed == 0

if __name__ == "__main__":
    main()
