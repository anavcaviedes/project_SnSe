set terminal pngcairo size 900,650 enhanced font "Arial,14"
set output "SnSe_monolayer_IP_vs_vacuum.png"

set xlabel "Cell height C (Å)"
set ylabel "E_{vac} - E_{VBM} (eV)"
set grid
set key top right

plot "work_function_vs_vacuum.dat" using 1:6 with linespoints lw 2 pt 7 title "E_{vac} - E_{VBM}"

set output
