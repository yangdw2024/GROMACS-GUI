#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
溶剂删除脚本 (examples/FClFCl/SA/Process/delete_solvent.py & examples/ClFFCl/delete_solvent.py)
单元测试与回归测试
"""

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import uuid
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FCLFCL_SCRIPT = REPO_ROOT / "examples" / "FClFCl" / "SA" / "Process" / "delete_solvent.py"
CLFFCL_SCRIPT = REPO_ROOT / "examples" / "ClFFCl" / "delete_solvent.py"


@pytest.fixture
def tmp_path():
    base = pathlib.Path(tempfile.gettempdir()) / "ds_unit_tmp" / uuid.uuid4().hex
    os.makedirs(base, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _format_gro_line(resnr: int, resname: str, atomname: str, atomnr: int, x: float, y: float, z: float) -> str:
    return f"{resnr:5d}{resname:<5s}{atomname:>5s}{atomnr:5d}{x:8.3f}{y:8.3f}{z:8.3f}\n"


def _write_synthetic_system(
    gro_path: pathlib.Path,
    top_path: pathlib.Path,
    cf_mols: int = 10,
    atoms_per_cf: int = 5,
    top_cf_count: int = None,
):
    if top_cf_count is None:
        top_cf_count = cf_mols
    lines = ["Synthetic Mix\n"]
    atom_lines = []
    idx = 1
    # 2 non-solvent atoms before CF
    atom_lines.append(_format_gro_line(1, "DON", "C1", idx, 1.0, 1.0, 1.0))
    idx += 1
    atom_lines.append(_format_gro_line(1, "DON", "C2", idx, 1.1, 1.0, 1.0))
    idx += 1
    # CF molecules
    for m in range(cf_mols):
        resnr = 10 + m
        for a in range(atoms_per_cf):
            atom_lines.append(
                _format_gro_line(resnr, "CF", f"X{a+1}", idx, float(m), float(a), 2.5)
            )
            idx += 1
    # 2 non-solvent atoms after CF
    atom_lines.append(_format_gro_line(999, "DIO", "I1", idx, 9.0, 9.0, 9.0))
    idx += 1
    atom_lines.append(_format_gro_line(999, "DIO", "I2", idx, 9.1, 9.0, 9.0))

    lines.append(f"{len(atom_lines)}\n")
    lines.extend(atom_lines)
    lines.append("  10.00000  10.00000  10.00000\n")
    gro_path.write_text("".join(lines), encoding="utf-8")

    top_text = (
        "[ defaults ]\n"
        "1 2 yes 0.5 0.8333\n\n"
        "[ molecules ]\n"
        "DON     1   ; 给体\n"
        f"CF     {top_cf_count} ; 溶剂数量\n"
        "DIO     1   ; 添加剂\n"
    )
    top_path.write_text(top_text, encoding="utf-8")


def _legacy_delete_and_update(gro_text: str, top_text: str, solvent: str, delete_num: int, atoms_per_solvent: int):
    """参考旧版核心逻辑（仅用于合法输入的字节级等价性对照）"""
    lines = gro_text.splitlines(keepends=True)
    header = lines[0]
    atoms = lines[2:-1]
    box = lines[-1]
    kept = []
    current_mol = []
    deleted_count = 0
    for line in atoms:
        resname = line[5:10].strip()
        if resname != solvent:
            if current_mol:
                kept.extend(current_mol)
                current_mol = []
            kept.append(line)
            continue
        current_mol.append(line)
        if len(current_mol) == atoms_per_solvent:
            if deleted_count < delete_num:
                deleted_count += 1
            else:
                kept.extend(current_mol)
            current_mol = []
    if current_mol:
        kept.extend(current_mol)
    out_gro = header + f"{len(kept)}\n" + "".join(kept) + box

    top_lines = top_text.splitlines(keepends=True)
    out_top_lines = []
    in_molecules = False
    for line in top_lines:
        if "[ molecules ]" in line:
            in_molecules = True
            out_top_lines.append(line)
            continue
        if in_molecules and line.strip() and not line.startswith(";"):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == solvent:
                new_cnt = int(parts[1]) - delete_num
                out_top_lines.append(f"{solvent}\t\t{new_cnt}\n")
            else:
                out_top_lines.append(line)
        else:
            out_top_lines.append(line)
    return out_gro, "".join(out_top_lines)


def test_two_scripts_are_byte_identical():
    assert FCLFCL_SCRIPT.read_bytes() == CLFFCL_SCRIPT.read_bytes()


@pytest.mark.parametrize("script_path", [FCLFCL_SCRIPT, CLFFCL_SCRIPT])
@pytest.mark.parametrize("delete_num", [0, 1, 4, 10])
def test_normal_input_byte_equivalence_and_order(tmp_path, script_path, delete_num):
    mod = _load_module(script_path, f"ds_{delete_num}")
    in_gro = tmp_path / "in.gro"
    in_top = tmp_path / "in.top"
    out_gro = tmp_path / "out.gro"
    out_top = tmp_path / "out.top"
    _write_synthetic_system(in_gro, in_top, cf_mols=10, atoms_per_cf=5)

    orig_gro_text = in_gro.read_text(encoding="utf-8")
    orig_top_text = in_top.read_text(encoding="utf-8")
    exp_gro, exp_top = _legacy_delete_and_update(orig_gro_text, orig_top_text, "CF", delete_num, 5)

    new_num = mod.delete_solvent_molecules(str(in_gro), str(out_gro), "CF", delete_num, 5)
    mod.update_topology(str(in_top), str(out_top), "CF", delete_num)

    assert new_num == 4 + (10 - delete_num) * 5
    assert out_gro.read_text(encoding="utf-8") == exp_gro
    assert out_top.read_text(encoding="utf-8") == exp_top

    # 验证删除顺序：保留的第一个 CF 分子应当是 resnr = 10 + delete_num
    if delete_num < 10:
        kept_lines = out_gro.read_text(encoding="utf-8").splitlines()[2:-1]
        cf_lines = [l for l in kept_lines if l[5:10].strip() == "CF"]
        assert int(cf_lines[0][:5].strip()) == 10 + delete_num


@pytest.mark.parametrize("script_path", [FCLFCL_SCRIPT, CLFFCL_SCRIPT])
def test_over_delete_raises_and_prevents_negative_top(tmp_path, script_path):
    mod = _load_module(script_path, "ds_over")
    in_gro = tmp_path / "in.gro"
    in_top = tmp_path / "in.top"
    out_gro = tmp_path / "out.gro"
    out_top = tmp_path / "out.top"
    _write_synthetic_system(in_gro, in_top, cf_mols=5, atoms_per_cf=5)

    with pytest.raises(ValueError, match="不足"):
        mod.delete_solvent_molecules(str(in_gro), str(out_gro), "CF", 6, 5)

    with pytest.raises(ValueError, match="小于请求删除数量"):
        mod.update_topology(str(in_top), str(out_top), "CF", 6)


@pytest.mark.parametrize("script_path", [FCLFCL_SCRIPT, CLFFCL_SCRIPT])
def test_wrong_solvent_name_raises_no_false_success(tmp_path, script_path):
    in_gro = tmp_path / "in.gro"
    in_top = tmp_path / "in.top"
    out_gro = tmp_path / "out.gro"
    out_top = tmp_path / "out.top"
    _write_synthetic_system(in_gro, in_top, cf_mols=5, atoms_per_cf=5)

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--solvent", "WRONG_SOL",
            "--delete-num", "2",
            "--loop", "1",
            "--input", str(in_gro),
            "--output", str(out_gro),
            "--topology", str(in_top),
            "--topology-output", str(out_top),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "SUCCESS" not in proc.stdout
    assert not out_gro.exists()
    assert not out_top.exists()


@pytest.mark.parametrize("script_path", [FCLFCL_SCRIPT, CLFFCL_SCRIPT])
def test_gro_corruptions_rejected(tmp_path, script_path):
    mod = _load_module(script_path, "ds_corrupt")
    in_gro = tmp_path / "in.gro"
    in_top = tmp_path / "in.top"
    out_gro = tmp_path / "out.gro"
    _write_synthetic_system(in_gro, in_top, cf_mols=3, atoms_per_cf=5)

    # 1. 截断行 (<44 chars)
    lines = in_gro.read_text(encoding="utf-8").splitlines(keepends=True)
    bad_short = list(lines)
    bad_short[4] = bad_short[4][:30] + "\n"
    short_gro = tmp_path / "short.gro"
    short_gro.write_text("".join(bad_short), encoding="utf-8")
    with pytest.raises(ValueError, match="长度太短"):
        mod.delete_solvent_molecules(str(short_gro), str(out_gro), "CF", 1, 5)

    # 2. 头部原子数与实际行数不符
    bad_cnt = list(lines)
    bad_cnt[1] = "999\n"
    cnt_gro = tmp_path / "cnt.gro"
    cnt_gro.write_text("".join(bad_cnt), encoding="utf-8")
    with pytest.raises(ValueError, match="不一致"):
        mod.delete_solvent_molecules(str(cnt_gro), str(out_gro), "CF", 1, 5)

    # 3. 不完整溶剂分子块（3个CF原子后跟非CF原子）
    bad_frag = [
        "Frag test\n",
        "9\n",
        _format_gro_line(1, "CF", "X1", 1, 1.0, 1.0, 1.0),
        _format_gro_line(1, "CF", "X2", 2, 1.0, 1.0, 1.0),
        _format_gro_line(1, "CF", "X3", 3, 1.0, 1.0, 1.0),
        _format_gro_line(2, "DIO", "I1", 4, 2.0, 2.0, 2.0),
        _format_gro_line(3, "CF", "X1", 5, 1.0, 1.0, 1.0),
        _format_gro_line(3, "CF", "X2", 6, 1.0, 1.0, 1.0),
        _format_gro_line(3, "CF", "X3", 7, 1.0, 1.0, 1.0),
        _format_gro_line(3, "CF", "X4", 8, 1.0, 1.0, 1.0),
        _format_gro_line(3, "CF", "X5", 9, 1.0, 1.0, 1.0),
        "  5.00000  5.00000  5.00000\n",
    ]
    frag_gro = tmp_path / "frag.gro"
    frag_gro.write_text("".join(bad_frag), encoding="utf-8")
    with pytest.raises(ValueError, match="不完整的 CF 分子块"):
        mod.delete_solvent_molecules(str(frag_gro), str(out_gro), "CF", 1, 5)


@pytest.mark.parametrize("script_path", [FCLFCL_SCRIPT, CLFFCL_SCRIPT])
def test_cli_flags_and_env_fallback_and_rollback_on_top_error(tmp_path, script_path, monkeypatch):
    in_gro = tmp_path / "in.gro"
    in_top = tmp_path / "in.top"
    out_gro = tmp_path / "out.gro"
    out_top = tmp_path / "out.top"
    # 每个 CF 分子 4 个原子，共 3 个分子
    _write_synthetic_system(in_gro, in_top, cf_mols=3, atoms_per_cf=4, top_cf_count=3)

    # 1. 通过环境变量 ATOMS_PER_SOLVENT=4 运行
    env = dict(**os_environ_copy())
    env["ATOMS_PER_SOLVENT"] = "4"
    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--solvent", "CF",
            "--delete-num", "1",
            "--loop", "1",
            "--input", str(in_gro),
            "--output", str(out_gro),
            "--topology", str(in_top),
            "--topology-output", str(out_top),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "SUCCESS: Deleted 1 CF molecules. New atoms: 12" in proc.stdout

    # 2. 通过 --atoms-per-mol 4 覆盖错误的环境变量 ATOMS_PER_SOLVENT=9
    env["ATOMS_PER_SOLVENT"] = "9"
    proc2 = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--solvent", "CF",
            "--delete-num", "2",
            "--atoms-per-mol", "4",
            "--loop", "1",
            "--input", str(in_gro),
            "--output", str(out_gro),
            "--topology", str(in_top),
            "--topology-output", str(out_top),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc2.returncode == 0
    assert "SUCCESS: Deleted 2 CF molecules. New atoms: 8" in proc2.stdout

    # 3. 当 TOP 中 CF 数量不足时，main() 应报错且清理已生成的 out_gro
    bad_gro = tmp_path / "bad_out.gro"
    bad_top = tmp_path / "bad_out.top"
    _write_synthetic_system(in_gro, in_top, cf_mols=3, atoms_per_cf=4, top_cf_count=1)
    proc3 = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--solvent", "CF",
            "--delete-num", "2",
            "--atoms-per-solvent", "4",
            "--loop", "1",
            "--input", str(in_gro),
            "--output", str(bad_gro),
            "--topology", str(in_top),
            "--topology-output", str(bad_top),
        ],
        capture_output=True,
        text=True,
    )
    assert proc3.returncode != 0
    assert not bad_gro.exists()
    assert not bad_top.exists()


def os_environ_copy():
    import os
    return os.environ.copy()


def test_shell_and_ps1_scripts_defensive_guards():
    fclfcl_sh = (REPO_ROOT / "examples" / "FClFCl" / "SA" / "Process" / "run_solvent_evap_fclfcl.sh").read_bytes()
    clffcl_sh = (REPO_ROOT / "examples" / "ClFFCl" / "run_solvent_evap_clffcl.sh").read_bytes()
    fclfcl_legacy = REPO_ROOT / "examples" / "FClFCl" / "SA" / "Process" / "run_solvent_evap_fclfcl_legacy.sh"
    clffcl_legacy = REPO_ROOT / "examples" / "ClFFCl" / "run_solvent_evap_clffcl_legacy.sh"
    ps1_text = (REPO_ROOT / "examples" / "ClFFCl" / "run_sa_windows.ps1").read_text(encoding="utf-8-sig")

    # 0. Legacy 备份脚本必须保留
    assert fclfcl_legacy.is_file()
    assert clffcl_legacy.is_file()
    assert b"\r" not in fclfcl_legacy.read_bytes()
    assert b"\r" not in clffcl_legacy.read_bytes()

    # 1. Shell 脚本必须保持 LF 换行，不含 CR
    assert b"\r" not in fclfcl_sh
    assert b"\r" not in clffcl_sh

    fclfcl_text = fclfcl_sh.decode("utf-8")
    clffcl_text = clffcl_sh.decode("utf-8")

    # 2. Corrected Shell 脚本必须具备逐轮结构继承、分轮拓扑保存、同轮CPT恢复不重删、GRO完整性校验与状态记录
    for text in (fclfcl_text, clffcl_text):
        assert '--atoms-per-mol "$ATOMS_PER_SOLVENT"' in text
        assert "read_top_solvent_count()" in text
        assert "count_gro_solvent_atoms()" in text
        assert "verify_gro_complete()" in text
        assert "resolve_loop_inputs()" in text
        assert "--input \"$LOOP_IN_GRO\"" in text
        assert "--topology \"$LOOP_IN_TOP\"" in text
        assert 'cp "${OUTBASE}.gro" "$WORK_GRO"' in text
        assert 'mv "$NEW_TOP" "$LOOP_TOP"' in text
        assert 'IN_ROUND_CPT_ARGS=(-cpi "${OUTBASE}.cpt" -append)' in text
        assert '"workflow_version": "Corrected"' in text
        assert "_sa_state.json" in text

    # 3. ClFFCl Shell 帮助信息中默认 MDP 必须与实际变量 ydw-npt-sa.mdp 一致
    assert "默认: ydw-npt-sa.mdp" in clffcl_text
    assert "mdrun (10ps NPT)" in clffcl_text

    # 4. PowerShell 脚本必须包含剩余溶剂截断、GRO/TOP 对账与状态记录
    assert "Get-TopSolventCount" in ps1_text
    assert "Get-GroSolventAtomCount" in ps1_text
    assert "[Math]::Min($DELETE_NUM, $CURRENT_SOLVENT_COUNT)" in ps1_text
    assert "_sa_state.json" in ps1_text

