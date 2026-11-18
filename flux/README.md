# FLUX · Cara LEGO con FLUX + minifig LDraw

A partir de la **foto de una persona** se genera la **estampa de su cara LEGO** con FLUX.2-klein-4B (sin entrenar) y se arma una **minifig en LDraw** con esa cara, el cabello y el color de ropa más parecidos a la foto. Al final se hace un render 3D.

```
foto ──► FLUX (Kaggle, GPU) ──► cara RGBA ──► minifig .ldr ──► cabello/ropa (local) ──► render 3D (local)
```

## Contenido

| Archivo / carpeta | Qué es |
|---|---|
| `flux_cara_ldraw.ipynb` | **Notebook principal.** Corre en Kaggle con GPU y hace las etapas Datos y 1–6. |
| `cabello_minifigs.ipynb` | Notebook local, sin GPU. Elige el cabello (y, si quieres, el color de ropa) de cada minifig para que se parezca a la foto. |
| `render_minifigs.ipynb` | Notebook local, sin GPU. Hace el render 3D de las minifigs (lámina con la estampa y 5 vistas). |
| `src/` | El código. **Los `.py` son la fuente de verdad**: los notebooks se generan a partir de ellos. |
| `construir_notebook.py`, `construir_cabello.py`, `construir_render.py` | Vuelven a generar los 3 notebooks después de editar `src/`. |
| `tests/` | Prueban el pipeline completo sin GPU, con FLUX y CLIP falsos. |
| `salidas_kaggle/entregar/` | Resultados de la última corrida, incluido `reporte.txt` con todo lo que se imprimió. |

### Módulos de `src/`

| Módulo | Función |
|---|---|
| `config.py` | Todos los parámetros (modelo, semillas, umbrales, rutas). |
| `dataset.py` | Lee PairLegoFace, detecta las columnas y elige 10 fotos de prueba variadas. |
| `flux.py` | Carga FLUX.2-klein y genera las imágenes. |
| `postproceso.py` | Pasa la imagen a RGBA (quita el fondo amarillo) y aplica el guardrail de calidad. |
| `ajuste.py` | Ajusta el encuadre a los márgenes de las estampas LEGO reales. |
| `cara.py` | `generar_cara(foto, rasgos, n=5)` con reintentos. |
| `ldraw.py` | Arma la minifig `.ldr` y aplica la cara con `!TEXMAP PLANAR`. |
| `registro.py` | Arma `reporte.txt` y `entregar.zip`. |
| `mosaico.py` | Etapa 6 (Anexo A). Una *ronda* = una llamada que genera las 5 caras de una foto. Ronda 1: rasgos de la foto. Ronda 2: con el cambio de `CAMBIO_RONDA2` (por defecto alterna los lentes) y las mismas semillas. Variar: el pedido de la ronda 2 con otras semillas (142–146). |
| `cabello.py`, `ropa.py`, `estampa.py` | Sugieren el cabello y el color de ropa a partir de la foto (uso local). |
| `render.py` | Rasterizador 3D en numpy (perspectiva, z-buffer, luz y textura de la cara). |

## Cómo correrlo

### 1. Kaggle: generar las caras y las minifigs

1. Subir `flux_cara_ldraw.ipynb` a Kaggle.
2. *Add Input* → **PairLegoFace** y **LegosPartsVae**.
3. *Settings* → **Internet: On** y **Accelerator: GPU T4 x2**.
4. *Run All*. La primera vez descarga FLUX (~16 GB) y la librería LDraw (~140 MB).
5. Desde el panel *Output*, descargar `flux_cara/entregar.zip` y descomprimirlo en `salidas_kaggle/entregar/`.

> Este paquete ya trae los resultados en `salidas_kaggle/entregar/`, así que puedes saltarte este paso y pasar directo al 2.

### 2. Local: cabello y render (sin GPU)

Requisitos: Python con `numpy`, `pillow`, `pandas` y Jupyter.

1. Abrir `cabello_minifigs.ipynb`, revisar la galería de peinados y poner tu elección en `ELECCION` (o aceptar la sugerencia). Para cambiar también la ropa, poner `CAMBIAR_ROPA = True` y los colores en `ROPA`. El notebook reescribe `minifig_<foto>.ldr` y guarda una copia `.orig`.
2. Abrir `render_minifigs.ipynb` y correrlo. Los renders quedan en `salidas_kaggle/entregar/etapa5/<foto>/renders/`.

La librería oficial LDraw (`complete.zip`) **no viene en el paquete porque pesa 140 MB**: se descarga sola a `ldraw/complete.zip` la primera vez.

### 3. Tests (opcional)

```
FLUX_CARA_LDRAW_ZIP=ldraw/complete.zip python tests/test_notebook.py
```

## Etapas y resultados de la última corrida

| Etapa | Qué hace | Resultado | Archivos |
|---|---|---|---|
| Datos | Elige 10 fotos de prueba y mide los márgenes de 351 estampas reales | Encuadre final 128×118 px | `datos/` |
| 1 | Carga FLUX una sola vez y genera 1 imagen por foto | OK · ~34 s por imagen | `etapa1/grilla_etapa1.jpg`, `prompts.csv`, `tiempos.csv` |
| 2 | Detecta la falla más común con CLIP, prueba 3 variantes de prompt y deja fija la mejor | Falla más común: dibujaba la **cabeza completa** (10/10). Prompt fijado: `v3_recortado` | `etapa2/tabla_prompts.csv`, `prompt_congelado.txt`, grillas |
| 3 | Post-proceso a RGBA con guardrail | **10/10** pasan el guardrail | `etapa3/grilla_rgba.jpg`, `caras/` |
| 4 | Genera 5 caras por foto con reintentos | 15 caras · 1 descartada · ~42 s por cara | `etapa4/` |
| 5 | Arma la minifig LDraw con la cara aplicada | OK · 3 minifigs con todos los chequeos LDraw en ✅ | `etapa5/<foto>/` |
| 6 | Anexo A: misma foto con modelo propio y FLUX · ronda 1, ronda 2 (con un cambio pedido) y Variar · 5 caras cada una | Aún no se corre en Kaggle | `etapa6/mosaico_rondas.jpg`, `rondas.csv` |
| Cabello + render | Cabello elegido según la foto y render 3D | 3 minifigs renderizadas | `etapa5/cabello_elegido.csv`, `etapa5/renders_todas.png` |

Detalle del prompt fijado (`v3_recortado`): 10/10 caras planas y amarillas, 10/10 con solo los rasgos, **6/10 respetan los lentes y la barba**.

**Para ver el resultado final rápido:** `salidas_kaggle/entregar/etapa5/renders_todas.png` y la `lamina_<foto>.png` de cada minifig.

## Limitaciones

- Lentes y barba se respetan en 6 de 10 casos: FLUX se usa sin entrenar, solo con el prompt.
- El cabello sale por defecto según el género y el color de las cejas. Para que se parezca a la foto hay que elegirlo en `cabello_minifigs.ipynb`; las 3 minifigs entregadas ya tienen el cabello elegido a mano.
- El render es un rasterizador propio y simple. Para un render más realista, los `.ldr` se pueden abrir en LDView o Blender (instrucciones en cada `README_render.md`).
