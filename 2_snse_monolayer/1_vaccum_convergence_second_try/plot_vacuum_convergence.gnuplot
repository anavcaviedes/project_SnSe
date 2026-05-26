# ===============================
# Vacuum convergence summary
# ===============================

set terminal pngcairo size 900,650 enhanced font "Arial,14"
set output "SnSe_monolayer_vacuum_convergence.png"

set xlabel "Cell height C (Å)"
set ylabel "E_{vac} - E_{VBM} (eV)"

set grid
set key top right

plot "vacuum_convergence_summary.dat" using 1:12 with linespoints lw 2 pt 7 title "E_{vac} - E_{VBM}"

set output
