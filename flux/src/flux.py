"""Etapa 1: FLUX.2-klein-4B (sin entrenar) foto -> estampa de cara sobre fondo amarillo.

    pipe = flux.cargar()                       # UNA sola vez; los reload del módulo no lo pierden
    tabla = flux.prompts(ELEGIDAS)             # prompt de cada foto según sus rasgos (config.FRASES)
    res = flux.probar(pipe, tabla, "etapa1")   # genera, guarda PNG y mide el tiempo por imagen
    flux.grilla_pares(tabla, res)              # foto | resultado

Lo verificado en la ficha oficial está anotado en config.py (sección Etapa 1).
"""
import inspect
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import config as C
from dataset import cuadrada, texto_rasgos

# El pipeline vive fuera del módulo: importlib.reload(flux) no obliga a volver a cargar 16 GB.
_ESTADO = sys.modules.setdefault("_flux_cara_estado", types.ModuleType("_flux_cara_estado"))
if not hasattr(_ESTADO, "pipe"):
    _ESTADO.pipe = None


def carpeta(etapa):
    d = C.SALIDA / etapa
    d.mkdir(parents=True, exist_ok=True)
    return d


# ===================================================================== carga
def _gpus():
    import torch
    if not torch.cuda.is_available():
        return "sin GPU"
    return " · ".join(f"cuda:{i} {torch.cuda.get_device_name(i)} "
                      f"{torch.cuda.memory_allocated(i) / 2**30:.1f}/{torch.cuda.get_device_properties(i).total_memory / 2**30:.1f} GiB"
                      for i in range(torch.cuda.device_count()))


def cargar(forzar=False):
    """Carga el pipeline una sola vez (DiffusionPipeline.from_pretrained con device_map) y lo reutiliza."""
    if _ESTADO.pipe is not None and not forzar:
        print("Pipeline ya cargado: se reutiliza.")
        return _ESTADO.pipe
    import torch
    import diffusers
    from diffusers import DiffusionPipeline
    print("diffusers", diffusers.__version__, "· torch", torch.__version__)
    print("GPUs antes:", _gpus())
    kw = dict(torch_dtype=getattr(torch, C.DTYPE))
    if C.DEVICE_MAP:
        kw["device_map"] = C.DEVICE_MAP
    if C.MAX_MEMORY:
        kw["max_memory"] = C.MAX_MEMORY
    t = time.time()
    pipe = DiffusionPipeline.from_pretrained(C.MODELO_ID, **kw)
    print(f"{type(pipe).__name__} cargado en {time.time() - t:.0f} s · {kw}")
    mapa = getattr(pipe, "hf_device_map", None)
    print("hf_device_map:", mapa)
    if mapa and any(str(v) in ("cpu", "disk") for v in mapa.values()):
        print("⚠ Hay componentes en CPU/disco: va a ser lento. Revisa config.MAX_MEMORY.")
    print("GPUs después:", _gpus())
    try:
        pipe.set_progress_bar_config(disable=True)
    except Exception:
        pass
    _ESTADO.pipe = pipe
    return pipe


def verificar_firma(pipe):
    """Comprueba en la versión instalada que __call__ acepta la imagen de referencia y los parámetros que usamos."""
    params = inspect.signature(pipe.__call__).parameters
    faltan = [p for p in ("prompt", "image", "height", "width", "num_inference_steps", "guidance_scale", "generator")
              if p not in params]
    ok = not faltan
    print(("✅" if ok else "❌") + f" {type(pipe).__name__}.__call__ acepta image= (referencia)"
          + ("" if ok else f" · faltan: {faltan}"))
    if "image" in params:
        print("   anotación de image:", params["image"].annotation)
    return ok


# ===================================================================== prompt
def _vacio(v):
    return v is None or (isinstance(v, float) and np.isnan(v))


def _si(v):
    if _vacio(v):
        return None
    if isinstance(v, str):
        return v.strip().lower() in C.VALORES_SI
    return bool(v)


def frases(fila):
    """Rasgos de una foto -> frases del prompt + qué se rellenó por defecto."""
    defecto = []
    lentes = _si(fila.get("lentes"))
    if lentes is None:
        defecto.append("lentes")
    barba, bigote = _si(fila.get("barba")), _si(fila.get("bigote"))
    if barba is None or bigote is None:
        defecto.append("vello")
    vello = [C.FRASES["barba"]] * bool(barba) + [C.FRASES["bigote"]] * bool(bigote)
    expr = fila.get("expresion")
    if _vacio(expr) or expr not in C.FRASES["expresion"]:
        defecto.append("expresion")
        expr = C.EXPRESION_POR_DEFECTO
    color = fila.get("color_cejas")
    if _vacio(color):
        defecto.append("color")
        color = C.COLOR_CEJAS_POR_DEFECTO
    return dict(expresion=C.FRASES["expresion"][expr], lentes=C.FRASES["lentes"][bool(lentes)],
                vello=C.UNIR_VELLO.join(vello) if vello else C.FRASE_SIN_VELLO, color=color), defecto


def prompts(fotos, plantilla=None):
    """Tabla con el prompt de cada foto (idx, nombre, ruta, rasgos, frases, prompt, por_defecto)."""
    plantilla = plantilla or C.PROMPT_BASE
    filas = []
    for k, (_, f) in enumerate(fotos.iterrows()):
        fr, defecto = frases(f)
        filas.append(dict(idx=f.get("idx", k), nombre=f["nombre"], ruta=f["ruta"], rasgos=texto_rasgos(f),
                          **{c: f.get(c) for c in ("lentes", "barba", "bigote", "femenino", "expresion", "color_cejas")},
                          rasgos_lego=f.get("rasgos_lego"), **{"frase_" + a: b for a, b in fr.items()},
                          prompt=plantilla.format(**fr), por_defecto=",".join(defecto)))
    t = pd.DataFrame(filas)
    n = (t["por_defecto"] != "").sum()
    print(f"{len(t)} prompts armados" + (f" · {n} con algún rasgo por defecto (columna por_defecto)" if n else ""))
    return t


# ===================================================================== generar
def _sincronizar():
    import torch
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            torch.cuda.synchronize(i)


def generar(pipe, ruta_foto, prompt, semilla):
    """Una imagen: foto de referencia (recorte cuadrado) + prompt. Devuelve (PIL RGB, segundos)."""
    import torch
    ref = cuadrada(ruta_foto, C.LADO_REFERENCIA)
    gen = torch.Generator(C.GENERADOR_EN).manual_seed(int(semilla))
    _sincronizar()
    t = time.perf_counter()
    salida = pipe(prompt=prompt, image=ref, height=C.ALTO, width=C.ANCHO, num_inference_steps=C.PASOS,
                  guidance_scale=C.GUIA, generator=gen)
    _sincronizar()
    return salida.images[0].convert("RGB"), time.perf_counter() - t


def probar(pipe, tabla, etapa, etiqueta="base", semilla=None):
    """Genera una imagen por fila de la tabla; guarda etapa/etiqueta/idx_nombre.png. Devuelve la tabla con tiempos."""
    semilla = C.SEMILLA_FLUX if semilla is None else semilla
    d = carpeta(etapa) / "crudas" / etiqueta          # crudas/ no va al zip (pesan); las grillas sí
    d.mkdir(parents=True, exist_ok=True)
    filas = []
    for _, f in tabla.iterrows():
        im, s = generar(pipe, f["ruta"], f["prompt"], semilla)
        destino = d / f"{f['idx']:02d}_{Path(f['nombre']).stem}.png"
        im.save(destino)
        a = np.asarray(im)
        filas.append(dict(idx=f["idx"], nombre=f["nombre"], semilla=semilla, segundos=round(s, 2), salida=str(destino),
                          ancho=im.width, alto=im.height, media_rgb=[round(x) for x in a.reshape(-1, 3).mean(0)]))
        print(f"  #{f['idx']} {f['nombre']}: {s:.1f} s")
    r = pd.DataFrame(filas)
    t = r["segundos"]
    print(f"Tiempo por imagen: primera {t.iloc[0]:.1f} s (incluye calentamiento) · resto media {t.iloc[1:].mean():.1f} s "
          f"(mín {t.iloc[1:].min():.1f}, máx {t.iloc[1:].max():.1f}) · total {t.sum():.0f} s" if len(t) > 1 else
          f"Tiempo: {t.iloc[0]:.1f} s")
    return r


# ===================================================================== grilla
def grilla_pares(tabla, res, cols=5, lado=200):
    """Foto | resultado, con índice, rasgos y tiempo debajo."""
    res = res.set_index("idx")
    ancho = lado * 2 + 8
    filas = (len(tabla) + cols - 1) // cols
    hoja = Image.new("RGB", (cols * ancho, filas * (lado + 44)), "white")
    d = ImageDraw.Draw(hoja)
    for k, (_, f) in enumerate(tabla.iterrows()):
        x, y = (k % cols) * ancho, (k // cols) * (lado + 44)
        hoja.paste(cuadrada(f["ruta"], lado), (x, y))
        r = res.loc[f["idx"]]
        hoja.paste(cuadrada(r["salida"], lado), (x + lado, y))
        d.text((x + 4, y + lado + 2), f"#{f['idx']} {str(f['nombre'])[:22]}  {r['segundos']:.1f}s", fill="black")
        d.text((x + 4, y + lado + 15), str(f["rasgos"])[:44], fill=(0, 90, 160))
        extra = f"cejas {f['frase_color']}" + (f" · defecto: {f['por_defecto']}" if f["por_defecto"] else "")
        d.text((x + 4, y + lado + 28), extra[:44], fill=(150, 60, 0))
    return hoja


# ===================================================================== verificación
def verificar(tabla, res, firma_ok):
    chequeos = [
        ("pipeline acepta image= (foto de referencia)", firma_ok),
        (f"{len(tabla)} imágenes generadas", len(res) == len(tabla) and len(res) > 0),
        (f"tamaño {C.ANCHO}x{C.ALTO}", bool(((res["ancho"] == C.ANCHO) & (res["alto"] == C.ALTO)).all())),
        ("ninguna imagen negra/vacía (NaN en fp16 da negro)", all(max(m) > 10 for m in res["media_rgb"])),
        ("tiempo medido en todas", bool(res["segundos"].notna().all())),
    ]
    for texto, ok in chequeos:
        print(("✅ " if ok else "❌ ") + texto)
    return all(ok for _, ok in chequeos)
