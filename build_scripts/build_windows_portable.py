#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS-GUI 可复现 Windows 生产打包与校验脚本 (Portable onedir + ZIP + SHA256 + Smoke Test)
合规要求：
- 严格不重新分发任何第三方 GROMACS 二进制程序；
- 自动打包 core, gui (含 tabs/themes/i18n/dialogs/workers), simulation, utils, config, resources, version.config；
- 输出 ZIP 便携包与 SHA256SUMS.txt，并可选执行离线 Smoke Test 验证独立运行稳定性。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_spec_text(app_name: str, icon_path: Path, repo_root: Path) -> str:
    datas = [
        (str(repo_root / "version.config"), "."),
        (str(repo_root / "LICENSE"), "."),
        (str(repo_root / "README.md"), "."),
        (str(repo_root / "source" / "core"), "core"),
        (str(repo_root / "source" / "gui"), "gui"),
        (str(repo_root / "source" / "simulation"), "simulation"),
        (str(repo_root / "source" / "utils"), "utils"),
        (str(repo_root / "source" / "config"), "config"),
        (str(repo_root / "resources"), "resources"),
    ]
    # Filter existing paths
    datas_literal = ",\n        ".join(
        f"({src!r}, {dst!r})" for src, dst in datas if Path(src).exists()
    )
    icon_arg = f"r'{icon_path}'" if icon_path.exists() else "None"

    return f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    [{str(repo_root / 'source' / 'gromacs_gui_v4.py')!r}],
    pathex=[{str(repo_root / 'source')!r}],
    binaries=[],
    datas=[
        {datas_literal}
    ],
    hiddenimports=[
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip',
        'numpy', 'psutil', 'matplotlib', 'matplotlib.pyplot',
        'matplotlib.backends.backend_agg',
        'gui.i18n', 'gui.themes', 'gui.themes.theme_tokens',
        'gui.tabs', 'gui.tabs.md_tab', 'gui.tabs.structure_tab',
        'gui.tabs.advanced_tab', 'gui.tabs.trajectory_tab',
        'gui.tabs.analysis_tab', 'gui.tabs.mmpbsa_tab', 'gui.tabs.script_tab',
        'simulation.md_runner', 'simulation.mdp_builder',
        'simulation.analysis', 'simulation.validation',
    ] + collect_submodules('PyQt5'),
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name={app_name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon={icon_arg},
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name={app_name!r},
)
"""


def main():
    parser = argparse.ArgumentParser(description="Build GROMACS-GUI portable Windows distribution")
    parser.add_argument("--smoke-test", action="store_true", help="Run frozen executable --smoke-test after build")
    parser.add_argument("--out-root", default=None, help="Output base directory (default: repo root)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_root = Path(args.out_root).resolve() if args.out_root else repo_root
    dist_dir = out_root / "dist"
    release_dir = out_root / "release"
    build_tmp = out_root / "build_pyi_tmp"
    icon_path = repo_root / "resources" / "app_icon.ico"

    version_config_path = repo_root / "version.config"
    version = "4.3.0"
    if version_config_path.exists():
        vc = json.loads(version_config_path.read_text(encoding="utf-8"))
        version = vc.get("version_string", version)

    print(f"[Build] GROMACS-GUI v{version} | Python={sys.executable}")

    # 1. Verify PyInstaller & dependencies
    subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True)
    for d in [dist_dir, release_dir, build_tmp]:
        d.mkdir(parents=True, exist_ok=True)

    app_name = f"GROMACS_GUI_v{version}"
    spec_path = build_tmp / f"{app_name}.spec"
    spec_path.write_text(build_spec_text(app_name, icon_path, repo_root), encoding="utf-8")

    # 2. Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", str(dist_dir),
        "--workpath", str(build_tmp / "work"),
        "--log-level=WARN",
        str(spec_path),
    ]
    print("[Build] Running PyInstaller...")
    subprocess.run(cmd, cwd=str(repo_root), check=True)

    bundle_dir = dist_dir / app_name
    exe_path = bundle_dir / f"{app_name}.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected built executable missing: {exe_path}")

    # Copy readable top-level docs
    for doc_name in ["README.md", "LICENSE", "version.config", "说明书.md"]:
        src = repo_root / doc_name
        if src.exists():
            shutil.copy2(src, bundle_dir / doc_name)

    # 3. Smoke test frozen binary in isolated directory
    if args.smoke_test:
        print(f"[Smoke] Running frozen executable smoke test: {exe_path} --smoke-test")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(
            [str(exe_path), "--smoke-test"],
            cwd=str(bundle_dir),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )
        out_s = res.stdout or ""
        err_s = res.stderr or ""
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        print("  Stdout:", out_s.encode("ascii", errors="replace").decode("ascii").strip())
        if err_s.strip():
            print("  Stderr:", err_s.encode("ascii", errors="replace").decode("ascii").strip()[:500])
        if res.returncode != 0 or "SMOKE_TEST_OK" not in out_s:
            raise RuntimeError(f"Frozen smoke test failed (rc={res.returncode})")
        print("[Smoke] Frozen binary verified OK!")
        # Clean runtime artifacts produced during smoke test so distributed zip is pristine
        for art in ["gromacs_gui.log", "gromacs_gui.lock", "gromacs_gui_config.json"]:
            p = bundle_dir / art
            if p.exists():
                p.unlink()
        for d in ["logs"]:
            dp = bundle_dir / d
            if dp.exists():
                shutil.rmtree(dp, ignore_errors=True)

    # 4. Create Portable ZIP + SHA256SUMS.txt
    zip_name = f"GROMACS-GUI-v{version}-win64-portable.zip"
    zip_path = release_dir / zip_name
    if zip_path.exists():
        zip_path.unlink()

    print(f"[Package] Creating portable archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_item in sorted(bundle_dir.rglob("*")):
            if file_item.is_file():
                rel = file_item.relative_to(dist_dir)
                zf.write(file_item, arcname=str(rel))

    sha256 = compute_sha256(zip_path)
    sha_file = release_dir / "SHA256SUMS.txt"
    sha_file.write_text(f"{sha256}  {zip_name}\n", encoding="utf-8")
    print(f"[Package] Done! Size={zip_path.stat().st_size / 1024 / 1024:.1f} MB | SHA256={sha256}")

    # Cleanup work dir
    shutil.rmtree(build_tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
