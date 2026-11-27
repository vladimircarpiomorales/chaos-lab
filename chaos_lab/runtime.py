"""Motor de contenedores: Podman o Docker.

Autodetecta podman → docker; se puede forzar con CHAOS_RUNTIME=podman|docker.
La sintaxis que usa Chaos Lab (run, exec, ps, rm, inspect, network, images) es la misma en los dos;
las diferencias (image exists, build con Containerfile) se resuelven en arrancar.sh e images/construir.sh.
"""
from __future__ import annotations

import os
import shutil


def detect_runtime() -> str:
    forced = os.environ.get("CHAOS_RUNTIME", "").strip().lower()
    if forced in ("podman", "docker"):
        return forced
    for rt in ("podman", "docker"):
        if shutil.which(rt):
            return rt
    return "podman"


RUNTIME = detect_runtime()
