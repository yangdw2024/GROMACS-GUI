import sys
from pathlib import Path

out = Path(sys.argv[1])
frames = [Path(x) for x in sys.argv[2:]]

with out.open("w") as fout:
    for model_id, p in enumerate(frames, start=1):
        fout.write(f"MODEL     {model_id}\n")
        with p.open("r") as fin:
            for line in fin:
                rec = line[:6].strip()
                if rec in {"ATOM", "HETATM", "TER"}:
                    fout.write(line)
        fout.write("ENDMDL\n")
    fout.write("END\n")
