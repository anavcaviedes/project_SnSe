import re
import subprocess
from pathlib import Path


input_template = "snse_bulk_alat.in"


qe_command = "mpirun -np 6 pw.x -npools 3"


summary_file = "ecut_alat_results.dat"


Path("tmp").mkdir(exist_ok=True)


with open(input_template, "r") as f:
    template = f.read()


ecutwfc_values = [30, 40, 50, 60]


alat_values = [12.15 - 0.05 * i for i in range(25)]


with open(summary_file, "w") as summary:

    summary.write(
        "# ecutwfc_Ry  alat_A  ecutrho_Ry  total_energy_Ry  "
        "converged  iterations  wall_time\n"
    )

    for ecutwfc in ecutwfc_values:

        ecutrho = 10 * ecutwfc

        for alat in alat_values:

            alat_label = f"{alat:.2f}".replace(".", "p")

            input_file = f"snse_ecutwfc_{ecutwfc}_A_{alat_label}.in"
            output_file = f"snse_ecutwfc_{ecutwfc}_A_{alat_label}.out"


            new_input = re.sub(
                r"ecutwfc\s*=\s*[0-9.]+",
                f"ecutwfc     = {ecutwfc}",
                template,
            )


            new_input = re.sub(
                r"ecutrho\s*=\s*[0-9.]+",
                f"ecutrho     = {ecutrho}",
                new_input,
            )


            new_input = re.sub(
                r"^\s*A\s*=\s*[0-9.]+,?",
                f"  A           = {alat:.2f},",
                new_input,
                flags=re.MULTILINE,
            )


            with open(input_file, "w") as f:
                f.write(new_input)

            print(
                f"Running ecutwfc = {ecutwfc} Ry, "
                f"ecutrho = {ecutrho} Ry, A = {alat:.2f}"
            )


            subprocess.run(
                f"{qe_command} < {input_file} > {output_file} 2>&1",
                shell=True,
                check=True,
            )


            with open(output_file, "r", errors="ignore") as f:
                output = f.read()


            converged = "yes" if "convergence has been achieved" in output else "no"


            match = re.search(
                r"convergence has been achieved in\s+([0-9]+)\s+iterations",
                output,
            )
            iterations = match.group(1) if match else "NA"


            match = re.search(r"PWSCF\s*:\s*.*?CPU\s*(.*?)\s*WALL", output)
            wall_time = match.group(1).strip() if match else "NA"


            match = re.search(
                r"!\s+total energy\s+=\s+([-0-9.]+)\s+Ry",
                output,
            )

            if match:
                total_energy = float(match.group(1))
            else:
                total_energy = "NA"


            summary.write(
                f"{ecutwfc}  {alat:.2f}  {ecutrho}  {total_energy}  "
                f"{converged}  {iterations}  {wall_time}\n"
            )

print(f"Done. Results saved in {summary_file}")
