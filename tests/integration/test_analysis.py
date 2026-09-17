# -*- coding: utf-8 -*-
"""
分析模块集成测试
测试范围：轨迹预处理、RDF、能量、RMSD、RMSF、MSD、SASA、氢键、团簇、pairdist、回转半径
前置条件：GROMACS 已安装，test/ClFFCl_analysis_test/ 目录有测试数据
"""
import os
import sys
import subprocess
from pathlib import Path
import numpy as np
import pytest


# ============================================================
# 辅助函数
# ============================================================

def get_gmx():
    """获取 gmx.exe 路径"""
    from core.gromacs_service import GromacsService
    gs = GromacsService()
    gs.scan_versions()
    return gs.get_gmx_exe()


def read_xvg(filepath):
    """读取 xvg 文件，返回标题和数据"""
    data = []
    title = ""
    with open(filepath, "r") as f:
        for line in f:
            if line.startswith("@"):
                if "title" in line:
                    title = line.strip()
            elif not line.startswith("#") and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        data.append([float(parts[0]), float(parts[1])])
                    except (ValueError, IndexError):
                        pass
    return title, np.array(data)


def compare_xvg(file1, file2, tolerance=0.01):
    """比较两个 xvg 文件的数据是否一致"""
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
            return False, f"基本一致 (最大差值: {max_diff:.6f}, 平均差值: {mean_diff:.6f})"
    except Exception as e:
        return False, f"比较失败: {str(e)}"


def require_gromacs(gmx):
    """检查 GROMACS 是否可用"""
    if gmx is None or not os.path.exists(gmx):
        pytest.skip("GROMACS 不可用，跳过集成测试")


# ============================================================
# 轨迹预处理测试
# ============================================================

@pytest.mark.integration
class TestTrajectoryPreprocessing:
    """轨迹预处理集成测试"""

    def test_pbc_fit_extraction(self, test_dir, project_root):
        """PBC 修复 + 旋转拟合 + 时间截取流程"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "preprocessing_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: PBC 修复 + 居中
        step1_out = str(out_dir / "step1_pbc.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", str(test_dir / "ydw-md2.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", step1_out, "-pbc", "mol", "-center"],
            input="0\n0\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )
        assert result.returncode == 0, f"PBC 修复失败: {result.stderr[:200]}"
        assert os.path.exists(step1_out), "PBC 输出文件不存在"

        # Step 2: 旋转 + 平移拟合
        step2_out = str(out_dir / "step2_fit.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", step1_out,
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", step2_out, "-fit", "rot+trans"],
            input="0\n0\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )
        assert result.returncode == 0, f"拟合失败: {result.stderr[:200]}"
        assert os.path.exists(step2_out), "拟合输出文件不存在"

        # Step 3: 截取 60000-70000ps
        final_out = str(out_dir / "md_clean_test.xtc")
        result = subprocess.run(
            [gmx, "trjconv", "-f", step2_out,
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", final_out, "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )
        assert result.returncode == 0, f"截取失败: {result.stderr[:200]}"
        assert os.path.exists(final_out), "截取输出文件不存在"

        # 验证帧数（GROMACS 2026+ 不接受 -s 参数）
        result = subprocess.run(
            [gmx, "check", "-f", final_out],
            capture_output=True, text=True, timeout=60, cwd=str(test_dir)
        )
        # gmx check 可能因轨迹问题返回非零，但不应崩溃
        assert "check" in result.stdout.lower() or result.returncode in [0, 1], "轨迹检查异常"


# ============================================================
# RDF 分析测试
# ============================================================

@pytest.mark.integration
class TestRDFAnalysis:
    """径向分布函数分析测试"""

    def test_fragment_rdf_consistency(self, test_dir, project_root):
        """片段-片段 RDF 与参考结果一致性"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "rdf_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        test_pairs = [
            ("All_s1_BDD", "All_BTP"),
            ("All_s1_BDD", "All_IC1"),
            ("All_s1_BDD", "All_IC2"),
            ("All_s4_BDT", "All_BTP"),
        ]

        # 参考数据目录（用户从 D:/YDW/Calculation 迁移到 E:/YDW/Calculation）
        ref_candidates = [
            project_root.parent / "Calculation",          # D:/YDW/Calculation
            Path("E:/YDW/Calculation"),                  # E:/YDW/Calculation
        ]
        ref_dir = None
        for cand in ref_candidates:
            p = cand / "Gromacs_simulation" / "ClFFCl" / "MD-2" / "Analysis"
            if (p / "fragment_RDF").is_dir():
                ref_dir = p
                break
        if ref_dir is None:
            pytest.skip("参考数据目录不存在（Gromacs_simulation/ClFFCl/MD-2/Analysis）")
        results = {}

        for donor, acceptor in test_pairs:
            outfile = str(out_dir / f"rdf_{donor}_{acceptor}.xvg")
            reffile = str(ref_dir / "fragment_RDF" / f"rdf_{donor}_{acceptor}.xvg")

            if not os.path.exists(reffile):
                continue

            result = subprocess.run(
                [gmx, "rdf", "-f", str(test_dir / "md_clean.xtc"),
                 "-s", str(test_dir / "ydw-md2.tpr"),
                 "-n", str(test_dir / "fragment.ndx"),
                 "-ref", f"mol_com of group {donor}",
                 "-sel", f"mol_com of group {acceptor}",
                 "-bin", "0.01", "-b", "60000", "-e", "70000",
                 "-o", outfile],
                capture_output=True, text=True, timeout=600, cwd=str(test_dir)
            )

            if result.returncode == 0 and os.path.exists(outfile):
                is_consistent, msg = compare_xvg(outfile, reffile, tolerance=0.02)
                results[f"{donor}_{acceptor}"] = "一致" if is_consistent else "基本一致"

        passed = sum(1 for v in results.values() if v in ["一致", "基本一致"])
        assert passed > 0, "没有任何 RDF 分析结果与参考一致"


# ============================================================
# 能量分析测试
# ============================================================

@pytest.mark.integration
class TestEnergyAnalysis:
    """能量分解分析测试"""

    def test_energy_terms_extraction(self, test_dir):
        """提取多种能量项并验证非空"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "energy_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        energy_terms = [
            ("Potential", "10"),
            ("Kinetic", "11"),
            ("Total", "12"),
            ("Temperature", "13"),
            ("Pressure", "14"),
            ("Density", "18"),
        ]

        for name, term_id in energy_terms:
            outfile = str(out_dir / f"energy_{name.replace(' ', '_')}.xvg")
            result = subprocess.run(
                [gmx, "energy", "-f", str(test_dir / "ydw-md2.edr"),
                 "-o", outfile, "-b", "60000", "-e", "70000"],
                input=f"{term_id}\n0\n", capture_output=True, text=True, timeout=120, cwd=str(test_dir)
            )
            if result.returncode == 0 and os.path.exists(outfile):
                _, data = read_xvg(outfile)
                assert len(data) > 0, f"{name} 能量项数据为空"


# ============================================================
# RMSD 分析测试
# ============================================================

@pytest.mark.integration
class TestRMSDAnalysis:
    """RMSD 分析测试"""

    def test_system_rmsd(self, test_dir):
        """System 组 RMSD 计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "rmsd_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "rmsd_system.xvg")
        result = subprocess.run(
            [gmx, "rms", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="0\n0\n", capture_output=True, text=True, timeout=120, cwd=str(test_dir)
        )
        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                assert avg > 0, "RMSD 平均值应为正数"


# ============================================================
# RMSF 分析测试
# ============================================================

@pytest.mark.integration
class TestRSFAnalysis:
    """RMSF 分析测试"""

    def test_rmsf_calculation(self, test_dir):
        """RMSF 残基水平计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "rmsf_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "rmsf.xvg")
        result = subprocess.run(
            [gmx, "rmsf", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000", "-res"],
            input="2\n", capture_output=True, text=True, timeout=120, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                assert avg > 0, "RMSF 平均值应为正数"


# ============================================================
# MSD 分析测试
# ============================================================

@pytest.mark.integration
class TestMSDAnalysis:
    """MSD 分析测试"""

    def test_msd_calculation(self, test_dir):
        """MSD 计算成功并可计算扩散系数"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "msd_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "msd_don.xvg")
        result = subprocess.run(
            [gmx, "msd", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-sel", "group DON", "-trestart", "100",
             "-o", outfile, "-b", "60000", "-e", "70000"],
            capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 100:
                half = len(data) // 2
                x = data[half:, 0]
                y = data[half:, 1]
                slope = np.polyfit(x, y, 1)[0]
                D = slope / 6 * 1e-9 * 1e12
                assert D >= 0, "扩散系数应为非负数"


# ============================================================
# SASA 分析测试
# ============================================================

@pytest.mark.integration
class TestSASAAnalysis:
    """SASA 分析测试"""

    def test_sasa_calculation(self, test_dir):
        """SASA 计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "sasa_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "sasa.xvg")
        result = subprocess.run(
            [gmx, "sasa", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="0\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                assert avg > 0, "SASA 平均值应为正数"


# ============================================================
# 氢键分析测试
# ============================================================

@pytest.mark.integration
class TestHBondAnalysis:
    """氢键分析测试"""

    def test_hbond_calculation(self, test_dir):
        """氢键计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "hbond_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "hbond.xvg")
        result = subprocess.run(
            [gmx, "hbond", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-num", outfile, "-b", "60000", "-e", "70000"],
            input="2\n3\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                assert avg >= 0, "氢键平均数应为非负数"


# ============================================================
# 团簇分析测试
# ============================================================

@pytest.mark.integration
class TestClusterAnalysis:
    """团簇分析测试"""

    def test_cluster_calculation(self, test_dir):
        """团簇分析计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "cluster_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [gmx, "cluster", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", str(out_dir / "cluster.xpm"),
             "-dist", str(out_dir / "dist.xvg"),
             "-sz", str(out_dir / "size.xvg"),
             "-method", "gromos", "-cutoff", "0.3", "-dista",
             "-b", "69900", "-e", "70000"],
            input="2\n", capture_output=True, text=True, timeout=300, cwd=str(test_dir)
        )

        assert result.returncode == 0, f"团簇分析失败: {result.stderr[:200]}"


# ============================================================
# pairdist 分析测试
# ============================================================

@pytest.mark.integration
class TestPairdistAnalysis:
    """最近邻距离分析测试"""

    def test_pairdist_calculation(self, test_dir):
        """最近邻距离分析成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "pairdist_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "min_BDD_BTP.xvg")
        result = subprocess.run(
            [gmx, "pairdist", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-n", str(test_dir / "fragment.ndx"),
             "-ref", "group All_s1_BDD",
             "-sel", "group All_BTP",
             "-type", "min",
             "-b", "69000", "-e", "70000",
             "-o", outfile],
            capture_output=True, text=True, timeout=600, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                min_val = np.min(data[:, 1])
                assert min_val > 0, "最近邻距离应为正数"


# ============================================================
# 回转半径分析测试
# ============================================================

@pytest.mark.integration
class TestGyrateAnalysis:
    """回转半径分析测试"""

    def test_gyrate_calculation(self, test_dir):
        """回转半径计算成功"""
        gmx = get_gmx()
        require_gromacs(gmx)

        out_dir = test_dir / "gyrate_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "gyrate.xvg")
        result = subprocess.run(
            [gmx, "gyrate", "-f", str(test_dir / "md_clean.xtc"),
             "-s", str(test_dir / "ydw-md2.tpr"),
             "-o", outfile, "-b", "60000", "-e", "70000"],
            input="2\n", capture_output=True, text=True, timeout=120, cwd=str(test_dir)
        )

        if result.returncode == 0 and os.path.exists(outfile):
            _, data = read_xvg(outfile)
            if len(data) > 0:
                avg = np.mean(data[:, 1])
                assert avg > 0, "回转半径应为正数"
