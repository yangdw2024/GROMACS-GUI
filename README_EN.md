# GROMACS-GUI · Integrated Molecular Dynamics & Analysis Workbench

<div align="center">

![Version](https://img.shields.io/badge/version-v4.4.0--rc.1-blue)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-green)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT%20(Pending%20Review)-yellow)

[中文文档](README.md) | [Changelog](CHANGELOG.md) | [Engineering Report](docs/engineering/FINAL_ENGINEERING_REPORT.md)

</div>

---

## Overview

**GROMACS-GUI** is a cross-platform Python/PyQt5 desktop application wrapping GROMACS simulation workflows, trajectory preprocessing, structural analysis, enhanced sampling, and custom automation into a modern, modular scientific workbench.

### Highlights
- **Modern Design System & Dual Layouts**: Left navigation workbench + Classic tabbed layout toggle, high-contrast Slate Dark & Light themes, and live **Chinese / English (`EN` / `中文`) switching** without losing form state or altering generated GROMACS commands.
- **Modular 7-Tab Architecture**: Clean separation between the Application Shell (`source/gui/main_window.py`), 7 standalone tab components (`source/gui/tabs/`), and pure scientific command builders (`source/simulation/`).
- **Scientific Safety Guarantees**:
  - Round-by-round NPT coordinate/velocity inheritance during solvent evaporation (SA), strict cross-round checkpoint (`.cpt`) isolation, and GRO/TOP molecule count conservation checks;
  - Controlled `grompp -maxwarn` upper limits (`DEFAULT_MAXWARN = 2`, `SA_SAFE_MAXWARN = 5`, rejecting unguarded thresholds like `200`);
  - Spatial Z-coordinate sorting modes (`z_top` / `z_bottom`) alongside legacy GRO record-order compatibility (`bottom` / `top`);
  - Post-run structural & log sanity validation (`NaN`/`Inf`, LINCS/SETTLE explosions, without false-flagging normal condensed-phase NPT pressure oscillations).

---

## Quick Start

### Requirements
- **OS**: Windows 10/11 (64-bit) or Linux
- **Python**: 3.11 / 3.12 / 3.13
- **GROMACS**: Separately installed GROMACS 2025.x / 2026.x binary (third-party GROMACS binaries are **not** redistributed inside the package)

### Run from Source
```bash
git clone https://github.com/yangdw2024/GROMACS-GUI.git
cd GROMACS-GUI
pip install -r requirements.txt

# Launch GUI
python source/gromacs_gui_v4.py

# Quick headless smoke check
python source/gromacs_gui_v4.py --smoke-test

# Run full automated test suite
python -m pytest tests/unit -v
```

### Reproducible Windows Portable Build
```bash
pip install pyinstaller
python build_scripts/build_windows_portable.py --smoke-test
```
Produces a clean portable archive under `release/` (`GROMACS-GUI-v<version>-win64-portable.zip` + `SHA256SUMS.txt`) and runs the frozen executable `--smoke-test` automatically. When installed into read-only directories (e.g., `Program Files`), runtime logs and configuration automatically fall back to `%LOCALAPPDATA%\GROMACS-GUI`.

---

## Scientific Scope & Licensing Notice

1. **MMPBSA Module (Experimental Scope)**: Converts physical simulation time (ps) into 1-based frames via explicit trajectory frame spacing (`traj_dt_ps`), parses real `.ndx` group headers (replacing hardcoded `-cg 1 13`), generates `mmpbsa.in`, and checks `gmx_MMPBSA` availability before execution. Using MM/PBSA on non-standard complex systems remains an experimental utility and requires user validation of force-field & dielectric settings.
2. **Licensing Discrepancy Notice**: Root [`LICENSE`](LICENSE) specifies the MIT License, whereas the in-app EULA (`source/gui/app.py`) includes a non-commercial restriction. Formal stable release tagging awaits explicit copyright owner resolution between Option A (pure MIT) and Option B (non-commercial license).

---

## Copyright
Copyright (c) 2026 YangDewu. All rights reserved.
