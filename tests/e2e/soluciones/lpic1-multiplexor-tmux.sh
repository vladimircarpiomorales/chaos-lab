#!/usr/bin/env bash
# Solución e2e de lpic1-multiplexor-tmux (reto r101-multiplexor-tmux); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-multiplexor-tmux "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-multiplexor-tmux
tmux new-session -d -s lpi101 -c "$PWD" bash
tmux ls > sesiones.txt
tmux send-keys -t lpi101 'echo "hola desde tmux"' Enter
sleep 1
tmux capture-pane -p -t lpi101 > pantalla.txt
tmux kill-session -t lpi101
chown -R alumno:alumno "$RETO"
SOL
