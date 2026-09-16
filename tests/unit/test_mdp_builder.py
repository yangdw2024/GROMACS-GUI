#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""simulation/mdp_builder 单元测试"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "source"))

from simulation.mdp_builder import (
    build_ions_mdp, build_em_mdp, build_nvt_mdp, build_npt_mdp, build_md_mdp,
    build_simple_mdp,
    build_full_ions_mdp, build_full_em_mdp, build_full_nvt_mdp, build_full_npt_mdp,
    build_full_md_mdp, build_full_sa_mdp, build_full_annealing_mdp, build_full_mdp,
    build_umbrella_mdp_files, build_plumed_metad, build_plumed_abf,
)


class TestSimpleMdp(unittest.TestCase):
    """简化模板（generate_mdp_template 路径）"""

    def test_ions(self):
        s = build_ions_mdp()
        self.assertIn("integrator  = steep", s)
        self.assertIn("nsteps       = 1000", s)
        self.assertIn("pbc          = xyz", s)

    def test_em(self):
        s = build_em_mdp()
        self.assertIn("emtol       = 1000.0", s)
        self.assertIn("nsteps      = 50000", s)

    def test_nvt_interp(self):
        s = build_nvt_mdp(0.002, 300.0)
        self.assertIn("dt          = 0.002", s)
        self.assertIn("ref_t       = 300.0 300.0", s)

    def test_npt_interp(self):
        s = build_npt_mdp(0.002, 310.0, 1.5)
        self.assertIn("ref_t       = 310.0 310.0", s)
        self.assertIn("ref_p       = 1.5", s)

    def test_md_interp(self):
        s = build_md_mdp(0.002, 500000, 300.0, 1.0)
        self.assertIn("nsteps      = 500000", s)
        self.assertIn("ref_t       = 300.0 300.0", s)

    def test_simple_dispatch_unknown(self):
        """未知 mdp_type 返回空串（与原字典 .get 行为一致）"""
        self.assertEqual(build_simple_mdp("unknown"), "")


class TestFullMdp(unittest.TestCase):
    """完整模板（_get_full_mdp_template 路径）"""

    def test_ions_full(self):
        s = build_full_ions_mdp()
        self.assertIn("cutoff-scheme = Verlet", s)
        self.assertIn("pme_order     = 4", s)
        self.assertIn("DispCorr      = EnerPres", s)

    def test_em_full(self):
        s = build_full_em_mdp()
        self.assertIn("nstenergy     = 1000", s)
        self.assertIn("nstlog        = 1000", s)

    def test_nvt_full_interp(self):
        s = build_full_nvt_mdp(0.002, 300.0)
        self.assertIn("dt            = 0.002", s)
        self.assertIn("ref_t         = 300.0", s)
        self.assertIn("gen_temp      = 300.0", s)
        self.assertIn("lincs_order   = 4", s)

    def test_npt_full_interp(self):
        s = build_full_npt_mdp(0.002, 310.0, 1.5)
        self.assertIn("ref_t         = 310.0", s)
        self.assertIn("ref_p         = 1.5", s)
        self.assertIn("pcoupl        = C-rescale", s)

    def test_md_full_interp(self):
        s = build_full_md_mdp(0.002, 1000000, 300.0, 1.0)
        self.assertIn("nsteps        = 1000000", s)
        self.assertIn("pcoupl        = Parrinello-Rahman", s)
        self.assertIn("energygrps    = System", s)

    def test_sa_full(self):
        s = build_full_sa_mdp()
        self.assertIn("ewald-rtol    = 1e-5", s)
        self.assertIn("nstxtcout     = 1000", s)

    def test_annealing_full(self):
        s = build_full_annealing_mdp()
        self.assertIn("annealing     = single", s)
        self.assertIn("annealing_npoints = 7", s)
        self.assertIn("annealing_temp = 300 373 373 373 373 300 300", s)
        self.assertIn("nstenergy     = 10000", s)

    def test_full_dispatch_unknown(self):
        self.assertEqual(build_full_mdp("unknown"), "")


class TestUmbrellaMdp(unittest.TestCase):
    """伞形采样模板"""

    def test_three_windows(self):
        files = build_umbrella_mdp_files(
            "umbrella", "Protein", "Lig", 1000.0, 0.0, 1.0, 3
        )
        self.assertEqual(len(files), 3)
        for i, (fname, content) in enumerate(files):
            self.assertEqual(fname, f"umbrella_{i}.mdp")
        # 检查位置插值
        self.assertIn("pull_coord1_init = 0.0", files[0][1])
        self.assertIn("pull_coord1_init = 0.5", files[1][1])
        self.assertIn("pull_coord1_init = 1.0", files[2][1])
        # 检查 group/coord 插值
        self.assertIn("pull_group0 = Protein", files[0][1])
        self.assertIn("pull_group1 = Lig", files[0][1])
        self.assertIn("pull_coord1_type = umbrella", files[0][1])
        self.assertIn("pull_coord1_k = 1000.0", files[0][1])

    def test_one_window_no_delta(self):
        files = build_umbrella_mdp_files("d", "A", "B", 500.0, 0.0, 0.0, 1)
        self.assertEqual(len(files), 1)
        # delta=0 不会触发除零
        self.assertIn("pull_coord1_init = 0.0", files[0][1])

    def test_zero_windows(self):
        self.assertEqual(build_umbrella_mdp_files("d", "A", "B", 1.0, 0.0, 1.0, 0), [])


class TestPlumed(unittest.TestCase):
    """PLUMED 元动力学 / ABF"""

    def test_metad(self):
        s = build_plumed_metad(10.0, 1.2, 0.3)
        self.assertIn("METAD ARG=d1 SIGMA=0.3 HEIGHT=1.2 BIASFACTOR=10.0 TEMP=300", s)
        self.assertIn("PRINT ARG=d1 FILE=COLVAR STRIDE=100", s)

    def test_abf(self):
        s = build_plumed_abf(-1.0, 5.0, 50)
        self.assertIn("ABF ARG=d1 MIN=-1.0 MAX=5.0 NBINS=50", s)
        self.assertIn("PRINT ARG=d1 FILE=COLVAR STRIDE=100", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
