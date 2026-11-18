"""Etapa 2: juzgar cada imagen (¿plana?, ¿fondo amarillo?, ¿solo rasgos?, ¿respeta lentes y barba?), detectar la
falla más común, probar 3 variantes del prompt y congelar la mejor.

El juez es automático (CLIP zero-shot + reglas de color) y por eso es una ESTIMACIÓN: las grillas de cada variante
quedan para revisarlas a ojo y config.REVISION_MANUAL corrige cualquier veredicto.
"""
import colorsys
import sys
import types

import numpy as np
import pandas as pd
from PIL import Image

import config as C
import postproceso

_ESTADO = sys.modules.setdefault("_flux_cara_estado", types.ModuleType("_flux_cara_estado"))
if not hasattr(_ESTADO, "clip"):
    _ESTADO.clip = None

FALLAS = ("3d", "fondo", "cara_completa")


# ===================================================================== CLIP
def _clip():
    if _ESTADO.clip is None:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        disp = "cuda:0" if torch.cuda.is_available() else "cpu"
        modelo = CLIPModel.from_pretrained(C.MODELO_CLIP).to(disp).eval()
        _ESTADO.clip = (modelo, CLIPProcessor.from_pretrained(C.MODELO_CLIP), disp)
        print(f"CLIP {C.MODELO_CLIP} cargado en {disp}")
    return _ESTADO.clip


def clip_probs(img, textos):
    """Probabilidad (softmax) de cada texto para la imagen."""
    import torch
    modelo, proc, disp = _clip()
    ent = proc(text=list(textos), images=img, return_tensors="pt", padding=True)
    ent = {k: v.to(disp) for k, v in ent.items()}
    with torch.no_grad():
        logits = modelo(**ent).logits_per_image
    return logits.float().softmax(dim=-1).cpu().numpy()[0]


# ===================================================================== reglas
def fondo_amarillo(a):
    r, g, b = (np.asarray(a["fondo_rgb"], float) / 255).tolist()
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    ok = C.AMARILLO_H[0] <= h <= C.AMARILLO_H[1] and s >= C.AMARILLO_S_MIN and v >= C.AMARILLO_V_MIN \
        and a["borde_fondo"] >= C.BORDE_FONDO_MIN
    return ok, round(h), round(s, 2), round(v, 2)


def fraccion_suave(a):
    """Fracción de píxeles del trazo con degradé suave en L* (sombreado típico de 3D/foto)."""
    gy, gx = np.gradient(a["lab"][..., 0])
    g = np.hypot(gx, gy)
    zona = ndilatar(a["trazo"])
    if not zona.any():
        return 0.0
    lo, hi = C.GRADIENTE_SUAVE
    return float(((g > lo) & (g < hi))[zona].mean())


def ndilatar(m, it=2):
    from scipy import ndimage
    return ndimage.binary_dilation(m, iterations=it)


def _objetivo(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, str):
        return v.strip().lower() in C.VALORES_SI
    return bool(v)


def evaluar(img, fila):
    """Veredicto de una imagen. fila = rasgos de la foto (lentes, barba)."""
    a = postproceso.analizar(img)
    amarillo, h, s, v = fondo_amarillo(a)
    suave = fraccion_suave(a)
    r = dict(amarillo=amarillo, fondo_hsv=f"{h},{s},{v}", borde_fondo=round(a["borde_fondo"], 2),
             cobertura=round(a["cobertura"], 3), suave=round(suave, 3), plana_regla=suave <= C.MAX_FRACCION_SUAVE)
    if C.USAR_CLIP:
        p = clip_probs(img, C.CLIP_TEXTOS["plana"])
        r["plana_clip"] = round(float(p[0]), 2)
        r["plana"] = bool(p.argmax() == 0)
        r["solo_rasgos"] = bool(clip_probs(img, C.CLIP_TEXTOS["solo_rasgos"]).argmax() == 0) \
            and a["cobertura"] <= C.COBERTURA_MAX and a["silueta"] <= C.SILUETA_MAX
        r["lentes_det"] = bool(clip_probs(img, C.CLIP_TEXTOS["lentes"]).argmax() == 0)
        r["barba_det"] = bool(clip_probs(img, C.CLIP_TEXTOS["barba"]).argmax() == 0)
    else:
        r.update(plana=r["plana_regla"], solo_rasgos=a["cobertura"] <= C.COBERTURA_MAX and a["silueta"] <= C.SILUETA_MAX,
                 lentes_det=None, barba_det=None)
    r["silueta"] = round(a["silueta"], 3)
    ok = []
    for k in ("lentes", "barba"):
        obj = _objetivo(fila.get(k))
        det = r[k + "_det"]
        ok.append(True if obj is None or det is None else obj == det)
    r["respeta"] = all(ok)
    return r


def evaluar_lote(tabla, res, variante):
    """tabla = prompts (con rasgos de ELEGIDAS unidos), res = salida de flux.probar."""
    filas = []
    for (_, f), (_, r) in zip(tabla.iterrows(), res.iterrows()):
        ev = evaluar(Image.open(r["salida"]), f)
        ev.update(C.REVISION_MANUAL.get(variante, {}).get(int(f["idx"]), {}))
        filas.append(dict(variante=variante, idx=f["idx"], nombre=f["nombre"], **ev))
    e = pd.DataFrame(filas)
    e["plana_y_amarilla"] = e["plana"] & e["amarillo"]
    return e


def falla_principal(ev):
    cuentas = {"3d": int((~ev["plana"]).sum()), "fondo": int((~ev["amarillo"]).sum()),
               "cara_completa": int((~ev["solo_rasgos"]).sum())}
    falla = max(FALLAS, key=lambda k: cuentas[k])          # empate: el orden de FALLAS
    print(f"Fallas en la Etapa 1 (de {len(ev)}): {cuentas} → la más común: '{falla}'")
    return falla, cuentas


def resumen(ev, prompt):
    return dict(variante=ev["variante"].iloc[0], n=len(ev), planas=int(ev["plana"].sum()),
                fondo_amarillo=int(ev["amarillo"].sum()), planas_y_amarillas=int(ev["plana_y_amarilla"].sum()),
                respetan_lentes_y_barba=int(ev["respeta"].sum()), solo_rasgos=int(ev["solo_rasgos"].sum()),
                cobertura_media=round(float(ev["cobertura"].mean()), 3), prompt=prompt)


COLUMNA_FALLA = {"3d": "planas", "fondo": "fondo_amarillo", "cara_completa": "solo_rasgos"}


def elegir(tabla_prompts, falla=None):
    """Congela la variante que mejor corrige la falla detectada.

    Orden: 1) cumple la meta de planas y amarillas · 2) la columna de la falla (p. ej. solo_rasgos para
    'cara_completa': si no, se congela un prompt que no arregla lo que se vino a arreglar) · 3) respetan lentes
    y barba · 4) planas y amarillas · 5) más trazo (a igual puntaje, la que perdió menos rasgos)."""
    t = tabla_prompts.copy()
    t["_meta"] = t["planas_y_amarillas"] >= C.META_PLANAS_AMARILLAS
    col = COLUMNA_FALLA.get(falla)
    orden = ["_meta"] + ([col] if col else []) + ["respetan_lentes_y_barba", "planas_y_amarillas", "cobertura_media"]
    mejor = t.sort_values(orden, ascending=False, kind="stable").iloc[0].drop("_meta")
    meta = bool(mejor["planas_y_amarillas"] >= C.META_PLANAS_AMARILLAS)
    print(f"Criterio: {' > '.join(o.lstrip('_') for o in orden)}")
    print(f"Congelada: '{mejor['variante']}' · planas y amarillas {mejor['planas_y_amarillas']}/{mejor['n']} "
          f"(meta {C.META_PLANAS_AMARILLAS}) {'✅' if meta else '❌ meta no alcanzada'} · "
          f"solo rasgos {mejor['solo_rasgos']}/{mejor['n']} · "
          f"respetan lentes y barba {mejor['respetan_lentes_y_barba']}/{mejor['n']}")
    return mejor, meta
