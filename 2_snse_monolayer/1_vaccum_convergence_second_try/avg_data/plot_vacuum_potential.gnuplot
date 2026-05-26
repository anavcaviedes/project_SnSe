# ===============================
# Planar-averaged potential
# Monolayer SnSe vacuum test
# ===============================

set terminal pngcairo size 1000,650 enhanced font "Arial,14"
set output "SnSe_monolayer_vacuum_potential.png"

set title "Planar-averaged electrostatic potential"
set xlabel "z (Å)"
set ylabel "V(z) (Ry)"

set grid
set key top right

# average.x usually gives z in bohr.
# Convert bohr to Angstrom:
bohr_to_A = 0.5291772109

plot "avg_C5.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 5 Å", \
     "avg_C8.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 8 Å", \
     "avg_C10.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 10 Å", \
     "avg_C12.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 12 Å", \
     "avg_C15.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 15 Å", \
     "avg_C18.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 18 Å", \
     "avg_C20.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 20 Å", \
     "avg_C22.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 22 Å", \
     "avg_C24.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 24 Å", \
     "avg_C26.dat" using ($1*bohr_to_A):2 with lines lw 2 title "C = 26 Å", \

set output
