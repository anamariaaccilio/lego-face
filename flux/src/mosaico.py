"""Etapa 6 (Anexo A): misma foto en ambos métodos (modelo propio y FLUX), rondas 1 y 2 y una ronda con Variar.

Una "ronda" es una llamada que genera las 5 caras de una foto, como en la app:
    Ronda 1: rasgos de la foto                 · semillas SEMILLA_FLUX + k   (= Etapa 4, se reutiliza sin regenerar)
    Ronda 2: el usuario pide un cambio          · mismas semillas que la ronda 1, así la única diferencia es el cambio
             (config.CAMBIO_RONDA2, p. ej. {"lentes": "alternar"})
    Variar:  mismo pedido que la ronda 2        · otras semillas, SEMILLA_FLUX + SALTO_VARIAR + k

El modelo propio no vive en este notebook. Sus caras entran de una de dos formas (ver la celda de la Etapa 6):
    GENERAR_PROPIO = función (ruta_foto, rasgos, n, semilla_base) -> lista de n imágenes PIL
                     (en la ronda 2 y en Variar recibe los rasgos ya cambiados)
    config.CARPETA_PROPIO = carpeta con <foto sin extensión>/{ronda1,ronda2,variar}/*.png
Si no hay ninguna, sus filas salen en gris como "pendiente" y el resto del mosaico se arma igual.
"""
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

import config as C
import cara
import flux
import postproceso
from dataset import cuadrada


def rondas():
    """Las 3 rondas del Anexo A: clave, nombre, si lleva el cambio de la ronda 2 y semilla base."""
    return [dict(clave="ronda1", nombre="Ronda 1", cambio=False, base=C.SEMILLA_FLUX),
            dict(clave="ronda2", nombre="Ronda 2", cambio=True, base=C.SEMILLA_FLUX),
            dict(clave="variar", nombre="Variar", cambio=True, base=C.SEMILLA_FLUX + C.SALTO_VARIAR)]


def aplicar_cambio(fila):
    """Rasgos de la ronda 2: los de la foto con el cambio de config. Devuelve (fila cambiada, texto del cambio).
    "alternar" invierte un rasgo sí/no (lentes, barba, bigote); cualquier otro valor se pone tal cual."""
    cambio = C.CAMBIOS_RONDA2_MANUAL.get(fila["nombre"], C.CAMBIO_RONDA2)
    nueva, textos = fila.copy(), []
    for rasgo, valor in cambio.items():
        antes = fila.get(rasgo)
        if valor == "alternar":
            valor = not bool(flux._si(antes))
            antes = bool(flux._si(antes))
        nueva[rasgo] = valor
        si_no = {True: "si", False: "no"}
        textos.append(f"{rasgo}: {si_no.get(antes, antes)} -> {si_no.get(valor, valor)}")
    return nueva, ", ".join(textos)


def ronda_flux(fila, ronda, plantilla, pipe, marg, tamano, carpeta, previas=None):
    """5 caras de FLUX para una ronda (fila ya trae los rasgos de esa ronda).
    La ronda 1 reutiliza las de la Etapa 4 si existen (mismos rasgos y semillas)."""
    if ronda["clave"] == "ronda1" and previas is not None:
        caras, t = previas
        return caras, t.assign(origen="etapa4 (reutilizada)")
    caras, t = cara.generar_cara(fila["ruta"], fila, n=C.N_CARAS, plantilla=plantilla, pipe=pipe, marg=marg,
                                 tamano=tamano, carpeta=carpeta, semilla_base=ronda["base"])
    return caras, t.assign(origen="generada")


def ronda_propio(fila, ronda, generar=None, carpeta=None):
    """5 caras del modelo propio para una ronda. Devuelve (caras o None, tabla, origen)."""
    n, base = C.N_CARAS, ronda["base"]
    stem = Path(str(fila["nombre"])).stem
    caras, origen = None, "pendiente"
    if generar is not None:
        caras = list(generar(fila["ruta"], fila, n, base))[:n]
        origen = "función GENERAR_PROPIO"
    elif C.CARPETA_PROPIO:
        d = Path(C.CARPETA_PROPIO) / stem / ronda["clave"]
        pngs = sorted(d.glob("*.png"))[:n] if d.is_dir() else []
        if pngs:
            caras = [Image.open(p) for p in pngs]
            origen = f"carpeta {d}"
    if caras is not None:
        caras = [c.convert("RGBA") for c in caras]
        if carpeta is not None:
            carpeta.mkdir(parents=True, exist_ok=True)
            for k, c in enumerate(caras):
                c.save(carpeta / f"cara_{k}.png")
    filas = [dict(k=k, semilla_final=base + k if generar is not None else None, descartada=False,
                  segundos=None, reintentos=0) for k in range(len(caras or []))]
    return caras, pd.DataFrame(filas, columns=["k", "semilla_final", "descartada", "segundos", "reintentos"]), origen


def _celda(c, f, lado):
    """Una cara sobre tablero + pie con semilla y estado."""
    im = Image.new("RGB", (lado, lado + 16), "white")
    p = postproceso.sobre_tablero(c, lado - 8)
    im.paste(p, (4, (lado - p.height) // 2))
    d = ImageDraw.Draw(im)
    s = "" if f is None or pd.isna(f.get("semilla_final")) else f"s{int(f['semilla_final'])}"
    malo = f is not None and bool(f.get("descartada"))
    d.text((4, lado + 2), (s + (" descartada" if malo else "")).strip(), fill=(170, 0, 0) if malo else (60, 60, 60))
    return im


def _pendiente(lado):
    im = Image.new("RGB", (lado, lado + 16), (225, 225, 225))
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, lado - 3, lado - 3], outline=(170, 170, 170))
    d.text((10, lado // 2 - 6), "pendiente", fill=(110, 110, 110))
    return im


def mosaico(bloques, lado=128, ancho_etiqueta=170):
    """bloques: [dict(foto, nombre, cambio, filas=[dict(metodo, ronda (dict de rondas()), caras o None, tabla, origen)])].
    Por persona: la foto a la izquierda y una fila de 5 caras por método y ronda.
    (Texto sin tildes: la fuente por defecto de PIL no las tiene.)"""
    alto_fila = lado + 16
    n = C.N_CARAS
    ancho = lado + 12 + ancho_etiqueta + n * lado
    alto_bloque = [max(lado + 60, len(b["filas"]) * alto_fila) + 14 for b in bloques]
    hoja = Image.new("RGB", (ancho, 30 + sum(alto_bloque)), "white")
    d = ImageDraw.Draw(hoja)
    r = rondas()
    d.text((6, 4), f"{n} caras por metodo. Ronda 1: rasgos de la foto, semillas {r[0]['base']}+k. "
                   f"Ronda 2: con el cambio pedido, mismas semillas.", fill="black")
    d.text((6, 16), f"Variar: mismo pedido que la ronda 2, semillas {r[2]['base']}+k (k = 0..{n - 1}).", fill="black")
    y = 30
    for b, h in zip(bloques, alto_bloque):
        d.line([(0, y), (ancho, y)], fill=(160, 160, 160))
        hoja.paste(cuadrada(b["foto"], lado), (4, y + 6))
        d.text((4, y + lado + 10), str(b["nombre"])[:22], fill="black")
        d.text((4, y + lado + 24), "cambio ronda 2:", fill=(90, 90, 90))
        d.text((4, y + lado + 38), str(b.get("cambio", ""))[:22], fill=(90, 90, 90))
        for i, fila in enumerate(b["filas"]):
            yy = y + 6 + i * alto_fila
            x0 = lado + 12
            color = (0, 70, 140) if fila["metodo"] == "FLUX" else (140, 60, 0)
            d.text((x0, yy + lado // 2 - 14), fila["metodo"], fill=color)
            d.text((x0, yy + lado // 2), fila["ronda"]["nombre"], fill="black")
            if fila["origen"] == "pendiente":
                d.text((x0, yy + lado // 2 + 14), "pendiente", fill=(150, 150, 150))
            x0 += ancho_etiqueta
            t = fila["tabla"].reset_index(drop=True) if fila["tabla"] is not None else None
            for k in range(n):
                if fila["caras"] is None or k >= len(fila["caras"]):
                    celda = _pendiente(lado)
                else:
                    celda = _celda(fila["caras"][k], t.iloc[k] if t is not None and k < len(t) else None, lado)
                hoja.paste(celda, (x0 + k * lado, yy))
        y += h
    return hoja
