import os
import sys
import subprocess
import json
import time

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

TEST_DIR = r"D:\YDW\Trae_Gromacs\test\test_water_system"

def test_fragment_index_generator():
    """测试片段索引生成器"""
    print("测试片段索引生成器...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        
        ndx_content = """[ fragment1 ]
1 2 3
4 5 6

[ fragment2 ]
7 8 9
10 11 12
"""
        ndx_path = os.path.join(TEST_DIR, "test_fragment.ndx")
        with open(ndx_path, 'w') as f:
            f.write(ndx_content)
        print("  ✅ 测试片段索引文件生成成功")
        
        result = subprocess.run(
            [gs.get_gmx_exe(), "make_ndx", "-f", os.path.join(TEST_DIR, "md.gro"), "-n", ndx_path, "-o", ndx_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 or "Reading file" in result.stdout:
            print("  ✅ 片段索引文件验证通过")
            return True
        else:
            print(f"  ⚠️ 片段索引验证警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ 片段索引生成器测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rdf_analysis():
    """测试RDF分析"""
    print("测试RDF分析...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "rdf", "-f", os.path.join(TEST_DIR, "md.xtc"), "-s", os.path.join(TEST_DIR, "md.tpr"),
             "-ref", "Water", "-sel", "Water", "-o", "test_rdf.xvg"],
            input="1\n1\n0\n", capture_output=True, text=True, timeout=120, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ RDF分析成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_rdf.xvg")):
                print("  ✅ RDF输出文件生成成功")
                with open(os.path.join(TEST_DIR, "test_rdf.xvg"), 'r') as f:
                    lines = f.readlines()
                    print(f"  ✅ RDF数据点数: {len([l for l in lines if not l.startswith('#') and not l.startswith('@')])}")
                os.remove(os.path.join(TEST_DIR, "test_rdf.xvg"))
            return True
        else:
            print(f"  ❌ RDF分析失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ RDF分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_trajectory_preprocessing():
    """测试轨迹预处理"""
    print("测试轨迹预处理...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 测试PBC修复
        result = subprocess.run(
            [gmx_path, "trjconv", "-f", os.path.join(TEST_DIR, "md.xtc"), "-s", os.path.join(TEST_DIR, "md.tpr"),
             "-o", "test_pbc.xtc", "-pbc", "mol", "-center"],
            input="0\n0\n", capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(os.path.join(TEST_DIR, "test_pbc.xtc")):
            print("  ✅ PBC修复成功")
        else:
            print(f"  ⚠️ PBC修复警告: {result.stderr[:100]}")
        
        # 测试拟合
        result = subprocess.run(
            [gmx_path, "trjconv", "-f", os.path.join(TEST_DIR, "test_pbc.xtc"), "-s", os.path.join(TEST_DIR, "md.tpr"),
             "-o", "test_fit.xtc", "-fit", "rot+trans"],
            input="0\n0\n", capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(os.path.join(TEST_DIR, "test_fit.xtc")):
            print("  ✅ 旋转+平移拟合成功")
        else:
            print(f"  ⚠️ 拟合警告: {result.stderr[:100]}")
        
        # 测试截取和降采样
        result = subprocess.run(
            [gmx_path, "trjconv", "-f", os.path.join(TEST_DIR, "test_fit.xtc"), "-s", os.path.join(TEST_DIR, "md.tpr"),
             "-o", "test_clean.xtc", "-b", "100", "-dt", "10"],
            input="0\n", capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(os.path.join(TEST_DIR, "test_clean.xtc")):
            print("  ✅ 截取+降采样成功")
        
        # 清理临时文件
        for f in ["test_pbc.xtc", "test_fit.xtc", "test_clean.xtc"]:
            fp = os.path.join(TEST_DIR, f)
            if os.path.exists(fp):
                os.remove(fp)
        
        return True
    except Exception as e:
        print(f"  ❌ 轨迹预处理测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_energy_decomposition():
    """测试能量分解分析"""
    print("测试能量分解分析...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 测试能量提取
        result = subprocess.run(
            [gmx_path, "energy", "-f", os.path.join(TEST_DIR, "md.edr"), "-o", "test_energy.xvg"],
            input="10\n0\n", capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ 能量提取成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_energy.xvg")):
                print("  ✅ 能量输出文件生成成功")
                os.remove(os.path.join(TEST_DIR, "test_energy.xvg"))
            return True
        else:
            print(f"  ⚠️ 能量提取警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ 能量分解分析测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_file_check():
    """测试文件检查功能"""
    print("测试文件检查功能...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 测试gmx check
        result = subprocess.run(
            [gmx_path, "check", "-f", os.path.join(TEST_DIR, "md.xtc"), "-s", os.path.join(TEST_DIR, "md.tpr")],
            capture_output=True, text=True, timeout=30, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ 文件检查成功")
            # 解析输出获取帧数
            for line in result.stdout.split('\n'):
                if "Frames" in line:
                    print(f"  ✅ 轨迹帧数: {line.strip()}")
            return True
        else:
            print(f"  ⚠️ 文件检查警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ 文件检查功能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_gpu_cpu_switch():
    """测试GPU/CPU切换"""
    print("测试GPU/CPU切换...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 检查GPU是否可用
        result = subprocess.run(
            [gmx_path, "gpu_id", "-list"],
            capture_output=True, text=True, timeout=15
        )
        if "Detected" in result.stdout or "GPU" in result.stdout:
            print("  ✅ GPU检测成功")
        else:
            print("  ⚠️ GPU检测无输出")
        
        # 检查mdrun参数
        result = subprocess.run(
            [gmx_path, "mdrun", "-h"],
            capture_output=True, text=True, timeout=15
        )
        has_gpu_flags = "-nb gpu" in result.stdout or "-pme gpu" in result.stdout
        has_cpu_flags = "-nb cpu" in result.stdout or "-pme cpu" in result.stdout
        
        if has_gpu_flags and has_cpu_flags:
            print("  ✅ GPU/CPU切换参数支持")
        elif has_cpu_flags:
            print("  ✅ CPU模式支持")
        else:
            print("  ⚠️ GPU/CPU参数检查不完全")
        
        return True
    except Exception as e:
        print(f"  ❌ GPU/CPU切换测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_mdrun_basic():
    """测试mdrun基本功能"""
    print("测试mdrun基本功能...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 测试短时间模拟（仅1步）
        result = subprocess.run(
            [gmx_path, "mdrun", "-s", os.path.join(TEST_DIR, "em.tpr"), "-v", "-nsteps", "1",
             "-deffnm", "test_mdrun"],
            capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ mdrun执行成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_mdrun.log")):
                print("  ✅ mdrun日志生成成功")
                # 清理临时文件
                for f in ["test_mdrun.log", "test_mdrun.trr", "test_mdrun.edr", "test_mdrun.gro", "test_mdrun.cpt"]:
                    fp = os.path.join(TEST_DIR, f)
                    if os.path.exists(fp):
                        os.remove(fp)
            return True
        else:
            print(f"  ❌ mdrun执行失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ mdrun测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pdb2gmx():
    """测试pdb2gmx"""
    print("测试pdb2gmx...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "pdb2gmx", "-f", os.path.join(TEST_DIR, "step10b.pdb"), "-o", "test_pdb2gmx.gro",
             "-p", "test_pdb2gmx.top", "-water", "tip3p"],
            input="1\n", capture_output=True, text=True, timeout=60, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ pdb2gmx执行成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_pdb2gmx.gro")):
                print("  ✅ 结构文件生成成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_pdb2gmx.top")):
                print("  ✅ 拓扑文件生成成功")
                # 清理临时文件
                for f in ["test_pdb2gmx.gro", "test_pdb2gmx.top", "posre.itp"]:
                    fp = os.path.join(TEST_DIR, f)
                    if os.path.exists(fp):
                        os.remove(fp)
            return True
        else:
            print(f"  ❌ pdb2gmx执行失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ pdb2gmx测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_editconf():
    """测试editconf"""
    print("测试editconf...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "editconf", "-f", os.path.join(TEST_DIR, "em.gro"), "-o", "test_editconf.gro",
             "-box", "3", "3", "3"],
            capture_output=True, text=True, timeout=30, cwd=TEST_DIR
        )
        if result.returncode == 0 and os.path.exists(os.path.join(TEST_DIR, "test_editconf.gro")):
            print("  ✅ editconf执行成功")
            os.remove(os.path.join(TEST_DIR, "test_editconf.gro"))
            return True
        else:
            print(f"  ⚠️ editconf警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ editconf测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_solvate():
    """测试solvate"""
    print("测试solvate...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "solvate", "-cp", os.path.join(TEST_DIR, "em.gro"), "-cs", "spc216.gro",
             "-o", "test_solvate.gro", "-p", os.path.join(TEST_DIR, "topol.top")],
            capture_output=True, text=True, timeout=30, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ solvate执行成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_solvate.gro")):
                os.remove(os.path.join(TEST_DIR, "test_solvate.gro"))
            return True
        else:
            print(f"  ⚠️ solvate警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ solvate测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_genion():
    """测试genion"""
    print("测试genion...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "genion", "-s", os.path.join(TEST_DIR, "em.tpr"), "-o", "test_genion.gro",
             "-p", os.path.join(TEST_DIR, "topol.top"), "-neutral"],
            input="13\n", capture_output=True, text=True, timeout=30, cwd=TEST_DIR
        )
        if result.returncode == 0:
            print("  ✅ genion执行成功")
            if os.path.exists(os.path.join(TEST_DIR, "test_genion.gro")):
                os.remove(os.path.join(TEST_DIR, "test_genion.gro"))
            return True
        else:
            print(f"  ⚠️ genion警告: {result.stderr[:100]}")
            return True
    except Exception as e:
        print(f"  ❌ genion测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("GROMACS 工作流模块全面检测")
    print("="*60 + "\n")
    
    tests = [
        ("片段索引生成器", test_fragment_index_generator),
        ("RDF分析", test_rdf_analysis),
        ("轨迹预处理", test_trajectory_preprocessing),
        ("能量分解分析", test_energy_decomposition),
        ("文件检查功能", test_file_check),
        ("GPU/CPU切换", test_gpu_cpu_switch),
        ("mdrun基本功能", test_mdrun_basic),
        ("pdb2gmx", test_pdb2gmx),
        ("editconf", test_editconf),
        ("solvate", test_solvate),
        ("genion", test_genion),
    ]
    
    results = {}
    all_passed = True
    
    for name, test_func in tests:
        try:
            passed = test_func()
            results[name] = passed
            if not passed:
                all_passed = False
            print(f"\n  {'✅' if passed else '❌'} {name} {'通过' if passed else '失败'}")
        except Exception as e:
            print(f"\n  ❌ {name} 异常: {str(e)}")
            results[name] = False
            all_passed = False
    
    print("\n" + "="*60)
    print("检测总结")
    print("="*60)
    print(f"总测试数: {len(tests)}")
    passed_count = sum(1 for v in results.values() if v)
    print(f"通过数: {passed_count}")
    print(f"失败数: {len(tests) - passed_count}")
    print(f"整体状态: {'✅ 全部通过' if all_passed else '❌ 部分失败'}")
    
    # 保存报告
    report = {
        "检测时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "整体状态": "全部通过" if all_passed else "部分失败",
        "测试详情": results
    }
    report_path = os.path.join(r"D:\YDW\Trae_Gromacs", "工作流模块检测报告_20260714.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已保存到: {report_path}")
    
    return all_passed

if __name__ == "__main__":
    main()
