"""Etapa 4: generar_cara(foto, rasgos, n=5) -> n estampas RGBA.

Cinco semillas (SEMILLA_FLUX + k). Si el guardrail descarta una, se reintenta con semilla + 1000, máximo 2 veces;
si las 3 se descartan, queda la última marcada como descartada.
"""
import time
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

import config as C
import flux
import postproceso


def generar_cara(foto, rasgos, n=None, plantilla=None, pipe=None, marg=None, tamano=None, carpeta=None,
                 semilla_base=None):
    """foto: ruta. rasgos: dict/Series con lentes, barba, bigote, expresion, color_cejas.
    semilla_base: semilla de la cara k=0 (por defecto SEMILLA_FLUX); la Etapa 6 la cambia para la ronda 2.
    Devuelve (lista de n PIL RGBA, DataFrame con semilla, intentos, descartes y segundos por cara)."""
    n = n or C.N_CARAS
    semilla_base = C.SEMILLA_FLUX if semilla_base is None else semilla_base
    plantilla = plantilla or C.PROMPT_BASE
    pipe = pipe or flux.cargar()
    if marg is None or tamano is None:
        marg, tamano, _ = postproceso.margenes(ruta_json=C.SALIDA / "datos" / "margenes.json")
    fr, defecto = flux.frases(rasgos)
    prompt = plantilla.format(**fr)
    caras, filas = [], []
    t_total = time.perf_counter()
    for k in range(n):
        base = semilla_base + k
        intentos, seg = [], 0.0
        for r in range(C.MAX_REINTENTOS + 1):
            semilla = base + r * C.SALTO_REINTENTO
            img, s = flux.generar(pipe, foto, prompt, semilla)
            seg += s
            res = postproceso.a_rgba(img, marg, tamano)
            intentos.append(f"{semilla}:{'descartada (' + res['motivo'] + ')' if res['descartada'] else 'ok'}")
            if not res["descartada"]:
                break
        rgba = res["rgba"] if res["rgba"] is not None else Image.new("RGBA", tamano, (0, 0, 0, 0))
        caras.append(rgba)
        fila = dict(k=k, semilla_final=semilla, reintentos=len(intentos) - 1, descartada=res["descartada"],
                    motivo=res["motivo"], cobertura=round(res["cobertura"], 3), segundos=round(seg, 2),
                    intentos=" | ".join(intentos), por_defecto=",".join(defecto))
        if carpeta is not None:
            carpeta.mkdir(parents=True, exist_ok=True)
            fila["png"] = str(carpeta / f"cara_{k}_s{semilla}.png")
            rgba.save(fila["png"])
            (carpeta / "crudas").mkdir(exist_ok=True)
            img.save(carpeta / "crudas" / f"cruda_{k}_s{semilla}.png")
        filas.append(fila)
    tabla = pd.DataFrame(filas)
    tabla.attrs["segundos_total"] = time.perf_counter() - t_total
    tabla.attrs["prompt"] = prompt
    return caras, tabla


def sobre_amarillo(rgba, lado=224):
    """Estampa RGBA centrada sobre amarillo liso (cuadrada), para juzgarla con CLIP."""
    W, H = rgba.size
    L = max(W, H) + 40
    fondo = Image.new("RGBA", (L, L), (*C.AMARILLO_COMPUESTO, 255))
    fondo.alpha_composite(rgba.convert("RGBA"), ((L - W) // 2, (L - H) // 2))
    return fondo.convert("RGB").resize((lado, lado), Image.BICUBIC)


def puntuar(caras, tabla, rasgos):
    """Por cada cara: ¿tiene lentes? ¿tiene vello (barba o bigote)? según CLIP, y cuántos coinciden con la foto."""
    import ajuste
    obj = dict(lentes=flux._si(rasgos.get("lentes")))
    barba, bigote = flux._si(rasgos.get("barba")), flux._si(rasgos.get("bigote"))
    obj["vello"] = None if barba is None and bigote is None else bool(barba or bigote)
    filas = []
    for k, (c, (_, f)) in enumerate(zip(caras, tabla.iterrows())):
        fila = dict(k=k, semilla=f["semilla_final"], descartada=bool(f["descartada"]), coinciden=0, de=0)
        img = sobre_amarillo(c)
        for r in ("lentes", "vello"):
            p = float(ajuste.clip_probs(img, C.CLIP_TEXTOS[r])[0])
            fila[f"p_{r}"] = round(p, 2)
            if obj[r] is not None:
                fila["de"] += 1
                fila["coinciden"] += int((p > C.UMBRAL_RASGO_CLIP) == obj[r])
        filas.append(fila)
    return pd.DataFrame(filas)


def mejor(caras, tabla, rasgos=None):
    """Cara para la minifig: entre las no descartadas, la que más rasgos de la foto respeta (lentes y vello facial,
    juzgados con CLIP); a igual puntaje, la de menor k. Sin CLIP o sin rasgos: la primera no descartada.
    Devuelve (cara, índice, tabla de puntajes o None)."""
    ok = tabla.index[~tabla["descartada"]]
    candidatas = list(ok) if len(ok) else list(tabla.index)
    if rasgos is None or not C.USAR_CLIP:
        return caras[int(candidatas[0])], int(candidatas[0]), None
    p = puntuar(caras, tabla, rasgos)
    p["elegible"] = p["k"].isin(candidatas)
    i = int(p[p["elegible"]].sort_values(["coinciden", "k"], ascending=[False, True]).iloc[0]["k"])
    p["elegida"] = p["k"] == i
    return caras[i], i, p.drop(columns="elegible")


def tira(foto, caras, tabla, lado=160):
    """Foto + sus n estampas (sobre tablero), con semilla y estado."""
    hoja = Image.new("RGB", ((len(caras) + 1) * lado, lado + 30), "white")
    hoja.paste(flux.cuadrada(foto, lado), (0, 0))
    d = ImageDraw.Draw(hoja)
    for k, (c, (_, f)) in enumerate(zip(caras, tabla.iterrows()), start=1):
        p = postproceso.sobre_tablero(c, lado - 8)
        hoja.paste(p, (k * lado + 4, (lado - p.height) // 2))
        d.text((k * lado + 4, lado + 2), f"s{f['semilla_final']} · {f['segundos']:.1f}s", fill="black")
        d.text((k * lado + 4, lado + 15), "descartada" if f["descartada"] else f"ok (+{f['reintentos']} reint.)",
               fill=(170, 0, 0) if f["descartada"] else (0, 120, 0))
    d.text((4, lado + 2), Path(str(foto)).name[:24], fill="black")
    return hoja
