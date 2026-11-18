"""Test del notebook completo (Datos + Etapas 1–5) sin GPU: FLUX y CLIP falsos (tests/falsos.py), datasets de
juguete y la librería LDraw REAL (complete.zip; ruta en FLUX_CARA_LDRAW_ZIP).

A) como PairLegoFace: pares.csv con prompts reales, ids g1/g2, 'pasa', estampas RGBA en OTRO Input
B) sin tablas: carpetas train/test, estampas sin alfa sobre amarillo, rasgos a mano
C) como A pero sin estampas (márgenes por defecto)

Uso:  FLUX_CARA_LDRAW_ZIP=/ruta/complete.zip python tests/test_notebook.py
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import falsos  # noqa: E402

NB = AQUI.parent / "flux_cara_ldraw.ipynb"
rng = np.random.default_rng(0)


def foto(r):
    r.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rng.integers(0, 255, (300, 240, 3), dtype=np.uint8)).save(r)


def estampa(r, alfa=True, arriba=20, abajo=24, izq=15, der=17, W=128, H=118):
    r.parent.mkdir(parents=True, exist_ok=True)
    if alfa:
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        col = (20, 20, 20, 255)
    else:
        im = Image.new("RGB", (W, H), (250, 200, 40))
        col = (20, 20, 20)
    d = ImageDraw.Draw(im)
    d.rectangle([izq, arriba, W - 1 - der, arriba + 8], fill=col)
    d.rectangle([40, H - 1 - abajo - 6, 80, H - 1 - abajo], fill=col)
    im.save(r)


def dataset_a(entrada, con_estampas=True):
    raiz = entrada / "pairlegoface"
    filas = []
    exprs = ["lopsided grin", "closed mouth and frown", "open mouth smile with tongue", "surprised open mouth",
             "neutral expression"]
    cejas = ["white thick", "dark brown", "black", "nougat", "reddish brown"]
    for i in range(40):
        g = "g1" if i < 30 else "g2"
        pid = i if i < 30 else i - 30
        nombre = f"p{pid:02d}_00.jpg"
        carpeta = f"personas_{g}_parte0"
        foto(raiz / carpeta / carpeta / "imagenes" / nombre)
        pieza = f"lego_{i % 6:02d}"
        filas.append(dict(id=pid, version=g, pasa=0 if i == 5 else 1, pieza=pieza,
                          particion="test" if pid % 3 == 0 or i >= 30 else "train",
                          ruta=f"{carpeta}/imagenes/{nombre}", ruta_lego=f"caras/{pieza}.png",
                          genero="mujer" if i % 3 == 1 else "hombre", edad=["joven", "adulto", "mayor"][i % 3],
                          origen="flux", lentes=i % 4 == 0, barba=i % 5 == 1, bigote=i % 7 == 2,
                          femenino=i % 3 == 1, semilla=i,
                          prompt="Turn this LEGO minifigure face into a realistic photograph of a real 20-year-old "
                                 "man. The person must have exactly these facial features from the LEGO face: "
                                 f"{cejas[i % 5]} eyebrows, {exprs[i % 5]}. Keep the same expression, the same "
                                 "eyebrow shape and the same facial hair shape and color. Bare face with no smile."))
    if con_estampas:
        for k in range(6):
            estampa(entrada / "legospartsvae" / "caras" / f"lego_{k:02d}.png")
    pd.DataFrame(filas).to_csv(raiz / "pares.csv", index=False)


def dataset_b(entrada):
    raiz = entrada / "otro_nombre"
    for part, n in (("train", 15), ("test", 14)):
        for i in range(n):
            foto(raiz / part / f"{part}_{i:02d}.jpg")
    for k in range(5):
        estampa(raiz / "mascaras" / f"m{k}.png", alfa=False, arriba=10, abajo=12, izq=8, der=8)
    return {f"test_{i:02d}.jpg": dict(lentes=i % 3 == 0, barba=i % 4 == 1, bigote=False,
                                      expresion=["sonrisa", "serio", "sorpresa", "neutral"][i % 4])
            for i in range(14)}


def correr_notebook(entrada, salida, reemplazos=()):
    os.environ["FLUX_CARA_ENTRADA"] = str(entrada)
    os.environ["FLUX_CARA_SALIDA"] = str(salida)
    nb = json.loads(NB.read_text(encoding="utf-8"))
    ns = {"__name__": "__main__"}
    for k in [m for m in sys.modules if m in ("config", "registro", "dataset", "flux", "postproceso", "ajuste",
                                               "cara", "ldraw", "mosaico", "_flux_cara_estado")]:
        del sys.modules[k]
    falsos.instalar()
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        s = "".join(c["source"]).replace("/kaggle/working/flux_cara", salida.as_posix())
        for a, b in reemplazos:
            s = s.replace(a, b)
        if s.startswith("%%writefile"):
            primera, cuerpo = s.split("\n", 1)
            Path(primera.split(maxsplit=1)[1]).write_text(cuerpo, encoding="utf-8")
            continue
        exec(compile(s, "<celda>", "exec"), ns)
    return ns


def comunes(ns, salida, etiqueta):
    """Chequeos que valen para cualquier dataset."""
    assert ns["ETAPA1_OK"], f"{etiqueta}: Etapa 1"
    ll = falsos.LLAMADAS
    assert falsos.CARGAS == [dict(modelo="black-forest-labs/FLUX.2-klein-4B", torch_dtype="bfloat16",
                                  device_map="balanced")], falsos.CARGAS          # cargado UNA sola vez
    assert all(c["pasos"] == 4 and c["guia"] == 1.0 and c["height"] == c["width"] == 512 and c["gen"] == "cpu"
               and c["image"].size == (512, 512) for c in ll), ll[0]
    assert all(c["semilla"] == 42 for c in ll[:40]), "Etapas 1–2: misma semilla para todas"
    # Etapa 2: la base sale gris -> falla 'fondo'; ganan las variantes con "edge to edge"
    tp = ns["TABLA_PROMPTS"]
    assert ns["FALLA"] == "fondo", ns["CUENTAS"]
    assert list(tp["variante"]) == ["base", "v1_fondo_hex", "v2_fondo_primero", "v3_fondo_papel"], tp["variante"]
    assert tp.set_index("variante").loc["base", "fondo_amarillo"] == 0
    assert tp.set_index("variante").loc["v1_fondo_hex", "planas_y_amarillas"] == 10
    assert ns["MEJOR"]["variante"] == "v1_fondo_hex" and ns["META_OK"]
    # Etapa 3: tamaño y encuadre
    t3 = ns["TABLA3"]
    assert (~t3["descartada"]).all(), t3
    W, H = ns["TAMANO"]
    for png in (salida / "etapa3" / "caras").glob("*.png"):
        im = Image.open(png)
        assert im.mode == "RGBA" and im.size == (W, H), (png, im.mode, im.size)
        a = np.asarray(im)[..., 3] > 0
        filas = np.where(a.any(1))[0]
        top = filas[0] / H
        assert abs(top - ns["MARG"]["arriba"]) < 0.03 or a.any(0).sum() >= W * 0.89, (top, ns["MARG"])
    # Etapa 4: 5 caras, semilla 45 se descarta y se reintenta con 1045
    t4 = ns["TABLA4"]
    assert len(t4) == 5 * ns["config"].N_FOTOS_ETAPA4
    r45 = t4[t4["k"] == 3].iloc[0]
    assert r45["reintentos"] == 1 and r45["semilla_final"] == 1045 and not r45["descartada"], r45.to_dict()
    assert not t4["descartada"].any()
    # Etapa 5
    assert ns["ETAPA5_OK"], f"{etiqueta}: Etapa 5"
    z = zipfile.ZipFile(salida / "entregar.zip")
    n = set(z.namelist())
    nec = {"reporte.txt", "datos/grilla_10.jpg", "datos/margenes.json", "etapa1/grilla_etapa1.jpg",
           "etapa1/prompts.csv", "etapa1/tiempos.csv", "etapa2/tabla_prompts.csv", "etapa2/prompt_congelado.txt",
           "etapa3/grilla_rgba.jpg", "etapa4/generacion.csv", "etapa5/catalogo_cabello.csv"}
    assert nec <= n, nec - n
    assert not any("crudas/" in x or x.startswith("src/") for x in n), "crudas/src no deben ir al zip"
    ldrs = [x for x in n if x.endswith(".ldr")]
    assert len(ldrs) == ns["config"].N_FOTOS_ETAPA4, ldrs
    for ldr in ldrs:
        base = ldr.rsplit("/", 1)[0]
        nombre = ldr.rsplit("/", 1)[1][8:-4]
        assert {f"{base}/cabeza_{nombre}.dat", f"{base}/textures/cara_{nombre}.png", f"{base}/README_render.md",
                f"{base}/vista_previa_{nombre}.png"} <= n, base
    # Etapa 6 (Anexo A): 3 personas x 2 métodos x (ronda1, ronda2, variar)
    t6 = ns["TABLA6"]
    assert {"etapa6/mosaico_rondas.jpg", "etapa6/rondas.csv"} <= n, "falta el mosaico"
    assert t6["foto"].nunique() == 3 and set(t6["ronda"]) == {"ronda1", "ronda2", "variar"}, t6
    fl = t6[t6["metodo"] == "FLUX"]
    assert (fl[fl["ronda"] == "ronda1"]["origen"] == "etapa4 (reutilizada)").all()
    for foto, g in fl.groupby("foto"):
        sem = {r: sorted(int(x) for x in g[g["ronda"] == r]["semilla"]) for r in ("ronda1", "ronda2", "variar")}
        assert sem["ronda2"] == sem["ronda1"] == [42, 43, 44, 46, 1045], sem      # ronda 2: mismas semillas
        assert sem["variar"] == [142, 144, 145, 146, 1143], sem                    # Variar: otras semillas
        p1, p2 = g[g["ronda"] == "ronda1"]["prompt"].iloc[0], g[g["ronda"] == "ronda2"]["prompt"].iloc[0]
        assert p1 != p2 and p2 == g[g["ronda"] == "variar"]["prompt"].iloc[0], (p1, p2)
        assert g[g["ronda"] == "ronda2"]["cambio"].iloc[0].startswith("lentes: ")
        assert ("rectangular glasses" in p1) != ("rectangular glasses" in p2), (p1, p2)   # lentes alternados
    m = Image.open(salida / "etapa6" / "mosaico_rondas.jpg")
    assert m.height > 3 * 6 * 128, m.size
    rep = z.read("reporte.txt").decode("utf-8")
    for clave in ("hf_device_map", "acepta image=", "Tiempo por imagen", "la más común", "Congelada",
                  "Pasan el guardrail", "generar_cara", "Catálogo de cabello", "ETAPA5_OK = True", "entregar.zip"):
        assert clave in rep, f"{etiqueta}: falta '{clave}' en el reporte"
    assert type(sys.stdout).__name__ != "_Tee"
    return z


def main():
    assert Path(os.environ.get("FLUX_CARA_LDRAW_ZIP", "")).exists(), "Falta FLUX_CARA_LDRAW_ZIP (complete.zip real)"
    tmp = Path(tempfile.mkdtemp(prefix="nb_"))
    try:
        print("=" * 30, "Dataset A (pares.csv)")
        dataset_a(tmp / "A" / "input")
        propio = ("GENERAR_PROPIO = lambda ruta, rasgos, n, base: "
                  "[Image.new('RGBA', TAMANO, (20, 20, 20, 255 * (k % 2))) for k in range(n)]")
        ns = correr_notebook(tmp / "A" / "input", tmp / "A" / "working",
                             reemplazos=[("GENERAR_PROPIO = None", propio)])
        t6 = ns["TABLA6"]
        pr = t6[t6["metodo"] == "Modelo propio"]
        assert ns["PROPIO_LISTO"] and len(pr) == 45 and (pr["origen"] == "función GENERAR_PROPIO").all(), pr
        assert set(pr[pr["ronda"] == "variar"]["semilla"]) == {142, 143, 144, 145, 146}
        z = comunes(ns, tmp / "A" / "working", "A")
        fotos, sel = ns["FOTOS"], ns["ELEGIDAS"]
        assert (sel["particion"] == "prueba").all() and not fotos["id"].duplicated().any()
        assert ns["TAMANO"] == (128, 118) and abs(ns["MARG"]["arriba"] - 20 / 118) < 0.01, (ns["TAMANO"], ns["MARG"])
        reales = {
            "white thick eyebrows, lopsided grin": ("sonrisa", "white"),
            "dark brown eyebrows, crooked smile and laugh lines": ("sonrisa", "dark brown"),
            "nougat cut half circle beard, black eyebrows and open mouth smile with tongue": ("sonrisa", "black"),
            "black eyebrows, reddish brown freckles, grin": ("sonrisa", "black"),
            "brown eyebrows, nougat cheek lines, smile": ("sonrisa", "brown"),
        }
        for cl, esperado in reales.items():
            r = ns["dataset"].rasgos_de_texto("... facial features from the LEGO face: " + cl + ". Keep the same expression")
            assert (r["expresion"], r["color_cejas"]) == esperado, (cl, r)
        assert {"sonrisa", "serio", "sorpresa", "neutral"} <= set(sel["expresion"])
        t1 = ns["TABLA1"]
        for _, f in t1.iterrows():
            assert ("wearing black rectangular glasses" in f["prompt"]) == bool(f["lentes"])
            assert "{" not in f["prompt"] and f["prompt"].startswith("Flat 2D printed face decal")
        assert t1["prompt"].str.contains(r"eyebrows in (?:white|dark brown|black|light brown|reddish brown)\.").all()
        # LDraw: la cabeza propia sigue la convención de 3626cpx0.dat y el modelo usa piezas oficiales
        ldr = sorted(x for x in z.namelist() if x.endswith(".ldr"))[0]
        texto = z.read(ldr).decode("utf-8")
        assert "\r\n" in texto and "73200b-f1.dat" in texto and "973.dat" in texto and "3820.dat" in texto
        cab = z.read(ldr.replace("minifig_", "cabeza_").replace(".ldr", ".dat")).decode("utf-8")
        assert "0 !TEXMAP START PLANAR -13 0 10 13 0 10 -13 21 10 cara_" in cab and "s\\3626cs01.dat" in cab
        print("A OK")

        print("=" * 30, "Dataset C (sin estampas)")
        dataset_a(tmp / "C" / "input", con_estampas=False)
        ns = correr_notebook(tmp / "C" / "input", tmp / "C" / "working")
        comunes(ns, tmp / "C" / "working", "C")
        assert not ns["PROPIO_LISTO"] and (ns["TABLA6"].query("metodo == 'Modelo propio'")["origen"] == "pendiente").all()
        assert ns["INFO_ESTAMPAS"].get("margen_por_defecto") and ns["TAMANO"] == (128, 118), ns["TAMANO"]
        print("C OK")

        print("=" * 30, "Dataset B (sin tablas, rasgos a mano)")
        manual = dataset_b(tmp / "B" / "input")
        ns = correr_notebook(tmp / "B" / "input", tmp / "B" / "working",
                             reemplazos=[("RASGOS_MANUALES = {}", "RASGOS_MANUALES = " + repr(manual))])
        comunes(ns, tmp / "B" / "working", "B")
        assert ns["INFO_ESTAMPAS"]["n"] == 5 and (ns["ELEGIDAS"]["fuente_rasgos"] == "manual").all()
        print("B OK")
        print("\nTODO OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
