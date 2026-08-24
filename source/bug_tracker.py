#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS GUI 问题追踪与知识库系统
功能：
1. 记录所有已修复的bug和问题
2. 按类别分类管理
3. 搜索和查询历史问题
4. 导出问题报告
"""

import json
import os
import datetime
from pathlib import Path


class BugTracker:
    def __init__(self, data_file=None):
        if data_file is None:
            data_file = Path(__file__).parent / "bug_tracking.json"
        self.data_file = Path(data_file)
        self.data = self._load_data()

    def _load_data(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "project": "GROMACS GUI",
            "last_updated": "",
            "total_bugs_fixed": 0,
            "categories": {
                "编译问题": [],
                "GUI界面问题": [],
                "功能bug": [],
                "版本管理问题": [],
                "性能优化": [],
                "配置问题": []
            },
            "knowledge_base": []
        }

    def _save_data(self):
        self.data["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存数据失败: {e}")
            return False

    def add_bug(self, category, title, description, solution, severity="medium", related_files=None, date=None):
        if category not in self.data["categories"]:
            self.data["categories"][category] = []

        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")

        bug = {
            "id": len(self.data["categories"][category]) + 1,
            "title": title,
            "description": description,
            "solution": solution,
            "severity": severity,
            "related_files": related_files or [],
            "date": date,
            "status": "fixed"
        }

        self.data["categories"][category].append(bug)
        self.data["total_bugs_fixed"] += 1
        self._save_data()
        return bug

    def add_knowledge(self, topic, content, tags=None):
        kb = {
            "id": len(self.data["knowledge_base"]) + 1,
            "topic": topic,
            "content": content,
            "tags": tags or [],
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        self.data["knowledge_base"].append(kb)
        self._save_data()
        return kb

    def search_bugs(self, keyword):
        results = []
        keyword = keyword.lower()
        for category, bugs in self.data["categories"].items():
            for bug in bugs:
                if (keyword in bug["title"].lower() or
                    keyword in bug["description"].lower() or
                    keyword in bug["solution"].lower()):
                    results.append({"category": category, **bug})
        return results

    def get_stats(self):
        stats = {
            "total_fixed": self.data["total_bugs_fixed"],
            "by_category": {},
            "by_severity": {"high": 0, "medium": 0, "low": 0},
            "knowledge_base_count": len(self.data["knowledge_base"])
        }
        for category, bugs in self.data["categories"].items():
            stats["by_category"][category] = len(bugs)
            for bug in bugs:
                sev = bug.get("severity", "medium")
                if sev in stats["by_severity"]:
                    stats["by_severity"][sev] += 1
        return stats

    def generate_report(self):
        stats = self.get_stats()
        report = []
        report.append("=" * 70)
        report.append("GROMACS GUI 问题追踪报告")
        report.append("=" * 70)
        report.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"累计修复bug: {stats['total_fixed']} 个")
        report.append(f"知识库条目: {stats['knowledge_base_count']} 个")
        report.append("")

        report.append("【按类别统计】")
        for cat, count in stats["by_category"].items():
            if count > 0:
                report.append(f"  {cat}: {count} 个")
        report.append("")

        report.append("【按严重程度统计】")
        report.append(f"  严重(high): {stats['by_severity']['high']} 个")
        report.append(f"  中等(medium): {stats['by_severity']['medium']} 个")
        report.append(f"  轻微(low): {stats['by_severity']['low']} 个")
        report.append("")

        for category, bugs in self.data["categories"].items():
            if not bugs:
                continue
            report.append(f"【{category}】({len(bugs)} 个)")
            for bug in bugs:
                sev_label = {"high": "🔴严重", "medium": "🟡中等", "low": "🟢轻微"}.get(bug["severity"], "⚪未知")
                report.append(f"  {sev_label} [{bug['date']}] {bug['title']}")
            report.append("")

        if self.data["knowledge_base"]:
            report.append("【知识库】")
            for kb in self.data["knowledge_base"]:
                tags = ", ".join(kb.get("tags", []))
                report.append(f"  [{kb['date']}] {kb['topic']} ({tags})")
            report.append("")

        report.append("=" * 70)
        return "\n".join(report)

    def get_bug_detail(self, category, bug_id):
        bugs = self.data["categories"].get(category, [])
        for bug in bugs:
            if bug["id"] == bug_id:
                return bug
        return None


def init_default_data(tracker):
    bugs = [
        {
            "category": "编译问题",
            "title": "CUDA路径拼写错误（Tookit vs Toolkit）",
            "description": "CUDA安装目录路径拼写错误，应为Toolkit但写成了Tookit，导致编译时找不到CUDA。",
            "solution": "1. 将目录 D:\\NVIDIA_CUDA_Tookit 重命名为 D:\\NVIDIA_CUDA_Toolkit\n2. 更新所有批处理脚本中的CUDA路径引用\n3. 验证环境变量是否正确设置",
            "severity": "high",
            "related_files": ["build_gromacs_*.bat"],
            "date": "2026-07-06"
        },
        {
            "category": "编译问题",
            "title": "AVX-512非法指令导致程序崩溃（STATUS_ILLEGAL_INSTRUCTION）",
            "description": "AMD Ryzen 7 9700X (Zen 5)不支持AVX-512_VBMI扩展指令，但GROMACS编译时使用了VBMI指令（如_mm512_maskz_compress_ps），导致运行时崩溃（错误码0xc000001d）。",
            "solution": "1. 修改 gmxSimdFlags.cmake 中的AVX-512检测代码，移除permutexvar等VBMI指令检测\n2. 修改 impl_x86_avx_512_util_float.h，用基础AVX-512指令替换VBMI指令\n3. 重新编译并测试验证",
            "severity": "high",
            "related_files": [
                "gromacs/gromacs-2026.3/cmake/gmxSimdFlags.cmake",
                "gromacs/gromacs-2026.3/src/gromacs/simd/impl_x86_avx_512_util_float.h"
            ],
            "date": "2026-07-06"
        },
        {
            "category": "编译问题",
            "title": "PLUMED在Windows下官方不支持",
            "description": "GROMACS官方CMake配置中明确禁止Windows下PLUMED支持，导致无法编译带PLUMED的Windows版本。",
            "solution": "1. 修改 gmxManagePlumed.cmake，移除Windows限制\n2. 手动创建 dlfcn.h 的Windows兼容实现\n3. 复制 dl.dll、libplumedKernel.dll 到编译环境\n4. 修复模板重载歧义问题（将nullptr显式转换为void*）",
            "severity": "high",
            "related_files": [
                "gromacs/gromacs-2026.3/cmake/gmxManagePlumed.cmake",
                "gromacs/gromacs-2026.3/src/external/plumed/dlfcn.h",
                "gromacs/gromacs-2026.3/src/gromacs/applied_forces/plumed/plumedforceprovider.cpp"
            ],
            "date": "2026-07-07"
        },
        {
            "category": "编译问题",
            "title": "缺少CUDA运行时DLL",
            "description": "编译后的GROMACS运行时提示缺少 cufft64_12.dll 等CUDA DLL文件。",
            "solution": "从 CUDA Toolkit 的 bin/x64 目录复制所有DLL文件到 GROMACS 的 bin 目录。",
            "severity": "medium",
            "related_files": ["build_gromacs_*.bat"],
            "date": "2026-07-06"
        },
        {
            "category": "编译问题",
            "title": "编译后版本缺少DLL文件",
            "description": "gromacs-2026.3-AVX2-CUDA 和 gromacs-2026.3-AVX512-CUDA 编译后只有gmx.exe，缺少必要的DLL文件，运行时报错0xC0000135（STATUS_DLL_NOT_FOUND）。",
            "solution": "从完整版本 gromacs-2026.3-AVX512-CUDA-PLUMED 的 bin 目录复制所有DLL文件到对应版本的 bin 目录。\n需要复制的DLL包括：cublas*.dll、cudart*.dll、cufft*.dll、curand*.dll、cusolver*.dll、cusparse*.dll、npp*.dll、nv*.dll、fftw3f.dll、dl.dll 等。",
            "severity": "medium",
            "related_files": [
                "gromacs/gromacs-2026.3-AVX2-CUDA/bin/",
                "gromacs/gromacs-2026.3-AVX512-CUDA/bin/"
            ],
            "date": "2026-07-07"
        },
        {
            "category": "GUI界面问题",
            "title": "UI界面默认值未随版本更换而更新",
            "description": "切换GROMACS版本后，线程数、内存限制等默认参数未根据新版本特性更新，导致用户可能使用不适合的配置。",
            "solution": "1. 在 _on_version_changed 函数中添加默认参数更新逻辑\n2. 根据新版本的GPU支持情况自动调整默认线程数：\n   - GPU加速模式：推荐4-8核\n   - GPU支持但不可用：推荐最多16核\n   - 不支持GPU：推荐最多24核\n3. 添加AVX-512指令集检测和提示\n4. 优化日志输出，显示版本切换后的配置变化",
            "severity": "medium",
            "related_files": ["source/gromacs_gui_v3.py"],
            "date": "2026-07-07"
        },
        {
            "category": "功能bug",
            "title": "实时监控功能直接闪退",
            "description": "打开实时监控面板并开始监控后程序直接闪退，无明确错误提示。",
            "solution": "根本原因：DataExtractorThread 使用了全局变量 GMX_EXE（模块加载时确定的路径），而不是当前选中的版本路径。当用户切换版本后，监控线程仍然使用旧的（可能已失效的）gmx.exe路径。\n\n修复方案：\n1. 在 DataExtractorThread 中添加 _gmx_exe 属性和 set_gmx_exe() 方法\n2. 修改 SimulationMonitorDialog 的构造函数，接收 gmx_exe 参数\n3. 修改 _on_start() 方法，调用 set_gmx_exe() 设置当前选中的版本路径\n4. 修改主窗口的 open_monitor() 方法，传递 self.gmx_path\n5. 添加异常捕获，将错误信息通过信号发送到主线程并显示",
            "severity": "high",
            "related_files": ["source/gromacs_gui_v3.py"],
            "date": "2026-07-07"
        },
        {
            "category": "GUI界面问题",
            "title": "GROMACS误选build目录中的gmx.exe",
            "description": "GUI的版本扫描函数错误选择了编译中间目录 build-2026.3-AVX512-CUDA 中的 gmx.exe，而不是安装目录中的版本。",
            "solution": "修改 scan_gromacs_versions() 函数，排除含 build- 前缀的目录。",
            "severity": "medium",
            "related_files": ["source/gromacs_gui_v3.py"],
            "date": "2026-07-06"
        },
        {
            "category": "功能bug",
            "title": "PLUMED模板重载歧义",
            "description": "调用 plumed_->cmd(\"init\", nullptr) 时，编译器无法确定 nullptr 匹配哪个构造函数，导致编译失败。",
            "solution": "将 nullptr 显式转换为 void*，如 static_cast<void*>(nullptr)。",
            "severity": "high",
            "related_files": ["gromacs/gromacs-2026.3/src/gromacs/applied_forces/plumed/plumedforceprovider.cpp"],
            "date": "2026-07-07"
        },
        {
            "category": "版本管理问题",
            "title": "项目文件混乱，存在大量旧版本无用文件",
            "description": "项目中存在大量旧版本的GUI打包文件、编译日志、旧版本GROMACS等，修改日期停留在过去，用户难以分辨哪些文件还有用。",
            "solution": "1. 建立版本管理工具 version_manager.py\n2. 清理无用文件：\n   - 删除 dist/ 目录（旧版GUI打包文件）\n   - 删除 build/ 目录（PyInstaller编译中间文件）\n   - 删除 archive/ 目录（旧GUI版本备份）\n   - 删除 gmx2020.6_GPU（2020年老版本）\n   - 删除 gromacs-2026.1-plumed-CUDA（旧版本）\n   - 删除 gromacs-2025.1-SM120-AVX512（2025旧版本）\n   - 删除 compile*.log、cmake*.log 等编译日志\n3. 修复缺少DLL的版本\n4. 保留3个有效版本：AVX512+CUDA+PLUMED、AVX512+CUDA、AVX2+CUDA",
            "severity": "medium",
            "related_files": [
                "source/version_manager.py",
                "dist/",
                "build/",
                "archive/"
            ],
            "date": "2026-07-07"
        },
        {
            "category": "功能bug",
            "title": "缺少日志记录和异常处理机制",
            "description": "程序闪退时没有错误日志，难以定位问题原因，排查效率低。",
            "solution": "1. 添加全局日志文件记录（logs/gromacs_gui_时间戳.log）\n2. 建立全局异常处理，崩溃时自动保存堆栈跟踪到 logs/crash_时间戳.log\n3. 添加启动失败异常捕获\n4. 实现五级日志分类：INFO/SUCCESS/WARNING/ERROR/CMD\n5. 实时监控面板添加详细日志输出",
            "severity": "medium",
            "related_files": ["source/gromacs_gui_v3.py"],
            "date": "2026-07-07"
        },
        {
            "category": "性能优化",
            "title": "版本选择策略优化",
            "description": "原版本选择逻辑不够智能，未充分考虑SIMD指令集、PLUMED支持等因素对性能的影响。",
            "solution": "优化 _select_best_gmx_version 函数，按以下优先级选择：\n1. GPU支持（权重最高，+1000分）\n2. SIMD指令集级别（AVX-512: +500, AVX2: +300）\n3. PLUMED支持（+100分）\n4. 版本号（主版本*10+次版本）",
            "severity": "low",
            "related_files": ["source/gromacs_gui_v3.py"],
            "date": "2026-07-07"
        }
    ]

    for bug in bugs:
        tracker.add_bug(**bug)

    knowledge_base = [
        {
            "topic": "GROMACS Windows编译环境配置",
            "content": "必要工具：\n- Visual Studio 2022 (VS 2026)\n- CUDA Toolkit 13.x\n- CMake 4.x\n- Ninja build system\n- Python 3.x\n\n环境变量配置：\n- CUDA_PATH: CUDA安装目录\n- PATH: 添加CMake、Ninja、Python等路径\n- 使用 vcvars64.bat 配置MSVC编译环境\n\n编译命令：\ncmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DGMX_SIMD=AVX_512 -DGMX_GPU=CUDA -DGMX_USE_PLUMED=ON\ncmake --build . -j16",
            "tags": ["编译", "环境配置", "Windows"]
        },
        {
            "topic": "AVX-512兼容性问题排查",
            "content": "AMD Zen 5 (Ryzen 7 9700X) AVX-512支持情况：\n✅ 支持：AVX512F, AVX512CD, AVX512VL, AVX512DQ, AVX512BW\n❌ 不支持：AVX-512_VBMI, AVX-512_VBMI2, AVX-512_FP16 等扩展\n\n常见崩溃错误：\n- STATUS_ILLEGAL_INSTRUCTION (0xc000001d)：使用了不支持的指令\n- 定位方法：Windows事件查看器 -> 应用程序 -> 错误 -> 异常代码\n\n修复方法：\n1. 检查CPU支持的指令集：coreinfo.exe 或 CPU-Z\n2. 修改SIMD检测代码，移除不支持的指令\n3. 用基础指令替换高级指令实现",
            "tags": ["AVX-512", "兼容性", "Zen 5", "调试"]
        },
        {
            "topic": "GROMACS版本选择指南",
            "content": "按性能从高到低排序：\n1. AVX512 + CUDA + PLUMED - 最强性能，支持增强采样\n2. AVX512 + CUDA - 最强性能，无PLUMED\n3. AVX2 + CUDA - 兼容性好，性能稍次\n4. AVX512 (无GPU) - CPU优化，无GPU加速\n5. AVX2 (无GPU) - 兼容大多数CPU\n\n何时使用哪个版本：\n- 日常使用：AVX512+CUDA+PLUMED（推荐）\n- PLUMED有问题时：AVX512+CUDA\n- AVX512崩溃时：AVX2+CUDA（降级方案）\n- 旧电脑/服务器：根据CPU和GPU支持情况选择",
            "tags": ["版本选择", "性能优化", "指南"]
        },
        {
            "topic": "PLUMED Windows编译要点",
            "content": "PLUMED官方不支持Windows，但可以通过以下方法实现：\n\n1. 修改CMake配置：\n   - 编辑 gmxManagePlumed.cmake\n   - 移除 WIN32 或 MSVC 的限制检查\n\n2. 提供dlfcn.h兼容层：\n   - 创建Windows版的dlfcn.h\n   - 实现 dlopen, dlsym, dlclose 等函数\n   - 用 Win32 API (LoadLibrary, GetProcAddress) 包装\n\n3. 提供必要的DLL：\n   - dl.dll - 动态链接库模拟\n   - libplumedKernel.dll - PLUMED核心库\n   - fftw3f.dll - FFTW库\n\n4. 修复C++编译错误：\n   - nullptr模板歧义：显式转换为 void*\n   - 其他Windows特定的编译问题",
            "tags": ["PLUMED", "Windows", "编译", "高级"]
        },
        {
            "topic": "程序闪退排查步骤",
            "content": "当程序闪退时，按以下步骤排查：\n\n1. 检查日志文件：\n   - logs/gromacs_gui_*.log - 运行日志\n   - logs/crash_*.log - 崩溃堆栈\n\n2. 检查Windows事件查看器：\n   - Win+R -> eventvwr\n   - 应用程序日志 -> 错误\n   - 查看异常代码和错误模块\n\n3. 常见错误码：\n   - 0xC0000005: 访问冲突（空指针、数组越界）\n   - 0xC000001D: 非法指令（SIMD不兼容）\n   - 0xC0000135: 缺少DLL\n   - 0xC00000FD: 栈溢出\n\n4. 实时监控闪退常见原因：\n   - gmx.exe路径不正确\n   - EDR文件不存在或格式错误\n   - 缺少必要的DLL\n   - 线程间通信问题",
            "tags": ["调试", "闪退", "排查指南"]
        }
    ]

    for kb in knowledge_base:
        tracker.add_knowledge(**kb)

    return tracker


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GROMACS GUI 问题追踪系统")
    parser.add_argument("--report", action="store_true", help="生成问题报告")
    parser.add_argument("--search", type=str, help="搜索问题")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--init", action="store_true", help="初始化默认数据")
    args = parser.parse_args()

    tracker = BugTracker()

    if args.init:
        init_default_data(tracker)
        print("已初始化默认数据")
        print(tracker.generate_report())
    elif args.report:
        print(tracker.generate_report())
    elif args.stats:
        stats = tracker.get_stats()
        print("=" * 50)
        print("问题统计")
        print("=" * 50)
        print(f"累计修复: {stats['total_fixed']} 个")
        print(f"知识库: {stats['knowledge_base_count']} 条")
        print("\n按类别:")
        for cat, count in stats['by_category'].items():
            if count > 0:
                print(f"  {cat}: {count}")
        print("\n按严重程度:")
        for sev, count in stats['by_severity'].items():
            print(f"  {sev}: {count}")
    elif args.search:
        results = tracker.search_bugs(args.search)
        if not results:
            print(f"未找到包含 '{args.search}' 的问题")
        else:
            print(f"找到 {len(results)} 个相关问题:")
            print("=" * 50)
            for r in results:
                print(f"[{r['category']}] {r['title']}")
                print(f"  严重程度: {r['severity']} | 日期: {r['date']}")
                print(f"  描述: {r['description'][:80]}...")
                print("-" * 50)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
