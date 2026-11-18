"""Color de la ropa de la minifig según la foto (la Etapa 5 usa torso rojo y piernas azules por defecto).

    s = ropa.estimar(foto, lib)                       # {"torso": "Black", "rgb": (19, 23, 38), ...}
    ropa.aplicar(lib, carpeta, torso="Black")         # torso + brazos; piernas=None las deja como están

En los retratos solo se ve la polera (en los hombros, abajo a los lados); las piernas no salen en la foto.
"""
from pathlib import Path

import numpy as np

import cabello

# Colores de ropa (nombres de LDConfig.ldr) entre los que elige estimar().
COLORES_ROPA = ["Black", "Dark_Blue", "Blue", "Medium_Blue", "Dark_Azure", "Sand_Blue", "Dark_Bluish_Grey",
                "Light_Bluish_Grey", "White", "Red", "Dark_Red", "Green", "Dark_Green", "Sand_Green", "Olive_Green",
                "Tan", "Dark_Tan", "Reddish_Brown", "Dark_Brown", "Orange", "Dark_Orange", "Yellow",
                "Bright_Pink", "Dark_Pink", "Medium_Lavender", "Magenta", "Dark_Turquoise"]

TORSO = {"973.dat", "3818.dat", "3819.dat"}          # torso y brazos (las manos 3820.dat no se tocan)
PIERNAS = {"73200b-f1.dat"}                          # caderas + piernas (config.PIERNAS)


def estimar(img, lib):
    """Mediana de los píxeles de los hombros (abajo a los lados), sin pared ni piel -> color LDraw más cercano."""
    a = np.asarray(img.convert("RGB").resize((200, 200)), float)
    z = np.concatenate([a[176:199, 5:60].reshape(-1, 3), a[176:199, 140:195].reshape(-1, 3)])
    fondo = np.median(np.concatenate([a[:15, :15].reshape(-1, 3), a[:15, -15:].reshape(-1, 3)]), 0)
    ok = ~cabello._piel(z) & (np.linalg.norm(z - fondo, axis=1) > 45)
    if ok.mean() < 0.3:                               # casi no hay ropa a la vista
        return dict(torso=None, rgb=None, ropa_visible=round(float(ok.mean()), 2))
    rgb = np.median(z[ok], 0)
    return dict(torso=cabello.color_ldraw(lib, rgb, COLORES_ROPA), rgb=tuple(int(v) for v in rgb),
                ropa_visible=round(float(ok.mean()), 2))


def colores_actuales(lib, carpeta, original=False):
    """{"torso": nombre, "piernas": nombre} del .ldr (o del .ldr.orig de la Etapa 5 si original=True)."""
    nombres = {str(c): n for n, (c, _) in lib.colores.items()}
    out = {}
    ruta = cabello.ldr_actual(carpeta)
    if original and ruta.with_suffix(".ldr.orig").exists():
        ruta = ruta.with_suffix(".ldr.orig")
    for l in ruta.read_text(encoding="utf-8").splitlines():
        p = l.split()
        if len(p) >= 15 and p[0] == "1":
            pieza = p[14].lower()
            if pieza in TORSO:
                out.setdefault("torso", nombres.get(p[1], p[1]))
            elif pieza in PIERNAS:
                out.setdefault("piernas", nombres.get(p[1], p[1]))
    return out


def aplicar(lib, carpeta, torso=None, piernas=None):
    """Cambia el color del torso+brazos y/o de las piernas en minifig_<foto>.ldr (respaldo en .ldr.orig)."""
    ruta = cabello.ldr_actual(carpeta)
    orig = ruta.with_suffix(".ldr.orig")
    if not orig.exists():
        orig.write_bytes(ruta.read_bytes())
    cambios = {}
    if torso:
        cambios.update({p: lib.codigo(torso) for p in TORSO})
    if piernas:
        cambios.update({p: lib.codigo(piernas) for p in PIERNAS})
    lineas = []
    for l in ruta.read_text(encoding="utf-8").splitlines():
        p = l.split()
        if len(p) >= 15 and p[0] == "1" and p[14].lower() in cambios:
            l = " ".join(["1", str(cambios[p[14].lower()])] + p[2:])
        lineas.append(l)
    ruta.write_bytes((cabello.CRLF.join(lineas) + cabello.CRLF).encode("utf-8"))
    return colores_actuales(lib, carpeta)
