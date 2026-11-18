"""Genera cabello_minifigs.ipynb (local, sin GPU): elige el cabello de cada minifig para que se parezca a la foto.

    python construir_cabello.py
"""
import json
from pathlib import Path

celdas = []


def md(t):
    celdas.append(dict(cell_type="markdown", metadata={}, source=t.strip("\n")))


def code(t):
    celdas.append(dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=t.strip("\n")))


md(r"""
# Cabello de las minifigs (local)

La Etapa 5 de `flux_cara_ldraw.ipynb` le pone a cada minifig un cabello **por defecto**: corto si es hombre, largo si
es mujer, con el color de las **cejas**. Por eso no se parece a la foto (p. ej. pelo gris en alguien de pelo negro).

Este notebook lo corrige antes del render:

1. Muestra la foto junto a la minifig actual.
2. **Sugiere** color y estilo mirando la foto (heurística simple, `src/cabello.py`).
3. Arma una **galería**: la cabeza con cada peinado de la librería oficial LDraw, en el color sugerido.
4. Tú eliges en `ELECCION` (o aceptas la sugerencia) y se **reescribe** `minifig_<foto>.ldr`
   (la primera vez guarda el original como `minifig_<foto>.ldr.orig`; al final hay una celda para volver atrás).
5. **Retoca la estampa**: cambia el color de cejas, bigote o barba para que combine con el pelo de la foto
   (sin volver a correr FLUX; el original queda como `cara_<foto>.orig.png`).
6. *(Opcional, apagado)* **Colores de la ropa**: la polera de la foto al torso y los brazos.

**Color del pelo:** los colores oficiales de LEGO/LDraw son pocos y algunos tiran a azul (`Black` = #1B2A34 se ve
azul marino). Por eso, por defecto, el pelo usa el **color exacto medido en la foto** como color directo de LDraw
(`0x2RRGGBB`, lo leen LDView, Blender/ImportLDraw y el render de este proyecto). Si prefieres un color LEGO real,
pon su nombre (`"Black"`, `"Dark_Brown"`…) en `ELECCION`.

Corre **en tu PC** (solo CPU: numpy, pillow, pandas, scipy). No necesita Kaggle ni GPU.

Después corre **`render_minifigs.ipynb`** para sacar las láminas con el cabello nuevo.
""")

code(r"""
import sys
from pathlib import Path
import pandas as pd
from IPython.display import display

RAIZ = Path.cwd()                                   # carpeta flux (donde está este notebook)
sys.path.insert(0, str(RAIZ / "src"))
import ldraw, render, cabello, estampa, ropa

# ---- ajustes ---------------------------------------------------------------------------------------------
CARPETA_ENTREGAR = RAIZ / "salidas_kaggle" / "entregar"      # lo que bajaste de Kaggle (entregar.zip)
CARPETA_ETAPA5 = CARPETA_ENTREGAR / "etapa5"
LDRAW_ZIP = RAIZ / "ldraw" / "complete.zip"
FOTOS_ORIGINALES = None   # carpeta con las fotos originales (p. ej. PairLegoFace bajado de Kaggle); None = usar
                          # las miniaturas de datos/grilla_10.jpg (200 px), que alcanzan para color y forma
CALIDAD = 2               # supermuestreo de los renders de este notebook (2 rápido, 3 fino)

MINIFIGS = sorted(p for p in CARPETA_ETAPA5.iterdir() if p.is_dir() and list(p.glob("minifig_*.ldr")))
print(f"{len(MINIFIGS)} minifigs:", [p.name for p in MINIFIGS])
assert MINIFIGS, "No encontré minifig_*.ldr: revisa CARPETA_ETAPA5"
""")

code(r"""
LIB = ldraw.Libreria(ldraw.descargar(LDRAW_ZIP))
FOTOS = {c.name: cabello.foto(CARPETA_ENTREGAR, c.name, FOTOS_ORIGINALES) for c in MINIFIGS}
DATOS = {c.name: cabello.datos_foto(CARPETA_ENTREGAR, c.name) for c in MINIFIGS}
sin_foto = [n for n, f in FOTOS.items() if f is None]
print("Fotos encontradas:", len(FOTOS) - len(sin_foto), "de", len(FOTOS), "· sin foto:", sin_foto or "ninguna")
""")

md(r"""
## 1. La foto y el cabello actual
""")

code(r"""
filas = []
for c in MINIFIGS:
    pieza, color = cabello.cabello_actual(LIB, c)
    filas.append(dict(minifig=c.name, pieza=pieza, descripcion=LIB.descripciones().get(pieza, "sin pelo") if pieza else "sin pelo",
                      color=color, femenino=DATOS[c.name].get("femenino"), cejas=DATOS[c.name].get("color_cejas")))
    hoja = cabello.galeria(LIB, c, [pieza or "calvo"], color or "Black", FOTOS[c.name], columnas=2, ss=CALIDAD)
    display(hoja)
display(pd.DataFrame(filas))
""")

md(r"""
## 2. Sugerencia automática

Se mira la franja de arriba de la foto (lo que no es pared ni piel = pelo) para el **color**, y los lados de la cara
para decidir **largo / corto / calvo**. Los cuadritos muestran: color medido en la foto | color LEGO más cercano
(se ve cuánto se aleja el LEGO del real: por eso por defecto se usa el de la foto).
Es solo un punto de partida: textura (rizado, peinado hacia atrás…) no la adivina; eso se elige en la galería.
""")

code(r"""
SUGERENCIA = {}
for c in MINIFIGS:
    f = FOTOS[c.name]
    if f is None:
        SUGERENCIA[c.name] = dict(color="Black", estilo="corto", rgb=(0, 0, 0), pelo_arriba=None, pelo_lados=None)
        continue
    SUGERENCIA[c.name] = cabello.estimar(f, LIB, femenino=DATOS[c.name].get("femenino"))
    s = SUGERENCIA[c.name]
    print(f"{c.name}: {s['estilo']:<13} foto {s['foto']}  ·  LEGO más cercano {s['color']}")
    display(cabello.muestra(s["rgb"], LIB.colores[s["color"]][1]))
display(pd.DataFrame(SUGERENCIA).T)
""")

md(r"""
## 3. Catálogo de peinados

`cabello.ESTILOS` trae 20 peinados elegidos de la librería oficial (hay 223 piezas "Minifig Hair").
Para buscar otros: `cabello.buscar(LIB, "wavy")`; puedes usar su número de pieza directo en `ELECCION`
(p. ej. `"40239.dat"`) o agregarlo: `cabello.ESTILOS["mi_estilo"] = "40239.dat"`.
""")

code(r"""
display(cabello.catalogo(LIB))
display(cabello.buscar(LIB, "swept back"))      # ejemplo de búsqueda
""")

md(r"""
## 4. Galería por minifig

La cabeza de cada minifig con cada peinado, en el color medido en la foto.
Se guarda en `etapa5/<foto>/cabello/galeria_<foto>.png`. Tarda unos segundos por minifig.
""")

code(r"""
GALERIA = list(cabello.ESTILOS)                 # o una lista corta: ["corto", "peinado_atras", "rizado", ...]
for c in MINIFIGS:
    color = SUGERENCIA[c.name].get("foto") or SUGERENCIA[c.name]["color"]
    hoja = cabello.galeria(LIB, c, GALERIA, color, FOTOS[c.name], columnas=7, ss=CALIDAD)
    (c / "cabello").mkdir(exist_ok=True)
    hoja.save(c / "cabello" / f"galeria_{c.name}.png")
    print(f"{c.name} · color {color}")
    display(hoja)
""")

md(r"""
## 5. Tu elección

Para cada minifig: `estilo` (clave de `cabello.ESTILOS`, un número de pieza `"xxxx.dat"` o `"calvo"`) y `color`:
- `"foto"`: el color exacto medido en la foto (por defecto);
- un RGB `"#rrggbb"` o `(r, g, b)` para afinarlo a mano;
- un color LEGO de `LDConfig.ldr`: `Black`, `Dark_Brown`, `Reddish_Brown`, `Medium_Nougat`, `Tan`,
  `Dark_Bluish_Grey`, `Light_Bluish_Grey`, `White`…

Lo que no pongas aquí usa la sugerencia del paso 2 con el color de la foto.

Los valores de abajo son los elegidos mirando las fotos de esta entrega; cámbialos a tu gusto.
""")

code(r"""
ELECCION = {
    "3626bp39_09": dict(estilo="peinado_atras", color="#77736f"),   # canoso: gris neutro (la mediana #504742 sale
                                                                     # café porque mezcla canas y mechones oscuros)
    "3626cp76_04": dict(estilo="largo_ondulado", color="foto"),     # largo, ondulado, negro cálido
    "3626cp7a_04": dict(estilo="corto_liso", color="foto"),         # corto, negro cálido
}

FINAL = {}
for c in MINIFIGS:
    e = dict(estilo=SUGERENCIA[c.name]["estilo"], color="foto", fuente="sugerencia")
    if c.name in ELECCION:
        e.update(ELECCION[c.name], fuente="ELECCION")
    if e["color"] == "foto":
        e["color"] = SUGERENCIA[c.name].get("foto") or SUGERENCIA[c.name]["color"]
    FINAL[c.name] = e
display(pd.DataFrame(FINAL).T)
""")

md(r"""
## 6. Aplicar y comparar

Reescribe cada `minifig_<foto>.ldr` (solo las líneas del cabello) y muestra: foto | antes | después.
La comparación queda en `etapa5/<foto>/cabello/comparacion_<foto>.png` y lo elegido en `etapa5/cabello_elegido.csv`.
""")

code(r"""
registro = []
for c in MINIFIGS:
    e = FINAL[c.name]
    r = cabello.aplicar(LIB, c, e["estilo"], e["color"], nota=f"{e['fuente']} en cabello_minifigs.ipynb")
    hoja, _ = cabello.comparar(LIB, c, FOTOS[c.name], ss=CALIDAD)
    (c / "cabello").mkdir(exist_ok=True)
    hoja.save(c / "cabello" / f"comparacion_{c.name}.png")
    registro.append(dict(minifig=c.name, estilo=r["estilo"], pieza=r["pieza"], color=r["color"], fuente=e["fuente"]))
    print(f"{c.name}: {r['estilo']} ({r['pieza']}) {r['color']} → {r['ldr'].name}")
    display(hoja)
pd.DataFrame(registro).to_csv(CARPETA_ETAPA5 / "cabello_elegido.csv", index=False)
display(pd.DataFrame(registro))
print("Listo. Ahora corre render_minifigs.ipynb para las láminas con el cabello nuevo.")
""")

md(r"""
## 7. Cejas, bigote y barba de la estampa

FLUX dibujó esos rasgos con el color del **dataset** (que describe la pieza LEGO del par, no a la persona): por eso
salieron cejas grises en alguien de pelo negro, o barba negra en alguien canoso. Aquí se recolorean en la estampa:

- `zona="gris"`: los rasgos grises (cejas, bigote, barba gris).
- `zona="barba"`: la mancha oscura y gruesa bajo los ojos (barba + bigote) y las patillas; ojos, cejas y la línea
  de la boca no se tocan.

`color`: nombre de `LDConfig.ldr` (como el pelo) o un RGB `(r, g, b)`. Siempre parte de la estampa original, así que
puedes correr la celda las veces que quieras. Se guarda en `textures/cara_<foto>.png` (lo que usa el render).
""")

code(r"""
RETOQUES = {
    "3626cp7a_04": [dict(zona="gris", color=(31, 24, 22))],      # cejas y bigote negro cálido, como su pelo
    "3626bp39_09": [dict(zona="barba", color=(160, 157, 152))],  # barba canosa (más clara que el pelo, como en la foto)
}

def a_rgb(color):
    if isinstance(color, str) and color.startswith("#"):
        return tuple(int(color[k:k + 2], 16) for k in (1, 3, 5))
    if isinstance(color, str):
        h = LIB.colores[color][1]
        return tuple(int(h[k:k + 2], 16) for k in (1, 3, 5))
    return tuple(color)

for c in MINIFIGS:
    if c.name not in RETOQUES:
        continue
    antes = estampa.original(c)
    nueva = antes
    for r in RETOQUES[c.name]:
        if r["zona"] == "gris":
            m, tinta = estampa.mascara_gris(nueva), None
        elif r["zona"] == "barba":
            m, tinta = estampa.mascara_barba(nueva), (0, 0, 0)
        else:
            raise ValueError(f"zona desconocida: {r['zona']} (usa 'gris' o 'barba')")
        nueva = estampa.recolorear(nueva, m, a_rgb(r["color"]), tinta=tinta)
        print(f"{c.name}: {r['zona']} -> {r['color']} ({int(m.sum())} px)")
    estampa.guardar(c, nueva)
    pieza, color = cabello.cabello_actual(LIB, c)
    cabeza = cabello.cabeza_con(LIB, c, pieza or "calvo", color or "Black", lado=260, yaw=0, pitch=8, ss=CALIDAD)
    hoja = cabello._rotulo(estampa.sobre_amarillo(antes, 2), "antes")
    paneles = [FOTOS[c.name].resize((236, 236)) if FOTOS[c.name] else None, hoja,
               cabello._rotulo(estampa.sobre_amarillo(nueva, 2), "despues"), cabello._rotulo(cabeza, "en la cabeza")]
    paneles = [p for p in paneles if p is not None]
    from PIL import Image
    W, H = sum(p.width for p in paneles) + 10 * len(paneles), max(p.height for p in paneles)
    lam = Image.new("RGB", (W, H), "white")
    x = 0
    for p in paneles:
        lam.paste(p, (x, (H - p.height) // 2)); x += p.width + 10
    (c / "cabello").mkdir(exist_ok=True)
    lam.save(c / "cabello" / f"estampa_{c.name}.png")
    display(lam)
print("Listo. Corre render_minifigs.ipynb para ver la minifig completa con la estampa nueva.")
""")

md(r"""
## 8. Colores de la ropa (opcional)

Apagado por defecto (`CAMBIAR_ROPA = False`): la ropa queda con los colores de la Etapa 5.

En los retratos se ve la polera en los hombros: se mide ahí (sin pared ni piel) y se elige el color LDraw más
cercano para el **torso y los brazos** (las manos siguen amarillas). Las **piernas** no salen en la foto: quedan como
están salvo que pongas un color en `ROPA`. Cuadritos: color medido en la foto | color LDraw.
""")

code(r"""
CAMBIAR_ROPA = False
ROPA = {
    # "3626bp39_09": dict(torso="Dark_Blue", piernas="Black"),   # ejemplo: manda sobre lo medido
}

filas = []
for c in MINIFIGS:
    s = ropa.estimar(FOTOS[c.name], LIB) if FOTOS[c.name] else dict(torso=None, rgb=None, ropa_visible=0)
    e = dict(torso=s["torso"], piernas=None, fuente="foto")
    if c.name in ROPA:
        e.update(ROPA[c.name], fuente="ROPA")
    if not CAMBIAR_ROPA:                                   # colores de la Etapa 5
        e = dict(ropa.colores_actuales(LIB, c, original=True), fuente="Etapa 5")
    antes = ropa.colores_actuales(LIB, c)
    despues = ropa.aplicar(LIB, c, torso=e["torso"], piernas=e["piernas"])
    filas.append(dict(minifig=c.name, rgb_foto=s["rgb"], torso_antes=antes.get("torso"), torso=despues.get("torso"),
                      piernas=despues.get("piernas"), fuente=e["fuente"]))
    if s["rgb"]:
        display(cabello.muestra(s["rgb"], LIB.colores[despues["torso"]][1]))
    hoja, _ = cabello.comparar(LIB, c, FOTOS[c.name], ss=CALIDAD)
    hoja.save(c / "cabello" / f"comparacion_{c.name}.png")
    display(hoja)
display(pd.DataFrame(filas))
print("Listo. Ahora corre render_minifigs.ipynb para las láminas finales.")
""")

md(r"""
## Volver atrás (opcional)

`RESTAURAR = True` deja los `.ldr` como los entregó la Etapa 5 (desde `minifig_<foto>.ldr.orig`) y
`RESTAURAR_ESTAMPA = True` vuelve a la estampa original (desde `cara_<foto>.orig.png`).
""")

code(r"""
RESTAURAR = False
RESTAURAR_ESTAMPA = False
for c in MINIFIGS:
    if RESTAURAR:
        print(c.name, ".ldr", "restaurado" if cabello.restaurar(c) else "sin .ldr.orig (nunca se cambió)")
    if RESTAURAR_ESTAMPA:
        print(c.name, "estampa", "restaurada" if estampa.restaurar(c) else "sin respaldo (nunca se cambió)")
""")

nb = dict(cells=celdas, nbformat=4, nbformat_minor=5,
          metadata=dict(kernelspec=dict(display_name="Python 3", language="python", name="python3"),
                        language_info=dict(name="python")))
destino = Path(__file__).parent / "cabello_minifigs.ipynb"
destino.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{destino.name}: {len(celdas)} celdas")
