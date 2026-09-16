#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MDP / PLUMED 文件内容生成器

所有函数均为纯函数（无 Qt / 文件 I/O 依赖），输入参数、返回字符串或文件清单。
由 gui/main_window.py 中的生成方法调用，零逻辑改动搬运自原 GromacsGUI 类。
"""

from typing import List, Tuple


# =============================================================================
# 简化模板（generate_mdp_template，5 种）
# =============================================================================

def build_ions_mdp() -> str:
    """离子化能量最小化（简化模板）"""
    return """; ions.mdp
integrator  = steep
nsteps       = 1000
coulombtype  = PME
rcoulomb     = 1.0
rvdw         = 1.0
pbc          = xyz
"""


def build_em_mdp() -> str:
    """能量最小化（简化模板）"""
    return """; em.mdp
integrator  = steep
emtol       = 1000.0
emstep      = 0.01
nsteps      = 50000
nstlist     = 1
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
"""


def build_nvt_mdp(dt: float, temp: float) -> str:
    """NVT 平衡（简化模板）"""
    return f"""; nvt.mdp
define      = -DPOSRES
integrator  = md
dt          = {dt}
nsteps      = {int(1000/dt*1000)}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
continuation = no
"""


def build_npt_mdp(dt: float, temp: float, press: float) -> str:
    """NPT 平衡（简化模板）"""
    return f"""; npt.mdp
define      = -DPOSRES
integrator  = md
dt          = {dt}
nsteps      = {int(1000/dt*1000)}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = {press}
compressibility = 4.5e-5
continuation = yes
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
"""


def build_md_mdp(dt: float, nsteps: int, temp: float, press: float) -> str:
    """生产模拟（简化模板）"""
    return f"""; md.mdp
integrator  = md
dt          = {dt}
nsteps      = {nsteps}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = {press}
compressibility = 4.5e-5
continuation = yes
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
"""


def build_simple_mdp(mdp_type: str, dt: float = 0.002, nsteps: int = 50000,
                     temp: float = 300.0, press: float = 1.0) -> str:
    """简化模板统一入口（对应原 generate_mdp_template 的 templates 字典）

    mdp_type: ions | em | nvt | npt | md
    """
    if mdp_type == "ions":
        return build_ions_mdp()
    if mdp_type == "em":
        return build_em_mdp()
    if mdp_type == "nvt":
        return build_nvt_mdp(dt, temp)
    if mdp_type == "npt":
        return build_npt_mdp(dt, temp, press)
    if mdp_type == "md":
        return build_md_mdp(dt, nsteps, temp, press)
    return ""


# =============================================================================
# 完整模板（_get_full_mdp_template，7 种）
# =============================================================================

def build_full_ions_mdp() -> str:
    """离子位置限制能量最小化（完整模板）"""
    return """; ions.mdp - 离子位置限制能量最小化
integrator    = steep
nsteps        = 1000
emtol         = 1000.0
emstep        = 0.01

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

constraints   = none
"""


def build_full_em_mdp() -> str:
    """能量最小化（完整模板）"""
    return """; em.mdp - 能量最小化
integrator    = steep
emtol         = 1000.0
emstep        = 0.01
nsteps        = 50000

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

nstenergy     = 1000
nstlog        = 1000
constraints   = none
"""


def build_full_nvt_mdp(dt: float, temp: float) -> str:
    """NVT 平衡（完整模板）"""
    return f"""; nvt.mdp - 恒温恒容平衡
define        = -DPOSRES
integrator    = md
dt            = {dt}
nsteps        = {int(50000/dt*1000)}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

gen_vel       = yes
gen_temp      = {temp}
gen_seed      = -1

constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = no

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 5000
xtc-precision = 1000
"""


def build_full_npt_mdp(dt: float, temp: float, press: float) -> str:
    """NPT 平衡（完整模板）"""
    return f"""; npt.mdp - 恒温恒压平衡
define        = -DPOSRES
integrator    = md
dt            = {dt}
nsteps        = {int(100000/dt*1000)}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

pcoupl        = C-rescale
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = {press}
compressibility = 4.5e-5
refcoord_scaling = com

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 5000
xtc-precision = 1000
"""


def build_full_md_mdp(dt: float, nsteps: int, temp: float, press: float) -> str:
    """生产模拟（完整模板）"""
    return f"""; md.mdp - 生产模拟
integrator    = md
dt            = {dt}
nsteps        = {nsteps}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = {press}
compressibility = 4.5e-5
refcoord_scaling = com

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 5000
nstlog        = 5000
nstcheckpoint = 50000
nstxtcout     = 10000
xtc-precision = 1000

energygrps    = System
"""


def build_full_sa_mdp() -> str:
    """SA 溶剂蒸发（完整模板）"""
    return """; sa.mdp - SA溶剂蒸发
integrator    = md
dt            = 0.002
nsteps        = 50000
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 100
ns-type       = grid
rlist         = 1.5
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.5
pme_order     = 4
fourierspacing = 0.12
ewald-rtol    = 1e-5

vdw-type      = cut-off
rvdw          = 1.5
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.5
ref_t         = 300

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 1.0
ref_p         = 1.0
compressibility = 4.5e-5

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 1000
xtc-precision = 1000

energygrps    = System
"""


def build_full_annealing_mdp() -> str:
    """模拟退火（完整模板）"""
    return """; annealing.mdp - 模拟退火
integrator    = md
dt            = 0.002
nsteps        = 500000
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 100
ns-type       = grid
rlist         = 1.5
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.5
pme_order     = 4
fourierspacing = 0.12
ewald-rtol    = 1e-5

vdw-type      = cut-off
rvdw          = 1.5
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.5
ref_t         = 300

annealing     = single
annealing_npoints = 7
annealing_time = 0 100 300 500 700 900 1000
annealing_temp = 300 373 373 373 373 300 300

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 1.0
ref_p         = 1.0
compressibility = 4.5e-5

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 10000
nstlog        = 10000
nstcheckpoint = 10000
nstxtcout     = 10000
xtc-precision = 1000

energygrps    = System
"""


def build_full_mdp(mdp_type: str, dt: float = 0.002, nsteps: int = 50000,
                   temp: float = 300.0, press: float = 1.0) -> str:
    """完整模板统一入口（对应原 _get_full_mdp_template 的 templates 字典）

    mdp_type: ions | em | nvt | npt | md | sa | annealing
    """
    if mdp_type == "ions":
        return build_full_ions_mdp()
    if mdp_type == "em":
        return build_full_em_mdp()
    if mdp_type == "nvt":
        return build_full_nvt_mdp(dt, temp)
    if mdp_type == "npt":
        return build_full_npt_mdp(dt, temp, press)
    if mdp_type == "md":
        return build_full_md_mdp(dt, nsteps, temp, press)
    if mdp_type == "sa":
        return build_full_sa_mdp()
    if mdp_type == "annealing":
        return build_full_annealing_mdp()
    return ""


# =============================================================================
# 高级采样模板
# =============================================================================

def build_umbrella_mdp_files(coord: str, group1: str, group2: str,
                             force: float, start: float, end: float,
                             nwindows: int) -> List[Tuple[str, str]]:
    """生成 N 个伞形采样窗口的 MDP 文件

    返回 [(filename, content), ...]，nwindows=0 时返回空列表。
    """
    if nwindows <= 0:
        return []
    if nwindows == 1:
        delta = 0.0
    else:
        delta = (end - start) / (nwindows - 1)

    files = []
    for i in range(nwindows):
        pos = start + i * delta
        content = f"""; umbrella_{i}.mdp
integrator  = md
dt          = 0.002
nsteps      = 500000
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
continuation = yes

pull = yes
pull_ngroups = 1
pull_ncoords = 1
pull_group0 = {group1}
pull_group1 = {group2}
pull_coord1_type = {coord}
pull_coord1_geometry = distance
pull_coord1_groups = 0 1
pull_coord1_k = {force}
pull_coord1_init = {pos}
pull_coord1_rate = 0
pull_coord1_target = {pos}
pull_coord1_print_com = yes

nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
nstxout-compressed = 5000
"""
        files.append((f"umbrella_{i}.mdp", content))
    return files


def build_plumed_metad(biasfactor: float, height: float, sigma: float) -> str:
    """PLUMED 元动力学输入文件"""
    return f"""# Metadynamics with PLUMED
d1: DISTANCE ATOMS=1,100

METAD ARG=d1 SIGMA={sigma} HEIGHT={height} BIASFACTOR={biasfactor} TEMP=300
PRINT ARG=d1 FILE=COLVAR STRIDE=100
"""


def build_plumed_abf(min_val: float, max_val: float, nbins: int) -> str:
    """PLUMED ABF 输入文件"""
    return f"""# ABF with PLUMED
d1: DISTANCE ATOMS=1,100

ABF ARG=d1 MIN={min_val} MAX={max_val} NBINS={nbins}
PRINT ARG=d1 FILE=COLVAR STRIDE=100
"""
