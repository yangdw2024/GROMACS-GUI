import sys

infile = sys.argv[1]
outfile = sys.argv[2]
wanted = ["L8B", "CF", "DIO"]

groups = {}
current = None

with open(infile, "r") as f:
    for line in f:
        s = line.strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1].strip()
            groups[current] = []
        else:
            if current is None:
                continue
            groups[current].extend(int(x) for x in s.split())

missing = [g for g in wanted if g not in groups]
if missing:
    print("缺少组: " + ", ".join(missing), file=sys.stderr)
    print("当前可用组: " + ", ".join(groups.keys()), file=sys.stderr)
    sys.exit(2)

merged = sorted(set(i for g in wanted for i in groups[g]))

with open(outfile, "w") as f:
    for gname, atoms in groups.items():
        f.write(f"[ {gname} ]\n")
        for i in range(0, len(atoms), 15):
            f.write(" ".join(str(x) for x in atoms[i:i+15]) + "\n")
    f.write("[ MERGED ]\n")
    for i in range(0, len(merged), 15):
        f.write(" ".join(str(x) for x in merged[i:i+15]) + "\n")
