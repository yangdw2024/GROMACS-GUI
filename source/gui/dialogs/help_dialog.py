#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帮助对话框
"""

import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QTabWidget, QDialog
)


from PyQt5.QtCore import Qt


# =============================================================================
# 帮助对话框
# =============================================================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助说明")
        self.resize(800, 600)
        self._create_ui()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        tab_widget = QTabWidget()

        intro_tab = QWidget()
        intro_layout = QVBoxLayout(intro_tab)
        intro_text = QTextEdit()
        intro_text.setReadOnly(True)
        intro_text.setText("""GROMACS GUI 分子动力学模拟平台

这是一个基于 PyQt5 的 GROMACS 可视化操作界面，帮助用户轻松完成分子动力学模拟的全流程。

主要功能模块：
1. 分子动力学模拟 - 能量最小化、NVT/NPT平衡、生产模拟
2. 模拟监控 - 实时查看温度、压力、能量等曲线
3. MDP编辑器 - 可视化编辑模拟参数文件
4. 快速脚本 - 一键生成常用模拟脚本
5. 结果分析 - RMSD、RDF、氢键、SASA、PCA等分析

支持三种脚本类型：
- PowerShell (.ps1) - Windows PowerShell脚本
- Batch (.bat) - Windows批处理脚本
- Shell 命令 - Linux/Mac命令行脚本

使用前请确保：
1. 已安装 GROMACS 并配置好环境变量
2. 已选择正确的工作目录
3. 已准备好输入文件（.gro, .top, .mdp等）
""")
        intro_layout.addWidget(intro_text)
        tab_widget.addTab(intro_tab, "简介")

        md_tab = QWidget()
        md_layout = QVBoxLayout(md_tab)
        md_text = QTextEdit()
        md_text.setReadOnly(True)
        md_text.setText("""分子动力学模拟模块

支持以下模拟步骤：
1. 能量最小化 (EM)
   - EM-1: 最速下降法，初步优化结构
   - EM-2: 共轭梯度法，精细优化

2. 离子化 (Ionize)
   - 在系统中添加离子中和电荷

3. NVT平衡 (恒温恒容)
   - 在恒定温度和体积下进行平衡
   - 推荐时间：100ps-1ns

4. NPT平衡 (恒温恒压)
   - 在恒定温度和压力下进行平衡
   - NPT-1: 初始平衡（100ps-1ns）
   - NPT-2: 扩展平衡（500ps-5ns）

5. MD生产模拟
   - 长时间生产模拟
   - 默认10ns，可根据需要调整

6. SA溶剂蒸发
   - 逐步蒸发溶剂分子
   - 每轮10ps，共100轮

7. 退火模拟
   - 温度循环模拟
""")
        md_layout.addWidget(md_text)
        tab_widget.addTab(md_tab, "分子动力学模拟")

        script_tab = QWidget()
        script_layout = QVBoxLayout(script_tab)
        script_text = QTextEdit()
        script_text.setReadOnly(True)
        script_text.setText("""快速脚本模板

预定义模板说明：
1. 能量最小化 - 完整EM流程（EM-1 + EM-2）
2. 完整MD流程 - EM + NVT + NPT + MD全流程
3. RMSD分析 - 计算蛋白质主链原子的RMSD
4. RDF分析 - 径向分布函数分析
5. 氢键分析 - 统计体系中的氢键数量
6. SASA分析 - 溶剂可及表面积分析
7. PCA分析 - 主成分分析（需要先做轨迹拟合）
8. NVT - 恒温平衡模拟
9. NPT - 恒压平衡模拟
10. MD - 生产模拟

ClFFCl专用模板：
11. ClFFCl EM+NPT - ClFFCl体系专用EM+NPT流程
12. ClFFCl SA蒸发 - ClFFCl体系溶剂蒸发流程
13. ClFFCl MD-1 - ClFFCl体系MD-1生产模拟（10ns）
14. ClFFCl evapDIO - ClFFCl体系蒸发动力学分析

管理自定义模板：
- 添加：创建新的自定义脚本模板
- 编辑：修改已有模板
- 删除：移除不需要的模板
- 模板保存在 templates.json 文件中

模板变量说明：
{gmx} - GROMACS命令路径
{nt} - 线程数
{pwd} - 当前工作目录
""")
        script_layout.addWidget(script_text)
        tab_widget.addTab(script_tab, "快速脚本")

        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_text = QTextEdit()
        analysis_text.setReadOnly(True)
        analysis_text.setText("""结果分析模块

1. RMSD分析
   - 计算原子位置相对于参考结构的均方根偏差
   - 常用于评估蛋白质结构稳定性
   - 输入：traj.xtc, index.ndx, conf.gro

2. RDF分析
   - 径向分布函数，描述原子间距离分布
   - 输入：traj.xtc, index.ndx, conf.gro
   - 输出：rdf.xvg

3. 氢键分析
   - 统计体系中氢键的数量和寿命
   - 输入：traj.xtc, index.ndx, conf.gro
   - 输出：hbond.xvg, hbond_analysis.xvg

4. SASA分析
   - 溶剂可及表面积，评估蛋白质折叠状态
   - 输入：traj.xtc, index.ndx, conf.gro
   - 输出：sasa.xvg

5. PCA分析
   - 主成分分析，提取主要运动模式
   - 需要先做轨迹拟合（gmx trjconv -fit rot+trans）
   - 输入：traj_fit.xtc, index.ndx, conf.gro
   - 输出：eigenvalues.xvg, eigenvectors.trr, pcaprojection.xvg

6. 能量分析
   - 提取势能、动能、总能量等
   - 输入：ener.edr
   - 输出：energy.xvg

7. 温度/压力分析
   - 提取温度、压力变化曲线
   - 输入：ener.edr
   - 输出：temperature.xvg, pressure.xvg
""")
        analysis_layout.addWidget(analysis_text)
        tab_widget.addTab(analysis_tab, "结果分析")

        mdp_tab = QWidget()
        mdp_layout = QVBoxLayout(mdp_tab)
        mdp_text = QTextEdit()
        mdp_text.setReadOnly(True)
        mdp_text.setText("""MDP编辑器

MDP（Molecular Dynamics Parameters）文件定义模拟参数。

常用参数说明：

模拟类型：
- integrator: 积分器类型（md, md-vv, steep, cg）
- nsteps: 总步数
- dt: 时间步长（fs）

温度耦合：
- tcoupl: 温度耦合类型（v-rescale, berendsen）
- tc-grps: 温度耦合组
- tau_t: 温度耦合时间常数
- ref_t: 参考温度（K）

压力耦合：
- pcoupl: 压力耦合类型（parrinello-rahman, berendsen）
- tau_p: 压力耦合时间常数
- ref_p: 参考压力（bar）
- compressibility: 压缩系数

约束：
- constraints: 约束类型（none, h-bonds, all-bonds）
- constraint_algorithm: 约束算法（LINCS, SHAKE）

邻域搜索：
- cutoff-scheme: 截断方案（Verlet, group）
- rlist: 邻域列表截断半径
- rcoulomb: 库仑相互作用截断半径
- rvdw: 范德华相互作用截断半径

输出控制：
- nstxout: 坐标输出频率
- nstvout: 速度输出频率
- nstenergy: 能量输出频率
- nstlog: 日志输出频率

预定义模板：
- EM-1: 最速下降法能量最小化
- EM-2: 共轭梯度法能量最小化
- NPT-1: 初始NPT平衡
- NPT-2: 扩展NPT平衡
- MD: 生产模拟（10ns）
- SA溶剂蒸发
- 退火模拟
""")
        mdp_layout.addWidget(mdp_text)
        tab_widget.addTab(mdp_tab, "MDP参数")

        ndx_tab = QWidget()
        ndx_layout = QVBoxLayout(ndx_tab)
        ndx_text = QTextEdit()
        ndx_text.setReadOnly(True)
        ndx_text.setText("""索引文件 (.ndx)

索引文件用于定义原子组，在GROMACS模拟和分析中非常重要。

用途：
- 定义温度耦合组（tc-grps）
- 定义压力耦合组（pcouplgrps）
- 选择特定原子进行分析（如RMSD、RMSF、SASA等）
- 定义能量组（energygrps）
- 指定位置限制的原子组

常见选择表达式：
- 'protein' - 选择所有蛋白质原子
- 'resname LIG' - 选择配体（将LIG替换为实际配体残基名）
- 'resname SOL' - 选择水分子
- 'resname NA CL' - 选择钠离子和氯离子
- 'resname ALA' - 选择丙氨酸残基
- 'backbone' - 选择主链原子
- 'name CA' - 选择α-碳原子
- 'chain A' - 选择A链
- 'resid 1-100' - 选择1-100号残基
- 'not water' - 选择非水原子
- 'within 0.5 of protein' - 选择蛋白质周围0.5nm内的原子

创建索引文件：
使用 gmx make_ndx 命令创建或修改索引文件。
- 输入：结构文件（gro/pdb）
- 输出：索引文件（ndx）

示例命令：
gmx make_ndx -f protein.gro -o index.ndx -select 'protein'
gmx make_ndx -f protein.gro -o index.ndx -select 'resname LIG'

在分析中使用索引文件：
大多数分析命令支持 -n 参数指定索引文件：
gmx rms -f md.xtc -s md.tpr -o rmsd.xvg -n index.ndx
gmx rmsf -f md.xtc -s md.tpr -o rmsf.xvg -n index.ndx -res
""")
        ndx_layout.addWidget(ndx_text)
        tab_widget.addTab(ndx_tab, "索引文件")

        main_layout.addWidget(tab_widget)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)
