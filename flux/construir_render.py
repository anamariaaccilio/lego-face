"""Genera render_minifigs.ipynb (local, sin GPU): renderiza en 3D las minifigs de la Etapa 5.

    python construir_render.py
"""
import json
from pathlib import Path

celdas = []


def md(t):
    celdas.append(dict(cell_type="markdown", metadata={}, source=t.strip("\n")))


def code(t):
    celdas.append(dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=t.strip("\n")))


md(r"""
# Render de las minifigs (local)

Toma las minifigs que armó la Etapa 5 de `flux_cara_ldraw.ipynb` (`entregar/etapa5/<foto>/minifig_<foto>.ldr`) y las
renderiza en 3D **en tu PC, sin GPU y sin instalar programas**: un rasterizador en numpy (`src/render.py`) con
perspectiva, z-buffer, luz de plástico, aristas de LDraw y la cara aplicada por `!TEXMAP PLANAR` tal como lo define la
especificación (la misma proyección que usan LDView y Blender).

**Requisitos:** Python con `numpy`, `pillow`, `pandas` (los mismos del proyecto). La librería oficial de piezas
(`complete.zip`, ~140 MB) se descarga sola la primera vez a `ldraw/complete.zip`.

**Salida** (por cada minifig, en `etapa5/<foto>/renders/`): `lamina_<foto>.png` (estampa + 5 vistas) y cada vista en
PNG con fondo transparente. Además, `etapa5/renders_todas.png` con todas las minifigs juntas.

Opcional al final: si tienes **LDView** instalado, también saca su render para comparar.
""")

code(r"""
import sys, time
from pathlib import Path
from IPython.display import display

RAIZ = Path.cwd()                                   # carpeta flux (donde está este notebook)
sys.path.insert(0, str(RAIZ / "src"))
import ldraw, render

# ---- ajustes ---------------------------------------------------------------------------------------------
CARPETA_ETAPA5 = RAIZ / "salidas_kaggle" / "entregar" / "etapa5"   # lo que bajaste de Kaggle (entregar.zip)
LDRAW_ZIP = RAIZ / "ldraw" / "complete.zip"                       # se descarga aquí si no está
ANCHO, ALTO = 420, 540                                            # tamaño de cada vista (px)
CALIDAD = 3                                                       # supermuestreo (antialias): 2 rápido, 3-4 fino
VISTAS = {"frente": (0, 10), "3/4 izquierda": (-35, 15), "3/4 derecha": (35, 15),
          "perfil": (-90, 5), "espalda": (180, 10)}                # nombre: (giro, inclinación) en grados
ARISTAS = True                                                    # líneas negras de LDraw

MINIFIGS = sorted(p for p in CARPETA_ETAPA5.iterdir() if p.is_dir() and list(p.glob("minifig_*.ldr")))
print(f"{len(MINIFIGS)} minifigs en {CARPETA_ETAPA5}:", [p.name for p in MINIFIGS])
assert MINIFIGS, "No encontré minifig_*.ldr: revisa CARPETA_ETAPA5"
""")

code(r"""
LIB = ldraw.Libreria(ldraw.descargar(LDRAW_ZIP))
""")

md(r"""
## Render de cada minifig
Una lámina por minifig: la estampa de la cara (sobre amarillo, como queda en la cabeza) y cinco vistas.
""")

code(r"""
from PIL import Image

RENDERS = {}
for carpeta in MINIFIGS:
    t = time.time()
    modelo = render.Modelo(LIB, next(carpeta.glob("minifig_*.ldr")))
    cara = Image.open(next((carpeta / "textures").glob("cara_*.png")))
    hoja, vistas = render.lamina(modelo, carpeta.name, vistas=VISTAS, ancho=ANCHO, alto=ALTO, cara=cara,
                                 ss=CALIDAD, aristas=ARISTAS)
    salida = carpeta / "renders"
    salida.mkdir(exist_ok=True)
    hoja.save(salida / f"lamina_{carpeta.name}.png")
    for nombre, im in vistas.items():
        im.save(salida / f"{carpeta.name}_{nombre.replace('/', '-').replace(' ', '_')}.png")
    RENDERS[carpeta.name] = vistas
    print(f"{modelo} · {time.time() - t:.1f} s → {salida}")
    display(hoja)
""")

md("## Todas juntas")
code(r"""
VISTA_GRUPO = "3/4 izquierda"
imgs = [RENDERS[n][VISTA_GRUPO] for n in RENDERS]
grupo = Image.new("RGBA", (ANCHO * len(imgs), ALTO), (0, 0, 0, 0))
for k, im in enumerate(imgs):
    grupo.alpha_composite(im, (k * ANCHO, 0))
grupo = render.sobre_fondo(grupo)
grupo.save(CARPETA_ETAPA5 / "renders_todas.png")
print("→", CARPETA_ETAPA5 / "renders_todas.png")
display(grupo)
""")

md(r"""
## Una vista a medida (opcional)
Cambia el giro y la inclinación para sacar la toma que quieras (más grande, en alta).
""")
code(r"""
MINIFIG, GIRO, INCLINACION = MINIFIGS[0].name, -25, 20
modelo = render.Modelo(LIB, CARPETA_ETAPA5 / MINIFIG / f"minifig_{MINIFIG}.ldr")
im = render.render(modelo, 800, 1000, yaw=GIRO, pitch=INCLINACION, ss=CALIDAD, aristas=ARISTAS)
im.save(CARPETA_ETAPA5 / MINIFIG / "renders" / f"{MINIFIG}_a_medida.png")
display(render.sobre_fondo(im))
""")

md(r"""
## Comparar con LDView (opcional)
Si tienes LDView instalado (https://tcobbs.github.io/ldview/), se usa para sacar su propio render de cada minifig.
LDView necesita la librería descomprimida: se extrae a `ldraw/ldraw/` la primera vez (~ 500 MB). Si no está instalado,
esta celda solo avisa y no hace nada.
""")
code(r"""
import shutil, subprocess, zipfile

LDVIEW = next((str(p) for p in [Path(r"C:\Program Files\LDView\LDView64.exe"), Path(r"C:\Program Files\LDView\LDView.exe"),
                                Path(r"C:\Program Files (x86)\LDView\LDView.exe")] if p.exists()),
              shutil.which("LDView64") or shutil.which("LDView") or shutil.which("ldview"))
if LDVIEW is None:
    print("LDView no está instalado: se omite (los renders de arriba no lo necesitan).")
else:
    LDRAW_DIR = LDRAW_ZIP.parent / "ldraw"
    if not (LDRAW_DIR / "LDConfig.ldr").exists():
        print("Descomprimiendo la librería para LDView…")
        zipfile.ZipFile(LDRAW_ZIP).extractall(LDRAW_ZIP.parent)
    for carpeta in MINIFIGS:
        ldr = next(carpeta.glob("minifig_*.ldr"))
        destino = carpeta / "renders" / f"ldview_{carpeta.name}.png"
        p = subprocess.run([LDVIEW, str(ldr), f"-LDrawDir={LDRAW_DIR}", f"-SaveSnapshot={destino}",
                            "-SaveWidth=800", "-SaveHeight=1000", "-SaveZoomToFit=1"],
                           cwd=carpeta, capture_output=True, text=True, timeout=300)
        if destino.exists():
            print("LDView →", destino)
            display(Image.open(destino))
        else:
            print(f"LDView no generó {destino.name} (código {p.returncode}) {p.stderr[-300:]}")
""")

nb = dict(cells=celdas, nbformat=4, nbformat_minor=5,
          metadata=dict(kernelspec=dict(display_name="Python 3", language="python", name="python3"),
                        language_info=dict(name="python")))
destino = Path(__file__).parent / "render_minifigs.ipynb"
destino.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{destino.name}: {len(celdas)} celdas")
