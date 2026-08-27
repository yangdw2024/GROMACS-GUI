import os
import subprocess
import json

GROMACS_BASE = r"D:\YDW\Trae_Gromacs\gromacs"
VERSIONS = [
    "gromacs-2025.1-SM120-AVX512",
    "gromacs-2026.1-plumed-CUDA",
    "gromacs-2026.3-AVX2-CUDA",
    "gromacs-2026.3-AVX512-CUDA",
    "gromacs-2026.3-AVX512-CUDA-PLUMED",
    "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120",
    "gromacs-2026.3-AVX512-CUDA-sm120-final2"
]

def check_gmx_version(gmx_path):
    """检测gmx版本信息"""
    try:
        result = subprocess.run(
            [gmx_path, "--version"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith("GROMACS version"):
                    return line.strip()
        return f"Error: {result.stderr[:200]}"
    except Exception as e:
        return f"Exception: {str(e)}"

def check_plumed_support(gmx_path):
    """检测PLUMED支持"""
    try:
        result = subprocess.run(
            [gmx_path, "mdrun", "-h"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            if "-plumed" in result.stdout or "-plumed" in result.stderr:
                return "✅ PLUMED支持 (静态链接)"
            else:
                # 检查动态链接库
                gmx_dir = os.path.dirname(gmx_path)
                if os.path.exists(os.path.join(gmx_dir, "libplumedKernel.dll")):
                    return "✅ PLUMED支持 (动态链接)"
                return "❌ 无PLUMED支持"
        return "❌ mdrun -h失败"
    except Exception as e:
        return f"Exception: {str(e)}"

def check_gpu_support(gmx_path):
    """检测GPU支持"""
    try:
        result = subprocess.run(
            [gmx_path, "mdrun", "-h"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            if "-gpu_id" in result.stdout or "-nb gpu" in result.stdout:
                return "✅ GPU CUDA支持"
            return "❌ 无GPU支持"
        return "❌ mdrun -h失败"
    except Exception as e:
        return f"Exception: {str(e)}"

def check_binary_arch(gmx_path):
    """检测二进制架构"""
    try:
        result = subprocess.run(
            [gmx_path, "version", "-a"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
        # 尝试其他方式
        result2 = subprocess.run(
            [gmx_path, "--version"], capture_output=True, text=True, timeout=30
        )
        arch_info = ""
        for line in result2.stdout.split('\n'):
            if "SIMD" in line or "AVX" in line or "SSE" in line:
                arch_info += line.strip() + "; "
        return arch_info if arch_info else "未知"
    except Exception as e:
        return f"Exception: {str(e)}"

def check_file_structure(version_dir):
    """检查文件结构完整性"""
    required_files = [
        ("bin/gmx.exe", "主程序"),
        ("bin/cudart64_13.dll", "CUDA运行时"),
        ("bin/cufft64_12.dll", "FFT库"),
        ("share/gromacs/top/ffG53a6.itp", "力场文件"),
        ("share/gromacs/top/tip3p.itp", "水模型"),
    ]
    
    missing = []
    for rel_path, desc in required_files:
        full_path = os.path.join(version_dir, rel_path)
        if not os.path.exists(full_path):
            missing.append(desc)
    
    return missing

def main():
    report = {
        "检测时间": "2026-07-14",
        "总版本数": len(VERSIONS),
        "版本详情": []
    }
    
    all_ok = True
    
    for i, version in enumerate(VERSIONS, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(VERSIONS)}] 检测: {version}")
        print('='*60)
        
        version_dir = os.path.join(GROMACS_BASE, version)
        gmx_path = os.path.join(version_dir, "bin", "gmx.exe")
        
        info = {
            "版本名称": version,
            "路径": version_dir,
            "gmx.exe存在": os.path.exists(gmx_path),
        }
        
        if os.path.exists(gmx_path):
            info["版本信息"] = check_gmx_version(gmx_path)
            info["GPU支持"] = check_gpu_support(gmx_path)
            info["PLUMED支持"] = check_plumed_support(gmx_path)
            info["架构信息"] = check_binary_arch(gmx_path)
            
            # 检查文件完整性
            missing_files = check_file_structure(version_dir)
            if missing_files:
                info["缺失文件"] = missing_files
                info["状态"] = "⚠️ 部分文件缺失"
                all_ok = False
            else:
                info["缺失文件"] = []
                info["状态"] = "✅ 完整可用"
                
            print(f"  版本信息: {info['版本信息']}")
            print(f"  GPU支持: {info['GPU支持']}")
            print(f"  PLUMED支持: {info['PLUMED支持']}")
            print(f"  架构信息: {info['架构信息']}")
            if missing_files:
                print(f"  ⚠️ 缺失文件: {', '.join(missing_files)}")
            print(f"  状态: {info['状态']}")
        else:
            info["版本信息"] = "gmx.exe不存在"
            info["状态"] = "❌ 不可用"
            all_ok = False
            print("  ❌ gmx.exe不存在")
        
        report["版本详情"].append(info)
    
    print(f"\n{'='*60}")
    print("检测总结")
    print('='*60)
    print(f"总版本数: {len(VERSIONS)}")
    print(f"全部完整: {'✅ 是' if all_ok else '❌ 否'}")
    
    # 保存报告
    report_path = os.path.join(r"D:\YDW\Trae_Gromacs", "全面检测报告_20260714.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    
    print(f"\n报告已保存到: {report_path}")
    return report

if __name__ == "__main__":
    main()
