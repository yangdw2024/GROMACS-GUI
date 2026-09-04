#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入的独立命令行脚本（溶剂/添加剂删除）

这两个脚本以字符串形式嵌入，运行时写出为独立 .py 文件执行。
各自必须自包含（含各自的 import 与 gro 读写函数），不做共享导入。
"""

# === 溶剂/添加剂删除脚本（由 ClFFCl/delete_solvent.py 与 delete_additive_all.py 嵌入）===
DELETE_SOLVENT_SCRIPT = r'''#!/usr/bin/env python3

import argparse
import os

def validate_gro_line(line, line_num):
    if len(line.rstrip('\n')) < 20:
        stripped_line = line.rstrip('\n')
        raise ValueError(f"行 {line_num}: 长度太短 ({len(stripped_line)} chars): {stripped_line}")

def read_gro_file(gro_file):
    with open(gro_file, 'r') as f:
        lines = f.readlines()

    header = lines[0]
    num_atoms = int(lines[1].strip())
    atoms = lines[2:-1]
    box = lines[-1]

    for i, line in enumerate(atoms, start=3):
        validate_gro_line(line, i)

    return header, num_atoms, atoms, box

def write_gro_file(output_file, header, num_atoms, atoms, box):
    with open(output_file, 'w') as f:
        f.write(header)
        f.write(f"{num_atoms}\n")
        f.writelines(atoms)
        f.write(box)

def delete_solvent_molecules(gro_file, output_file, solvent_name, delete_num, atoms_per_solvent, delete_from="bottom"):
    header, num_atoms, atoms, box = read_gro_file(gro_file)

    if delete_from == "bottom":
        # 从 gro 文件末尾向前扫描，删除最后出现的溶剂分子
        removed = 0
        i = len(atoms) - atoms_per_solvent

        while i >= 0 and removed < delete_num:
            is_solvent = True
            for j in range(atoms_per_solvent):
                if atoms[i + j][5:10].strip() != solvent_name:
                    is_solvent = False
                    break

            if is_solvent:
                for j in range(atoms_per_solvent):
                    atoms[i + j] = None
                removed += 1
                i -= atoms_per_solvent
            else:
                i -= 1
    else:
        # 从 gro 文件开头向后扫描，删除最先出现的溶剂分子
        kept = []
        current_mol = []
        deleted_count = 0

        for line in atoms:
            resname = line[5:10].strip()

            if resname != solvent_name:
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
        write_gro_file(output_file, header, len(kept), kept, box)
        return len(kept)

    kept = [a for a in atoms if a is not None]
    new_num = len(kept)
    write_gro_file(output_file, header, new_num, kept, box)
    return new_num

def update_topology(top_file, out_top, solvent, delete_num, delete_from="bottom"):
    with open(top_file, 'r') as f:
        lines = f.readlines()

    # 收集 [molecules] 节中所有匹配的溶剂条目
    in_molecules = False
    matches = []

    for i, line in enumerate(lines):
        if '[ molecules ]' in line:
            in_molecules = True
            continue
        if in_molecules and line.strip() and not line.startswith(';'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == solvent:
                matches.append((i, int(parts[1])))

    if not matches:
        raise ValueError(f"Solvent '{solvent}' not found in topology [molecules]")

    # 根据 delete_from 决定减数顺序
    if delete_from == "bottom":
        # 优先从最后一个条目减，不够再往前减
        order = reversed(range(len(matches)))
    else:
        # 优先从第一个条目减，不够再往后减
        order = range(len(matches))

    remaining = delete_num
    for idx in order:
        if remaining <= 0:
            break
        line_idx, count = matches[idx]
        to_remove = min(count, remaining)
        new_cnt = count - to_remove
        lines[line_idx] = f"{solvent}\t\t{new_cnt}\n"
        remaining -= to_remove

    if remaining > 0:
        total = sum(c for _, c in matches)
        raise ValueError(
            f"Cannot delete {delete_num} {solvent} molecules: "
            f"only {total} available in total."
        )

    with open(out_top, 'w') as f:
        f.writelines(lines)

def main():
    parser = argparse.ArgumentParser(description="精确删除N个溶剂分子")
    parser.add_argument('--solvent', required=True, help="溶剂残基名，例如 CF")
    parser.add_argument('--delete-num', type=int, required=True, help="要删除的溶剂分子数量")
    parser.add_argument('--atoms-per-mol', type=int, default=5, help="每个溶剂分子的原子数，默认5")
    parser.add_argument('--loop', type=int, required=True, help="当前循环次数")
    parser.add_argument('--delete-from', choices=['top', 'bottom'], default='bottom',
                        help="删除顺序: top=从开头/顶部删除, bottom=从末尾/底部删除(默认)")
    parser.add_argument('--input', required=True, help="输入gro文件")
    parser.add_argument('--output', required=True, help="输出gro文件")
    parser.add_argument('--topology', required=True, help="输入top文件")
    parser.add_argument('--topology-output', required=True, help="输出top文件")
    args = parser.parse_args()

    new_num = delete_solvent_molecules(
        args.input, args.output,
        args.solvent, args.delete_num, args.atoms_per_mol, args.delete_from
    )

    update_topology(args.topology, args.topology_output, args.solvent, args.delete_num, args.delete_from)
    print(f"SUCCESS: Deleted {args.delete_num} {args.solvent} molecules (from {args.delete_from}). New atoms: {new_num}")

if __name__ == "__main__":
    main()
'''

DELETE_ADDITIVE_SCRIPT = r'''#!/usr/bin/env python3

import argparse

def validate_gro_line(line, line_num):
    if len(line.rstrip('\n')) < 20:
        stripped_line = line.rstrip('\n')
        raise ValueError(f"行 {line_num}: 长度太短 ({len(stripped_line)} chars): {stripped_line}")

def read_gro_file(gro_file):
    with open(gro_file, 'r') as f:
        lines = f.readlines()

    header = lines[0]
    num_atoms = int(lines[1].strip())
    atoms = lines[2:-1]
    box = lines[-1]

    for i, line in enumerate(atoms, start=3):
        validate_gro_line(line, i)

    return header, num_atoms, atoms, box

def write_gro_file(output_file, header, num_atoms, atoms, box):
    with open(output_file, 'w') as f:
        f.write(header)
        f.write(f"{num_atoms}\n")
        f.writelines(atoms)
        f.write(box)

def delete_all_additive(gro_file, output_file, additive_name, atoms_per_additive):
    header, num_atoms, atoms, box = read_gro_file(gro_file)

    kept = []
    current_mol = []
    deleted_count = 0

    for line in atoms:
        resname = line[5:10].strip()

        if resname != additive_name:
            if current_mol:
                kept.extend(current_mol)
                current_mol = []
            kept.append(line)
            continue

        current_mol.append(line)
        if len(current_mol) == atoms_per_additive:
            deleted_count += 1
            current_mol = []

    if current_mol:
        kept.extend(current_mol)

    new_num = len(kept)
    write_gro_file(output_file, header, new_num, kept, box)
    return new_num, deleted_count

def update_topology_remove_all(top_file, out_top, additive_name):
    with open(top_file, 'r') as f:
        lines = f.readlines()

    out = []
    in_molecules = False

    for line in lines:
        if '[ molecules ]' in line:
            in_molecules = True
            out.append(line)
            continue

        if in_molecules and line.strip() and not line.startswith(';'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == additive_name:
                out.append(f"{additive_name}\t\t0\n")
            else:
                out.append(line)
        else:
            out.append(line)

    with open(out_top, 'w') as f:
        f.writelines(out)

def main():
    parser = argparse.ArgumentParser(description="一次性删除所有添加剂分子")
    parser.add_argument('--additive', required=True, help="要删除的添加剂名称，例如 DIO")
    parser.add_argument('--atoms-per-mol', type=int, required=True, help="每个添加剂分子的原子数")
    parser.add_argument('--input', required=True, help="输入gro文件")
    parser.add_argument('--output', required=True, help="输出gro文件")
    parser.add_argument('--topology', required=True, help="输入top文件")
    parser.add_argument('--topology-output', required=True, help="输出top文件")
    args = parser.parse_args()

    new_num, deleted_count = delete_all_additive(
        args.input, args.output,
        args.additive, args.atoms_per_mol
    )

    update_topology_remove_all(args.topology, args.topology_output, args.additive)

    print(f"成功删除【所有】{args.additive} 分子！共删除 {deleted_count} 个分子")
    print(f"新原子总数: {new_num}")

if __name__ == "__main__":
    main()
'''
