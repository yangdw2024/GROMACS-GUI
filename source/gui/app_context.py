#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用上下文：运行时路径初始化、版本配置、GROMACS 检测、硬件检测
"""

import sys
import os
import subprocess
import platform
import json
from pathlib import Path

def _setup_runtime_paths():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        os.chdir(exe_dir)
        if exe_dir not in sys.path:
            sys.path.insert(0, exe_dir)
        meipass = sys._MEIPASS
        if meipass not in sys.path:
            sys.path.insert(0, meipass)
        return True
    return False

_IS_FROZEN = _setup_runtime_paths()


def _get_app_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

def get_version_config():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        # __file__ = source/gui/app_context.py，三级上溯到项目根（version.config 所在）
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base, "version.config")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"display_name": "GROMACS 动力学模拟与分析集成工具", "version_string": "4.2.0", "full_version": "v4.2.0"}

VERSION_CONFIG = get_version_config()


# =============================================================================
# GROMACS 可执行文件路径 - 自动检测
# =============================================================================
def _find_bundled_gmx():
    """自动检测程序自带的GROMACS（支持打包模式和源码模式，优先相对路径检测）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 优先从相对路径查找（便携包模式）
    search_bases = [
        base,
        os.path.join(base, '..'),
        os.path.join(os.path.dirname(base), '..'),
    ]
    
    for sb in search_bases:
        gromacs_dir = os.path.join(sb, 'gromacs')
        if os.path.isdir(gromacs_dir):
            # 检查是否直接有bin/gmx.exe（单版本便携包模式）
            direct_gmx = os.path.join(gromacs_dir, 'bin', 'gmx.exe')
            if os.path.isfile(direct_gmx):
                return direct_gmx
            
            # 多版本目录模式：扫描子目录找最佳版本
            best = None
            best_score = -1
            for entry in os.listdir(gromacs_dir):
                candidate = os.path.join(gromacs_dir, entry, 'bin', 'gmx.exe')
                if os.path.isfile(candidate):
                    name_lower = entry.lower()
                    score = 0
                    if 'cuda' in name_lower:
                        score += 100
                    if 'avx512' in name_lower or 'avx-512' in name_lower:
                        score += 50
                    elif 'avx2' in name_lower:
                        score += 30
                    if 'plumed' in name_lower:
                        score += 20
                    if 'fixed' in name_lower:
                        score += 10
                    if 'final' in name_lower:
                        score += 5
                    if score > best_score:
                        best_score = score
                        best = candidate
            if best:
                return best
    
    # 兜底：本地开发环境路径（仅在开发机上有效）
    dev_paths = [
        r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED\bin\gmx.exe",
        r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA\bin\gmx.exe",
        r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.1-plumed-CUDA\bin\gmx.exe",
        r"D:\YDW\Trae_Gromacs\gromacs\gmx2020.6_GPU\bin\gmx.exe",
    ]
    for path in dev_paths:
        if os.path.isfile(path):
            return path
    
    # 返回空字符串表示未找到，由上层逻辑处理
    return ""

GMX_EXE = _find_bundled_gmx()


# =============================================================================
# 系统资源检测函数
# =============================================================================
def detect_cpu_cores():
    """检测物理CPU核心数"""
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4


def detect_total_memory_gb():
    """检测系统总内存 (GB)"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "computersystem", "get", "totalphysicalmemory"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:
                line = line.strip()
                if line.isdigit():
                    return round(int(line) / (1024 ** 3), 1)
    except Exception:
        pass
    return 8.0


def detect_cpu_info():
    """检测CPU详细信息（型号、指令集支持）"""
    cpu_info = {
        "name": "未知CPU",
        "cores": os.cpu_count() or 4,
        "simd_support": [],
        "avx512": False,
        "avx2": False,
        "avx": False,
        "sse4_2": False
    }
    
    try:
        result = subprocess.run(
            ["wmic", "cpu", "get", "Name"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            line = line.strip()
            if line:
                cpu_info["name"] = line
                break
    except Exception:
        pass
    
    try:
        try:
            from cpuinfo import get_cpu_info
            info = get_cpu_info()
            # 不再用 py-cpuinfo 的 brand_raw 覆盖 wmic 获取的准确名称
            # py-cpuinfo 在部分 AMD 平台上会错误识别 CPU 型号
            flags = info.get("flags", [])
            simd_flags = [f for f in [
                'avx', 'avx2', 'avx512f', 'avx512cd', 'avx512vl',
                'avx512dq', 'avx512bw', 'sse4_1', 'sse4_2', 'sse2', 'sse3', 'ssse3'
            ] if f in flags]
            cpu_info["simd_support"] = simd_flags
            cpu_info["avx512"] = 'avx512f' in flags
            cpu_info["avx2"] = 'avx2' in flags
            cpu_info["avx"] = 'avx' in flags
            cpu_info["sse4_2"] = 'sse4_2' in flags
        except ImportError:
            cpu_name_lower = cpu_info["name"].lower()
            if "ryzen" in cpu_name_lower and ("9000" in cpu_name_lower or "9700x" in cpu_name_lower or "zen 5" in cpu_name_lower):
                cpu_info["avx512"] = True
                cpu_info["avx2"] = True
                cpu_info["avx"] = True
                cpu_info["simd_support"] = ['avx', 'avx2', 'avx512f', 'avx512cd', 'avx512vl', 'avx512dq', 'avx512bw']
            elif "ryzen" in cpu_name_lower or "epyc" in cpu_name_lower:
                cpu_info["avx2"] = True
                cpu_info["avx"] = True
                cpu_info["simd_support"] = ['avx', 'avx2']
            elif "i3" in cpu_name_lower or "i5" in cpu_name_lower or "i7" in cpu_name_lower or "i9" in cpu_name_lower:
                cpu_info["avx2"] = True
                cpu_info["avx"] = True
                cpu_info["simd_support"] = ['avx', 'avx2']
    except Exception:
        pass
    
    return cpu_info


def get_performance_recommendations(cpu_info, gmx_info, gpu_info):
    """根据硬件和GROMACS版本给出性能优化建议"""
    recommendations = []
    
    if cpu_info.get("avx512") and gmx_info.get("simd") and gmx_info["simd"].lower() in ("avx_256", "avx2", "sse2"):
        recommendations.append({
            "level": "high",
            "title": "CPU AVX-512 未充分利用",
            "description": f"您的CPU ({cpu_info['name']}) 支持AVX-512指令集，但当前GROMACS版本仅使用 {gmx_info['simd']}。",
            "suggestions": [
                "编译支持AVX-512的GROMACS版本可获得约30-50%的性能提升",
                "编译时使用 -DGMX_SIMD=AVX_512 选项",
                "对于浮点密集型计算（如PME、非键相互作用）提升更明显"
            ]
        })
    
    if gpu_info.get("available") and gmx_info.get("gpu", "").lower() in ("no", "none", "disabled", "否"):
        recommendations.append({
            "level": "high",
            "title": "GPU未被利用",
            "description": "系统中有可用的NVIDIA GPU，但当前GROMACS版本不支持GPU加速。",
            "suggestions": [
                "使用支持CUDA的GROMACS版本可获得数倍的性能提升",
                "编译时添加 -DGMX_GPU=CUDA 选项",
                "GPU加速对PME和非键相互作用效果最显著"
            ]
        })
    
    if cpu_info.get("avx2") and not cpu_info.get("avx512") and gmx_info.get("simd", "").lower() in ("sse2", "sse4.1", "sse4.2"):
        recommendations.append({
            "level": "medium",
            "title": "CPU AVX2 未充分利用",
            "description": f"您的CPU支持AVX2指令集，但当前GROMACS版本仅使用 {gmx_info['simd']}。",
            "suggestions": [
                "使用支持AVX2的GROMACS版本可获得约20-40%的性能提升",
                "编译时使用 -DGMX_SIMD=AVX2_256 选项"
            ]
        })
    
    if not gpu_info.get("available"):
        recommendations.append({
            "level": "low",
            "title": "未检测到NVIDIA GPU",
            "description": "系统中未检测到可用的NVIDIA GPU，将仅使用CPU进行计算。",
            "suggestions": [
                "如有NVIDIA显卡，请确保正确安装驱动程序",
                "CPU版本也可以完成模拟，但速度较慢"
            ]
        })
    
    return recommendations


def detect_all_gpus(nvidia_gpu_info=None):
    """通过WMI检测系统中所有GPU，对于NVIDIA GPU优先使用nvidia-smi的准确数据"""
    all_gpus = []
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            if len(lines) >= 2:
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        name = parts[2]
                        ram_str = parts[1]
                        if "OrayIdd" in name:
                            continue
                        gpu = {"name": name}
                        
                        # 对于NVIDIA GPU，优先使用nvidia-smi的准确数据
                        is_nvidia = "NVIDIA" in name.upper()
                        found_nvidia = False
                        if is_nvidia and nvidia_gpu_info and nvidia_gpu_info.get("available"):
                            for i, n_name in enumerate(nvidia_gpu_info.get("names", [])):
                                if n_name in name or name in n_name:
                                    if i < len(nvidia_gpu_info.get("memories", [])):
                                        gpu["memory"] = nvidia_gpu_info["memories"][i]
                                        found_nvidia = True
                                        break
                        
                        if not found_nvidia:
                            try:
                                ram_bytes = int(ram_str)
                                if ram_bytes >= 1024 ** 3:
                                    gpu["memory"] = f"{ram_bytes / (1024**3):.1f} GB"
                                else:
                                    gpu["memory"] = f"{ram_bytes / (1024**2):.0f} MB"
                            except ValueError:
                                gpu["memory"] = "未知"
                        
                        all_gpus.append(gpu)
    except Exception:
        pass
    return all_gpus


def detect_gpu_info():
    """检测NVIDIA GPU信息"""
    gpu_info = {"available": False, "count": 0, "ids": [], "names": [], "memories": [], "driver": "N/A", "cuda_version": "N/A", "all_gpus": []}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            gpu_info["count"] = len(lines)
            gpu_info["ids"] = []
            gpu_info["names"] = []
            gpu_info["memories"] = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpu_info["ids"].append(int(parts[0]))
                    gpu_info["names"].append(parts[1])
                    gpu_info["driver"] = parts[2]
                    mem_str = parts[3].strip()
                    gpu_info["memories"].append(mem_str)
            gpu_info["available"] = True
    except Exception:
        pass
    # 检测 CUDA 版本
    try:
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "release" in line.lower():
                    gpu_info["cuda_version"] = line.strip()
                    break
    except Exception:
        pass
    # 检测所有GPU（用于显示信息），对于NVIDIA GPU优先使用nvidia-smi的准确数据
    gpu_info["all_gpus"] = detect_all_gpus(gpu_info)
    return gpu_info


def scan_gromacs_versions(base_dir=None):
    """扫描GROMACS安装目录下的所有版本（自动检测程序自带和用户安装的版本）"""
    versions = {}
    exclude_patterns = [
        'build-', 'build_', 'cmake-', 'CMakeFiles', 
        'src', 'source', '.git', '_build', 'debug', 'release'
    ]
    search_dirs = []
    if getattr(sys, 'frozen', False):
        exe_base = os.path.dirname(sys.executable)
    else:
        exe_base = os.path.dirname(os.path.abspath(__file__))
    search_dirs.append(os.path.join(exe_base, 'gromacs'))
    search_dirs.append(exe_base)
    dev_dir = r"D:\YDW\Trae_Gromacs"
    search_dirs.append(os.path.join(dev_dir, 'gromacs'))
    search_dirs.append(dev_dir)
    if base_dir:
        search_dirs.append(base_dir)
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for entry in os.listdir(search_dir):
            subdir = os.path.join(search_dir, entry)
            if not os.path.isdir(subdir):
                continue
            if any(pattern in entry.lower() for pattern in exclude_patterns):
                continue
            gmx_path = os.path.join(subdir, "bin", "gmx.exe")
            if os.path.isfile(gmx_path):
                label = entry
                versions[label] = gmx_path
    return versions


def get_gromacs_version_info(gmx_exe, gpu_available=True):
    """获取指定GROMACS可执行文件的版本信息（增强版）"""
    info = {
        "version": "未知", "gpu": "否", "plumed": "否",
        "simd": "未知", "precision": "未知", "openmp": "未知",
        "c_compiler": "未知", "cuda_version": "未知", "fftw": "未知"
    }
    if not os.path.isfile(gmx_exe):
        return info
    try:
        env = None
        if not gpu_available:
            env = os.environ.copy()
            env["GMX_DISABLE_GPU_DETECTION"] = "1"
            env["CUDA_VISIBLE_DEVICES"] = ""
        result = subprocess.run(
            [gmx_exe, "--version"],
            capture_output=True, text=True, timeout=15, env=env
        )
        out = result.stdout + result.stderr
        for line in out.split("\n"):
            line_lower = line.lower()
            if "gromacs version:" in line_lower:
                info["version"] = line.split(":", 1)[1].strip()
            elif "gpu support:" in line_lower:
                info["gpu"] = line.split(":", 1)[1].strip()
            elif "plumed support:" in line_lower:
                info["plumed"] = line.split(":", 1)[1].strip()
            elif "simd instructions:" in line_lower:
                info["simd"] = line.split(":", 1)[1].strip()
            elif "precision:" in line_lower:
                info["precision"] = line.split(":", 1)[1].strip()
            elif "openmp support:" in line_lower:
                info["openmp"] = line.split(":", 1)[1].strip()
            elif "c compiler:" in line_lower:
                info["c_compiler"] = line.split(":", 1)[1].strip()
            elif "cuda runtime:" in line_lower:
                info["cuda_version"] = line.split(":", 1)[1].strip()
            elif "cpu fft library:" in line_lower:
                info["fftw"] = line.split(":", 1)[1].strip()
    except Exception:
        pass
    return info
