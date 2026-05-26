#!/usr/bin/env python3

from pathlib import Path
import re

SUMMARY_IN = Path("vacuum_convergence_summary.dat")
OUTPUT_DIR = Path("vacuum_outputs")
SUMMARY_OUT = Path("work_function_vs_vacuum.dat")

def parse_summary(path):
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            C = float(parts[0])
            Evac_eV = float(parts[9])  # column 10
            rows.append((C, Evac_eV))
    return rows

def extract_fermi_and_vbm(out_file):
    text = out_file.read_text(errors="ignore")

    ef = None
    vbm = None

    # Fermi level
    m = re.findall(
        r"the Fermi energy is\s+([+-]?\d+\.\d+)\s+ev",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        ef = float(m[-1])

    # Case 1: highest occupied, lowest unoccupied level (ev): VBM CBM
    m = re.findall(
        r"highest occupied.*?lowest unoccupied.*?:\s*([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        vbm = float(m[-1][0])

    # Case 2: highest occupied level (ev): VBM
    if vbm is None:
        m = re.findall(
            r"highest occupied level.*?:\s*([+-]?\d+\.\d+)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            vbm = float(m[-1])

    return ef, vbm

rows = parse_summary(SUMMARY_IN)

with SUMMARY_OUT.open("w") as out:
    out.write("# C_Ang  Evac_eV  EF_eV  VBM_eV  Phi_Evac_minus_EF_eV  IP_Evac_minus_VBM_eV\n")

    for C, Evac_eV in rows:
        tag = f"C{int(C) if C.is_integer() else str(C).replace('.', 'p')}"
        out_file = OUTPUT_DIR / f"snse_mono_scf_{tag}.out"

        ef, vbm = extract_fermi_and_vbm(out_file)

        phi = Evac_eV - ef if ef is not None else None
        ip = Evac_eV - vbm if vbm is not None else None

        def fmt(x):
            return "nan" if x is None else f"{x:.8f}"

        out.write(
            f"{C:.4f}  {Evac_eV:.8f}  {fmt(ef)}  {fmt(vbm)}  {fmt(phi)}  {fmt(ip)}\n"
        )

print(f"Written: {SUMMARY_OUT}")
