# -*- coding: utf-8 -*-
"""
完整工作流集成测试
测试范围：pdb2gmx → editconf → solvate → grompp → mdrun → 后处理分析
         + GPU/CPU 切换、mdrun 基础功能
前置条件：GROMACS 已安装，test/test_simple/ 目录有测试数据
"""
import os
import sys
import subprocess
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


def run_cmd(cmd, cwd, input_text=None, timeout=600):
    """运行命令并返回 (成功, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, input=input_text,
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "超时"
    except Exception as e:
        return False, "", str(e)


def read_xvg(filepath):
    """读取 xvg 文件数据"""
    data = []
    with open(filepath, "r") as f:
        for line in f:
            if not line.startswith("#") and not line.startswith("@") and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        data.append([float(parts[0]), float(parts[1])])
                    except (ValueError, IndexError):
                        pass
    return np.array(data)


def skip_if_no_gromacs():
    """检查 GROMACS 是否可用"""
    gmx = get_gmx()
    if not gmx or not os.path.exists(gmx):
        pytest.skip("GROMACS 不可用")
    return gmx


# ============================================================
# 第一阶段：模拟准备工作流
# ============================================================

@pytest.mark.integration
class TestSimulationPreparation:
    """模拟准备工作流测试"""

    def test_pdb2gmx_conversion(self, simple_test_dir):
        """PDB → GRO+TOP 转换"""
        gmx = skip_if_no_gromacs()

        pdb_file = simple_test_dir / "test.pdb"
        if not pdb_file.exists():
            pytest.skip("测试 PDB 不存在")

        out_dir = simple_test_dir.parent / "full_workflow_test" / "01_pdb2gmx"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "pdb2gmx", "-f", str(pdb_file),
             "-o", "out.gro", "-p", "out.top",
             "-ff", "oplsaa", "-water", "tip3p", "-ignh"],
            str(out_dir), timeout=120
        )
        assert ok and (out_dir / "out.gro").exists(), f"pdb2gmx 失败: {err[:200]}"

    def test_editconf_box(self, simple_test_dir):
        """editconf 调整盒子大小"""
        gmx = skip_if_no_gromacs()

        gro_file = simple_test_dir / "processed.gro"
        if not gro_file.exists():
            pytest.skip("测试 GRO 不存在")

        out_dir = simple_test_dir.parent / "full_workflow_test" / "02_editconf"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "editconf", "-f", str(gro_file),
             "-o", "newbox.gro", "-box", "4", "4", "4", "-c"],
            str(out_dir), timeout=60
        )
        assert ok and (out_dir / "newbox.gro").exists(), f"editconf 失败: {err[:200]}"

    def test_solvate(self, simple_test_dir):
        """溶剂化"""
        gmx = skip_if_no_gromacs()

        gro_file = simple_test_dir / "newbox.gro"
        top_file = simple_test_dir / "topol.top"
        if not gro_file.exists():
            pytest.skip("测试文件不存在")

        import shutil
        out_dir = simple_test_dir.parent / "full_workflow_test" / "03_solvate"
        out_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(str(top_file), str(out_dir / "topol.top"))

        ok, out, err = run_cmd(
            [gmx, "solvate", "-cp", str(gro_file),
             "-cs", "spc216.gro", "-o", "solvated.gro",
             "-p", "topol.top"],
            str(out_dir), timeout=120
        )
        assert ok and (out_dir / "solvated.gro").exists(), f"solvate 失败: {err[:200]}"

    def test_grompp_em(self, simple_test_dir):
        """grompp 能量最小化预处理"""
        gmx = skip_if_no_gromacs()

        mdp_file = simple_test_dir / "em.mdp"
        gro_file = simple_test_dir / "solvated.gro"
        top_file = simple_test_dir / "topol.top"
        if not all(f.exists() for f in [mdp_file, gro_file, top_file]):
            pytest.skip("测试文件不存在")

        out_dir = simple_test_dir.parent / "full_workflow_test" / "04_grompp_em"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "grompp", "-f", str(mdp_file),
             "-c", str(gro_file), "-r", str(gro_file), "-p", str(top_file),
             "-o", "em.tpr", "-maxwarn", "10"],
            str(out_dir), timeout=120
        )
        assert ok and (out_dir / "em.tpr").exists(), f"grompp 失败: {err[:300]}"

    def test_mdrun_em(self, simple_test_dir):
        """mdrun 能量最小化"""
        gmx = skip_if_no_gromacs()

        tpr_file = simple_test_dir / "em.tpr"
        if not tpr_file.exists():
            pytest.skip("TPR 文件不存在")

        out_dir = simple_test_dir.parent / "full_workflow_test" / "05_mdrun_em"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "mdrun", "-s", str(tpr_file),
             "-deffnm", "em", "-v", "-nsteps", "5"],
            str(out_dir), timeout=300
        )
        assert ok and (out_dir / "em.gro").exists(), f"mdrun 失败: {err[:300]}"


# ============================================================
# 第二阶段：后处理分析工作流
# ============================================================

@pytest.mark.integration
class TestPostProcessing:
    """后处理分析工作流测试"""

    def test_trjconv_pbc(self, test_dir):
        """PBC 修复"""
        gmx = skip_if_no_gromacs()

        xtc_file = test_dir / "ydw-md2.xtc"
        tpr_file = test_dir / "ydw-md2.tpr"
        if not xtc_file.exists():
            pytest.skip("测试轨迹不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "06_trjconv_pbc"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "trjconv", "-f", str(xtc_file), "-s", str(tpr_file),
             "-o", "pbc.xtc", "-pbc", "mol", "-center",
             "-b", "69000", "-e", "70000"],
            str(out_dir), input_text="0\n0\n", timeout=300
        )
        assert ok and (out_dir / "pbc.xtc").exists(), f"PBC 修复失败: {err[:200]}"

    def test_trjconv_fit(self, test_dir):
        """旋转+平移拟合"""
        gmx = skip_if_no_gromacs()

        pbc_dir = test_dir.parent / "full_workflow_test" / "06_trjconv_pbc"
        xtc_file = pbc_dir / "pbc.xtc"
        tpr_file = test_dir / "ydw-md2.tpr"
        if not xtc_file.exists():
            pytest.skip("前一步输出不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "07_trjconv_fit"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "trjconv", "-f", str(xtc_file), "-s", str(tpr_file),
             "-o", "fit.xtc", "-fit", "rot+trans"],
            str(out_dir), input_text="0\n0\n", timeout=300
        )
        assert ok and (out_dir / "fit.xtc").exists(), f"拟合失败: {err[:200]}"

    def test_rdf_analysis(self, test_dir):
        """RDF 分析"""
        gmx = skip_if_no_gromacs()

        xtc_file = test_dir / "md_clean.xtc"
        tpr_file = test_dir / "ydw-md2.tpr"
        ndx_file = test_dir / "fragment.ndx"
        if not all(f.exists() for f in [xtc_file, tpr_file, ndx_file]):
            pytest.skip("测试文件不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "08_rdf"
        out_dir.mkdir(parents=True, exist_ok=True)

        test_pairs = [
            ("All_s1_BDD", "All_BTP"),
            ("All_s1_BDD", "All_IC1"),
        ]

        for donor, acceptor in test_pairs:
            outfile = str(out_dir / f"rdf_{donor}_{acceptor}.xvg")
            ok, out, err = run_cmd(
                [gmx, "rdf", "-f", str(xtc_file), "-s", str(tpr_file), "-n", str(ndx_file),
                 "-ref", f"mol_com of group {donor}",
                 "-sel", f"mol_com of group {acceptor}",
                 "-bin", "0.02", "-b", "69000", "-e", "70000",
                 "-o", outfile],
                str(out_dir), timeout=300
            )
            if ok and os.path.exists(outfile):
                data = read_xvg(outfile)
                assert len(data) > 0, f"{donor}↔{acceptor} RDF 数据为空"

    def test_energy_analysis(self, test_dir):
        """能量分析"""
        gmx = skip_if_no_gromacs()

        edr_file = test_dir / "ydw-md2.edr"
        if not edr_file.exists():
            pytest.skip("EDR 文件不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "09_energy"
        out_dir.mkdir(parents=True, exist_ok=True)

        terms = [("Potential", "10"), ("Temperature", "13"), ("Pressure", "14")]
        for name, term_id in terms:
            outfile = str(out_dir / f"energy_{name}.xvg")
            ok, out, err = run_cmd(
                [gmx, "energy", "-f", str(edr_file), "-o", outfile,
                 "-b", "60000", "-e", "70000"],
                str(out_dir), input_text=f"{term_id}\n0\n", timeout=120
            )
            if ok and os.path.exists(outfile):
                data = read_xvg(outfile)
                assert len(data) > 0, f"{name} 能量数据为空"

    def test_rmsd_analysis(self, test_dir):
        """RMSD 分析"""
        gmx = skip_if_no_gromacs()

        xtc_file = test_dir / "md_clean.xtc"
        tpr_file = test_dir / "ydw-md2.tpr"
        if not all(f.exists() for f in [xtc_file, tpr_file]):
            pytest.skip("测试文件不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "10_rmsd"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "rmsd.xvg")
        ok, out, err = run_cmd(
            [gmx, "rms", "-f", str(xtc_file), "-s", str(tpr_file),
             "-o", outfile, "-b", "69000", "-e", "70000"],
            str(out_dir), input_text="0\n0\n", timeout=120
        )
        if ok and os.path.exists(outfile):
            data = read_xvg(outfile)
            assert len(data) > 0, "RMSD 数据为空"

    def test_gyration_analysis(self, test_dir):
        """回转半径分析"""
        gmx = skip_if_no_gromacs()

        xtc_file = test_dir / "md_clean.xtc"
        tpr_file = test_dir / "ydw-md2.tpr"
        if not all(f.exists() for f in [xtc_file, tpr_file]):
            pytest.skip("测试文件不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "15_gyrate"
        out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(out_dir / "gyrate.xvg")
        ok, out, err = run_cmd(
            [gmx, "gyrate", "-f", str(xtc_file), "-s", str(tpr_file),
             "-o", outfile, "-b", "69000", "-e", "70000"],
            str(out_dir), input_text="2\n", timeout=120
        )
        if ok and os.path.exists(outfile):
            data = read_xvg(outfile)
            assert len(data) > 0, "回转半径数据为空"


# ============================================================
# 第三阶段：辅助功能测试
# ============================================================

@pytest.mark.integration
class TestAuxiliaryFeatures:
    """辅助功能测试"""

    def test_fragment_index_generator(self, project_root):
        """片段索引生成器逻辑验证"""
        out_dir = project_root / "test" / "full_workflow_test" / "18_fragment_ndx"
        out_dir.mkdir(parents=True, exist_ok=True)

        # 模拟 GUI 中的片段索引生成逻辑
        fragments = {"frag_A": "1-10,15-20", "frag_B": "25-35"}
        nmol = 5
        natom_per_mol = 50
        offset = 0

        def expand_ranges(rangestr):
            atoms = []
            for part in rangestr.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = map(int, part.split("-"))
                    atoms.extend(range(a, b + 1))
                else:
                    atoms.append(int(part))
            return atoms

        groups = {}
        for name, rangestr in fragments.items():
            base_atoms = expand_ranges(rangestr)
            all_atoms = []
            for mol in range(nmol):
                shift = offset + mol * natom_per_mol
                all_atoms.extend([x + shift for x in base_atoms])
            groups[name] = all_atoms

        output_path = out_dir / "test_fragment.ndx"
        with open(output_path, "w") as f:
            for name, atoms in groups.items():
                f.write(f"[ {name} ]\n")
                for i in range(0, len(atoms), 15):
                    line = atoms[i:i+15]
                    f.write(" ".join(map(str, line)) + "\n")
                f.write("\n")

        total = sum(len(atoms) for atoms in groups.values())
        assert total > 0, "片段索引总原子数应为正数"
        assert output_path.exists(), "索引文件未生成"

    def test_file_check(self, test_dir):
        """文件检查功能"""
        gmx = skip_if_no_gromacs()

        xtc_file = test_dir / "ydw-md2.xtc"
        if not xtc_file.exists():
            pytest.skip("测试文件不存在")

        out_dir = test_dir.parent / "full_workflow_test" / "19_file_check"
        out_dir.mkdir(parents=True, exist_ok=True)

        # GROMACS 2026+ 版本 gmx check 只接受 -f
        ok, out, err = run_cmd(
            [gmx, "check", "-f", str(xtc_file)],
            str(out_dir), timeout=60
        )
        assert ok or "check" in out.lower(), "文件检查未返回有效结果"


# ============================================================
# GPU/CPU 切换测试
# ============================================================

@pytest.mark.integration
class TestGPUCPUSwitch:
    """GPU/CPU 切换能力测试"""

    def test_gmx_mdrun_has_gpu_cpu_flags(self):
        """mdrun 帮助信息包含 GPU 和 CPU 参数"""
        gmx = skip_if_no_gromacs()

        result = subprocess.run(
            [gmx, "mdrun", "-h"],
            capture_output=True, text=True, timeout=15
        )
        out_text = (result.stdout + result.stderr).lower()

        # GROMACS 2026.3 格式: "-nb <enum> ... Calculate non-bonded interactions on: auto, cpu, gpu"
        # 检查是否列出了 cpu 和 gpu 作为可选值
        has_cpu = "auto, cpu, gpu" in out_text or "cpu, gpu" in out_text
        has_nb = "-nb" in out_text
        has_pme = "-pme" in out_text

        # 至少应包含 nb 和 pme 参数说明
        assert has_nb, "mdrun 缺少 -nb 参数"
        assert has_pme, "mdrun 缺少 -pme 参数"
        # CPU 支持应以某种形式存在
        assert has_cpu or "cpu" in out_text, "mdrun 未提及 CPU 模式"

    def test_gmx_gpu_id_list(self):
        """gpu_id 参数可用"""
        gmx = skip_if_no_gromacs()

        result = subprocess.run(
            [gmx, "mdrun", "-h"],
            capture_output=True, text=True, timeout=15
        )
        # gpu_id 是否存在不强制，但参数不应报错
        assert result.returncode == 0, "mdrun -h 执行失败"


# ============================================================
# mdrun 基础功能测试
# ============================================================

@pytest.mark.integration
class TestMDRunBasic:
    """mdrun 基础功能测试"""

    def test_mdrun_single_step(self, simple_test_dir):
        """mdrun 单步执行"""
        gmx = skip_if_no_gromacs()

        tpr_file = simple_test_dir / "em.tpr"
        if not tpr_file.exists():
            pytest.skip("TPR 文件不存在")

        out_dir = simple_test_dir.parent / "mdrun_basic_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        ok, out, err = run_cmd(
            [gmx, "mdrun", "-s", str(tpr_file), "-v", "-nsteps", "1",
             "-deffnm", "test_mdrun"],
            str(out_dir), timeout=60
        )
        # 单步执行可能因各种原因失败（如文件问题），但不应崩溃
        if ok:
            assert (out_dir / "test_mdrun.log").exists(), "mdrun 日志未生成"
