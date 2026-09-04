#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误诊断器与错误诊断对话框
"""

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QScrollArea, QDialog
)


# =============================================================================
# 错误诊断器
# =============================================================================
class ErrorDiagnoser:
    _ERROR_PATTERNS = [
        {
            "pattern": r"(?i)file.*not.*found|cannot.*find.*file|no.*such.*file.*or.*directory|cannot.*open.*file",
            "error_type": "文件不存在",
            "severity": "high",
            "description": "输入文件不存在或无法打开",
            "suggestions": [
                "检查文件路径是否正确",
                "确保所有输入文件（如PDB、GRO、TOP、MDP）都在工作目录中",
                "确认文件名拼写正确",
                "检查文件是否被其他程序占用",
                "使用浏览按钮重新选择文件"
            ]
        },
        {
            "pattern": r"(?i)fatal.*error.*topology|topology.*error|missing.*topology|cannot.*find.*atom.*type.*in.*topology",
            "error_type": "拓扑错误",
            "severity": "high",
            "description": "拓扑文件存在问题，可能缺少定义或参数",
            "suggestions": [
                "检查topol.top文件是否完整",
                "确保所有include的itp文件都存在",
                "验证posre.itp文件是否正确生成",
                "检查原子类型是否在力场中定义",
                "使用pdb2gmx重新生成拓扑"
            ]
        },
        {
            "pattern": r"(?i)out.*of.*memory|memory.*allocation.*failed|not.*enough.*memory|insufficient.*memory",
            "error_type": "内存不足",
            "severity": "high",
            "description": "系统内存不足，无法完成计算",
            "suggestions": [
                "减少模拟体系规模",
                "降低网格参数（如fourierspacing）",
                "减少-np或-nt线程数",
                "关闭其他占用内存的程序",
                "考虑增加系统物理内存",
                "启用内存限制选项"
            ]
        },
        {
            "pattern": r"(?i)cannot.*find.*gpu|cuda.*error|gpu.*not.*supported|gpu.*not.*found|nvidia.*error|opencl.*error",
            "error_type": "GPU错误",
            "severity": "high",
            "description": "GPU加速失败或GPU不可用",
            "suggestions": [
                "确保NVIDIA GPU驱动已安装并更新",
                "检查CUDA版本与GROMACS版本兼容",
                "确认系统中有可用的NVIDIA GPU",
                "尝试禁用GPU加速（使用CPU模式）",
                "检查-gpu_id参数是否正确",
                "使用nvidia-smi检查GPU状态"
            ]
        },
        {
            "pattern": r"(?i)syntax.*error|parse.*error|invalid.*syntax|unexpected.*token",
            "error_type": "语法错误",
            "severity": "high",
            "description": "输入文件存在语法错误",
            "suggestions": [
                "检查MDP文件格式（等号两边应有空格）",
                "验证所有参数值是否正确",
                "确保注释以分号开头",
                "检查TOP文件中的include语法",
                "使用MDP编辑器验证格式"
            ]
        },
        {
            "pattern": r"(?i)permission.*denied|access.*denied|cannot.*write.*to.*file|read.*only.*file",
            "error_type": "权限问题",
            "severity": "high",
            "description": "没有足够的权限读写文件",
            "suggestions": [
                "确保工作目录有写入权限",
                "检查目标文件是否被其他程序锁定",
                "尝试以管理员身份运行程序",
                "检查输出目录是否存在",
                "确保磁盘没有被写保护"
            ]
        },
        {
            "pattern": r"(?i)version.*mismatch|not.*compatible|incompatible.*version|version.*conflict",
            "error_type": "版本不兼容",
            "severity": "high",
            "description": "文件或组件版本不兼容",
            "suggestions": [
                "检查TPR文件与GROMACS版本是否匹配",
                "使用相同版本的GROMACS重新编译TPR",
                "更新GROMACS到最新版本",
                "检查PLUMED版本兼容性",
                "验证力场文件版本"
            ]
        },
        {
            "pattern": r"(?i)invalid.*argument|unknown.*option|bad.*argument|illegal.*option|unknown.*flag",
            "error_type": "参数错误",
            "severity": "high",
            "description": "命令行参数无效或不被识别",
            "suggestions": [
                "检查命令参数拼写是否正确",
                "验证参数顺序是否正确",
                "检查参数值是否在有效范围内",
                "参考GROMACS官方文档",
                "使用gmx <命令> -h查看帮助"
            ]
        },
        {
            "pattern": r"(?i)cannot.*find.*force.*field|ff.*library.*not.*found|force.*field.*not.*found|unknown.*force.*field",
            "error_type": "力场问题",
            "severity": "high",
            "description": "指定的力场不存在或无法加载",
            "suggestions": [
                "检查力场名称拼写是否正确",
                "确认力场文件已安装在GROMACS力场目录中",
                "尝试使用标准力场（如amber99sb-ildn）",
                "检查GMXLIB环境变量是否正确设置",
                "重新安装GROMACS力场文件"
            ]
        },
        {
            "pattern": r"(?i)unknown.*atom.*type|cannot.*find.*atom.*type|undefined.*atom.*type|atom.*type.*not.*found",
            "error_type": "原子类型错误",
            "severity": "high",
            "description": "拓扑中包含未定义的原子类型",
            "suggestions": [
                "检查PDB文件中是否有不标准的原子名称",
                "使用-ignh参数忽略氢原子",
                "确认选择的力场支持所有原子类型",
                "手动编辑拓扑文件添加缺失的原子类型",
                "尝试使用其他力场（如gaff需要AmberTools预处理）"
            ]
        },
        {
            "pattern": r"(?i)invalid.*box|box.*too.*small|box.*size.*error|box.*dimensions|cannot.*create.*box",
            "error_type": "盒子问题",
            "severity": "medium",
            "description": "模拟盒子参数无效",
            "suggestions": [
                "增大盒子尺寸或边距",
                "确保盒子足够容纳所有分子",
                "检查editconf参数是否正确",
                "验证PBC设置",
                "尝试使用更大的-d参数值"
            ]
        },
        {
            "pattern": r"(?i)cannot.*solvate|solvent.*box.*too.*small|solvate.*error|no.*space.*for.*solvent",
            "error_type": "溶剂化错误",
            "severity": "medium",
            "description": "无法向盒子中添加溶剂",
            "suggestions": [
                "增大盒子尺寸给溶剂留出空间",
                "检查结构是否超出盒子边界",
                "确保editconf已正确执行",
                "尝试使用更紧凑的盒子类型（如dodecahedron）",
                "检查水模型文件是否存在"
            ]
        },
        {
            "pattern": r"(?i)fft.*grid|pme.*grid|grid.*spacing|grid.*error|fourier.*grid",
            "error_type": "网格问题",
            "severity": "medium",
            "description": "PME/FFT网格参数有问题",
            "suggestions": [
                "调整fourierspacing参数（推荐0.12-0.16）",
                "增大网格尺寸",
                "检查盒子尺寸与网格的兼容性",
                "尝试使用-sm all参数",
                "降低pme_order值"
            ]
        },
        {
            "pattern": r"(?i)lincs.*error|constraint.*violation|shake.*error|bond.*constraint",
            "error_type": "约束问题",
            "severity": "medium",
            "description": "约束算法遇到问题",
            "suggestions": [
                "减小时间步长（dt）",
                "增加lincs_iter或lincs_order",
                "检查结构中是否有不合理的键长",
                "尝试使用SHAKE替代LINCS",
                "重新运行能量最小化",
                "减少约束数量"
            ]
        },
        {
            "pattern": r"(?i)temperature.*coupling|tc-grps|tcoupl.*error|temperature.*group",
            "error_type": "温度耦合问题",
            "severity": "medium",
            "description": "温度耦合参数配置错误",
            "suggestions": [
                "检查tc-grps是否定义了有效的组",
                "确保tau_t值合理（通常0.1-1.0 ps）",
                "验证ref_t值在合理范围内",
                "检查index文件中的组定义",
                "尝试使用tc-grps = System"
            ]
        },
        {
            "pattern": r"(?i)pressure.*coupling|pcoupl|barostat.*error|pressure.*group",
            "error_type": "压力耦合问题",
            "severity": "medium",
            "description": "压力耦合参数配置错误",
            "suggestions": [
                "检查pcoupl类型是否支持当前模拟",
                "确保tau_p值合理（通常1.0-5.0 ps）",
                "验证ref_p值在合理范围内",
                "检查compressibility值",
                "尝试使用pcoupltype = isotropic"
            ]
        },
        {
            "pattern": r"(?i)cannot.*write.*to.*file|disk.*full|out.*of.*disk.*space|write.*error|disk.*error",
            "error_type": "输出文件问题",
            "severity": "high",
            "description": "无法写入输出文件",
            "suggestions": [
                "检查磁盘空间是否充足",
                "确保输出目录有写入权限",
                "检查输出文件名是否有效",
                "删除不再需要的旧文件释放空间",
                "尝试更换输出目录"
            ]
        },
        {
            "pattern": r"(?i)invalid.*format|format.*error|wrong.*format|corrupt.*file|file.*format",
            "error_type": "输入文件格式错误",
            "severity": "high",
            "description": "输入文件格式不正确或已损坏",
            "suggestions": [
                "检查PDB/GRO文件格式是否正确",
                "验证文件编码（使用UTF-8）",
                "检查文件是否被意外修改",
                "重新生成输入文件",
                "使用editconf转换文件格式"
            ]
        },
        {
            "pattern": r"(?i)mpi.*error|openmp.*error|parallel.*error|thread.*error|cannot.*create.*thread",
            "error_type": "并行计算问题",
            "severity": "medium",
            "description": "并行计算配置有问题",
            "suggestions": [
                "减少-nt线程数",
                "检查MPI环境是否正确配置",
                "尝试使用单线程模式",
                "确保线程绑定正确（-pin on）",
                "检查系统资源限制"
            ]
        },
        {
            "pattern": r"(?i)checkpoint.*file|cannot.*read.*checkpoint|cpt.*error|restart.*error|continue.*error",
            "error_type": "检查点问题",
            "severity": "medium",
            "description": "检查点文件无法读取或不兼容",
            "suggestions": [
                "检查CPT文件是否存在",
                "确认CPT文件与TPR文件版本匹配",
                "尝试不使用-cpi参数重新运行",
                "检查CPT文件是否损坏",
                "使用-continuation = yes"
            ]
        },
        {
            "pattern": r"(?i)segmentation.*fault|segfault|crash|abort|terminate.*called",
            "error_type": "程序崩溃",
            "severity": "high",
            "description": "程序意外崩溃",
            "suggestions": [
                "减少体系规模或模拟步数",
                "检查输入文件是否正确",
                "尝试使用调试模式运行",
                "更新GROMACS到最新版本",
                "检查硬件是否正常",
                "报告问题到GROMACS论坛"
            ]
        },
        {
            "pattern": r"(?i)bond.*length.*warning|angle.*warning|dihedral.*warning|bad.*contact|clash",
            "error_type": "结构问题",
            "severity": "low",
            "description": "结构中存在不良接触",
            "suggestions": [
                "增加能量最小化步数",
                "使用更严格的emtol值",
                "检查PDB文件中是否有异常原子位置",
                "使用editconf检查结构",
                "考虑修复初始结构"
            ]
        }
    ]

    def diagnose(self, error_message, command=""):
        import re
        results = []
        for pattern_info in self._ERROR_PATTERNS:
            if re.search(pattern_info["pattern"], error_message):
                result = {
                    "error_type": pattern_info["error_type"],
                    "description": pattern_info["description"],
                    "suggestions": pattern_info["suggestions"],
                    "severity": pattern_info["severity"],
                    "matched_text": self._extract_matched_text(error_message, pattern_info["pattern"])
                }
                results.append(result)
        if not results:
            results.append({
                "error_type": "未知错误",
                "description": "无法识别的错误类型",
                "suggestions": [
                    "仔细阅读错误信息",
                    "检查所有输入文件",
                    "参考GROMACS官方文档",
                    "在GROMACS论坛搜索解决方案",
                    "尝试简化模拟参数"
                ],
                "severity": "medium",
                "matched_text": ""
            })
        return results

    def _extract_matched_text(self, text, pattern):
        import re
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        return ""


# =============================================================================
# 诊断结果对话框
# =============================================================================
class ErrorDiagnosisDialog(QDialog):
    def __init__(self, parent=None, diagnoses=None):
        super().__init__(parent)
        self.setWindowTitle("错误诊断结果")
        self.resize(700, 500)
        self._diagnoses = diagnoses or []
        self._create_ui()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        summary_label = QLabel(f"共检测到 {len(self._diagnoses)} 个错误类型")
        summary_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1565C0;")
        main_layout.addWidget(summary_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        for i, diag in enumerate(self._diagnoses):
            severity_color = self._get_severity_color(diag["severity"])
            severity_label = self._get_severity_label(diag["severity"])

            group = QGroupBox(f"诊断 {i + 1}: {diag['error_type']} [{severity_label}]")
            group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {severity_color}; }}")

            glayout = QVBoxLayout(group)

            desc_label = QLabel(f"<b>描述:</b> {diag['description']}")
            desc_label.setStyleSheet("color: #333;")
            desc_label.setWordWrap(True)
            glayout.addWidget(desc_label)

            if diag["matched_text"]:
                matched_label = QLabel(f"<b>匹配文本:</b> {diag['matched_text']}")
                matched_label.setStyleSheet("color: #666; font-family: Consolas; font-size: 11px;")
                matched_label.setWordWrap(True)
                glayout.addWidget(matched_label)

            suggestions_group = QGroupBox("修复建议")
            sg_layout = QVBoxLayout(suggestions_group)

            for j, suggestion in enumerate(diag["suggestions"]):
                item_label = QLabel(f"{j + 1}. {suggestion}")
                item_label.setStyleSheet("color: #2E7D32; padding-left: 5px;")
                item_label.setWordWrap(True)
                sg_layout.addWidget(item_label)

            glayout.addWidget(suggestions_group)
            content_layout.addWidget(group)

        content_layout.addStretch()
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area, stretch=1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_copy = QPushButton("复制诊断信息")
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        button_layout.addWidget(self.btn_copy)
        button_layout.addWidget(self.btn_close)
        main_layout.addLayout(button_layout)

    def _get_severity_color(self, severity):
        if severity == "high":
            return "#D32F2F"
        elif severity == "medium":
            return "#F57C00"
        else:
            return "#FBC02D"

    def _get_severity_label(self, severity):
        if severity == "high":
            return "严重"
        elif severity == "medium":
            return "中等"
        else:
            return "低"

    def _on_copy(self):
        text = self._generate_summary_text()
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.parent().add_log("诊断信息已复制到剪贴板", "success")

    def _generate_summary_text(self):
        lines = ["=" * 60, "错误诊断报告", "=" * 60]
        for i, diag in enumerate(self._diagnoses):
            lines.append(f"\n--- 诊断 {i + 1}: {diag['error_type']} [{diag['severity']}] ---")
            lines.append(f"描述: {diag['description']}")
            if diag["matched_text"]:
                lines.append(f"匹配: {diag['matched_text']}")
            lines.append("建议:")
            for j, suggestion in enumerate(diag["suggestions"]):
                lines.append(f"  {j + 1}. {suggestion}")
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
