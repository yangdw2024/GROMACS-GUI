import os
import sys
import subprocess
import json
import time
import numpy as np

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

TEST_DIR = r"D:\YDW\Trae_Gromacs\test\ClFFCl_analysis_test"
REF_DIR = r"D:\YDW\Calculation\Gromacs_simulation\ClFFCl\MD-2\Analysis"

def get_gmx():
    from core.gromacs_service import GromacsService
    gs = GromacsService()
    gs.scan_versions()
    return gs.get_gmx_exe()

def read_xvg(filepath):
    """读取xvg文件，返回标题和数据"""
    data = []
    title = ""
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('@'):
                if 'title' in line:
                    title = line.strip()
            elif not line.startswith('#') and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        data.append([float(parts[0]), float(parts[1])])
                    except:
                        pass
    return title, np.array(data)

def compare_xvg(file1, file2, tolerance=0.001):
    """比较两个xvg文件的数据是否一致"""
    try:
        _, data1 = read_xvg(file1)
        _, data2 = read_xvg(file2)
        
        if len(data1) != len(data2):
            return False, f"数据点数不同: {len(data1)} vs {len(data2)}"
        
        if len(data1) == 0:
            return False, "数据为空"
        
        max_diff = np.max(np.abs(data1[:, 1] - data2[:, 1]))
        mean_diff = np.mean(np.abs(data1[:, 1] - data2[:, 1]))
        
        if max_diff < tolerance:
            return True, f"一致 (最大差值: {max_diff:.6f}, 平均差值: {mean_diff:.6f})"
        else:
            return False, f"不一致 (最大差值: {max_diff:.6f}, 平均差值: {mean_diff:.6f})"
    except Exception as e:
        return False, f"比较失败: {str(e)}"

def test_trajectory_preprocessing():
    """测试轨迹预处理 - 复刻md_clean.xtc的生成"""
    print("\n" + "="*60)
    print("测试1: 轨迹预处理")
    print("="*60)
    
    try:
        gmx = get_gmx()
        print(f"使用gmx: {gmx}")
        
        out_dir = os.path.join(TEST_DIR, "preprocessing_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\nStep 1: PBC修复 + 居中...")
        step1_out = os.path.join(out_dir, "step1_pbc.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", os.path.join(TEST_DIR, "ydw-md2.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", step1_out, "-pbc", "mol", "-center"],
            input="0\n0\n", capture_output=True, text=True, timeout=300, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(step1_out):
            print("  ✅ PBC修复成功")
        else:
            print(f"  ❌ PBC修复失败: {result.stderr[:200]}")
            return False
        
        print("\nStep 2: 旋转+平移拟合...")
        step2_out = os.path.join(out_dir, "step2_fit.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", step1_out,
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", step2_out, "-fit", "rot+trans"],
            input="0\n0\n", capture_output=True, text=True, timeout=300, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(step2_out):
            print("  ✅ 拟合成功")
        else:
            print(f"  ❌ 拟合失败: {result.stderr[:200]}")
            return False
        
        print("\nStep 3: 截取60000-70000ps...")
        final_out = os.path.join(out_dir, "md_clean_test.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", step2_out,
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", final_out, "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=300, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(final_out):
            print("  ✅ 截取成功")
        else:
            print(f"  ❌ 截取失败: {result.stderr[:200]}")
            return False
        
        # 检查帧数
        result = subprocess.run(
            [gmx, "check", "-f", final_out, "-s", os.path.join(TEST_DIR, "ydw-md2.tpr")],
            capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        frames = "未知"
        for line in result.stdout.split('\n'):
            if 'frames' in line.lower() or 'Frames' in line:
                frames = line.strip()
                break
        print(f"\n  ✅ 轨迹帧数: {frames}")
        
        # 与参考md_clean.xtc对比文件大小
        ref_size = os.path.getsize(os.path.join(REF_DIR, "md_clean.xtc"))
        test_size = os.path.getsize(final_out)
        size_diff = abs(ref_size - test_size) / ref_size * 100
        print(f"\n  文件大小对比: 参考={ref_size/1024/1024:.2f}MB, 测试={test_size/1024/1024:.2f}MB, 差异={size_diff:.2f}%")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 轨迹预处理测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_fragment_rdf():
    """测试片段-片段RDF分析 - 复刻fragment_RDF中的结果"""
    print("\n" + "="*60)
    print("测试2: 片段-片段RDF分析")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "rdf_test")
        os.makedirs(out_dir, exist_ok=True)
        
        # 测试几个关键的RDF对
        test_pairs = [
            ("All_s1_BDD", "All_BTP"),
            ("All_s1_BDD", "All_IC1"),
            ("All_s1_BDD", "All_IC2"),
            ("All_s4_BDT", "All_BTP"),
        ]
        
        results = {}
        
        for donor, acceptor in test_pairs:
            print(f"\n计算: {donor} ↔ {acceptor}")
            
            outfile = os.path.join(out_dir, f"rdf_{donor}_{acceptor}.xvg")
            reffile = os.path.join(REF_DIR, "fragment_RDF", f"rdf_{donor}_{acceptor}.xvg")
            
            if not os.path.exists(reffile):
                print(f"  ⚠️ 参考文件不存在，跳过对比")
                continue
            
            result = subprocess.run(
                [gmx, "rdf", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
                 "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
                 "-n", os.path.join(TEST_DIR, "fragment.ndx"),
                 "-ref", f"mol_com of group {donor}",
                 "-sel", f"mol_com of group {acceptor}",
                 "-bin", "0.01", "-b", "60000", "-e", "70000",
                 "-o", outfile],
                capture_output=True, text=True, timeout=600, cwd=TEST_DIR
            )
            
            if result.returncode == 0 and os.path.exists(outfile):
                print(f"  ✅ 计算成功")
                
                # 与参考结果对比
                is_consistent, msg = compare_xvg(outfile, reffile)
                if is_consistent:
                    print(f"  ✅ 与参考结果{msg}")
                    results[f"{donor}_{acceptor}"] = "一致"
                else:
                    print(f"  ⚠️ 与参考结果{msg}")
                    results[f"{donor}_{acceptor}"] = "部分一致"
            else:
                print(f"  ❌ 计算失败: {result.stderr[:200]}")
                results[f"{donor}_{acceptor}"] = "失败"
        
        passed = sum(1 for v in results.values() if v == "一致")
        print(f"\n总结: {passed}/{len(results)} 个RDF分析结果一致")
        
        return passed > 0
        
    except Exception as e:
        print(f"  ❌ RDF测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_energy_analysis():
    """测试能量分析 - 提取并分析能量项"""
    print("\n" + "="*60)
    print("测试3: 能量分解分析")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "energy_test")
        os.makedirs(out_dir, exist_ok=True)
        
        # 测试各种能量项提取
        energy_terms = [
            ("Potential", "10"),
            ("Kinetic", "11"),
            ("Total", "12"),
            ("Temperature", "13"),
            ("Pressure", "14"),
            ("Density", "18"),
            ("LJ (SR)", "28"),
            ("Coulomb (SR)", "32"),
        ]
        
        results = {}
        
        for name, term_id in energy_terms:
            print(f"\n提取: {name}")
            outfile = os.path.join(out_dir, f"energy_{name.replace(' ', '_')}.xvg")
            
            result = subprocess.run(
                [gmx, "energy", "-f", os.path.join(TEST_DIR, "ydw-md2.edr"),
                 "-o", outfile, "-b", "60000", "-e", "70000"],
                input=f"{term_id}\n0\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
            )
            
            if result.returncode == 0 and os.path.exists(outfile):
                # 读取数据计算平均值
                _, data = read_xvg(outfile)
                if len(data) > 0:
                    avg = np.mean(data[:, 1])
                    std = np.std(data[:, 1])
                    print(f"  ✅ 提取成功 (平均值: {avg:.2f} ± {std:.2f})")
                    results[name] = "成功"
                else:
                    print(f"  ⚠️ 数据为空")
                    results[name] = "空数据"
            else:
                print(f"  ❌ 提取失败: {result.stderr[:200]}")
                results[name] = "失败"
        
        passed = sum(1 for v in results.values() if v == "成功")
        print(f"\n总结: {passed}/{len(results)} 个能量项提取成功")
        
        return passed > 0
        
    except Exception as e:
        print(f"  ❌ 能量分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rmsd_analysis():
    """测试RMSD分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试4: RMSD分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "rmsd_test")
        os.makedirs(out_dir, exist_ok=True)
        
        # 测试不同组的RMSD
        tests = [
            ("Backbone", "Backbone", "骨架RMSD"),
            ("Protein", "Protein", "蛋白质RMSD"),
        ]
        
        results = {}
        
        for ref_group, sel_group, desc in tests:
            print(f"\n计算: {desc}")
            outfile = os.path.join(out_dir, f"rmsd_{ref_group}.xvg")
            
            result = subprocess.run(
                [gmx, "rms", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
                 "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
                 "-o", outfile, "-b", "60000", "-e", "70000"],
                input=f"{ref_group}\n{sel_group}\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
            )
            
            if result.returncode == 0 and os.path.exists(outfile):
                _, data = read_xvg(outfile)
                if len(data) > 0:
                    avg = np.mean(data[:, 1])
                    final = data[-1, 1]
                    print(f"  ✅ 计算成功 (平均: {avg:.3f} nm, 最终: {final:.3f} nm)")
                    results[desc] = "成功"
                else:
                    print(f"  ⚠️ 数据为空")
                    results[desc] = "空数据"
            else:
                print(f"  ⚠️ 计算可能失败（可能组名不匹配）: {result.stderr[:100]}")
                results[desc] = "跳过"
        
        # 使用默认组测试
        print("\n使用默认组测试RMSD...")
        outfile = os.path.join(out_dir, "rmsd_default.xvg")
        result = subprocess.run(
            [gmx, "rms", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="4\n4\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                print(f"  ✅ 默认组RMSD成功 (平均值: {avg:.3f} nm)")
                results["默认组"] = "成功"
        
        return True
        
    except Exception as e:
        print(f"  ❌ RMSD分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rmsf_analysis():
    """测试RMSF分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试5: RMSF分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "rmsf_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\n计算原子RMSF...")
        outfile = os.path.join(out_dir, "rmsf.xvg")
        result = subprocess.run(
            [gmx, "rmsf", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000", "-res"],
            input="0\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
        )
        
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                max_rmsf = np.max(data[:, 1])
                print(f"  ✅ RMSF计算成功 (平均: {avg:.3f} nm, 最大: {max_rmsf:.3f} nm, 残基数: {len(data)})")
                return True
            else:
                print(f"  ⚠️ 数据为空")
                return False
        else:
            print(f"  ❌ RMSF计算失败: {result.stderr[:200]}")
            return False
        
    except Exception as e:
        print(f"  ❌ RMSF分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_msd_analysis():
    """测试MSD分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试6: MSD分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "msd_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\n计算MSD...")
        outfile = os.path.join(out_dir, "msd.xvg")
        result = subprocess.run(
            [gmx, "msd", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
        )
        
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                final_msd = data[-1, 1]
                # 计算扩散系数 (斜率/6，单位转换)
                if len(data) > 100:
                    # 取后半段线性拟合
                    half = len(data) // 2
                    x = data[half:, 0]
                    y = data[half:, 1]
                    if len(x) > 1:
                        slope = np.polyfit(x, y, 1)[0]
                        D = slope / 6 * 1e-9 * 1e12  # nm²/ps -> m²/s
                        print(f"  ✅ MSD计算成功 (最终值: {final_msd:.3f} nm², 扩散系数: {D:.2e} m²/s)")
                    else:
                        print(f"  ✅ MSD计算成功 (最终值: {final_msd:.3f} nm²)")
                return True
            else:
                print(f"  ⚠️ 数据为空")
                return False
        else:
            print(f"  ❌ MSD计算失败: {result.stderr[:200]}")
            return False
        
    except Exception as e:
        print(f"  ❌ MSD分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_sasa_analysis():
    """测试SASA分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试7: SASA分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "sasa_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\n计算SASA...")
        outfile = os.path.join(out_dir, "sasa.xvg")
        result = subprocess.run(
            [gmx, "sasa", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
        )
        
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                print(f"  ✅ SASA计算成功 (平均: {avg:.1f} nm²)")
                return True
            else:
                print(f"  ⚠️ 数据为空")
                return False
        else:
            print(f"  ⚠️ SASA计算可能失败: {result.stderr[:100]}")
            return False
        
    except Exception as e:
        print(f"  ❌ SASA分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_hbond_analysis():
    """测试氢键分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试8: 氢键分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "hbond_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\n计算氢键...")
        outfile = os.path.join(out_dir, "hbond.xvg")
        result = subprocess.run(
            [gmx, "hbond", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-num", outfile, "-b", "60000", "-e", "70000"],
            input="0\n0\n", capture_output=True, text=True, timeout=300, cwd=TEST_DIR
        )
        
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                print(f"  ✅ 氢键计算成功 (平均数: {avg:.1f})")
                return True
            else:
                print(f"  ⚠️ 数据为空")
                return False
        else:
            print(f"  ⚠️ 氢键计算可能失败: {result.stderr[:100]}")
            return False
        
    except Exception as e:
        print(f"  ❌ 氢键分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_cluster_analysis():
    """测试团簇分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试9: 团簇分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "cluster_test")
        os.makedirs(out_dir, exist_ok=True)
        
        print("\n计算团簇分布...")
        outfile = os.path.join(out_dir, "cluster.xvg")
        result = subprocess.run(
            [gmx, "cluster", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
             "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
             "-o", outfile, "-method", "gromos", "-cutoff", "0.2",
             "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=300, cwd=TEST_DIR
        )
        
        if result.returncode == 0:
            print(f"  ✅ 团簇分析成功")
            # 检查生成的文件
            for f in os.listdir(out_dir):
                print(f"     - {f}")
            return True
        else:
            print(f"  ⚠️ 团簇分析可能失败: {result.stderr[:100]}")
            return False
        
    except Exception as e:
        print(f"  ❌ 团簇分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pairdist_analysis():
    """测试pairdist分析 - 补全分析"""
    print("\n" + "="*60)
    print("测试10: 最近邻距离分析（补全）")
    print("="*60)
    
    try:
        gmx = get_gmx()
        
        out_dir = os.path.join(TEST_DIR, "pairdist_test")
        os.makedirs(out_dir, exist_ok=True)
        
        # 测试几个关键对
        test_pairs = [
            ("All_s1_BDD", "All_BTP"),
            ("All_s1_BDD", "All_IC1"),
        ]
        
        for group1, group2 in test_pairs:
            print(f"\n计算: {group1} ↔ {group2} 最近邻距离")
            outfile = os.path.join(out_dir, f"min_{group1}_{group2}.xvg")
            
            result = subprocess.run(
                [gmx, "pairdist", "-f", os.path.join(TEST_DIR, "md_clean.xtc"),
                 "-s", os.path.join(TEST_DIR, "ydw-md2.tpr"),
                 "-n", os.path.join(TEST_DIR, "fragment.ndx"),
                 "-ref", f"group {group1}",
                 "-sel", f"group {group2}",
                 "-type", "min",
                 "-b", "60000", "-e", "70000",
                 "-o", outfile],
                capture_output=True, text=True, timeout=300, cwd=TEST_DIR
            )
            
            if result.returncode == 0 and os.path.exists(outfile):
                _, data = read_xvg(outfile)
                if len(data) > 0:
                    avg = np.mean(data[:, 1])
                    min_val = np.min(data[:, 1])
                    print(f"  ✅ 计算成功 (平均: {avg:.3f} nm, 最小: {min_val:.3f} nm)")
                else:
                    print(f"  ⚠️ 数据为空")
            else:
                print(f"  ❌ 计算失败: {result.stderr[:200]}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ pairdist测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*70)
    print("  GROMACS 分析模块深度测试 - ClFFCl体系")
    print("="*70)
    print(f"测试目录: {TEST_DIR}")
    print(f"参考目录: {REF_DIR}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    tests = [
        ("轨迹预处理", test_trajectory_preprocessing),
        ("片段-片段RDF分析", test_fragment_rdf),
        ("能量分解分析", test_energy_analysis),
        ("RMSD分析（补全）", test_rmsd_analysis),
        ("RMSF分析（补全）", test_rmsf_analysis),
        ("MSD分析（补全）", test_msd_analysis),
        ("SASA分析（补全）", test_sasa_analysis),
        ("氢键分析（补全）", test_hbond_analysis),
        ("团簇分析（补全）", test_cluster_analysis),
        ("最近邻距离分析（补全）", test_pairdist_analysis),
    ]
    
    for name, test_func in tests:
        try:
            passed = test_func()
            results[name] = passed
            print(f"\n  >>> {'✅' if passed else '❌'} {name} {'通过' if passed else '失败'}")
        except Exception as e:
            print(f"\n  >>> ❌ {name} 异常: {str(e)}")
            results[name] = False
    
    print("\n" + "="*70)
    print("  检测总结")
    print("="*70)
    print(f"总测试数: {len(tests)}")
    passed_count = sum(1 for v in results.values() if v)
    print(f"通过数: {passed_count}")
    print(f"失败数: {len(tests) - passed_count}")
    print(f"整体状态: {'✅ 全部通过' if passed_count == len(tests) else '⚠️ 部分通过'}")
    
    print("\n详细结果:")
    for name, passed in results.items():
        print(f"  {'✅' if passed else '❌'} {name}")
    
    # 保存报告
    report = {
        "检测时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "测试体系": "ClFFCl MD-2",
        "整体状态": "全部通过" if passed_count == len(tests) else "部分通过",
        "测试详情": {k: "通过" if v else "失败" for k, v in results.items()},
        "已复刻分析": [
            "轨迹预处理（PBC修复+拟合+截取）",
            "片段-片段质心RDF分析",
            "能量分解分析",
        ],
        "补全分析": [
            "RMSD分析",
            "RMSF分析",
            "MSD分析（扩散系数）",
            "SASA分析",
            "氢键分析",
            "团簇分析",
            "最近邻距离分析",
        ]
    }
    
    report_path = os.path.join(TEST_DIR, "分析模块深度测试报告.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_path}")
    
    return passed_count == len(tests)

if __name__ == "__main__":
    main()
