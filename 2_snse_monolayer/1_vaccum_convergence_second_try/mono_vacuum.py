#!/usr/bin/env python3

from pathlib import Path
import subprocess
import re
import sys
import time
from datetime import datetime
import numpy as np

# ============================================================
# User settings
# ============================================================

TEMPLATE = Path("snse_mono_scf.in")   # after relax, replace this with your relaxed input/template

VACUUMS_ANG = [5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 24.0, 26.0]

PW_COMMAND = "mpirun -np 6 pw.x -npools 3"
PP_COMMAND = "pp.x"
AVG_COMMAND = "average.x"   # keep average.x serial

PREFIX = "SnSe_monolayer"
OUTDIR = "./tmp"
PSEUDO_DIR = "../pseudo"

# The monolayer cell has 2 formula units: 2 Sn + 2 Se = 2 SnSe
N_FORMULA_UNITS = 2

RY_TO_EV = 13.605693122994
ANG_TO_BOHR = 1.889726125

# average.x settings
AVG_NPOINTS = 1200
AVG_DIRECTION = 3
AVG_WINDOW_BOHR = 1.0  # only affects macroscopic average column; planar average is column 2

# folders
INPUT_DIR = Path("vacuum_inputs")
OUTPUT_DIR = Path("vacuum_outputs")
PP_DIR = Path("potential_files")
AVG_DIR = Path("avg_data")
SUMMARY = Path("vacuum_convergence_summary.dat")


# ============================================================
# Utilities
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(command: str, input_file: Path, output_file: Path) -> float:
    print(f"\n[{now()}] Running:")
    print(f"{command} < {input_file} > {output_file}")

    start = time.perf_counter()

    with input_file.open("r") as fin, output_file.open("w") as fout:
        result = subprocess.run(
            command,
            shell=True,
            stdin=fin,
            stdout=fout,
            stderr=subprocess.STDOUT,
        )

    elapsed = time.perf_counter() - start
    print(f"[{now()}] Finished in {elapsed:.2f} s")

    if result.returncode != 0:
        print(f"\nERROR: command failed with return code {result.returncode}")
        print(f"Check: {output_file}")
        sys.exit(result.returncode)

    return elapsed


def replace_control_for_scf(text: str) -> str:
    text = re.sub(
        r"calculation\s*=\s*['\"][^'\"]+['\"]",
        "calculation  = 'scf'",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"prefix\s*=\s*['\"][^'\"]+['\"]",
        f"prefix       = '{PREFIX}'",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"outdir\s*=\s*['\"][^'\"]+['\"]",
        f"outdir       = '{OUTDIR}'",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"pseudo_dir\s*=\s*['\"][^'\"]+['\"]",
        f"pseudo_dir   = '{PSEUDO_DIR}'",
        text,
        flags=re.IGNORECASE,
    )

    # Remove &IONS block for SCF
    text = re.sub(
        r"\n\s*&IONS\b.*?\n\s*/",
        "\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text


def get_alat_ang(text: str) -> float:
    m = re.search(r"\bA\s*=\s*([0-9.EeDd+-]+)", text)
    if not m:
        raise ValueError("Could not find A = ... in &SYSTEM.")
    return float(m.group(1).replace("D", "E").replace("d", "e"))


def get_old_c_alat(text: str) -> float:
    m = re.search(
        r"CELL_PARAMETERS\s*\{alat\}\s*\n"
        r"\s*[^\n]+\n"
        r"\s*[^\n]+\n"
        r"\s*([0-9.EeDd+-]+)\s+([0-9.EeDd+-]+)\s+([0-9.EeDd+-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        raise ValueError("Could not read CELL_PARAMETERS {alat}.")
    return float(m.group(3).replace("D", "E").replace("d", "e"))


def replace_c_alat(text: str, new_c_alat: float) -> str:
    pattern = (
        r"(CELL_PARAMETERS\s*\{alat\}\s*\n"
        r"\s*[^\n]+\n"
        r"\s*[^\n]+\n)"
        r"\s*([0-9.EeDd+-]+)\s+([0-9.EeDd+-]+)\s+([0-9.EeDd+-]+)"
    )

    replacement = (
        r"\1"
        f"  0.0000000000   0.0000000000   {new_c_alat:.10f}"
    )

    new_text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)

    if count != 1:
        raise ValueError("Could not replace the third CELL_PARAMETERS vector.")

    return new_text


def shift_atomic_z_alat(text: str, dz_alat: float) -> str:
    """
    Shift all z coordinates in ATOMIC_POSITIONS {alat} by dz_alat.
    Assumes the block ends before K_POINTS.
    """

    pattern = (
        r"(ATOMIC_POSITIONS\s*\{alat\}\s*\n)"
        r"(.*?)"
        r"(\n\s*K_POINTS)"
    )

    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        raise ValueError("Could not find ATOMIC_POSITIONS {alat} block.")

    header, block, tail = m.group(1), m.group(2), m.group(3)

    new_lines = []
    for line in block.strip().splitlines():
        parts = line.split()
        if len(parts) < 4:
            new_lines.append(line)
            continue

        atom = parts[0]
        x = float(parts[1])
        y = float(parts[2])
        z = float(parts[3]) + dz_alat

        extra = ""
        if len(parts) > 4:
            extra = "  " + " ".join(parts[4:])

        new_lines.append(f"{atom:2s}  {x:.10f}  {y:.10f}  {z:.10f}{extra}")

    new_block = "\n".join(new_lines)

    return text[:m.start()] + header + new_block + tail + text[m.end():]


def extract_total_energy(out_file: Path):
    text = out_file.read_text(errors="ignore")
    matches = re.findall(r"!\s+total energy\s+=\s+([+-]?\d+\.\d+)", text)
    if matches:
        return float(matches[-1])
    return None


def extract_band_edges(out_file: Path):
    """
    Returns VBM, CBM, gap in eV if QE prints:
    highest occupied, lowest unoccupied level (ev): ...
    """
    text = out_file.read_text(errors="ignore")
    matches = re.findall(
        r"highest occupied.*?level.*?:\s*([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        vbm = float(matches[-1][0])
        cbm = float(matches[-1][1])
        return vbm, cbm, cbm - vbm
    return None, None, None


def extract_fermi(out_file: Path):
    text = out_file.read_text(errors="ignore")
    matches = re.findall(
        r"the Fermi energy is\s+([+-]?\d+\.\d+)\s+ev",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        return float(matches[-1])
    return None


def make_pp_input(pp_file: Path, filplot: Path) -> str:
    return f"""&INPUTPP
  prefix  = '{PREFIX}',
  outdir  = '{OUTDIR}',
  filplot = '{filplot}',
  plot_num = 11,
/
&PLOT
  iflag = 3,
  output_format = 5,
/
"""


def make_average_input(filplot: Path) -> str:
    # Standard average.x input:
    # number of files
    # filename
    # weight
    # number of points
    # direction
    # window
    return f"""1
{filplot}
1.D0
{AVG_NPOINTS}
{AVG_DIRECTION}
{AVG_WINDOW_BOHR}
"""


def read_avg_and_extract_evac(avg_file: Path):
    """
    Reads avg.dat. Uses column 2 as planar-averaged potential.
    Evac is estimated as the median of the edge regions, because
    the slab is centered and vacuum is at cell boundaries.
    """
    data = []
    with avg_file.open() as f:
        for line in f:
            if not line.strip() or line.strip().startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    data.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

    if not data:
        return None

    arr = np.array(data)
    z = arr[:, 0]
    v = arr[:, 1]

    zmin, zmax = z.min(), z.max()
    width = zmax - zmin

    edge_mask = (z < zmin + 0.10 * width) | (z > zmax - 0.10 * width)
    if edge_mask.sum() >= 5:
        return float(np.median(v[edge_mask]))

    # fallback: median of the highest 10% potential values
    n = max(5, int(0.10 * len(v)))
    return float(np.median(np.sort(v)[-n:]))


def format_time(seconds):
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


# ============================================================
# Main
# ============================================================

def main():
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE}")

    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    PP_DIR.mkdir(exist_ok=True)
    AVG_DIR.mkdir(exist_ok=True)

    template = TEMPLATE.read_text()
    template = replace_control_for_scf(template)

    alat_ang = get_alat_ang(template)
    old_c_alat = get_old_c_alat(template)

    with SUMMARY.open("w") as summary:
        summary.write(
            "# C_Ang  C_alat  Etot_Ry  Etot_per_fu_Ry  "
            "VBM_eV  CBM_eV  Gap_eV  EF_eV  Evac_Ry  Evac_eV  "
            "Phi_Evac_minus_EF_eV  IP_Evac_minus_VBM_eV  "
            "scf_time_s  pp_time_s  avg_time_s\n"
        )

        for C_ang in VACUUMS_ANG:
            tag = f"C{int(C_ang) if C_ang.is_integer() else str(C_ang).replace('.', 'p')}"
            new_c_alat = C_ang / alat_ang
            dz_alat = 0.5 * (new_c_alat - old_c_alat)

            print("\n" + "=" * 70)
            print(f"Vacuum/cell height C = {C_ang:.2f} Å")
            print(f"C_alat = {new_c_alat:.10f}")
            print("=" * 70)

            scf_in = INPUT_DIR / f"snse_mono_scf_{tag}.in"
            scf_out = OUTPUT_DIR / f"snse_mono_scf_{tag}.out"

            text = replace_c_alat(template, new_c_alat)
            text = shift_atomic_z_alat(text, dz_alat)
            scf_in.write_text(text)

            scf_time = run(PW_COMMAND, scf_in, scf_out)

            etot = extract_total_energy(scf_out)
            vbm, cbm, gap = extract_band_edges(scf_out)
            ef = extract_fermi(scf_out)

            # pp.x
            filplot = PP_DIR / f"snse_mono_potential_{tag}.pp"
            pp_in = INPUT_DIR / f"pp_{tag}.in"
            pp_out = OUTPUT_DIR / f"pp_{tag}.out"
            pp_in.write_text(make_pp_input(pp_in, filplot))

            pp_time = run(PP_COMMAND, pp_in, pp_out)

            # average.x
            avg_in = INPUT_DIR / f"average_{tag}.in"
            avg_out = OUTPUT_DIR / f"average_{tag}.out"
            avg_in.write_text(make_average_input(filplot))

            avg_time = run(AVG_COMMAND, avg_in, avg_out)

            avg_dat = Path("avg.dat")
            final_avg = AVG_DIR / f"avg_{tag}.dat"

            if avg_dat.exists():
                avg_dat.replace(final_avg)
            else:
                print("WARNING: avg.dat was not created by average.x")
                final_avg = None

            evac_ry = read_avg_and_extract_evac(final_avg) if final_avg else None
            evac_ev = evac_ry * RY_TO_EV if evac_ry is not None else None

            phi = evac_ev - ef if (evac_ev is not None and ef is not None) else None
            ip = evac_ev - vbm if (evac_ev is not None and vbm is not None) else None

            etot_per_fu = etot / N_FORMULA_UNITS if etot is not None else None

            def val(x):
                if x is None:
                    return "nan"
                return f"{x:.10f}"

            summary.write(
                f"{C_ang:.4f}  {new_c_alat:.10f}  "
                f"{val(etot)}  {val(etot_per_fu)}  "
                f"{val(vbm)}  {val(cbm)}  {val(gap)}  {val(ef)}  "
                f"{val(evac_ry)}  {val(evac_ev)}  {val(phi)}  {val(ip)}  "
                f"{scf_time:.2f}  {pp_time:.2f}  {avg_time:.2f}\n"
            )

    print("\nDone.")
    print(f"Summary: {SUMMARY}")
    print(f"Average potential files: {AVG_DIR}/avg_C*.dat")


if __name__ == "__main__":
    main()
