"""Etapa 3: imagen de FLUX (fondo amarillo) -> estampa RGBA del tamaño de las estampas reales.

    info = postproceso.analizar(img)                  # Lab, fondo = mediana del borde, trazo, guardrail
    r = postproceso.a_rgba(img, margenes, tamano)     # r["rgba"] (PIL RGBA) o r["descartada"] con r["motivo"]

Pasos (especificación): Lab (skimage.color.rgb2lab) · fondo = mediana del 5 % exterior · trazo = distancia Lab > 25
· apertura 3x3 · se borran componentes < 15 px · encuadre con los márgenes medidos en las estampas reales ·
tamaño final con alfa NEAREST y color BOX · guardrail: trazo 2–50 % del área, >= 60 % del borde es fondo y
sin cabeza dibujada (silueta rellena más grande <= 30 % de la imagen).
"""
import json

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.color import rgb2lab

import config as C


def anillo(h, w, frac=None):
    """Máscara del borde exterior (frac del lado menor)."""
    b = max(1, int(round((C.BORDE_FONDO if frac is None else frac) * min(h, w))))
    m = np.zeros((h, w), bool)
    m[:b], m[-b:], m[:, :b], m[:, -b:] = True, True, True, True
    return m


def analizar(img):
    """Separa trazo y fondo. Devuelve dict con trazo (bool HxW), fondo_rgb, cobertura, borde_fondo y descarte."""
    rgb = np.asarray(img.convert("RGB"))
    lab = rgb2lab(rgb / 255.0)
    h, w = rgb.shape[:2]
    borde = anillo(h, w)
    fondo = np.median(lab[borde], axis=0)
    dist = np.linalg.norm(lab - fondo, axis=-1)
    trazo = dist > C.UMBRAL_LAB
    borde_fondo = float((~trazo[borde]).mean())               # antes de limpiar: ¿cuánto del borde es fondo?
    k = np.ones((C.APERTURA, C.APERTURA), bool)
    trazo = ndimage.binary_opening(trazo, structure=k)
    etiq, n = ndimage.label(trazo, structure=np.ones((3, 3)))
    if n:
        tam = np.bincount(etiq.ravel())
        chicos = tam < C.MIN_COMPONENTE
        chicos[0] = False
        trazo[chicos[etiq]] = False
    cobertura = float(trazo.mean())
    silueta = silueta_mayor(trazo)
    fondo_rgb = np.median(rgb[borde], axis=0)
    motivo = []
    if silueta > C.SILUETA_MAX:
        motivo.append(f"cabeza dibujada (silueta {silueta:.0%} > {C.SILUETA_MAX:.0%})")
    if cobertura < C.COBERTURA_MIN:
        motivo.append(f"trazo {cobertura:.1%} < {C.COBERTURA_MIN:.0%}")
    if cobertura > C.COBERTURA_MAX:
        motivo.append(f"trazo {cobertura:.1%} > {C.COBERTURA_MAX:.0%}")
    if borde_fondo < C.BORDE_FONDO_MIN:
        motivo.append(f"borde fondo {borde_fondo:.0%} < {C.BORDE_FONDO_MIN:.0%}")
    return dict(rgb=rgb, lab=lab, trazo=trazo, dist=dist, fondo_rgb=fondo_rgb, cobertura=cobertura,
                borde_fondo=borde_fondo, silueta=silueta, descartada=bool(motivo), motivo="; ".join(motivo))


def silueta_mayor(trazo):
    """Área (fracción de la imagen) de la figura rellena más grande del trazo.

    Una cabeza dibujada encierra la cara (contorno, pelo + barba) o viene rellena de piel: al cerrar huecos
    chicos y rellenar lo encerrado queda una silueta de ~40-50 % de la imagen. Ojos, cejas, boca, lentes o una
    barba en U quedan por debajo de ~20 % (medido en las grillas de la corrida de Kaggle del 2026-11-16)."""
    if not trazo.any():
        return 0.0
    cerrado = ndimage.binary_closing(trazo, structure=np.ones((3, 3)), iterations=C.SILUETA_CIERRE)
    etiq, n = ndimage.label(ndimage.binary_fill_holes(cerrado))
    if not n:
        return 0.0
    tam = np.bincount(etiq.ravel())
    tam[0] = 0
    return float(tam.max() / trazo.size)


def margenes(info_estampas=None, ruta_json=None):
    """Márgenes (fracción) y tamaño final (ancho, alto) desde lo medido en las estampas reales."""
    if info_estampas is None and ruta_json is not None and ruta_json.exists():
        info_estampas = json.loads(ruta_json.read_text(encoding="utf-8"))
    info_estampas = info_estampas or {}
    if info_estampas.get("margen_por_defecto") or not info_estampas.get("fraccion"):
        m, origen = dict(C.MARGEN_POR_DEFECTO), "por defecto (sin estampas reales)"
    else:
        clave = "fraccion_mediana" if C.ESTADISTICO_MARGEN == "mediana" else "fraccion"
        m, origen = dict(info_estampas.get(clave) or info_estampas["fraccion"]), f"{C.ESTADISTICO_MARGEN} de {info_estampas.get('n')} estampas reales"
    tam = tuple(C.TAMANO_FINAL or info_estampas.get("tamano_final") or C.TAMANO_POR_DEFECTO)
    return m, tam, origen


def a_rgba(img, marg, tamano):
    """Imagen -> dict(rgba, descartada, motivo, cobertura, borde_fondo, caja). Encuadre: alto según márgenes
    arriba/abajo, ancho centrado sin deformar y con al menos C.MARGEN_LATERAL_MIN a cada lado."""
    a = analizar(img)
    W, H = tamano
    res = dict(descartada=a["descartada"], motivo=a["motivo"], cobertura=a["cobertura"],
               borde_fondo=a["borde_fondo"], rgba=None, caja=None, trazo=a["trazo"])
    t = a["trazo"]
    if not t.any():
        res.update(descartada=True, motivo=(a["motivo"] + "; " if a["motivo"] else "") + "sin trazo")
        return res
    filas, cols = np.where(t.any(1))[0], np.where(t.any(0))[0]
    y0, y1, x0, x1 = filas[0], filas[-1] + 1, cols[0], cols[-1] + 1
    mascara = t[y0:y1, x0:x1]
    color = a["rgb"][y0:y1, x0:x1].copy()
    # el fondo toma el color del trazo más cercano: así BOX no mezcla amarillo en los bordes del trazo
    _, (iy, ix) = ndimage.distance_transform_edt(~mascara, return_indices=True)
    color = color[iy, ix]
    alto_caja = H * (1 - marg["arriba"] - marg["abajo"])
    ancho_max = W * (1 - 2 * C.MARGEN_LATERAL_MIN)
    esc = min(alto_caja / mascara.shape[0], ancho_max / mascara.shape[1])
    nw, nh = max(1, round(mascara.shape[1] * esc)), max(1, round(mascara.shape[0] * esc))
    col = Image.fromarray(color).resize((nw, nh), Image.BOX)
    alfa = Image.fromarray(mascara.astype(np.uint8) * 255).resize((nw, nh), Image.NEAREST)
    x = (W - nw) // 2
    y = int(round(H * marg["arriba"] + (alto_caja - nh) / 2))
    capa = col.convert("RGBA")
    capa.putalpha(alfa)
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lienzo.paste(capa, (x, y))
    res.update(rgba=lienzo, caja=(x, y, nw, nh))
    return res


def tablero(w, h, c=8):
    t = Image.new("RGB", (w, h), (230, 230, 230))
    d = ImageDraw.Draw(t)
    for yy in range(0, h, c):
        for xx in range((yy // c % 2) * c, w, 2 * c):
            d.rectangle([xx, yy, xx + c - 1, yy + c - 1], fill=(200, 200, 200))
    return t


def sobre_tablero(rgba, ancho):
    esc = ancho / rgba.width
    im = rgba.resize((ancho, round(rgba.height * esc)), Image.NEAREST)
    fondo = tablero(*im.size).convert("RGBA")
    fondo.alpha_composite(im)
    return fondo.convert("RGB")


def grilla(pares, etiquetas, cols=5, lado=200):
    """pares = [(imagen original, resultado de a_rgba)]: original | máscara | RGBA sobre tablero."""
    ancho = lado * 3 + 8
    filas = (len(pares) + cols - 1) // cols
    hoja = Image.new("RGB", (cols * ancho, filas * (lado + 32)), "white")
    d = ImageDraw.Draw(hoja)
    for k, ((orig, r), et) in enumerate(zip(pares, etiquetas)):
        x, y = (k % cols) * ancho, (k // cols) * (lado + 32)
        hoja.paste(orig.convert("RGB").resize((lado, lado)), (x, y))
        hoja.paste(Image.fromarray((~r["trazo"]).astype(np.uint8) * 255).resize((lado, lado), Image.NEAREST), (x + lado, y))
        if r["rgba"] is not None:
            p = sobre_tablero(r["rgba"], lado)
            hoja.paste(p, (x + 2 * lado, y + (lado - p.height) // 2))
        estado = ("DESCARTADA: " + r["motivo"]) if r["descartada"] else f"ok · trazo {r['cobertura']:.0%} · borde {r['borde_fondo']:.0%}"
        d.text((x + 4, y + lado + 2), str(et)[:60], fill="black")
        d.text((x + 4, y + lado + 16), estado[:70], fill=(170, 0, 0) if r["descartada"] else (0, 120, 0))
    return hoja
