"""Etapa 0: explorar PairLegoFace leyendo los archivos reales, sin suponer su estructura.

Flujo (cada paso imprime lo que encontró):
    raiz   = encontrar_dataset()
    inv    = inventario(raiz)                  # todos los archivos + tamaño/modo de las imágenes
    tablas = leer_tablas(raiz)                 # CSV/JSON con sus columnas
    fotos  = tabla_fotos(inv, tablas)          # una fila por foto: partición, estampa, rasgos normalizados
    est    = medir_estampas(fotos, inv)        # tamaño y márgenes de las estampas reales
    sel    = elegir_variadas(fotos)            # 10 fotos de prueba con variedad
"""
import json
import os
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageOps

import config as C

EXT_IMG = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
EXT_TABLA = (".csv", ".tsv", ".json", ".jsonl", ".parquet")
RASGOS = ("lentes", "barba", "bigote", "expresion", "cabello", "color_pelo", "color_cejas")


def carpeta_salida():
    d = C.SALIDA / "datos"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ===================================================================== dónde está el dataset
def encontrar_dataset(raiz=None):
    """Carpeta raíz de PairLegoFace bajo /kaggle/input (o C.RUTA_DATASET si está fijada)."""
    if C.RUTA_DATASET:
        p = Path(C.RUTA_DATASET)
        assert p.exists(), f"RUTA_DATASET no existe: {p}"
        return p
    raiz = Path(raiz or C.ENTRADA)
    assert raiz.exists(), f"No existe {raiz}: ¿agregaste PairLegoFace como Input del notebook?"
    hallados = []
    for actual, dirs, _ in os.walk(raiz):
        nivel = len(Path(actual).relative_to(raiz).parts)
        if nivel >= 4:
            dirs[:] = []
            continue
        for d in dirs:
            if re.search(C.PATRON_NOMBRE_DATASET, d, re.I):
                hallados.append(Path(actual) / d)
    if hallados:
        p = min(hallados, key=lambda h: len(h.parts))           # la menos profunda
        print(f"Dataset: {p}" + (f"  (también: {[str(h) for h in hallados if h != p][:3]})" if len(hallados) > 1 else ""))
        return p
    hijos = [d for d in raiz.iterdir() if d.is_dir()]
    p = hijos[0] if len(hijos) == 1 else raiz
    print(f"⚠ Ninguna carpeta se llama como '{C.PATRON_NOMBRE_DATASET}'. Uso {p}. Fija C.RUTA_DATASET si no es esa.")
    return p


# ===================================================================== inventario de archivos
def inventario(raiz):
    """DataFrame con todos los archivos: ruta, carpeta, ext, bytes y, para imágenes, ancho/alto/modo."""
    filas, leidas = [], Counter()
    for actual, dirs, archivos in os.walk(raiz):
        dirs.sort()
        rel = str(Path(actual).relative_to(raiz)).replace("\\", "/")
        for a in sorted(archivos):
            r = Path(actual) / a
            ext = r.suffix.lower()
            f = dict(ruta=str(r), rel=f"{rel}/{a}", nombre=a, carpeta=rel, ext=ext, bytes=r.stat().st_size,
                     ancho=np.nan, alto=np.nan, modo=None)
            if ext in EXT_IMG and (C.MUESTRA_TAMANOS is None or leidas[rel] < C.MUESTRA_TAMANOS):
                try:
                    with Image.open(r) as im:                    # solo lee la cabecera
                        f["ancho"], f["alto"], f["modo"] = im.width, im.height, im.mode
                        if im.mode == "P" and "transparency" in im.info:
                            f["modo"] = "P+alfa"
                    leidas[rel] += 1
                except Exception as e:                           # noqa: BLE001
                    f["modo"] = f"ilegible: {type(e).__name__}"
            filas.append(f)
    inv = pd.DataFrame(filas)
    print(f"{len(inv)} archivos · {inv['ext'].isin(EXT_IMG).sum()} imágenes · "
          f"{inv['ext'].isin(EXT_TABLA).sum()} tablas · {inv['carpeta'].nunique()} carpetas")
    return inv


def _tamanos(g):
    t = g.dropna(subset=["ancho"])
    if t.empty:
        return ""
    c = Counter(zip(t["ancho"].astype(int), t["alto"].astype(int), t["modo"]))
    return ", ".join(f"{w}x{h} {m} ({n / len(t):.0%})" for (w, h, m), n in c.most_common(3))


def arbol(inv):
    """Resumen por carpeta: cuántos archivos de cada tipo y tamaños de imagen más comunes."""
    lineas = []
    for carpeta, g in inv.groupby("carpeta", sort=True):
        exts = ", ".join(f"{n} {e}" for e, n in g["ext"].value_counts().items())
        t = _tamanos(g)
        lineas.append(f"{carpeta}/  — {exts}" + (f"  · {t}" if t else ""))
    texto = "\n".join(lineas[:C.LINEAS_ARBOL])
    if len(lineas) > C.LINEAS_ARBOL:
        texto += f"\n  … y {len(lineas) - C.LINEAS_ARBOL} carpetas más (sube C.LINEAS_ARBOL para verlas)"
    return texto


# ===================================================================== tablas
def _leer(r):
    ext = Path(r).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(r)
    if ext == ".tsv":
        return pd.read_csv(r, sep="\t")
    if ext == ".jsonl":
        return pd.read_json(r, lines=True)
    if ext == ".parquet":
        return pd.read_parquet(r)
    with open(r, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, list):
        return pd.json_normalize(d)
    if isinstance(d, dict):
        lista = next((v for v in d.values() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
        if lista is not None:
            return pd.json_normalize(lista)
        if all(isinstance(v, dict) for v in d.values()):             # {nombre: {rasgos}}
            return pd.DataFrame.from_dict(d, orient="index").rename_axis("archivo").reset_index()
    raise ValueError("JSON sin forma tabular")


def detectar_columnas(df):
    """{rol: columna} según C.PATRONES_COLUMNA (cada columna va a un solo rol)."""
    usadas, roles = set(), {}
    for rol, patron in C.PATRONES_COLUMNA.items():
        for c in df.columns:
            if c not in usadas and re.search(patron, str(c), re.I):
                roles[rol] = c
                usadas.add(c)
                break
    return roles


def leer_tablas(raiz):
    """Lee cada CSV/JSON del dataset y detecta qué columna es qué."""
    tablas = []
    for r in sorted(Path(raiz).rglob("*")):
        if r.suffix.lower() not in EXT_TABLA or not r.is_file():
            continue
        try:
            df = _leer(r)
        except Exception as e:                                       # noqa: BLE001
            print(f"  {r.relative_to(raiz)}: se omite ({e})")
            continue
        roles = detectar_columnas(df)
        puntos = 3 * ("foto" in roles) + 2 * ("particion" in roles) + ("estampa" in roles) \
            + sum(k in roles for k in ("lentes", "barba", "bigote", "vello", "expresion", "cabello")) \
            + 0.5 * (r.stem.lower() == "pares")
        tablas.append(dict(ruta=r, df=df, roles=roles, puntos=puntos))
        print(f"  {r.relative_to(raiz)}: {len(df)} filas × {len(df.columns)} columnas → {list(df.columns)}")
        print(f"      roles detectados: {roles}")
    if not tablas:
        print("  (sin tablas: la partición y los rasgos saldrán de las carpetas y de C.RASGOS_MANUALES)")
    return sorted(tablas, key=lambda t: -t["puntos"])


# ===================================================================== resolver rutas
class Resolutor:
    """Ruta escrita en una tabla -> archivo real (tal cual, relativa a la tabla o por nombre de archivo)."""

    def __init__(self, rutas):
        self.por_nombre = {}
        for r in rutas:
            self.por_nombre.setdefault(Path(r).name, []).append(Path(r))
        self.ambiguas = set()

    def __call__(self, ruta, base):
        if ruta is None or (isinstance(ruta, float) and np.isnan(ruta)):
            return None
        p = Path(str(ruta).replace("\\", "/"))
        for c in (p, Path(base) / p):
            if c.is_file():
                return c
        hits = self.por_nombre.get(p.name, [])
        if not hits:
            return None
        if len(hits) > 1:
            self.ambiguas.add(p.name)
        # gana la que comparte más carpetas con la ruta escrita; si empatan, la de nombre de carpeta "mayor" (g2 > g1)
        return max(sorted(hits, reverse=True), key=lambda h: sum(x in h.parts for x in p.parts[:-1]))


def imagenes_entrada(raiz=None):
    """Todas las imágenes bajo /kaggle/input (todos los Inputs del notebook), solo rutas."""
    raiz = Path(raiz or C.ENTRADA)
    out = []
    for actual, dirs, archivos in os.walk(raiz):
        out += [os.path.join(actual, a) for a in archivos if a.lower().endswith(EXT_IMG)]
    return out


def describir_tabla(t, muestras=5):
    """Columnas sin rol asignado (valores más comunes) y ejemplos del texto libre."""
    df, roles = t["df"], t["roles"]
    print(f"{t['ruta'].name}: {len(df)} filas · roles {roles}")
    for c in df.columns:
        if c in roles.values() and c not in (roles.get("femenino"), roles.get("edad")):
            continue
        vc = df[c].astype(str).value_counts()
        if len(vc) <= 15:
            print(f"  {c:<15} {vc.to_dict()}")
        else:
            print(f"  {c:<15} {len(vc)} valores distintos, p. ej. {vc.index[:3].tolist()}")
    if "texto" in roles:
        col = roles["texto"]
        print(f"\nEjemplos de '{col}':")
        for x in df[col].dropna().sample(min(muestras, int(df[col].notna().sum())), random_state=0):
            print("  -", str(x)[:400])


def color_cejas(clausula):
    """Color del trozo de la cláusula que menciona las cejas ('white thick eyebrows' -> 'white')."""
    for trozo in re.split(r",| and | with ", clausula):
        if "eyebrow" in trozo or "brow" in trozo:
            for c in C.COLORES_CEJAS:                         # más largo primero
                if re.search(r"\b" + re.escape(c) + r"\b", trozo):
                    return C.MAPEO_COLOR_CEJAS.get(c, c)
    return None


def rasgos_de_texto(texto):
    """Expresión, cabello, color de pelo y de cejas leídos de un texto libre (el prompt con que se generó la foto).
    Si el texto trae la cláusula de rasgos de la cara LEGO (config.PATRON_CLAUSULA_RASGOS), expresión y cejas
    se leen solo de ella."""
    r = dict(expresion=None, cabello=None, color_pelo=None, color_cejas=None, rasgos_lego=None)
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return r
    s = str(texto).lower()
    m = re.search(C.PATRON_CLAUSULA_RASGOS, s)
    clausula = m.group(1).strip() if m else s
    if m:
        r["rasgos_lego"] = clausula
        r["color_cejas"] = color_cejas(clausula)
    r["expresion"] = next((c for c, p in C.PATRONES_EXPRESION_TEXTO if re.search(p, clausula)), None)
    r["cabello"] = next((c for c, p in C.PATRONES_CABELLO_TEXTO if re.search(p, s)), None)
    m = re.search(C.PATRON_COLOR_PELO_TEXTO, s)
    r["color_pelo"] = m.group(1) if m else None
    return r


# ===================================================================== normalizar rasgos
def a_bool(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    if s in C.VALORES_SI:
        return True
    if s in C.VALORES_NO or s == "":
        return False
    return None


def norm_expresion(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().lower()
    if s in C.MAPEO_EXPRESION:
        return C.MAPEO_EXPRESION[s]
    if s in ("sonrisa", "serio", "sorpresa", "neutral"):
        return s
    for cat, patron in C.PATRONES_EXPRESION:
        if re.search(patron, s):
            return cat
    return None


def _texto(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def norm_fila(fila, roles):
    """Fila de la tabla -> dict con lentes, barba, bigote (bool/None), expresion, cabello, color_pelo."""
    g = lambda rol: fila.get(roles[rol]) if rol in roles else None
    r = dict(lentes=None, barba=None, bigote=None, expresion=None, cabello=None, color_pelo=None,
             color_cejas=None, rasgos_lego=None)
    v = g("lentes")
    if v is not None:
        b = a_bool(v)
        r["lentes"] = b if b is not None else not re.search(r"^no|sin|none", str(v).lower())
    for k in ("barba", "bigote"):
        if k in roles:
            r[k] = a_bool(g(k))
    if "vello" in roles:                                     # una sola columna tipo "barba_bigote", "candado", "no"
        s = str(g("vello")).lower()
        if r["barba"] is None:
            r["barba"] = bool(re.search(r"barba|beard|candado|goatee|chiva", s))
        if r["bigote"] is None:
            r["bigote"] = bool(re.search(r"bigote|mous|mustach|candado|goatee", s))
    r["expresion"] = norm_expresion(g("expresion"))
    r["cabello"] = _texto(g("cabello"))
    r["color_pelo"] = _texto(g("color_pelo"))
    r["femenino"] = a_bool(g("femenino")) if "femenino" in roles else None
    r["edad"] = _texto(g("edad"))
    r["fuente_texto"] = []
    if "texto" in roles:                                     # completa lo que la tabla no trae
        for k, v in rasgos_de_texto(g("texto")).items():
            if r[k] is None and v is not None:
                r[k] = v
                if k != "rasgos_lego":
                    r["fuente_texto"].append(k)
    return r


def _manual(nombre, ident):
    m = C.RASGOS_MANUALES
    return m.get(nombre) or (m.get(str(ident)) if ident is not None else None) or {}


def _particion(texto):
    partes = re.split(r"[/\\_\-. ]+", str(texto).lower())
    for nombre, palabras in C.PARTICIONES.items():
        if any(p == w or p.startswith(w) for p in partes for w in palabras):
            return nombre
    return None


def es_estampa(rel, modo, ancho, alto):
    """rel = ruta relativa a la raíz del dataset (así 'PairLegoFace' no cuenta como 'lego')."""
    if re.search(C.PALABRAS_ESTAMPA, str(rel), re.I):
        return True
    alfa = modo in ("RGBA", "LA", "PA", "P+alfa")
    return alfa and pd.notna(ancho) and max(ancho, alto) <= C.LADO_MAX_ESTAMPA


# ===================================================================== tabla de fotos
def tabla_fotos(inv, tablas):
    """Una fila por foto con: ruta, nombre, id, particion, estampa, rasgos normalizados y fuente de los rasgos."""
    res = Resolutor(inv.loc[inv["ext"].isin(EXT_IMG), "ruta"])
    t = tablas[0] if tablas and "foto" in tablas[0]["roles"] else None
    if t is not None:
        df, roles, base = t["df"].copy(), t["roles"], t["ruta"].parent
        print(f"Tabla principal: {t['ruta'].name} · roles {roles}")
        df["_ruta"] = [res(r, base) for r in df[roles["foto"]]]
        res_est = res
        if "estampa" in roles:
            if C.BUSCAR_ESTAMPAS_EN_TODO_INPUT:
                res_est = Resolutor(imagenes_entrada())
            unicas = df[roles["estampa"]].dropna().astype(str).unique()
            halladas = sum(res_est(r, base) is not None for r in unicas)
            print(f"  estampas en '{roles['estampa']}': {len(unicas)} distintas, {halladas} encontradas en disco. "
                  f"Ej.: {list(unicas[:3])}")
            if halladas == 0:
                otros = sorted(d.name for d in C.ENTRADA.iterdir() if d.is_dir()) if C.ENTRADA.exists() else []
                print(f"  ⚠ Ninguna estampa está en {C.ENTRADA}. Inputs presentes: {otros}. "
                      "Agrega como Input el dataset que tiene las caras LEGO (si no, se usa el margen por defecto).")
        n0 = len(df)
        if "ok" in roles:                                     # p. ej. columna "pasa": solo las aprobadas
            ok = df[roles["ok"]].map(a_bool)
            df = df[ok.fillna(False).astype(bool)]
            print(f"  columna '{roles['ok']}': quedan {len(df)} de {n0} filas aprobadas")
        if "id" in roles and df[roles["id"]].duplicated().any():
            antes = len(df)
            orden = roles.get("version", roles["foto"])
            df = df.sort_values(orden, ascending=False).drop_duplicates(roles["id"])
            print(f"  {antes - len(df)} filas con id repetido (p. ej. g1 y g2): se queda la de versión mayor")
        filas = []
        for _, f in df.iterrows():
            ruta = f["_ruta"]
            nombre = Path(str(f[roles["foto"]])).name
            ident = f[roles["id"]] if "id" in roles else None
            rasgos = norm_fila(f, roles)
            man = _manual(nombre, ident)
            est = res_est(f[roles["estampa"]], base) if "estampa" in roles else None
            texto = rasgos.pop("fuente_texto")
            filas.append(dict(ruta=str(ruta) if ruta else None, nombre=nombre, id=ident,
                              particion=_particion(f[roles["particion"]]) if "particion" in roles else _particion(ruta),
                              particion_original=f[roles["particion"]] if "particion" in roles else None,
                              estampa=str(est) if est else None,
                              pieza=f["pieza"] if "pieza" in f else (Path(str(est)).stem if est else None),
                              **{**rasgos, **{k: v for k, v in man.items() if k in RASGOS + ("femenino", "edad")}},
                              fuente_rasgos="tabla" + ("+texto(" + ",".join(texto) + ")" if texto else "")
                              + ("+manual" if man else "")))
        fotos = pd.DataFrame(filas)
        faltan = fotos["ruta"].isna().sum()
        if faltan:
            print(f"  ⚠ {faltan} fotos de la tabla no se encontraron en disco (se ignoran). "
                  f"Ej.: {fotos.loc[fotos['ruta'].isna(), 'nombre'].head(3).tolist()}")
        if res.ambiguas:
            print(f"  ⚠ {len(res.ambiguas)} nombres de archivo están en más de una carpeta; se eligió por ruta. "
                  f"Ej.: {sorted(res.ambiguas)[:3]}")
        fotos = fotos.dropna(subset=["ruta"]).drop_duplicates("ruta").reset_index(drop=True)
    else:
        print("Sin tabla con columna de foto: las fotos salen de las carpetas y los rasgos de C.RASGOS_MANUALES")
        img = inv[inv["ext"].isin(EXT_IMG)]
        img = img[[not es_estampa(r, m, w, h) for r, m, w, h in zip(img["rel"], img["modo"], img["ancho"], img["alto"])]]
        filas = []
        for r, nombre, carpeta in zip(img["ruta"], img["nombre"], img["carpeta"]):
            man = _manual(nombre, Path(nombre).stem)
            base = dict.fromkeys(RASGOS + ("femenino", "edad"))
            base.update({k: v for k, v in man.items() if k in RASGOS + ("femenino", "edad")})
            filas.append(dict(ruta=r, nombre=nombre, id=Path(nombre).stem, particion=_particion(carpeta),
                              particion_original=carpeta, estampa=None, pieza=None, **base,
                              fuente_rasgos="manual" if man else "ninguna"))
        fotos = pd.DataFrame(filas)
    resumen_fotos(fotos)
    return fotos


def resumen_fotos(fotos):
    print(f"\n{len(fotos)} fotos encontradas")
    print("Particiones:", fotos["particion"].fillna("(sin partición)").value_counts().to_dict())
    if fotos["particion_original"].notna().any():
        print("  valores originales:", fotos["particion_original"].astype(str).value_counts().head(8).to_dict())
    print("Rasgos (conteo por valor; None = sin dato):")
    for k in RASGOS + ("femenino", "edad"):
        vc = fotos[k].astype(object).where(fotos[k].notna(), None).map(repr).value_counts()
        print(f"  {k:<11} {vc.head(8).to_dict()}")
    print("Fuente de los rasgos:", fotos["fuente_rasgos"].value_counts().to_dict())
    if "rasgos_lego" in fotos and fotos["rasgos_lego"].notna().any():
        trozos = Counter(t.strip() for c in fotos["rasgos_lego"].dropna() for t in re.split(r",| and ", c)
                         if t.strip() and "brow" not in t)
        print("Frases más comunes de la cara LEGO (sin cejas):", dict(trozos.most_common(30)))
        sin = fotos[fotos["expresion"].isna() & fotos["rasgos_lego"].notna()]
        if len(sin):
            print(f"  {len(sin)} fotos sin expresión reconocida. Ej. de su cláusula (ajusta config.PATRONES_EXPRESION_TEXTO):")
            for c in sin["rasgos_lego"].drop_duplicates().head(10):
                print("   ·", c)


# ===================================================================== estampas reales y márgenes
def marco(h, w, frac):
    b = max(1, int(round(min(h, w) * frac)))
    m = np.zeros((h, w), bool)
    m[:b] = m[-b:] = True
    m[:, :b] = m[:, -b:] = True
    return m


def mascara_estampa(ruta):
    """Estampa -> (máscara bool del trazo, cómo se obtuvo). Usa el alfa; si no hay, distancia Lab al fondo."""
    im = ImageOps.exif_transpose(Image.open(ruta))
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        a = np.asarray(im.convert("RGBA"))[..., 3]
        if a.min() < 128:
            return a > 127, "alfa"
    from skimage.color import rgb2lab
    lab = rgb2lab(np.asarray(im.convert("RGB")))
    borde = marco(*lab.shape[:2], C.BORDE_FONDO)
    fondo = np.median(lab[borde], axis=0)
    return np.linalg.norm(lab - fondo, axis=-1) > C.UMBRAL_LAB_ESTAMPA, "fondo_lab"


def rutas_estampas(fotos, inv):
    """Estampas únicas: las que referencia la tabla; si no hay, las imágenes que parecen estampas."""
    if fotos["estampa"].notna().any():
        return sorted(fotos["estampa"].dropna().unique()), "tabla"
    img = inv[inv["ext"].isin(EXT_IMG)]
    sel = [r for r, rel, m, w, h in zip(img["ruta"], img["rel"], img["modo"], img["ancho"], img["alto"])
           if es_estampa(rel, m, w, h)]
    return sorted(set(sel)), "carpetas"


def medir_estampas(fotos, inv):
    """Tamaño y márgenes (px y fracción) de cada estampa real. Guarda etapa0/margenes.json."""
    rutas, origen = rutas_estampas(fotos, inv)
    filas = []
    for r in rutas:
        try:
            m, como = mascara_estampa(r)
        except Exception as e:                                      # noqa: BLE001
            filas.append(dict(ruta=r, error=f"{type(e).__name__}: {e}"))
            continue
        h, w = m.shape
        ys, xs = np.nonzero(m)
        f = dict(ruta=r, ancho=w, alto=h, mascara=como, cobertura=m.mean())
        if ys.size:
            px = dict(arriba=ys.min(), abajo=h - 1 - ys.max(), izquierda=xs.min(), derecha=w - 1 - xs.max())
            f.update({f"{k}_px": v for k, v in px.items()})
            f.update({k: px[k] / (h if k in ("arriba", "abajo") else w) for k in px})
        filas.append(f)
    est = pd.DataFrame(filas) if filas else pd.DataFrame(columns=["ruta"])
    lados = ("arriba", "abajo", "izquierda", "derecha")
    info = dict(n=len(rutas), origen=origen)
    if len(est) and "ancho" in est and est["ancho"].notna().any():
        validas = est.dropna(subset=["arriba"]) if "arriba" in est else est.iloc[0:0]
        cuenta = Counter(zip(est["ancho"].dropna().astype(int), est["alto"].dropna().astype(int)))
        (w, h), n = cuenta.most_common(1)[0]
        info.update(tamano_dominante=[int(w), int(h)], fraccion_tamano_dominante=n / len(est),
                    tamanos=[[int(a), int(b), int(c)] for (a, b), c in cuenta.most_common(5)],
                    n_vacias=int(len(est) - len(validas)),
                    n_error=int(est["error"].notna().sum()) if "error" in est else 0,
                    mascara=est["mascara"].value_counts().to_dict(),
                    cobertura_media=float(est["cobertura"].mean()))
        if len(validas):
            info["fraccion"] = {k: float(validas[k].mean()) for k in lados}
            info["fraccion_mediana"] = {k: float(validas[k].median()) for k in lados}
            info["px"] = {k: float(validas[f"{k}_px"].mean()) for k in lados}
    if "fraccion" not in info:
        info["fraccion"] = dict(C.MARGEN_POR_DEFECTO)
        info["margen_por_defecto"] = True
        print(f"⚠ No hay estampas reales medibles: se usará el margen por defecto {C.MARGEN_POR_DEFECTO}")
    info["tamano_final"] = list(C.TAMANO_FINAL or info.get("tamano_dominante") or C.TAMANO_POR_DEFECTO)
    d = carpeta_salida()
    est.to_csv(d / "estampas.csv", index=False)
    (d / "margenes.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{info['n']} estampas reales (desde {origen})")
    if "tamano_dominante" in info:
        w, h = info["tamano_dominante"]
        print(f"  tamaño más común: {w} de ancho × {h} de alto ({info['fraccion_tamano_dominante']:.0%}); "
              f"otros: {info['tamanos'][1:]}")
        print(f"  trazo obtenido por: {info['mascara']} · vacías: {info['n_vacias']} · "
              f"cobertura media del trazo: {info['cobertura_media']:.1%}")
    if not info.get("margen_por_defecto"):
        print("  margen medio  " + " · ".join(f"{k} {info['fraccion'][k]:.1%} ({info['px'][k]:.1f} px)" for k in lados))
        print("  margen mediano " + " · ".join(f"{k} {info['fraccion_mediana'][k]:.1%}" for k in lados))
    print(f"  → tamaño final que usará el post-proceso: {info['tamano_final'][0]}×{info['tamano_final'][1]} (ancho × alto)")
    return est, info


# ===================================================================== elegir 10 fotos variadas
def pares_rasgo(fila):
    return {(k, v) for k, v in ((k, fila.get(k)) for k, _ in C.VARIEDAD) if v is not None and not
            (isinstance(v, float) and np.isnan(v))} & set(C.VARIEDAD)


def elegir_variadas(fotos, n=None, semilla=None):
    """n fotos de la partición de prueba que cubran C.VARIEDAD de forma pareja (y caras LEGO distintas)."""
    n = n or C.N_FOTOS
    semilla = C.SEMILLA if semilla is None else semilla
    prueba = fotos[fotos["particion"] == "prueba"]
    if prueba.empty:
        print("⚠ No hay partición de prueba: elijo entre todas las fotos. Revisa C.PARTICIONES.")
        prueba = fotos
    con_rasgos = prueba[prueba[[k for k in RASGOS[:4]]].notna().any(axis=1)]
    if con_rasgos.empty:
        print("⚠ Ninguna foto de prueba tiene rasgos (ni del dataset ni de C.RASGOS_MANUALES): "
              "elijo al azar. Mira la hoja de contactos y completa C.RASGOS_MANUALES.")
    pool = (con_rasgos if len(con_rasgos) >= n else prueba).reset_index(drop=True)
    orden = list(range(len(pool)))
    random.Random(semilla).shuffle(orden)
    elegidas = [i for i in orden if pool.loc[i, "nombre"] in C.FOTOS_FORZADAS]
    conteo, vistos = Counter(), {c: set() for c in C.NOVEDAD}

    def marcar(i):
        conteo.update(pares_rasgo(pool.loc[i]))
        for c in C.NOVEDAD:
            vistos[c].add(pool.loc[i].get(c))

    for i in elegidas:
        marcar(i)
    while len(elegidas) < min(n, len(pool)):
        def puntaje(i):
            f = pool.loc[i]
            return sum(1 / (1 + conteo[p]) for p in pares_rasgo(f)) \
                + sum(0.5 * (bool(pd.notna(f.get(c))) and f.get(c) not in vistos[c]) for c in C.NOVEDAD)
        mejor = max((i for i in orden if i not in elegidas), key=puntaje)   # empate: el primero del orden barajado
        elegidas.append(mejor)
        marcar(mejor)
    sel = pool.loc[elegidas].reset_index(drop=True)
    sel.insert(0, "idx", range(len(sel)))
    print(f"{len(sel)} fotos elegidas de {len(pool)} candidatas (semilla {semilla}). Cobertura:")
    for p in C.VARIEDAD:
        print(f"  {p[0]}={p[1]!r:<12} {conteo[p]} {'✅' if conteo[p] else '— no hay en prueba'}")
    sel.to_csv(carpeta_salida() / "fotos_elegidas.csv", index=False)
    return sel


# ===================================================================== grillas
def cuadrada(ruta, lado):
    im = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    return ImageOps.fit(im, (lado, lado), Image.LANCZOS)


def texto_rasgos(f):
    partes = []
    if f.get("lentes") in (True,):
        partes.append("lentes")
    if f.get("barba") in (True,):
        partes.append("barba")
    if f.get("bigote") in (True,):
        partes.append("bigote")
    if f.get("femenino") in (True,):
        partes.append("mujer")
    for k in ("expresion", "cabello", "edad", "color_cejas"):
        if f.get(k) is not None and not (isinstance(f.get(k), float) and np.isnan(f.get(k))):
            partes.append(str(f[k]))
    return " ".join(partes) or "(sin rasgos)"


def grilla(fotos, cols=5, lado=200, con_estampa=None):
    """Foto (y su estampa real al lado, si existe) con el índice y los rasgos debajo."""
    if con_estampa is None:
        con_estampa = bool(fotos["estampa"].notna().any()) if "estampa" in fotos else False
    ancho_celda = lado * (2 if con_estampa else 1)
    filas = (len(fotos) + cols - 1) // cols
    hoja = Image.new("RGB", (cols * ancho_celda, filas * (lado + 30)), "white")
    d = ImageDraw.Draw(hoja)
    for k, (_, f) in enumerate(fotos.iterrows()):
        x, y = (k % cols) * ancho_celda, (k // cols) * (lado + 30)
        hoja.paste(cuadrada(f["ruta"], lado), (x, y))
        if con_estampa and f.get("estampa"):
            e = Image.open(f["estampa"]).convert("RGBA")
            e.thumbnail((lado - 10, lado - 10), Image.NEAREST)
            fondo = Image.new("RGBA", (lado, lado), (235, 235, 235, 255))
            fondo.alpha_composite(e, ((lado - e.width) // 2, (lado - e.height) // 2))
            hoja.paste(fondo.convert("RGB"), (x + lado, y))
        d.text((x + 4, y + lado + 2), f"#{f.get('idx', k)} {str(f['nombre'])[:28]}", fill="black")
        d.text((x + 4, y + lado + 15), texto_rasgos(f)[:40], fill=(0, 90, 160))
    return hoja


def hoja_estampas(rutas, n=24, cols=8, escala=2):
    """Muestra de estampas reales sobre damero (para ver alfa y formato)."""
    rutas = list(rutas)[:n]
    if not rutas:
        return None
    ims = [Image.open(r).convert("RGBA") for r in rutas]
    w = max(i.width for i in ims) * escala
    h = max(i.height for i in ims) * escala
    filas = (len(ims) + cols - 1) // cols
    hoja = Image.new("RGBA", (cols * w, filas * h), "white")
    for k, im in enumerate(ims):
        x, y = (k % cols) * w, (k // cols) * h
        cuadros = Image.new("RGBA", (w, h))
        dd = ImageDraw.Draw(cuadros)
        for i in range(0, w, 8):
            for j in range(0, h, 8):
                dd.rectangle([i, j, i + 7, j + 7], fill=(200, 200, 200, 255) if (i + j) // 8 % 2 else (250, 250, 250, 255))
        cuadros.alpha_composite(im.resize((im.width * escala, im.height * escala), Image.NEAREST))
        hoja.paste(cuadros, (x, y))
    return hoja.convert("RGB")


# ===================================================================== informe
def guardar_informe(raiz, inv, tablas, fotos, info_estampas, sel):
    d = carpeta_salida()
    inv.to_csv(d / "inventario.csv", index=False)
    fotos.to_csv(d / "fotos.csv", index=False)
    informe = dict(
        dataset=str(raiz),
        archivos=int(len(inv)),
        imagenes=int(inv["ext"].isin(EXT_IMG).sum()),
        tablas=[dict(archivo=str(t["ruta"].relative_to(raiz)), filas=len(t["df"]),
                     columnas=[str(c) for c in t["df"].columns], roles={k: str(v) for k, v in t["roles"].items()})
                for t in tablas],
        fotos=int(len(fotos)),
        particiones=fotos["particion"].fillna("(sin)").value_counts().to_dict(),
        rasgos_disponibles=[k for k in RASGOS if fotos[k].notna().any()],
        estampas=info_estampas,
        elegidas=sel["nombre"].tolist(),
    )
    (d / "informe.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return informe


def verificar(informe):
    """Autoverificación de la Etapa 0: imprime ✅/❌ y devuelve True si todo está bien."""
    d = carpeta_salida()
    pruebas = [
        ("se encontró el dataset", Path(informe["dataset"]).exists()),
        ("hay fotos", informe["fotos"] > 0),
        ("hay partición de prueba", informe["particiones"].get("prueba", 0) > 0),
        (f"se eligieron {C.N_FOTOS} fotos", len(informe["elegidas"]) == C.N_FOTOS),
        ("hay rasgos (dataset o manuales)", bool(informe["rasgos_disponibles"])),
        ("márgenes medidos en estampas reales", not informe["estampas"].get("margen_por_defecto")),
        ("grilla guardada", (d / "grilla_10.jpg").exists()),
        ("margenes.json guardado", (d / "margenes.json").exists()),
    ]
    for nombre, ok in pruebas:
        print(("✅ " if ok else "❌ ") + nombre)
    return all(ok for _, ok in pruebas)
