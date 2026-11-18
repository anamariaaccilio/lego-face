"""Retoques de color de la estampa (cara RGBA de la Etapa 4/5) sin volver a correr FLUX.

    rgba = estampa.cargar(carpeta)                                   # textures/cara_<foto>.png
    m = estampa.mascara_gris(rgba)                                   # rasgos grises (cejas, bigote…)
    m = estampa.mascara_barba(rgba)                                  # barba/bigote negro y grueso bajo los ojos
    nueva = estampa.recolorear(rgba, m, (25, 25, 25))
    estampa.guardar(carpeta, nueva)                                  # respalda el original como *.orig.png

La estampa tiene alfa binario: los bordes de cada rasgo son píxeles opacos mezclados con amarillo. Al recolorear,
cada píxel conserva su proporción de "tinta" frente al amarillo de la cabeza, así los bordes quedan suaves.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

AMARILLO = np.array([242, 205, 55], float)     # Yellow de LDConfig.ldr (#F2CD37): el color de la cabeza


def ruta(carpeta):
    carpeta = Path(carpeta)
    return carpeta / "textures" / f"cara_{carpeta.name}.png"


def cargar(carpeta):
    return Image.open(ruta(carpeta)).convert("RGBA")


def original(carpeta):
    """La estampa tal como la dejó la Etapa 5 (el respaldo si ya se retocó)."""
    r = ruta(carpeta)
    o = r.with_name(r.stem + ".orig.png")
    return Image.open(o if o.exists() else r).convert("RGBA")


def _tinta(px, tinta):
    """Proporción de tinta (0..1) de cada píxel sobre la recta amarillo -> tinta."""
    d = tinta - AMARILLO
    t = ((px - AMARILLO) @ d) / max(float(d @ d), 1e-6)
    return np.clip(t, 0, 1)


def mascara_gris(rgba, sat_max=40, lum=(70, 215)):
    """Píxeles opacos grises (poca saturación, luminancia media) y su borde mezclado con amarillo."""
    a = np.asarray(rgba, float)
    op = a[..., 3] > 0
    rgb = a[..., :3]
    sat = rgb.max(-1) - rgb.min(-1)
    l = rgb.mean(-1)
    gris = op & (sat < sat_max) & (l > lum[0]) & (l < lum[1])
    borde = ndimage.binary_dilation(gris, iterations=2) & op & (l > lum[0]) & ~gris
    return gris | borde


def mascara_barba(rgba, radio=5, debajo_de=None, patillas=True):
    """Zona oscura y gruesa (barba, bigote) debajo de los ojos.
    El 'opening' (erosión + dilatación) con `radio` px borra los trazos finos (contorno, boca); de lo que queda se
    toman las manchas cuyo centro está más abajo que `debajo_de` (fracción de la altura; por defecto el borde
    inferior de los ojos, estimado como la mancha gruesa más baja de la mitad superior)."""
    a = np.asarray(rgba, float)
    op = a[..., 3] > 0
    oscuro = op & (a[..., :3].mean(-1) < 110)
    est = np.ones((radio, radio), bool)
    grueso = ndimage.binary_opening(oscuro, structure=est)
    lab, n = ndimage.label(grueso)
    H = a.shape[0]
    cajas = ndimage.find_objects(lab)
    centros = [c[0] for c in ndimage.center_of_mass(grueso, lab, range(1, n + 1))]
    if debajo_de is None:
        sup = [cajas[k][0].stop for k in range(n) if centros[k] < H * 0.5]
        corte = max(sup) if sup else H * 0.45
    else:
        corte = H * debajo_de
    barba = np.isin(lab, [k + 1 for k in range(n) if centros[k] > corte])
    if patillas:   # trazos finos verticales pegados a la barba (patillas / contorno de la barba) y restos chicos
        delgado, toca = oscuro & ~barba, ndimage.binary_dilation(barba, iterations=2)
        lab2, _ = ndimage.label(delgado, structure=np.ones((3, 3)))
        for k, c in enumerate(ndimage.find_objects(lab2), 1):
            comp = lab2 == k
            alto, ancho = c[0].stop - c[0].start, c[1].stop - c[1].start
            if (toca & comp).any() and (alto >= 2 * ancho or comp.sum() < 15):
                barba |= comp
    # recupera los bordes antialias de la barba (píxeles oscuros o mezclados pegados a ella)
    cerca = ndimage.binary_dilation(barba, iterations=1) & op & (a[..., :3].mean(-1) < 150)
    return barba | cerca


def recolorear(rgba, mascara, color, tinta=None):
    """Cambia el color de la tinta en `mascara` por `color` (RGB), conservando el antialias contra el amarillo.
    tinta: color original de esos rasgos (por defecto, el más oscuro/saturado de la máscara)."""
    a = np.asarray(rgba, float).copy()
    px = a[..., :3][mascara]
    if tinta is None:
        tinta = np.median(px[_tinta(px, px.mean(0)) > 0.9], 0) if len(px) else np.zeros(3)
    tinta = np.asarray(tinta, float)
    t = _tinta(px, tinta)[:, None]
    a[..., :3][mascara] = t * np.asarray(color, float) + (1 - t) * AMARILLO
    return Image.fromarray(np.clip(a, 0, 255).round().astype(np.uint8), "RGBA")


def guardar(carpeta, rgba):
    """Escribe la estampa en textures/ y su copia junto al .ldr. La primera vez respalda la original."""
    carpeta = Path(carpeta)
    r = ruta(carpeta)
    o = r.with_name(r.stem + ".orig.png")
    if not o.exists():
        Image.open(r).save(o)
    rgba.save(r)
    rgba.save(carpeta / r.name)
    return r


def restaurar(carpeta):
    carpeta = Path(carpeta)
    r = ruta(carpeta)
    o = r.with_name(r.stem + ".orig.png")
    if not o.exists():
        return False
    img = Image.open(o)
    img.save(r)
    img.save(carpeta / r.name)
    return True


def sobre_amarillo(rgba, escala=3):
    """Vista ampliada de la estampa sobre el amarillo de la cabeza."""
    f = Image.new("RGBA", rgba.size, (*AMARILLO.astype(int), 255))
    f.alpha_composite(rgba)
    return f.convert("RGB").resize((rgba.width * escala, rgba.height * escala), Image.NEAREST)
