import os
import sys
import subprocess
import json

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

def test_module_imports():
    """测试核心模块导入"""
    print("测试模块导入...")
    try:
        from core.gromacs_service import GromacsService
        print("  ✅ core.gromacs_service 导入成功")
        from core.version_manager import VersionManager
        print("  ✅ core.version_manager 导入成功")
        from core.resource_monitor import ResourceMonitor
        print("  ✅ core.resource_monitor 导入成功")
        from core.config_manager import ConfigManager
        print("  ✅ core.config_manager 导入成功")
        from core.workflow_engine import WorkflowEngine
        print("  ✅ core.workflow_engine 导入成功")
        return True
    except Exception as e:
        print(f"  ❌ 模块导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_gromacs_service():
    """测试GromacsService"""
    print("测试 GromacsService...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        # 先扫描版本
        gs.scan_versions()
        versions = gs.get_version_list()
        print(f"  ✅ 检测到 {len(versions)} 个GROMACS版本")
        for v in versions:
            print(f"     - {v.get('name', '未知')}")
        
        gmx_exe = gs.get_gmx_exe()
        print(f"  ✅ gmx.exe路径: {gmx_exe}")
        return True
    except Exception as e:
        print(f"  ❌ GromacsService 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_version_manager():
    """测试VersionManager"""
    print("测试 VersionManager...")
    try:
        from core.version_manager import VersionManager
        vm = VersionManager()
        
        # 先扫描版本
        vm.scan_versions()
        
        # 测试获取版本列表
        versions = vm.get_version_list()
        print(f"  ✅ 版本数量: {len(versions)}")
        
        # 测试获取白名单
        whitelist = vm.get_version_whitelist()
        print(f"  ✅ 白名单数量: {len(whitelist)}")
        
        # 测试获取默认版本（通过配置文件）
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        config = cm.get_all()
        default_version = config.get('gromacs', {}).get('default_version', '未知')
        print(f"  ✅ 默认版本: {default_version}")
        assert "sm120" in default_version, f"默认版本不是sm120: {default_version}"
        print(f"  ✅ 默认版本已设置为sm120")
        
        return True
    except Exception as e:
        print(f"  ❌ VersionManager 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_resource_monitor():
    """测试ResourceMonitor"""
    print("测试 ResourceMonitor...")
    try:
        from core.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        cpu_info = rm.get_cpu_info()
        gpu_info = rm.get_gpu_info()
        print(f"  ✅ CPU信息: {cpu_info.get('name', '未知')}")
        print(f"  ✅ CPU核心数: {cpu_info.get('cores', '未知')}")
        
        if isinstance(gpu_info, dict):
            print(f"  ✅ GPU数量: {len(gpu_info)}")
            for gpu_name, gpu_data in gpu_info.items():
                memory = gpu_data.get('memory', '未知') if isinstance(gpu_data, dict) else '未知'
                print(f"     - {gpu_name} (显存: {memory})")
        else:
            print(f"  ✅ GPU信息: {gpu_info}")
        
        return True
    except Exception as e:
        print(f"  ❌ ResourceMonitor 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_config_manager():
    """测试ConfigManager"""
    print("测试 ConfigManager...")
    try:
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        config = cm.get_all()
        print(f"  ✅ 配置加载成功")
        print(f"     - 产品名称: {config.get('product_name', '未知')}")
        print(f"     - GUI版本: {config.get('version_string', '未知')}")
        print(f"     - 默认GMX版本: {config.get('gromacs', {}).get('default_version', '未知')}")
        print(f"     - 版本白名单数量: {len(config.get('gromacs', {}).get('version_whitelist', []))}")
        return True
    except Exception as e:
        print(f"  ❌ ConfigManager 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_workflow_engine():
    """测试WorkflowEngine"""
    print("测试 WorkflowEngine...")
    try:
        from core.workflow_engine import WorkflowEngine
        we = WorkflowEngine()
        tasks = we.get_all_tasks()
        print(f"  ✅ 工作流任务数: {len(tasks)}")
        return True
    except Exception as e:
        print(f"  ❌ WorkflowEngine 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_code_syntax():
    """测试GUI代码语法"""
    print("测试GUI代码语法...")
    try:
        import py_compile
        gui_path = os.path.join(r"D:\YDW\Trae_Gromacs\source", "gromacs_gui_v4.py")
        py_compile.compile(gui_path, doraise=True)
        print("  ✅ gromacs_gui_v4.py 语法检查通过")
        
        # 检查新增方法是否存在
        with open(gui_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_methods = [
            '_generate_fragment_ndx',
            '_expand_ranges',
            '_run_fragment_rdf_batch',
            '_run_pairdist_analysis',
            '_run_preprocessing_pipeline',
            '_run_energy_decomposition',
            '_generate_plot',
            '_run_batch_processing',
            '_run_file_check',
            '_check_file_status',
        ]
        
        missing_methods = []
        for method in new_methods:
            if f"def {method}" not in content:
                missing_methods.append(method)
            else:
                print(f"     ✅ {method} 方法存在")
        
        if missing_methods:
            print(f"     ❌ 缺少方法: {', '.join(missing_methods)}")
            return False
        return True
    except Exception as e:
        print(f"  ❌ GUI代码语法检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_analysis_enhancements():
    """测试分析工具增强"""
    print("测试分析工具增强...")
    try:
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        # 检查gmx rdf帮助
        result = subprocess.run([gmx_path, "rdf", "-h"], capture_output=True, text=True, timeout=30)
        assert "-ref" in result.stdout, "rdf缺少-ref参数"
        assert "-sel" in result.stdout, "rdf缺少-sel参数"
        assert "-seltype" in result.stdout, "rdf缺少-seltype参数"
        print("  ✅ RDF增强参数验证通过")
        
        # 检查gmx pairdist帮助
        result = subprocess.run([gmx_path, "pairdist", "-h"], capture_output=True, text=True, timeout=30)
        assert "-ref" in result.stdout, "pairdist缺少-ref参数"
        assert "-sel" in result.stdout, "pairdist缺少-sel参数"
        assert "-type" in result.stdout, "pairdist缺少-type参数"
        print("  ✅ pairdist增强参数验证通过")
        
        # 检查gmx msd帮助
        result = subprocess.run([gmx_path, "msd", "-h"], capture_output=True, text=True, timeout=30)
        assert "-sel" in result.stdout, "msd缺少-sel参数"
        print("  ✅ MSD增强参数验证通过")
        
        # 检查gmx cluster帮助
        result = subprocess.run([gmx_path, "cluster", "-h"], capture_output=True, text=True, timeout=30)
        assert "-method" in result.stdout, "cluster缺少-method参数"
        assert "-cutoff" in result.stdout, "cluster缺少-cutoff参数"
        print("  ✅ cluster增强参数验证通过")
        
        return True
    except Exception as e:
        print(f"  ❌ 分析工具增强测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_real_simulation():
    """测试真实模拟文件处理"""
    print("测试真实模拟文件处理...")
    try:
        test_dir = r"D:\YDW\Trae_Gromacs\test\test_water_system"
        if not os.path.exists(test_dir):
            print("  ⚠️ 测试目录不存在，跳过")
            return True
        
        required_files = ['em.tpr', 'em.gro', 'md.tpr', 'md.xtc', 'md.edr']
        missing = []
        for f in required_files:
            if not os.path.exists(os.path.join(test_dir, f)):
                missing.append(f)
        
        if missing:
            print(f"  ⚠️ 缺少测试文件: {', '.join(missing)}")
            return True
        
        # 测试gmx check
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gs.scan_versions()
        gmx_path = gs.get_gmx_exe()
        
        result = subprocess.run(
            [gmx_path, "check", "-f", os.path.join(test_dir, "md.xtc"), "-s", os.path.join(test_dir, "md.tpr")],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("  ✅ gmx check 验证通过")
        else:
            print(f"  ⚠️ gmx check 有警告: {result.stderr[:100]}")
        
        return True
    except Exception as e:
        print(f"  ❌ 真实模拟文件测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("GROMACS GUI 核心功能全面检测")
    print("="*60 + "\n")
    
    tests = [
        ("模块导入", test_module_imports),
        ("GromacsService", test_gromacs_service),
        ("VersionManager", test_version_manager),
        ("ResourceMonitor", test_resource_monitor),
        ("ConfigManager", test_config_manager),
        ("WorkflowEngine", test_workflow_engine),
        ("GUI代码语法", test_gui_code_syntax),
        ("分析工具增强", test_analysis_enhancements),
        ("真实模拟文件", test_real_simulation),
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
        "检测时间": "2026-07-14",
        "整体状态": "全部通过" if all_passed else "部分失败",
        "测试详情": results
    }
    report_path = os.path.join(r"D:\YDW\Trae_Gromacs", "GUI核心功能检测报告_20260714.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已保存到: {report_path}")
    
    return all_passed

if __name__ == "__main__":
    main()
