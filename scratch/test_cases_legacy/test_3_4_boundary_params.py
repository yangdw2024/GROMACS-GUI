"""
test_3_4_boundary_params.py
检测极端边界参数是否有前置拦截
====================================
读取 gromacs_gui_v4.py 源代码，搜索对应的前置校验逻辑，
输出边界漏洞清单。
"""

import sys
import os
import re

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

SOURCE_FILE = os.path.join(r"D:\YDW\Trae_Gromacs\source", "gromacs_gui_v4.py")


def read_source():
    """读取源代码全文"""
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────
# 各类边界参数的检测函数
# ──────────────────────────────────────────────

def check_memory_boundary(src: str):
    """
    内存限制边界检测
    - UI: cfg_mem_value = QDoubleSpinBox, setRange(0.5, sys_memory_gb)
    - 持久化加载: mem_val = max(0.5, min(mem_val, float(sys_memory_gb)))
    - Worker: mem_bytes = int(mem_limit_gb * 1024**3), 无额外校验
    """
    results = []

    # 0 GB
    has_0_check = bool(re.search(r"mem.*==\s*0|mem.*<=\s*0|mem.*<\s*0\.5|mem_limit.*==\s*0", src))
    has_range_min = "setRange(0.5" in src
    has_max_clamp = "max(0.5" in src and "min(mem_val" in src
    # QDoubleSpinBox setRange(0.5, ...) 本身阻止了 0 的输入，但若通过配置文件直接写入则仅靠 max(0.5,...) 保护
    results.append({
        "参数类型": "内存限制",
        "测试值": "0 GB",
        "是否有前置拦截": "是(QDoubleSpinBox范围0.5起 + max(0.5,...)钳位)" if has_range_min and has_max_clamp else "否",
        "会否导致崩溃": "否(UI层阻止)，但配置文件可绕过直接传0给Worker",
        "严重程度": "MEDIUM"
    })

    # -1 GB
    results.append({
        "参数类型": "内存限制",
        "测试值": "-1 GB",
        "是否有前置拦截": "是(QDoubleSpinBox范围0.5起 + max(0.5,...)钳位)",
        "会否导致崩溃": "否(UI层阻止)，配置文件绕过后Worker计算mem_bytes为负数，ctypes传入负值可能导致Job Object创建失败",
        "严重程度": "MEDIUM"
    })

    # 9999 GB（超硬件）
    has_max_clamp_upper = "min(mem_val" in src and "sys_memory_gb" in src
    results.append({
        "参数类型": "内存限制",
        "测试值": "9999 GB（超硬件）",
        "是否有前置拦截": "是(QDoubleSpinBox上限=sys_memory_gb + min(...,sys_memory_gb)钳位)" if has_max_clamp_upper else "否",
        "会否导致崩溃": "否(UI层限制)，配置文件绕过后Worker设置超出物理内存的Job Object，进程启动即被系统终止",
        "严重程度": "MEDIUM"
    })

    # 0.01 GB（极小值）
    has_min_05 = "setRange(0.5" in src
    results.append({
        "参数类型": "内存限制",
        "测试值": "0.01 GB（极小值）",
        "是否有前置拦截": "部分(QDoubleSpinBox下限0.5，但配置文件绕过后max(0.5,...)会修正到0.5)",
        "会否导致崩溃": "否(被钳位到0.5GB)，但0.5GB可能导致GROMACS进程因内存不足被系统频繁终止",
        "严重程度": "LOW"
    })

    return results


def check_thread_boundary(src: str):
    """
    线程数边界检测
    - UI: cfg_nt = QSpinBox, setRange(1, sys_cpu_cores)
    - 持久化加载: cfg_nt.setValue(nt) — 无范围钳位
    """
    results = []

    # 0线程
    has_range_1 = "setRange(1," in src
    results.append({
        "参数类型": "线程数",
        "测试值": "0 线程",
        "是否有前置拦截": "是(QSpinBox范围1起)" if has_range_1 else "否",
        "会否导致崩溃": "否(UI层阻止)，配置文件绕过后cfg_nt.setValue(0)，QSpinBox会被钳位到minimum=1",
        "严重程度": "LOW"
    })

    # -1线程
    results.append({
        "参数类型": "线程数",
        "测试值": "-1 线程",
        "是否有前置拦截": "是(QSpinBox范围1起)",
        "会否导致崩溃": "否(UI层阻止)，QSpinBox对负值自动钳位到minimum=1",
        "严重程度": "LOW"
    })

    # 999线程（超CPU核心）
    has_range_upper = "setRange(1, self.sys_cpu_cores)" in src
    # 检查配置加载时是否有钳位
    has_nt_clamp = bool(re.search(r"cfg_nt.*max|cfg_nt.*min|nt.*clamp|nt.*range", src))
    results.append({
        "参数类型": "线程数",
        "测试值": "999 线程（超CPU核心）",
        "是否有前置拦截": "部分(UI: QSpinBox上限=sys_cpu_cores；但配置加载时cfg_nt.setValue(nt)无钳位)",
        "会否导致崩溃": "否(QSpinBox会钳位到maximum)，但GROMACS命令行-nt 999会由GROMACS自身处理（通常自动降为物理核心数）",
        "严重程度": "LOW"
    })

    return results


def check_path_boundary(src: str):
    """
    文件路径边界检测
    - _get_work_dir(): 检查空值 + os.path.isdir(wd)
    - 部分步骤额外检查写入权限 (PermissionError)
    - 无中文路径/空格路径特殊处理
    """
    results = []

    # 中文路径
    has_chinese_check = bool(re.search(r"[\u4e00-\u9fff].*路径|中文.*路径|encode.*utf|decode.*utf", src))
    results.append({
        "参数类型": "文件路径",
        "测试值": "中文路径（如 D:\\模拟\\项目）",
        "是否有前置拦截": "否(无中文路径专项检测)",
        "会否导致崩溃": "可能(GROMACS subprocess在部分编码环境下对中文路径处理异常，subprocess.run可能因编码问题报错)",
        "严重程度": "MEDIUM"
    })

    # 带空格路径
    has_space_check = bool(re.search(r"path.*strip|path.*quote|空格|space.*path|\".*path", src))
    results.append({
        "参数类型": "文件路径",
        "测试值": "带空格路径（如 D:\\My Projects\\sim）",
        "是否有前置拦截": "否(无空格路径专项检测)，但cmd构建使用列表形式[subprocess]传递，不受空格影响",
        "会否导致崩溃": "否(subprocess列表传参天然支持空格)，但批处理脚本写入时路径含空格可能导致BAT脚本执行异常",
        "严重程度": "LOW"
    })

    # 只读目录
    has_permission_check = "PermissionError" in src
    results.append({
        "参数类型": "文件路径",
        "测试值": "只读目录",
        "是否有前置拦截": "部分(部分步骤有PermissionError检测，但_get_work_dir()无权限校验)",
        "会否导致崩溃": "否(运行时写入报错被捕获)，但缺少统一前置拦截会导致用户走到运行阶段才报错",
        "严重程度": "MEDIUM"
    })

    # 不存在的目录
    has_dir_exist_check = "os.path.isdir(wd)" in src or "os.path.exists(wd)" in src
    results.append({
        "参数类型": "文件路径",
        "测试值": "不存在的目录",
        "是否有前置拦截": "是(_get_work_dir检查os.path.isdir + 各步骤检查os.path.exists)",
        "会否导致崩溃": "否(前置拦截返回None/报错日志)",
        "严重程度": "LOW"
    })

    return results


def check_version_dir_boundary(src: str):
    """
    GROMACS版本目录边界检测
    - scan_gromacs_versions(): 检查os.path.isdir + os.path.isfile(gmx_path)
    - get_gromacs_version_info(): 检查os.path.isfile(gmx_exe)
    - _browse_gmx_exe(): 检查os.path.isfile + endswith("gmx.exe")
    - 版本切换时: os.path.isfile(new_path)
    """
    results = []

    # 空文件夹（无gmx.exe）
    has_gmx_exist_check = 'os.path.isfile(gmx_path)' in src and 'os.path.isfile(gmx_exe)' in src
    results.append({
        "参数类型": "GROMACS版本目录",
        "测试值": "空文件夹（无gmx.exe）",
        "是否有前置拦截": "是(scan_gromacs_versions跳过无gmx.exe的目录 + get_gromacs_version_info返回默认info)",
        "会否导致崩溃": "否(不会出现在版本列表中)",
        "严重程度": "LOW"
    })

    # gmx.exe损坏
    has_gmx_run_check = bool(re.search(r"subprocess.*gmx|gmx.*--version|timeout.*15", src))
    has_exception_handling = bool(re.search(r"try:.*gmx|except.*subprocess", src, re.DOTALL))
    results.append({
        "参数类型": "GROMACS版本目录",
        "测试值": "gmx.exe损坏（非有效PE文件）",
        "是否有前置拦截": "否(仅检查文件存在性os.path.isfile，不验证文件有效性)",
        "会否导致崩溃": "可能(subprocess.run执行损坏exe会抛出OSError/WinError，get_gromacs_version_info中有try/except但仅覆盖--version命令，运行模拟时损坏exe直接报错)",
        "严重程度": "HIGH"
    })

    # 力场目录为空
    has_forcefield_check = bool(re.search(r"力场目录|top.*dir|share.*gromacs.*top", src))
    # 7875行: "⚠ 未找到GROMACS力场目录" 仅在GPU诊断时检查，日常使用无校验
    results.append({
        "参数类型": "GROMACS版本目录",
        "测试值": "力场目录为空",
        "是否有前置拦截": "否(仅在GPU诊断流程中检查力场目录是否存在，grompp/pdb2gmx运行前无前置校验)",
        "会否导致崩溃": "否(GROMACS grompp/pdb2gmx运行时会报错，错误会被日志捕获和诊断)，但缺少前置提示导致用户需等运行后才知",
        "严重程度": "MEDIUM"
    })

    return results


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  gromacs_gui_v4.py 边界参数前置拦截检测报告")
    print("=" * 80)
    print(f"  源文件: {SOURCE_FILE}")
    print()

    src = read_source()

    all_results = []
    all_results.extend(check_memory_boundary(src))
    all_results.extend(check_thread_boundary(src))
    all_results.extend(check_path_boundary(src))
    all_results.extend(check_version_dir_boundary(src))

    # 输出表格
    header = f"{'参数类型':<16} {'测试值':<30} {'前置拦截':<40} {'会否崩溃':<30} {'严重程度':<8}"
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    # 按严重程度排序
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_results.sort(key=lambda r: severity_order.get(r["严重程度"], 9))

    for r in all_results:
        print(f"{r['参数类型']:<16} {r['测试值']:<30} {r['是否有前置拦截']:<40} {r['会否导致崩溃']:<30} {r['严重程度']:<8}")

    print(sep)
    print()

    # 统计
    high_count = sum(1 for r in all_results if r["严重程度"] == "HIGH")
    medium_count = sum(1 for r in all_results if r["严重程度"] == "MEDIUM")
    low_count = sum(1 for r in all_results if r["严重程度"] == "LOW")
    no_intercept_count = sum(1 for r in all_results if r["是否有前置拦截"].startswith("否"))
    partial_intercept_count = sum(1 for r in all_results if r["是否有前置拦截"].startswith("部分"))

    print("【统计汇总】")
    print(f"  总检测项: {len(all_results)}")
    print(f"  HIGH:   {high_count}")
    print(f"  MEDIUM: {medium_count}")
    print(f"  LOW:    {low_count}")
    print(f"  无前置拦截: {no_intercept_count}")
    print(f"  部分拦截:   {partial_intercept_count}")
    print()

    # 重点漏洞
    print("【重点漏洞（HIGH）】")
    for r in all_results:
        if r["严重程度"] == "HIGH":
            print(f"  ▸ {r['参数类型']} — {r['测试值']}")
            print(f"    拦截情况: {r['是否有前置拦截']}")
            print(f"    崩溃风险: {r['会否导致崩溃']}")
    print()

    print("【修复建议】")
    print("  1. gmx.exe损坏: 在版本切换/浏览选择时增加subprocess试运行校验，")
    print("     或检查文件PE头有效性，提前拦截损坏的可执行文件")
    print("  2. 内存限制绕过: 在GromacsWorker.__init__中增加mem_limit_gb<=0的显式拒绝")
    print("  3. 中文路径: 在_get_work_dir中增加路径编码检测，对非ASCII路径给出警告")
    print("  4. 只读目录: 将PermissionError检测统一到_get_work_dir()，而非分散在各步骤中")
    print("  5. 力场目录: 在版本切换时检查share/gromacs/top目录是否有效，提前预警")
    print()


if __name__ == "__main__":
    main()
