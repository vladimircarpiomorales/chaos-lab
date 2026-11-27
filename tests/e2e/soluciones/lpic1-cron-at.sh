#!/usr/bin/env bash
# Solución e2e de lpic1-cron-at (reto r102-cron-at); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-cron-at "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-cron-at
RET=/home/alumno/retos/r102-cron-at
su alumno -s /bin/bash -c "echo 'echo recordatorio > $RET/recordatorio.txt' | at now + 2 hours" 2>&1 | awk '/^job/ {print $2}' > at-id.txt
su alumno -s /bin/bash -c "echo 'echo otra cosa' | at now + 3 hours" 2>&1 | awk '/^job/ {print $2}' > otro.txt
su alumno -s /bin/bash -c "atrm $(cat otro.txt)"
su alumno -s /bin/bash -c 'atq' > atq.txt
rm -f otro.txt
su alumno -s /bin/bash -c "(crontab -l 2>/dev/null; echo '0 4 * * 0 $RET/limpia.sh') | crontab -"
chown -R alumno:alumno "$RETO"
SOL
