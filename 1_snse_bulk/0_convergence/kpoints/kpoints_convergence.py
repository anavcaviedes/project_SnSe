import re
import subprocess
from pathlib import Path

# Input template
input_template = "snse_bulk_scf.in"

# Output summary file
summary_file = "kpoints_results.dat"

# Make sure tmp folder exists
Path("tmp").mkdir(exist_ok=True)

# K-point meshes to test
# Format:
# kx, ky, kz, sx, sy, sz, cores, pools
kpoints_list = [
    (1, 3, 3, 1, 1, 1, 6, 1),
    (2, 4, 4, 1, 1, 1, 6, 2),
    (2, 6, 6, 1, 1, 1, 6, 3),
    (3, 8, 8, 1, 1, 1, 6, 3),
    (4, 10, 10, 1, 1, 1, 6, 6),
    (4, 12, 12, 1, 1, 1, 6, 6),
]

# Read original input
with open(input_template, "r") as f:
    template = f.read()

# Get number of atoms
nat = int(re.search(r"nat\s*=\s*([0-9]+)", template).group(1))

# Open results file
with open(summary_file, "w") as summary:

    summary.write(
        "# NXNXN  total_energy_Ry  total_energy_per_atom_Ry_atom  "
        "HOMO_eV  LUMO_eV  GAP_eV  converged  iterations  wall_time\n"
    )

    for kx, ky, kz, sx, sy, sz, cores, pools in kpoints_list:

        k_label = f"{kx}x{ky}x{kz}"

        input_file = f"snse_kpoints_{k_label}.in"
        output_file = f"snse_kpoints_{k_label}.out"

        # Define QE command for this specific k-mesh
        if pools == 1:
            qe_command = f"mpirun -np {cores} pw.x"
        else:
            qe_command = f"mpirun -np {cores} pw.x -npools {pools}"

        # Replace K_POINTS block
        new_input = re.sub(
            r"K_POINTS\s*\{automatic\}\s*\n\s*[0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9]+",
            f"K_POINTS {{automatic}}\n  {kx} {ky} {kz} {sx} {sy} {sz}",
            template,
        )

        # Write input file
        with open(input_file, "w") as f:
            f.write(new_input)

        print(f"Running k-points = {kx} {ky} {kz} {sx} {sy} {sz}")
        print(f"Command: {qe_command}")

        # Run Quantum ESPRESSO
        subprocess.run(
            f"{qe_command} < {input_file} > {output_file} 2>&1",
            shell=True,
            check=True,
        )

        # Read output file
        with open(output_file, "r", errors="ignore") as f:
            output = f.read()

        # Convergence
        converged = "yes" if "convergence has been achieved" in output else "no"

        # Iterations
        match = re.search(
            r"convergence has been achieved in\s+([0-9]+)\s+iterations",
            output,
        )
        iterations = match.group(1) if match else "NA"

        # Wall time
        match = re.search(r"PWSCF\s*:\s*.*?CPU\s*(.*?)\s*WALL", output)
        wall_time = match.group(1).strip() if match else "NA"

        # Total energy
        match = re.search(r"!\s+total energy\s+=\s+([-0-9.]+)\s+Ry", output)

        if match:
            total_energy = float(match.group(1))
            total_energy_per_atom = total_energy / nat
        else:
            total_energy = "NA"
            total_energy_per_atom = "NA"

        # HOMO and LUMO
        match = re.search(
            r"highest occupied,\s*lowest unoccupied level.*?:\s*([-0-9.]+)\s+([-0-9.]+)",
            output,
        )

        if match:
            homo = float(match.group(1))
            lumo = float(match.group(2))
            gap = lumo - homo
        else:
            homo = "NA"
            lumo = "NA"
            gap = "NA"

        # Save results
        summary.write(
            f"{k_label}  {total_energy}  {total_energy_per_atom}  "
            f"{homo}  {lumo}  {gap}  {converged}  {iterations}  {wall_time}\n"
        )

print(f"Done. Results saved in {summary_file}")
