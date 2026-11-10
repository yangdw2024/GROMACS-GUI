#!/usr/bin/env python3

import argparse
import os


def validate_gro_line(line, line_num):
    stripped_line = line.rstrip('\r\n')
    if len(stripped_line) < 44:
        raise ValueError(f"行 {line_num}: 长度太短 ({len(stripped_line)} chars): {stripped_line}")


def read_gro_file(gro_file):
    with open(gro_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    if len(lines) < 3:
        raise ValueError(f"GRO 文件行数不足 ({len(lines)} 行): {gro_file}")

    header = lines[0]
    try:
        num_atoms = int(lines[1].strip())
    except ValueError as exc:
        raise ValueError(f"GRO 原子数行无效: {lines[1].strip()!r}") from exc

    atoms = lines[2:-1]
    box = lines[-1]

    if not box.strip():
        raise ValueError("GRO 盒子向量行为空")

    if num_atoms != len(atoms):
        raise ValueError(
            f"GRO 头部声明原子数 ({num_atoms}) 与实际原子行数 ({len(atoms)}) 不一致"
        )

    for i, line in enumerate(atoms, start=3):
        validate_gro_line(line, i)

    return header, num_atoms, atoms, box


def write_gro_file(output_file, header, num_atoms, atoms, box):
    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(header)
        f.write(f"{num_atoms}\n")
        f.writelines(atoms)
        f.write(box)


# ==================== 最终稳定版：精确删除N个溶剂分子 ====================
def delete_solvent_molecules(gro_file, output_file, solvent_name, delete_num, atoms_per_solvent):
    if not solvent_name or not str(solvent_name).strip():
        raise ValueError("solvent_name 不能为空")
    if delete_num < 0:
        raise ValueError(f"delete_num 不能为负数: {delete_num}")
    if atoms_per_solvent <= 0:
        raise ValueError(f"atoms_per_solvent 必须为正整数: {atoms_per_solvent}")

    header, num_atoms, atoms, box = read_gro_file(gro_file)

    kept = []
    current_mol = []
    deleted_count = 0

    for idx, line in enumerate(atoms, start=3):
        resname = line[5:10].strip()

        if resname != solvent_name:
            if current_mol:
                raise ValueError(
                    f"行 {idx}: 发现不完整的 {solvent_name} 分子块 "
                    f"(已累积 {len(current_mol)} 个原子，期望 {atoms_per_solvent})"
                )
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
        raise ValueError(
            f"文件末尾发现不完整的 {solvent_name} 分子块 "
            f"(已累积 {len(current_mol)} 个原子，期望 {atoms_per_solvent})"
        )

    if deleted_count != delete_num:
        raise ValueError(
            f"GRO 中可删除的 {solvent_name} 分子数不足: 请求删除 {delete_num}，实际仅找到 {deleted_count}"
        )

    new_num = len(kept)
    if num_atoms - new_num != deleted_count * atoms_per_solvent:
        raise ValueError(
            f"删除前后原子数差值 ({num_atoms - new_num}) 与删除分子数 ({deleted_count} * {atoms_per_solvent}) 不匹配"
        )

    write_gro_file(output_file, header, new_num, kept, box)
    return new_num


# ==================== 拓扑文件精确更新 ====================
def update_topology(top_file, out_top, solvent, delete_num):
    if not solvent or not str(solvent).strip():
        raise ValueError("solvent 不能为空")
    if delete_num < 0:
        raise ValueError(f"delete_num 不能为负数: {delete_num}")

    with open(top_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    out = []
    in_molecules = False
    matched = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and ']' in stripped:
            sec_name = stripped.split(']', 1)[0].lstrip('[').strip().lower()
            in_molecules = (sec_name == 'molecules')
            out.append(line)
            continue

        if in_molecules and stripped and not stripped.startswith(';'):
            code_part = line.split(';', 1)[0].strip()
            parts = code_part.split()
            if len(parts) >= 2 and parts[0] == solvent and not matched:
                try:
                    old_cnt = int(parts[1])
                except ValueError as exc:
                    raise ValueError(f"TOP 中 {solvent} 分子数无效: {parts[1]!r}") from exc
                if old_cnt < delete_num:
                    raise ValueError(
                        f"TOP 中 {solvent} 分子数 ({old_cnt}) 小于请求删除数量 ({delete_num})"
                    )
                new_cnt = old_cnt - delete_num
                out.append(f"{solvent}\t\t{new_cnt}\n")
                matched = True
            else:
                out.append(line)
        else:
            out.append(line)

    if not matched:
        raise ValueError(f"在 TOP [ molecules ] 中未找到溶剂条目: {solvent}")

    with open(out_top, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(out)


# ==================== main ====================
def main():
    parser = argparse.ArgumentParser(description="精确删除N个溶剂分子")
    parser.add_argument('--solvent', required=True, help="溶剂残基名，例如 CF")
    parser.add_argument('--delete-num', type=int, required=True, help="要删除的溶剂分子数量")
    parser.add_argument(
        '--atoms-per-mol', '--atoms-per-solvent',
        dest='atoms_per_mol',
        type=int,
        default=None,
        help="每个溶剂分子的原子数，默认读取环境变量 ATOMS_PER_SOLVENT 或 5"
    )
    parser.add_argument('--loop', type=int, required=True, help="当前循环次数")
    parser.add_argument('--input', required=True, help="输入gro文件")
    parser.add_argument('--output', required=True, help="输出gro文件")
    parser.add_argument('--topology', required=True, help="输入top文件")
    parser.add_argument('--topology-output', required=True, help="输出top文件")
    args = parser.parse_args()

    if args.atoms_per_mol is not None:
        atoms_per_solvent = args.atoms_per_mol
    else:
        atoms_per_solvent = int(os.getenv('ATOMS_PER_SOLVENT', 5))

    new_num = delete_solvent_molecules(
        args.input, args.output,
        args.solvent, args.delete_num, atoms_per_solvent
    )

    try:
        update_topology(args.topology, args.topology_output, args.solvent, args.delete_num)
    except Exception:
        if os.path.abspath(args.output) != os.path.abspath(args.input) and os.path.exists(args.output):
            try:
                os.remove(args.output)
            except OSError:
                pass
        raise

    print(f"SUCCESS: Deleted {args.delete_num} {args.solvent} molecules. New atoms: {new_num}")


if __name__ == "__main__":
    main()
