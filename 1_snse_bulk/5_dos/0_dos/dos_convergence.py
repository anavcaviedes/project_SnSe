#!/usr/bin/env python3

from pathlib import Path
import subprocess
import re
import sys
import time
from datetime import datetime


# ============================================================
# Templates
# ============================================================

NSCF_TEMPLATE = Path("snse_bulk_nscf.in")
DOS_TEMPLATE = Path("snse_bulk_dos_tetra.in")


# ============================================================
# Grid, cores, pools
# Format: (nx, ny, nz, np, npools)
# ============================================================

GRID_CONFIGS = [
    (6,  6,  2,  8,  4),
    (8,  8,  3,  8,  4),
    (10, 10, 4,  8,  8),
    (12, 12, 4, 12,  4),
    (16, 16, 6, 12,  4),
]


# ============================================================
# Commands
# ============================================================

PW_EXEC = "pw.x"
DOS_EXEC = "dos.x"

# Use this if you want dos.x in serial
DOS_COMMAND = "dos.x"

# Or use this if you want dos.x in parallel
# DOS_COMMAND = "mpirun -np 4 dos.x"


# ============================================================
# Output folders
# ============================================================

INPUT_DIR = Path("generated_inputs")
OUTPUT_DIR = Path("outputs")
DOS_DIR = Path("dos_data")

SUMMARY_FILE = Path("dos_convergence_summary.dat")


# ============================================================
# Helper functions
# ============================================================

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_command(command: str, input_file: Path, output_file: Path) -> float:
    """Run command < input_file > output_file and return wall time in seconds."""
    print(f"\n[{now_string()}] Running:")
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

    end = time.perf_counter()
    elapsed = end - start

    print(f"[{now_string()}] Finished in {elapsed:.2f} s")

    if result.returncode != 0:
        print(f"\nERROR: command failed with return code {result.returncode}")
        print(f"Check output file: {output_file}")
        sys.exit(result.returncode)

    return elapsed


def check_job_done(output_file: Path) -> bool:
    text = output_file.read_text(errors="ignore")
    return "JOB DONE" in text


def replace_kpoints_automatic(text: str, nx: int, ny: int, nz: int) -> str:
    """Replace the line after K_POINTS {automatic}."""
    new_kline = f"  {nx} {ny} {nz} 0 0 0"

    pattern = (
        r"(K_POINTS\s*\{automatic\}\s*\n)"
        r"\s*\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+"
    )

    replacement = r"\1" + new_kline

    new_text, count = re.subn(
        pattern,
        replacement,
        text,
        flags=re.IGNORECASE,
    )

    if count != 1:
        raise ValueError("Could not replace K_POINTS {automatic} block.")

    return new_text


def force_tetrahedra_occupations(text: str) -> str:
    """
    Replace occupations with tetrahedra in the NSCF input.
    This is recommended when using tetrahedra DOS.
    """
    pattern = r"occupations\s*=\s*['\"][^'\"]+['\"]\s*,?"
    replacement = "occupations = 'tetrahedra',"

    new_text, count = re.subn(
        pattern,
        replacement,
        text,
        flags=re.IGNORECASE,
    )

    if count == 0:
        # Insert before the end of &SYSTEM namelist
        system_pattern = r"(&SYSTEM.*?)(/)"
        new_text, count = re.subn(
            system_pattern,
            r"\1  occupations = 'tetrahedra',\n\2",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    if count == 0:
        raise ValueError("Could not set occupations='tetrahedra'.")

    return new_text


def replace_fildos(text: str, fildos_name: str) -> str:
    """Replace fildos in the dos.x input."""
    pattern = r"fildos\s*=\s*['\"][^'\"]+['\"]\s*,?"
    replacement = f"fildos='{fildos_name}',"

    new_text, count = re.subn(
        pattern,
        replacement,
        text,
        flags=re.IGNORECASE,
    )

    if count != 1:
        raise ValueError("Could not replace fildos in DOS input.")

    return new_text


def extract_fermi_from_dos(dos_file: Path) -> str:
    """Extract EFermi from the first line of the DOS file, if present."""
    if not dos_file.exists():
        return "not_found"

    first_line = dos_file.open().readline()
    match = re.search(r"EFermi\s*=\s*([+-]?\d+(\.\d+)?)", first_line)

    if match:
        return match.group(1)

    return "not_found"


def format_time(seconds: float) -> str:
    """Format seconds as h:m:s."""
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


# ============================================================
# Main
# ============================================================

def main():
    if not NSCF_TEMPLATE.exists():
        raise FileNotFoundError(f"Missing file: {NSCF_TEMPLATE}")

    if not DOS_TEMPLATE.exists():
        raise FileNotFoundError(f"Missing file: {DOS_TEMPLATE}")

    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    DOS_DIR.mkdir(exist_ok=True)

    nscf_template_text = NSCF_TEMPLATE.read_text()
    dos_template_text = DOS_TEMPLATE.read_text()

    with SUMMARY_FILE.open("w") as summary:
        summary.write(
            "# grid  Nk_total  np  npools  "
            "nscf_seconds  nscf_time  dos_seconds  dos_time  total_seconds  total_time  "
            "EFermi_eV  dos_file\n"
        )

        for nx, ny, nz, np, npools in GRID_CONFIGS:
            grid_name = f"{nx}x{ny}x{nz}"
            nk_total = nx * ny * nz

            print("\n" + "=" * 80)
            print(f"Grid: {grid_name}")
            print(f"Nk total: {nk_total}")
            print(f"Using: mpirun -np {np} pw.x -npools {npools}")
            print("=" * 80)

            # -------------------------------
            # NSCF input/output
            # -------------------------------
            nscf_input = INPUT_DIR / f"snse_bulk_nscf_{grid_name}.in"
            nscf_output = OUTPUT_DIR / f"snse_bulk_nscf_{grid_name}.out"

            nscf_text = replace_kpoints_automatic(
                nscf_template_text,
                nx,
                ny,
                nz,
            )

            nscf_text = force_tetrahedra_occupations(nscf_text)

            nscf_input.write_text(nscf_text)

            pw_command = f"mpirun -np {np} {PW_EXEC} -npools {npools}"

            nscf_seconds = run_command(
                pw_command,
                nscf_input,
                nscf_output,
            )

            if not check_job_done(nscf_output):
                print(f"WARNING: JOB DONE not found in {nscf_output}")

            # -------------------------------
            # DOS input/output
            # -------------------------------
            dos_input = INPUT_DIR / f"snse_bulk_dos_tetra_{grid_name}.in"
            dos_output = OUTPUT_DIR / f"snse_bulk_dos_tetra_{grid_name}.out"
            dos_data = DOS_DIR / f"{grid_name}.dat"

            dos_text = replace_fildos(dos_template_text, str(dos_data))
            dos_input.write_text(dos_text)

            dos_seconds = run_command(
                DOS_COMMAND,
                dos_input,
                dos_output,
            )

            if not dos_data.exists():
                print(f"WARNING: DOS file was not created: {dos_data}")

            efermi = extract_fermi_from_dos(dos_data)

            total_seconds = nscf_seconds + dos_seconds

            summary.write(
                f"{grid_name:8s}  "
                f"{nk_total:8d}  "
                f"{np:3d}  "
                f"{npools:6d}  "
                f"{nscf_seconds:12.2f}  "
                f"{format_time(nscf_seconds):>10s}  "
                f"{dos_seconds:11.2f}  "
                f"{format_time(dos_seconds):>8s}  "
                f"{total_seconds:13.2f}  "
                f"{format_time(total_seconds):>10s}  "
                f"{efermi:>10s}  "
                f"{dos_data}\n"
            )

    print("\nAll DOS convergence calculations completed.")
    print(f"Summary file: {SUMMARY_FILE}")
    print(f"DOS data folder: {DOS_DIR}")


if __name__ == "__main__":
    main()
