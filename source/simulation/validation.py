# -*- coding: utf-8 -*-
"""
GROMACS 科研运行后置物理一致性与异常检测模块 (治理 Issue #2)

严格区分三类结果：
- PASS: 无阻断错误且结构/日志物理量均处于合理范围；
- WARNING: 出现可恢复的轻微警告（如零星 LINCS 警告、未发现正常结束脚注），需提醒用户核查；
- BLOCKED: 出现严重物理发散或结构损坏（如 NaN/Inf、Fatal Error、Too many LINCS warnings、
  水分子 SETTLE 崩溃、盒子体积坍塌或 GRO 原子数与实际行不匹配），必须阻断下游继承。

物理误报豁免声明：
- NPT 控压模拟中，凝聚相（如 10~20 nm 有机薄膜或水溶液盒子）的瞬时压力自然波动可达 ±500~2000 bar，
  此模块绝不因瞬时压力负值或大波动误报计算失败。
"""

import math
import os
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationIssue:
    code: str
    severity: str  # "WARNING" | "BLOCKED"
    message: str
    recommendation: str = ""


@dataclass
class ValidationResult:
    status: str = "PASS"  # "PASS" | "WARNING" | "BLOCKED"
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: str = ""

    def add_issue(self, code: str, severity: str, message: str, recommendation: str = ""):
        self.issues.append(ValidationIssue(code, severity, message, recommendation))
        if severity == "BLOCKED":
            self.status = "BLOCKED"
        elif severity == "WARNING" and self.status == "PASS":
            self.status = "WARNING"


def validate_gro_structure(gro_path: str) -> ValidationResult:
    """校验 GRO 结构文件物理完整性：原子数对账、坐标有限性 (NaN/Inf)、正定盒子矢量"""
    res = ValidationResult(summary="GRO 结构校验通过")
    if not os.path.isfile(gro_path):
        res.add_issue("GRO_MISSING", "BLOCKED", f"GRO 文件不存在: {gro_path}", "请确认上一步骤已正确输出结构文件。")
        res.summary = res.issues[0].message
        return res

    try:
        with open(gro_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        res.add_issue("GRO_READ_ERROR", "BLOCKED", f"读取 GRO 文件失败: {exc}")
        res.summary = res.issues[0].message
        return res

    if len(lines) < 3:
        res.add_issue("GRO_TRUNCATED", "BLOCKED", f"GRO 文件行数过少 ({len(lines)} 行)", "结构文件已损坏或截断。")
        res.summary = res.issues[0].message
        return res

    try:
        declared_atoms = int(lines[1].strip())
    except ValueError:
        res.add_issue("GRO_BAD_COUNT", "BLOCKED", f"GRO 第 2 行原子数格式无效: {lines[1].strip()!r}")
        res.summary = res.issues[0].message
        return res

    atom_lines = lines[2:-1]
    if len(atom_lines) != declared_atoms:
        res.add_issue(
            "GRO_COUNT_MISMATCH",
            "BLOCKED",
            f"GRO 声明原子数 ({declared_atoms}) 与实际原子行数 ({len(atom_lines)}) 不一致",
            "可能发生磁盘写入截断或非法编辑，禁止继承此结构文件。"
        )
        res.summary = res.issues[-1].message
        return res

    # 检查坐标非有限数值 (NaN / Inf)
    for idx, line in enumerate(atom_lines, start=3):
        if len(line) < 44:
            res.add_issue("GRO_SHORT_LINE", "BLOCKED", f"第 {idx} 行格式不完整: {line.rstrip()!r}")
            res.summary = res.issues[-1].message
            return res
        try:
            x = float(line[20:28])
            y = float(line[28:36])
            z = float(line[36:44])
        except ValueError:
            res.add_issue("GRO_BAD_COORD", "BLOCKED", f"第 {idx} 行坐标存在非法字符: {line[20:44]!r}")
            res.summary = res.issues[-1].message
            return res
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            res.add_issue(
                "GRO_NON_FINITE_COORD",
                "BLOCKED",
                f"第 {idx} 行发现非有限数值坐标 (NaN/Inf): ({x}, {y}, {z})",
                "体系已发生数值爆炸，请检查初始接触、能量最小化或减小积分步长。"
            )
            res.summary = res.issues[-1].message
            return res

    # 检查末端盒子矢量 (至少 3 个浮点数且主对角线 > 0)
    box_parts = lines[-1].split()
    if len(box_parts) < 3:
        res.add_issue("GRO_BAD_BOX", "BLOCKED", f"GRO 末行盒子矢量不完整: {lines[-1].strip()!r}")
        res.summary = res.issues[-1].message
        return res
    try:
        box_vals = [float(v) for v in box_parts]
    except ValueError:
        res.add_issue("GRO_BAD_BOX", "BLOCKED", f"GRO 盒子矢量含非数值: {lines[-1].strip()!r}")
        res.summary = res.issues[-1].message
        return res

    if any(not math.isfinite(v) for v in box_vals) or box_vals[0] <= 0 or box_vals[1] <= 0 or box_vals[2] <= 0:
        res.add_issue(
            "GRO_COLLAPSED_BOX",
            "BLOCKED",
            f"GRO 盒子主轴尺寸无效或已坍塌: {box_vals[:3]}",
            "请检查模拟控压或盒子定义参数。"
        )
        res.summary = res.issues[-1].message
        return res

    return res


def validate_md_log(log_path: str) -> ValidationResult:
    """分析 GROMACS md.log 日志中的致命错误、LINCS 约束崩溃与非有限数值，容忍正常 NPT 压力波动"""
    res = ValidationResult(summary="MD 日志物理一致性校验通过")
    if not os.path.isfile(log_path):
        res.add_issue("LOG_MISSING", "WARNING", f"未找到日志文件: {log_path}")
        res.summary = res.issues[0].message
        return res

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as exc:
        res.add_issue("LOG_READ_ERROR", "WARNING", f"读取日志失败: {exc}")
        res.summary = res.issues[0].message
        return res

    # 1. 致命错误检测
    if re.search(r"Fatal error|Segmentation fault|Program .* aborted", content, re.IGNORECASE):
        res.add_issue(
            "GMX_FATAL_ERROR",
            "BLOCKED",
            "日志中检测到 GROMACS Fatal error 或段错误 (Segmentation fault)",
            "请检查错误诊断日志定位初始结构冲突、拓扑参数缺失或硬件内存越界。"
        )

    # 2. 非有限数值 (NaN / Inf) 检测（仅匹配独立数值 token，排除正常单词如 'than'/'info'）
    if re.search(r"(?<![A-Za-z])[-+]?(?:nan|inf)(?![A-Za-z])", content, re.IGNORECASE):
        res.add_issue(
            "LOG_NON_FINITE_VALUE",
            "BLOCKED",
            "日志能量/力场输出中出现非有限数值 (NaN 或 Inf)",
            "模拟发生动力学爆炸，请重新做更充分的 EM 或缩短积分步长 dt。"
        )

    # 3. LINCS 与 SETTLE 约束报警分析
    if "Too many LINCS warnings" in content:
        res.add_issue(
            "TOO_MANY_LINCS",
            "BLOCKED",
            "发生 Too many LINCS warnings 导致积分崩溃",
            "原子受强力作用键长剧烈拉伸，建议检查拓扑键参数、进行两步 EM 或减小 dt。"
        )
    if re.search(r"water molecule starting at atom .* can not be settled", content, re.IGNORECASE):
        res.add_issue(
            "SETTLE_FAILURE",
            "BLOCKED",
            "水分子刚体约束 SETTLE 失败",
            "溶剂局部重叠或温度/压力骤变过大，请先执行充分的 EM 与温和 NVT 预平衡。"
        )

    lincs_warnings = len(re.findall(r"LINCS WARNING", content))
    if lincs_warnings > 5 and "Too many LINCS warnings" not in content:
        res.add_issue(
            "HIGH_LINCS_WARNINGS",
            "WARNING",
            f"日志中累计出现 {lincs_warnings} 次瞬时 LINCS 警告",
            "虽未触发崩溃，但建议抽查末帧结构稳定性并核实局部高能原子接触。"
        )
    elif 1 <= lincs_warnings <= 5:
        res.add_issue(
            "TRANSIENT_LINCS_WARNINGS",
            "WARNING",
            f"日志中出现 {lincs_warnings} 次轻微瞬时 LINCS 警告（通常在平衡早期可自行弛豫）"
        )

    # 4. 正常完成标记检查
    if "Finished mdrun on rank" not in content and "Performance:" not in content:
        res.add_issue(
            "INCOMPLETE_RUN",
            "WARNING",
            "未检测到 GROMACS 正常结束性能汇总 (Finished mdrun / Performance)",
            "计算可能被外部强行中断或尚在运行中，请确认是否需要使用 CPT 断点续跑。"
        )

    if res.issues:
        res.summary = f"校验结果: {res.status} (发现 {len(res.issues)} 项提示/问题)"
    return res
