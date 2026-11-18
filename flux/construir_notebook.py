"""Arma flux_cara_ldraw.ipynb a partir de src/*.py (la fuente de verdad son los .py).

Uso:  python construir_notebook.py
Cada módulo entra al notebook como una celda %%writefile, así el notebook es autocontenido en Kaggle.
"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SRC = AQUI / "src"
DESTINO = AQUI / "flux_cara_ldraw.ipynb"
SRC_KAGGLE = "/kaggle/working/flux_cara/src"

MODULOS = ["config.py", "registro.py", "dataset.py", "flux.py", "postproceso.py", "ajuste.py", "cara.py", "ldraw.py", "mosaico.py"]

celdas = []


def md(t):
    celdas.append(dict(cell_type="markdown", metadata={}, source=t.strip("\n")))


def code(t):
    celdas.append(dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=t.strip("\n")))


def modulo(nombre):
    code(f"%%writefile {SRC_KAGGLE}/{nombre}\n" + (SRC / nombre).read_text(encoding="utf-8"))


# ===================================================================== portada
md(r"""
# Cara LEGO con FLUX.2-klein-4B + ensamblado LDraw

Foto de una persona → estampa de cara RGBA (FLUX.2-klein-4B, sin entrenar) → minifig en LDraw (`.ldr`) con la cara
aplicada por `!TEXMAP`. El render final se hace fuera de Kaggle (LDView o Blender; instrucciones en el README que se genera).

**Antes de correr (panel derecho de Kaggle):**
1. *Add Input* → **PairLegoFace** y **LegosPartsVae** (las caras LEGO reales: de ahí salen el tamaño y los márgenes).
2. *Settings* → **Internet: On** y **Accelerator: GPU T4 x2**.
3. *Run All*. La primera vez descarga FLUX (~16 GB) y la librería LDraw (~140 MB).
4. Al terminar, descarga **un solo archivo**: `flux_cara/entregar.zip` (panel *Output*). Trae el reporte con todo lo
   impreso, las grillas, `tabla_prompts.csv`, las caras RGBA y la carpeta LDraw lista para renderizar.
   Si algo falla, el zip se arma igual con el error en `reporte.txt`: mándalo tal cual.

| Etapa | Qué hace | Salidas |
|---|---|---|
| Datos | 10 fotos de prueba con variedad + márgenes de las estampas reales | `datos/` |
| 1 | Cargar FLUX una vez y generar 1 imagen por foto | `etapa1/grilla_etapa1.jpg`, `prompts.csv`, `tiempos.csv` |
| 2 | Detectar la falla más común, probar 3 variantes del prompt y congelar la mejor | `etapa2/tabla_prompts.csv`, `prompt_congelado.txt`, grillas |
| 3 | Post-proceso a RGBA con guardrail | `etapa3/grilla_rgba.jpg`, `caras/*.png` |
| 4 | `generar_cara(foto, rasgos, n=5)` con reintentos | `etapa4/` |
| 5 | Minifig LDraw + README de render + vista previa | `etapa5/<foto>/` |
| 6 | Anexo A: misma foto con modelo propio y FLUX · ronda 1, ronda 2 (con un cambio) y Variar · 5 caras cada una | `etapa6/mosaico_rondas.jpg`, `rondas.csv` |

Todos los parámetros están en **`config.py`** (celda siguiente).
""")

code(f"""
# Instalación (solo en Kaggle). FLUX.2-klein necesita diffusers >= 0.37 (Flux2KleinPipeline) y transformers con Qwen3.
# Se mira la versión SIN importar diffusers, para no dejar una versión vieja cargada en memoria.
import os, sys, platform, subprocess
from importlib.metadata import version, PackageNotFoundError
PAQUETES = ["diffusers>=0.37.0", "transformers>=4.51.0", "accelerate"]
def _ver(p):
    try:
        return tuple(int(x) for x in version(p).split(".")[:2] if x.isdigit())
    except PackageNotFoundError:
        return (0, 0)
if os.path.isdir("/kaggle/working") and (_ver("diffusers") < (0, 37) or _ver("transformers") < (4, 51)):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", *PAQUETES], check=True)
for p in ("diffusers", "transformers", "accelerate", "torch"):
    try:
        print(p, version(p))
    except PackageNotFoundError:
        print(p, "(no instalado)")
os.makedirs("{SRC_KAGGLE}", exist_ok=True)
print("Python", platform.python_version())
""")

md("## Parámetros (`config.py`)\nTodo valor incierto está aquí. Si cambias algo, vuelve a correr esta celda y la de *Importar módulos*.")
modulo("config.py")

md("## Módulos")
for m in MODULOS[1:]:
    modulo(m)

code(f"""
# Importar módulos (se recargan para tomar cambios; el pipeline de FLUX cargado NO se pierde al recargar)
import importlib
if "{SRC_KAGGLE}" not in sys.path:
    sys.path.insert(0, "{SRC_KAGGLE}")
import config, registro, dataset, flux, postproceso, ajuste, cara, ldraw, mosaico
for _m in (config, registro, dataset, flux, postproceso, ajuste, cara, ldraw, mosaico):
    importlib.reload(_m)
import pandas as pd
from PIL import Image
registro.iniciar()
""")

# ===================================================================== Datos
md(r"""
---
# Datos: 10 fotos de prueba y márgenes de las estampas reales
Se lee `pares.csv` de PairLegoFace (partición, `pasa`, lentes/barba/bigote; expresión y color de cejas salen de la
descripción de la cara LEGO en el `prompt`). Las estampas reales (`ruta_lego`) se buscan en todos los Inputs.
""")
code("""
registro.seccion("Datos")
SALIDA0 = dataset.carpeta_salida()
RAIZ = dataset.encontrar_dataset()
INV = dataset.inventario(RAIZ)
TABLAS = dataset.leer_tablas(RAIZ)
FOTOS = dataset.tabla_fotos(INV, TABLAS)
ESTAMPAS, INFO_ESTAMPAS = dataset.medir_estampas(FOTOS, INV)
MARG, TAMANO, ORIGEN_MARG = postproceso.margenes(INFO_ESTAMPAS)
print(f"\\nEncuadre para la Etapa 3: {ORIGEN_MARG} · {MARG} · tamaño final {TAMANO[0]}x{TAMANO[1]} (ancho x alto)")
ELEGIDAS = dataset.elegir_variadas(FOTOS)
G0 = dataset.grilla(ELEGIDAS)
G0.save(SALIDA0 / "grilla_10.jpg", quality=92)
registro.mostrar(G0)
registro.mostrar(ELEGIDAS[[c for c in ["idx", "nombre", "lentes", "barba", "bigote", "femenino", "edad", "expresion", "color_cejas", "rasgos_lego"] if c in ELEGIDAS]])
""")

# ===================================================================== Etapa 1
md(r"""
---
# Etapa 1 · Cargar FLUX.2-klein-4B y primera prueba

Verificado en la ficha oficial (`black-forest-labs/FLUX.2-klein-4B`, Apache-2.0): el pipeline es `Flux2KleinPipeline`,
es destilado (4 pasos, guidance 1.0) y la foto de referencia se pasa con `image=`. Se carga **una sola vez** con
`DiffusionPipeline.from_pretrained(..., device_map="balanced")` (~16 GB repartidos entre las dos T4).
""")
code("""
registro.seccion("1.1 Cargar el pipeline")
SALIDA1 = flux.carpeta("etapa1")
PIPE = flux.cargar()
FIRMA_OK = flux.verificar_firma(PIPE)

registro.seccion("1.2 Prompts de las 10 fotos")
TABLA1 = flux.prompts(ELEGIDAS)
TABLA1.to_csv(SALIDA1 / "prompts.csv", index=False)
registro.mostrar(TABLA1[["idx", "nombre", "rasgos", "frase_expresion", "frase_lentes", "frase_vello", "frase_color", "por_defecto"]])
print("\\nEjemplo de prompt completo (#" + str(TABLA1["idx"].iloc[0]) + "):\\n" + TABLA1["prompt"].iloc[0])
""")
code("""
registro.seccion("1.3 Generar (" + str(config.PASOS) + " pasos, guidance " + str(config.GUIA) + ", "
                 + str(config.ANCHO) + "x" + str(config.ALTO) + ", semilla " + str(config.SEMILLA_FLUX) + ")")
RES1 = flux.probar(PIPE, TABLA1, "etapa1", etiqueta="base")
RES1.to_csv(SALIDA1 / "tiempos.csv", index=False)
G1 = flux.grilla_pares(TABLA1, RES1)
G1.save(SALIDA1 / "grilla_etapa1.jpg", quality=92)
registro.mostrar(G1)
registro.seccion("1.4 Autoverificación")
ETAPA1_OK = flux.verificar(TABLA1, RES1, FIRMA_OK)
print("\\nETAPA1_OK =", ETAPA1_OK)
registro.empaquetar()
""")

# ===================================================================== Etapa 2
md(r"""
---
# Etapa 2 · Ajuste del prompt
Cada imagen se juzga de forma automática (CLIP zero-shot + color del borde): **plana**, **fondo amarillo**,
**solo rasgos** y **respeta lentes y barba**. Es una estimación: revisa las grillas y corrige con
`config.REVISION_MANUAL` si hace falta. Se detecta la falla más común de la Etapa 1, se prueban las 3 variantes de
`config.VARIANTES[falla]` con las mismas fotos y semilla, y se congela la mejor: primero la que cumple la meta
(≥ 8/10 planas y amarillas), luego **la que más corrige la falla detectada** (para `cara_completa`, más imágenes
con solo rasgos), luego la que más respeta lentes y barba.
""")
code("""
registro.seccion("2.1 Juez sobre la Etapa 1 y falla más común")
SALIDA2 = flux.carpeta("etapa2")
EV = {"base": ajuste.evaluar_lote(TABLA1, RES1, "base")}
RES = {"base": RES1}
registro.mostrar(EV["base"])
FALLA, CUENTAS = ajuste.falla_principal(EV["base"])
FILAS_TP = [ajuste.resumen(EV["base"], config.PROMPT_BASE)]
""")
code("""
registro.seccion("2.2 Tres variantes para la falla '" + FALLA + "'")
PLANTILLAS = {"base": config.PROMPT_BASE, **config.VARIANTES[FALLA]}
for nombre_v, plantilla in config.VARIANTES[FALLA].items():
    print(f"\\n--- {nombre_v}")
    t = flux.prompts(ELEGIDAS, plantilla)
    r = flux.probar(PIPE, t, "etapa2", etiqueta=nombre_v)
    RES[nombre_v] = r
    EV[nombre_v] = ajuste.evaluar_lote(t, r, nombre_v)
    FILAS_TP.append(ajuste.resumen(EV[nombre_v], plantilla))
    flux.grilla_pares(t, r).save(SALIDA2 / f"grilla_{nombre_v}.jpg", quality=90)
TABLA_PROMPTS = pd.DataFrame(FILAS_TP)
TABLA_PROMPTS.to_csv(SALIDA2 / "tabla_prompts.csv", index=False)
pd.concat(EV.values()).to_csv(SALIDA2 / "juez_por_imagen.csv", index=False)
registro.mostrar(TABLA_PROMPTS.drop(columns="prompt"))
MEJOR, META_OK = ajuste.elegir(TABLA_PROMPTS, FALLA)
PROMPT_FINAL = PLANTILLAS[MEJOR["variante"]]
(SALIDA2 / "prompt_congelado.txt").write_text(MEJOR["variante"] + "\\n" + PROMPT_FINAL, encoding="utf-8")
print("\\nPrompt congelado:\\n" + PROMPT_FINAL)
registro.empaquetar()
""")

# ===================================================================== Etapa 3
md(r"""
---
# Etapa 3 · Post-proceso a RGBA
Lab → fondo = mediana del borde (5 %) → trazo = distancia > 25 → apertura 3x3 → sin componentes < 15 px →
encuadre con los márgenes medidos en las estampas reales → tamaño final (alfa NEAREST, color BOX).
Guardrail: se descarta si el trazo es < 2 % o > 50 % del área, si menos del 60 % del borde es fondo, o si hay
**cabeza dibujada** (la silueta rellena más grande pasa del 30 % de la imagen: contorno de cabeza, pelo o piel).
Se aplica a las 10 imágenes de la variante congelada.
""")
code("""
registro.seccion("3.1 Post-proceso de las 10 imágenes de '" + MEJOR["variante"] + "'")
SALIDA3 = flux.carpeta("etapa3")
PARES3, ETQ3, FILAS3 = [], [], []
for (_, f), (_, g) in zip(TABLA1.iterrows(), RES[MEJOR["variante"]].iterrows()):
    img = Image.open(g["salida"])
    r = postproceso.a_rgba(img, MARG, TAMANO)
    if r["rgba"] is not None:
        (SALIDA3 / "caras").mkdir(exist_ok=True)
        r["rgba"].save(SALIDA3 / "caras" / f"{int(f['idx']):02d}_{f['nombre'].rsplit('.', 1)[0]}.png")
    PARES3.append((img, r))
    ETQ3.append(f"#{f['idx']} {f['nombre']}")
    FILAS3.append(dict(idx=f["idx"], nombre=f["nombre"], descartada=r["descartada"], motivo=r["motivo"],
                       cobertura=round(r["cobertura"], 3), borde_fondo=round(r["borde_fondo"], 2), caja=r["caja"]))
TABLA3 = pd.DataFrame(FILAS3)
TABLA3.to_csv(SALIDA3 / "postproceso.csv", index=False)
G3 = postproceso.grilla(PARES3, ETQ3)
G3.save(SALIDA3 / "grilla_rgba.jpg", quality=92)
registro.mostrar(G3)
registro.mostrar(TABLA3)
print(f"\\nPasan el guardrail: {int((~TABLA3['descartada']).sum())}/{len(TABLA3)}")
registro.empaquetar()
""")

# ===================================================================== Etapa 4
md(r"""
---
# Etapa 4 · Generación completa: `generar_cara(foto, rasgos, n=5)`
Cinco semillas por foto; si el guardrail descarta una, se reintenta con semilla + 1000 (máximo 2 veces).
Se corre para las primeras `config.N_FOTOS_ETAPA4` fotos y se mide el tiempo de las cinco.
""")
code("""
registro.seccion("4.1 generar_cara para " + str(config.N_FOTOS_ETAPA4) + " fotos")
SALIDA4 = flux.carpeta("etapa4")
CARAS4, TABLAS4 = {}, []
for _, f in ELEGIDAS.head(config.N_FOTOS_ETAPA4).iterrows():
    nombre = f["nombre"].rsplit(".", 1)[0]
    caras, t = cara.generar_cara(f["ruta"], f, n=config.N_CARAS, plantilla=PROMPT_FINAL, pipe=PIPE,
                                 marg=MARG, tamano=TAMANO, carpeta=SALIDA4 / nombre)
    print(f"{f['nombre']}: {len(caras)} caras en {t.attrs['segundos_total']:.1f} s · reintentos {int(t['reintentos'].sum())}"
          f" · descartadas {int(t['descartada'].sum())}")
    CARAS4[f["nombre"]] = (f, caras, t)
    TABLAS4.append(t.assign(foto=f["nombre"]))
    tira = cara.tira(f["ruta"], caras, t)
    tira.save(SALIDA4 / f"tira_{nombre}.jpg", quality=92)
    registro.mostrar(tira)
TABLA4 = pd.concat(TABLAS4, ignore_index=True)
TABLA4.to_csv(SALIDA4 / "generacion.csv", index=False)
registro.mostrar(TABLA4[["foto", "k", "semilla_final", "reintentos", "descartada", "segundos", "intentos"]])
print(f"\\nTiempo medio por cara (con reintentos): {TABLA4['segundos'].mean():.1f} s")
registro.empaquetar()
""")

# ===================================================================== Etapa 5
md(r"""
---
# Etapa 5 · Ensamblado en LDraw
Se descarga la librería oficial (library.ldraw.org, `complete.zip`) y se lee sin descomprimir.
- Cabeza `3626c.dat` con la cara por `!TEXMAP START PLANAR -13 0 10 13 0 10 -13 21 10` (la misma convención que la
  cabeza oficial con textura `3626cpx0.dat`), con FALLBACK para visores sin texturas.
- Torso con brazos y manos `76382.dat`, caderas y piernas `73200b-f1.dat`, cabello del catálogo (buscado por
  descripción en la librería). PairLegoFace no trae cabello: el estilo sale de `config.CABELLO_MANUAL` o, si no, de
  `femenino` (supuesto), y el color, de las cejas.
- Cara de la minifig: de las 5 de la Etapa 4 (sin las descartadas), la que más rasgos de la foto respeta según CLIP
  (lentes y vello facial = barba o bigote, umbral `config.UMBRAL_RASGO_CLIP`); a igual puntaje, la de menor k.
  Los puntajes quedan en `eleccion_cara.csv`.
- Por cada foto de la Etapa 4: `minifig_<foto>.ldr`, `cabeza_<foto>.dat`, `textures/cara_<foto>.png`,
  `README_render.md` y una vista previa frontal aproximada.
""")
code("""
registro.seccion("5.1 Librería oficial y catálogo de cabello")
SALIDA5 = flux.carpeta("etapa5")
LIB = ldraw.Libreria(ldraw.descargar())
CATALOGO = ldraw.catalogo_cabello(LIB)
CATALOGO.to_csv(SALIDA5 / "catalogo_cabello.csv", index=False)
registro.mostrar(CATALOGO)

registro.seccion("5.2 Minifigs")
ETAPA5_OK = True
for foto, (f, caras, t) in CARAS4.items():
    nombre = foto.rsplit(".", 1)[0]
    rgba, i, puntos = cara.mejor(caras, t, f)
    rutas = ldraw.escribir_minifig(SALIDA5 / nombre, nombre, rgba, f, LIB, CATALOGO)
    print(f"\\n{foto}: cara #{i} · cabello {rutas['pelo']}")
    if puntos is not None:
        puntos.to_csv(SALIDA5 / nombre / "eleccion_cara.csv", index=False)
        registro.mostrar(puntos)
    ETAPA5_OK &= ldraw.verificar(rutas, LIB)
    ldraw.escribir_readme(rutas, nombre)
    previa = ldraw.vista_previa(rutas["ldr"], LIB)
    previa.save(SALIDA5 / nombre / f"vista_previa_{nombre}.png")
    registro.mostrar(previa)
print("\\nETAPA5_OK =", ETAPA5_OK)
""")

# ===================================================================== Etapa 6
md(r"""
---
# Etapa 6 · Anexo A: misma foto en ambos métodos, rondas 1 y 2 y una ronda con Variar
**Ronda** = una llamada que genera las 5 caras de una foto, como en la app.

| Ronda | Rasgos | Semillas |
|---|---|---|
| **Ronda 1** | los de la foto | `SEMILLA_FLUX + k` (42–46). En FLUX son las caras de la Etapa 4: se reutilizan |
| **Ronda 2** | los de la foto **con el cambio que pide el usuario** (`config.CAMBIO_RONDA2`) | las mismas de la ronda 1: la única diferencia es el cambio |
| **Variar** | el mismo pedido de la ronda 2 | otras: `SEMILLA_FLUX + SALTO_VARIAR + k` (142–146) |

El cambio por defecto es `{"lentes": "alternar"}`: si la persona tiene lentes se le quitan y si no, se le ponen.
Se puede pedir otro (`{"expresion": "sorpresa"}`, `{"barba": True}`, …) o uno por foto en `config.CAMBIOS_RONDA2_MANUAL`.

Para cada una de las `config.N_PERSONAS_MOSAICO` personas, el mosaico muestra la foto y 6 filas de 5 caras
(modelo propio y FLUX × ronda 1, ronda 2 y Variar). Cada cara lleva su semilla; las descartadas por el guardrail
salen en rojo. Para el Anexo A basta con el mosaico de una persona: `etapa6/mosaico_<foto>.jpg`.

**Modelo propio.** No vive en este notebook. Sus caras entran de una de estas dos formas (la primera que exista):
1. En la celda siguiente, `GENERAR_PROPIO = función(ruta_foto, rasgos, n, semilla_base)` que devuelva `n` imágenes PIL.
   En la ronda 2 y en Variar recibe los rasgos ya cambiados.
2. `config.CARPETA_PROPIO` apuntando a un Input con `<foto sin extensión>/ronda1/`, `/ronda2/` y `/variar/` (PNG).

Si no hay ninguna, las filas del modelo propio salen en gris como **pendiente** y el resto se arma igual.
""")
code("""
# Modelo propio: reemplaza None por la función de Persona 4, por ejemplo
#   def GENERAR_PROPIO(ruta_foto, rasgos, n, semilla_base):
#       return [modelo_propio(ruta_foto, rasgos, semilla=semilla_base + k) for k in range(n)]
GENERAR_PROPIO = None

registro.seccion("6.1 Anexo A · " + str(config.N_PERSONAS_MOSAICO) + " personas · " + config.NOMBRE_PROPIO
                 + " y FLUX · ronda 1, ronda 2 y Variar")
SALIDA6 = flux.carpeta("etapa6")
BLOQUES6, FILAS6 = [], []
for _, f in ELEGIDAS.head(config.N_PERSONAS_MOSAICO).iterrows():
    nombre = f["nombre"].rsplit(".", 1)[0]
    f2, cambio = mosaico.aplicar_cambio(f)
    print(f"\\n{f['nombre']} · cambio pedido en la ronda 2: {cambio}")
    print("  prompt ronda 1:", flux.frases(f)[0])
    print("  prompt ronda 2:", flux.frases(f2)[0])
    filas = []
    for metodo in (config.NOMBRE_PROPIO, "FLUX"):
        for r in mosaico.rondas():
            fr = f2 if r["cambio"] else f
            carpeta_r = SALIDA6 / nombre / f"{'flux' if metodo == 'FLUX' else 'propio'}_{r['clave']}"
            if metodo == "FLUX":
                previas = CARAS4[f["nombre"]][1:] if f["nombre"] in CARAS4 else None
                caras, t = mosaico.ronda_flux(fr, r, PROMPT_FINAL, PIPE, MARG, TAMANO, carpeta_r, previas)
                origen = t["origen"].iloc[0]
            else:
                caras, t, origen = mosaico.ronda_propio(fr, r, GENERAR_PROPIO, carpeta_r)
            filas.append(dict(metodo=metodo, ronda=r, caras=caras, tabla=t, origen=origen))
            n_ok = 0 if caras is None else int((~t["descartada"].astype(bool)).sum())
            estado = "pendiente" if caras is None else f"{n_ok}/{len(caras)} ok"
            print(f"  {metodo:<14} {r['nombre']:<8}: {estado} · semillas {r['base']}+k · {origen}")
            comun = dict(foto=f["nombre"], metodo=metodo, ronda=r["clave"], cambio=cambio if r["cambio"] else "",
                         origen=origen, prompt=PROMPT_FINAL.format(**flux.frases(fr)[0]))
            for _, x in t.iterrows():
                FILAS6.append(dict(**comun, k=x["k"], semilla=x["semilla_final"], descartada=bool(x["descartada"]),
                                   segundos=x["segundos"]))
            if caras is None:
                FILAS6.append(comun)
    BLOQUES6.append(dict(foto=f["ruta"], nombre=f["nombre"], cambio=cambio, filas=filas))
    mosaico.mosaico([BLOQUES6[-1]]).save(SALIDA6 / f"mosaico_{nombre}.jpg", quality=92)
TABLA6 = pd.DataFrame(FILAS6)
TABLA6.to_csv(SALIDA6 / "rondas.csv", index=False)
M6 = mosaico.mosaico(BLOQUES6)
M6.save(SALIDA6 / "mosaico_rondas.jpg", quality=92)
registro.mostrar(M6)
PROPIO_LISTO = not (TABLA6["origen"] == "pendiente").any()
print("\\nMosaico:", SALIDA6 / "mosaico_rondas.jpg", "· modelo propio", "incluido" if PROPIO_LISTO else "PENDIENTE (filas en gris)")
registro.empaquetar()
""")

md("## Resumen y paquete final\nDescarga **`flux_cara/entregar.zip`** del panel *Output* y mándalo.")
code("""
registro.seccion("Resumen")
print("Etapa 1 OK:", ETAPA1_OK)
print("Etapa 2: falla más común", repr(FALLA), CUENTAS, "· congelada", repr(MEJOR["variante"]), "· meta 8/10:", META_OK)
print("Etapa 3: pasan el guardrail", int((~TABLA3["descartada"]).sum()), "de", len(TABLA3))
print("Etapa 4: caras", len(TABLA4), "· descartadas", int(TABLA4["descartada"].sum()), "· s/cara", round(TABLA4["segundos"].mean(), 1))
print("Etapa 5 OK:", ETAPA5_OK)
print("Etapa 6 (Anexo A): mosaico de", len(BLOQUES6), "personas · ronda 1, ronda 2 con cambio y Variar · modelo propio",
      "incluido" if PROPIO_LISTO else "pendiente")
registro.empaquetar()
registro.detener()
""")

nb = dict(
    cells=celdas, nbformat=4, nbformat_minor=5,
    metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python", version="3.10"),
        kaggle=dict(accelerator="nvidiaTeslaT4", isInternetEnabled=True, isGpuEnabled=True,
                    language="python", sourceType="notebook"),
    ),
)
for c in nb["cells"]:                                   # formato estándar: lista de líneas
    c["source"] = c["source"].splitlines(keepends=True)
DESTINO.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"{DESTINO.name}: {len(celdas)} celdas")
