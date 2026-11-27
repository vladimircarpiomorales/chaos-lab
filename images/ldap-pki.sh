#!/usr/bin/env bash
# Genera la PKI de laboratorio de los nodos LDAP de Chaos Lab (CA propia + certificado de ldap-srv) en el directorio
# que se le pase. La llama construir.sh en un directorio temporal: ninguna clave privada se guarda en el repo.
# La CA privada se borra al terminar (solo hacen falta ca.crt, srv.crt y srv.key).
set -euo pipefail
OUT="${1:?uso: ldap-pki.sh <directorio de salida>}"
mkdir -p "$OUT"; cd "$OUT"
openssl req -x509 -newkey rsa:3072 -nodes -keyout ca.key -out ca.crt -days 3650 \
  -subj "/O=Chaos Lab/CN=Chaos Lab LDAP CA" 2>/dev/null
openssl req -newkey rsa:3072 -nodes -keyout srv.key -out srv.csr -subj "/O=Chaos Lab/CN=ldap-srv" 2>/dev/null
printf 'subjectAltName=DNS:ldap-srv,DNS:localhost\nextendedKeyUsage=serverAuth\n' > ext.cnf
openssl x509 -req -in srv.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out srv.crt -days 3650 -extfile ext.cnf 2>/dev/null
rm -f srv.csr ext.cnf ca.srl ca.key
chmod 644 ca.crt srv.crt srv.key
