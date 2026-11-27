#!/usr/bin/env bash
# Solución e2e de lpic1-gpg-simetrico (reto r102-gpg-simetrico); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-gpg-simetrico "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-gpg-simetrico
su alumno -s /bin/bash <<'FIN'
cd /home/alumno/retos/r102-gpg-simetrico
export GNUPGHOME=/home/alumno/retos/r102-gpg-simetrico/gnupg
gpg --batch --yes --pinentry-mode loopback --passphrase clave-reto --symmetric -o secreto.txt.gpg secreto.txt
gpg --batch --pinentry-mode loopback --passphrase '' --quick-generate-key 'Alumno LPI <alumno@lpi.example>' default default never
gpg --armor --export alumno@lpi.example > publica.asc
gpg --batch --yes --encrypt -r alumno@lpi.example -o mensaje.txt.gpg mensaje.txt
gpg --batch --yes -d -o mensaje-recuperado.txt mensaje.txt.gpg
FIN
chown -R alumno:alumno "$RETO"
SOL
