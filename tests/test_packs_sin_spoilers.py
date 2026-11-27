"""Regla «sin spoilers» para los packs de retos (chaos_lab/packs/*.json).

En los packs las sondas salen del corrector (`comprueba "etiqueta" …`) y la UI enseña sus etiquetas desde el
principio. Por eso una etiqueta no puede contener un dato que el jugador tiene que averiguar o calcular.

Cómo se detecta, sin leer a mano: un «dato de la respuesta» es algo que aparece en la pista 3, en el
resumen de la solución o en la solución e2e (tests/e2e/soluciones/<id>.sh) y que NO aparece en el briefing
(si el briefing ya lo dice, es lo que se pide configurar y puede verse). Solo cuentan los datos con forma de
dato: con algún dígito (puertos, IPs, fechas, cuentas, máscaras) o palabras sueltas que salen entre
`backticks` en la pista 3 / el resumen (nombres de programa, servicios, zonas…).

Si una etiqueta da un falso positivo, reescríbela como objetivo («grande.txt: el fichero más grande»). Solo
en último caso añade el dato a PERMITIDOS con un comentario.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PACKS = sorted((RAIZ / "chaos_lab" / "packs").glob("*.json"))
SOLUCIONES = RAIZ / "tests" / "e2e" / "soluciones"

# Datos que pueden salir en una etiqueta aunque no estén en el briefing (con su motivo)
PERMITIDOS: dict[str, set[str]] = {
    # "lpic1-ejemplo": {"dato"},  # motivo
}

# Palabras de shell o de uso general que nunca son «la respuesta» por sí solas
COMUNES = {
    "sudo", "echo", "cat", "grep", "awk", "sed", "cut", "tr", "head", "tail", "sort", "uniq", "wc", "ls",
    "cd", "rm", "cp", "mv", "mkdir", "chmod", "chown", "test", "bash", "sh", "nano", "vim", "vi", "less",
    "man", "true", "false", "then", "else", "done", "for", "while", "alumno", "root", "txt", "conf",
    "etc", "home", "retos", "the", "and", "with", "dev", "null", "tmp", "usr", "bin", "var", "log",
}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@*/+-]*[A-Za-z0-9*]|[A-Za-z0-9]")
ETIQUETA = re.compile(r'''^\s*(?:comprueba|ok|mal)\s+"([^"]*)"''', re.M)


def _tokens(texto: str) -> set[str]:
    out = set()
    for t in TOKEN.findall(texto or ""):
        t = t.strip(".:,;").lower()
        if len(t) >= 2:
            out.add(t)
            # también las piezas (10.0.32.0/20 → 10.0.32.0 y 20; fichero.txt:valor → valor)
            out.update(p for p in re.split(r"[/:=,]", t) if len(p) >= 2)
    return out


def _es_dato(t: str) -> bool:
    return any(c.isdigit() for c in t) or t not in COMUNES


def _en_backticks(texto: str) -> set[str]:
    return {t for trozo in re.findall(r"`([^`]+)`", texto or "") for t in _tokens(trozo)}


def fugas(item: dict, solucion_e2e: str = "") -> list[tuple[str, str]]:
    """(etiqueta, dato) de cada etiqueta que enseña un dato de la respuesta que el briefing no da."""
    briefing = _tokens(item.get("briefing", "")) | _tokens(item.get("title", ""))
    hint3 = item["hints"][-1] if item.get("hints") else ""
    resumen = item.get("solution_summary", "")
    # datos con dígitos: de la pista 3, del resumen y de la solución e2e; palabras: solo entre backticks
    con_digito = {t for t in _tokens(hint3) | _tokens(resumen) | _tokens(solucion_e2e) if any(c.isdigit() for c in t)}
    palabras = {t for t in _en_backticks(hint3) | _en_backticks(resumen) if t.isalpha() and len(t) >= 3}
    secretos = {t for t in con_digito | palabras if _es_dato(t)} - briefing - PERMITIDOS.get(item["id"], set())
    # los números de 1-2 cifras sueltos solo cuentan si la etiqueta los dice como valor («contiene 2»)
    out = []
    for etiqueta in ETIQUETA.findall(item.get("comprobar", "")):
        for t in sorted(_tokens(etiqueta) & secretos):
            if t.isdigit() and len(t) <= 2 and not re.search(rf"(contiene|dice|es|son|vale|prefijo)\s+{t}\b", etiqueta.lower()):
                continue
            out.append((etiqueta, t))
    return out


def _items():
    for p in PACKS:
        for item in json.loads(p.read_text(encoding="utf-8")):
            yield pytest.param(item, id=item["id"])


@pytest.mark.parametrize("item", list(_items()))
def test_etiquetas_no_ensenan_la_respuesta(item):
    sol = SOLUCIONES / f"{item['id']}.sh"
    encontradas = fugas(item, sol.read_text(encoding="utf-8") if sol.exists() else "")
    assert not encontradas, (
        f"{item['id']}: la etiqueta enseña un dato de la respuesta que el briefing no da "
        f"(reescríbela como objetivo): {encontradas}"
    )
