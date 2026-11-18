"""Convierte piezas de cabello de LDraw en mallas JSON para la web.

    python ldraw_a_json.py <complete.zip de ldraw.org> <carpeta_salida>

Lee cada pieza con sus subpiezas y primitivas, aplica las transformaciones y guarda
los triángulos en unidades LDraw (LDU). Las líneas de contorno (tipos 2 y 5) se omiten.
Las piezas de LDraw tienen licencia CC BY 2.0 (ldraw.org); ver CREDITOS.txt.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

# id de LDraw -> (nombre en la interfaz, largo para el agente)
PEINADOS = {
    "3901": ("Clásico corto", "corto"),
    "40233": ("Corto despeinado", "corto"),
    "99930": ("Peinado al costado", "corto"),
    "2631": ("En punta", "corto"),
    "62711": ("Bob", "medio"),
    "88283": ("Medio despeinado", "medio"),
    "29634": ("Muy rizado", "medio"),
    "40251": ("Largo ondulado", "largo"),
    "40239": ("Largo lacio", "largo"),
    "6093a": ("Cola de caballo", "largo"),
    "25613": ("Moño", "largo"),
}
CABEZA = "3626c"  # cabeza de minifigura, para calibrar la posición
CARPETAS = ["ldraw/parts/", "ldraw/parts/s/", "ldraw/p/", "ldraw/p/48/", "ldraw/p/8/"]


class Biblioteca:
    def __init__(self, ruta_zip: str):
        self.z = zipfile.ZipFile(ruta_zip)
        self.indice = {n.lower(): n for n in self.z.namelist()}
        self.cache: dict[str, list] = {}

    def buscar(self, nombre: str) -> str | None:
        nombre = nombre.replace("\\", "/").lower()
        for c in CARPETAS:
            if c + nombre in self.indice:
                return self.indice[c + nombre]
        return None

    def lineas(self, nombre: str) -> list[str]:
        if nombre not in self.cache:
            ruta = self.buscar(nombre)
            if ruta is None:
                raise FileNotFoundError(nombre)
            self.cache[nombre] = self.z.read(ruta).decode("utf-8", "replace").splitlines()
        return self.cache[nombre]

    def triangulos(self, nombre: str, m: np.ndarray, t: np.ndarray, salida: list, faltan: set):
        try:
            lineas = self.lineas(nombre)
        except FileNotFoundError:
            faltan.add(nombre)
            return
        for l in lineas:
            p = l.split()
            if not p:
                continue
            tipo = p[0]
            if tipo == "1" and len(p) >= 15:
                x, y, z, a, b, c, d, e, f, g, h, i = map(float, p[2:14])
                m2 = np.array([[a, b, c], [d, e, f], [g, h, i]])
                self.triangulos(" ".join(p[14:]), m @ m2, m @ np.array([x, y, z]) + t, salida, faltan)
            elif tipo == "3" and len(p) >= 11:
                v = np.array(p[2:11], float).reshape(3, 3)
                salida.append((v @ m.T) + t)
            elif tipo == "4" and len(p) >= 14:
                v = (np.array(p[2:14], float).reshape(4, 3) @ m.T) + t
                salida.append(v[[0, 1, 2]])
                salida.append(v[[0, 2, 3]])


def malla(lib: Biblioteca, pieza: str):
    tris, faltan = [], set()
    lib.triangulos(pieza + ".dat", np.eye(3), np.zeros(3), tris, faltan)
    pos = np.concatenate(tris).astype(np.float32) if tris else np.zeros((0, 3), np.float32)
    return pos, faltan


def main():
    lib = Biblioteca(sys.argv[1])
    salida = Path(sys.argv[2])
    salida.mkdir(parents=True, exist_ok=True)
    cab, _ = malla(lib, CABEZA)
    print(f"cabeza {CABEZA}: y {cab[:, 1].min():.1f}..{cab[:, 1].max():.1f}  x {cab[:, 0].min():.1f}..{cab[:, 0].max():.1f}")
    catalogo = []
    for pid, (nombre, largo) in PEINADOS.items():
        pos, faltan = malla(lib, pid)
        desc = lib.lineas(pid + ".dat")[0][2:].strip()
        (salida / f"{pid}.json").write_text(json.dumps(
            {"id": pid, "pos": np.round(pos.reshape(-1), 2).tolist()}, separators=(",", ":")))
        catalogo.append({"id": pid, "nombre": nombre, "largo": largo, "ldraw": desc})
        print(f"{pid:7} {len(pos) // 3:6} triángulos  y {pos[:, 1].min():6.1f}..{pos[:, 1].max():6.1f}"
              f"  faltan {sorted(faltan) if faltan else '-'}  {desc}")
    (salida / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "CREDITOS.txt").write_text(
        "Piezas de cabello tomadas de la biblioteca oficial de LDraw (https://library.ldraw.org),\n"
        "con licencia Creative Commons Attribution 2.0 (CC BY 2.0). Convertidas a triángulos con\n"
        "interfaz/herramientas/ldraw_a_json.py.\n\n" + "\n".join(f"{c['id']}.dat  {c['ldraw']}" for c in catalogo) + "\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
