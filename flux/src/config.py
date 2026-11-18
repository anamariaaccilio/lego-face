"""Parámetros del proyecto. Todo valor incierto vive aquí, no escondido en los módulos.

En Kaggle este archivo lo escribe la primera celda del notebook: edítalo ahí y vuelve a correr.
"""
import os
from pathlib import Path

# ----------------------------------------------------------------- rutas (Kaggle)
ENTRADA = Path(os.environ.get("FLUX_CARA_ENTRADA", "/kaggle/input"))
SALIDA = Path(os.environ.get("FLUX_CARA_SALIDA", "/kaggle/working/flux_cara"))
RUTA_DATASET = None                  # None = buscar PairLegoFace bajo ENTRADA; o la ruta exacta
PATRON_NOMBRE_DATASET = r"pair.?lego.?face"

# ----------------------------------------------------------------- Etapa 0: exploración
MUESTRA_TAMANOS = 300                # imágenes por carpeta a las que se les lee el tamaño (None = todas)
LINEAS_ARBOL = 60                    # máximo de carpetas que imprime el árbol

# Cómo se reconocen las columnas de las tablas (regex, sin distinguir mayúsculas). El orden importa:
# una columna queda asignada al primer rol que la reconoce.
PATRONES_COLUMNA = {
    "particion": r"split|partic|subset|^set$|conjunto",
    "estampa": r"lego|mascara|máscara|mask|estampa|stamp|decal",
    "foto": r"foto|photo|imagen|image|img|ruta|path|file|archivo",
    "id": r"^id$|^id_|_id$",
    "version": r"^version$|^versión$|^g$",
    "ok": r"^pasa$|^ok$|^valid[ao]?$|^aprobad",
    "color_pelo": r"(colou?r.*(pelo|cabell|hair|ceja|brow))|((pelo|cabell|hair|ceja|brow).*colou?r)",
    "cabello": r"cabell|pelo|hair|peinado",
    "lentes": r"lente|glass|gafa|anteojo",
    "barba": r"barba|beard",
    "bigote": r"bigote|mous|mustach",
    "vello": r"vello|facial",
    "expresion": r"expres|emoci|gesto|smile|sonri",
    "femenino": r"femenin|^mujer|female",
    "edad": r"^edad$|^age$",
    "texto": r"prompt|descrip|caption",        # texto libre del que se pueden leer expresión y cabello
}
# Palabras en la ruta (relativa al dataset, sin el nombre del dataset) que delatan una estampa
PALABRAS_ESTAMPA = r"lego|mascara|máscara|mask|estampa|stamp|decal"
# Las estampas se buscan por nombre en TODO ENTRADA (pueden venir en otro Input de Kaggle)
BUSCAR_ESTAMPAS_EN_TODO_INPUT = True
LADO_MAX_ESTAMPA = 256               # una imagen con alfa y lado <= esto se considera estampa
PARTICIONES = {                      # nombre normalizado <- palabras en la columna o en las carpetas
    "prueba": ("test", "prueba", "testing"),
    "validacion": ("val", "valid", "validation", "validacion", "validación"),
    "entrenamiento": ("train", "training", "entrenamiento"),
}
VALORES_SI = {"true", "1", "1.0", "si", "sí", "yes", "y", "x", "t"}
VALORES_NO = {"false", "0", "0.0", "no", "n", "f", "ninguno", "ninguna", "none"}

# Expresión del dataset -> una de: sonrisa, serio, sorpresa, neutral.
MAPEO_EXPRESION = {}                 # p. ej. {"sonrie_dientes": "sonrisa"}; manda sobre los patrones
PATRONES_EXPRESION = [               # se prueban en orden si el valor no está en MAPEO_EXPRESION
    ("sorpresa", r"sorpr|surpri|asombr|open"),
    ("neutral", r"neutr|calm"),
    ("sonrisa", r"sonr|smil|feliz|happy|ri[eé]|alegr"),
    ("serio", r"seri|enoj|angry|triste|sad"),
]
# Si la tabla no tiene columna de expresión/cabello, se leen del texto libre (columna "texto", p. ej. el prompt).
# Se prueban en orden; el primero que calza gana.
PATRONES_EXPRESION_TEXTO = [
    ("serio", r"not smil|no smil|without (a )?smil|serious|stern|frown|scowl|angry|grumpy|unsmiling|grimac|annoyed"
              r"|worried|determined|pursed|closed mouth|straight mouth|sad|serio"),
    ("sorpresa", r"surpris|shock|astonish|amazed|scream|gasp|o-shaped mouth"
                 r"|(open[- ]mouth(ed)?|mouth open)(?![\w -]{0,15}(smil|grin|laugh))|sorpr"),
    ("sonrisa", r"smil|smirk|grin|laugh|joyful|cheerful|teeth|tongue|sonr"),
    ("neutral", r"neutral|calm|relaxed|expressionless|blank expression"),
]
# En PairLegoFace el prompt describe la cara LEGO de origen: "...facial features from the LEGO face: white thick
# eyebrows, lopsided grin. Keep the same expression...". Si este patrón calza, expresión y cejas se leen SOLO de
# esa cláusula (el resto del prompt habla de "expression" y "facial hair" en general y confunde).
PATRON_CLAUSULA_RASGOS = r"features from the lego face:\s*(.+?)\.(?:\s|$)"
# Color de cejas: se busca el color dentro del trozo de la cláusula que dice "eyebrows" (el más largo primero)
COLORES_CEJAS = ["light bluish gray", "dark bluish gray", "reddish brown", "medium nougat", "dark brown",
                 "light brown", "dark orange", "dark tan", "nougat", "auburn", "blonde", "brown", "black", "white",
                 "gray", "grey", "orange", "ginger", "red", "tan", "yellow", "silver"]
MAPEO_COLOR_CEJAS = {"nougat": "light brown", "medium nougat": "light brown", "dark tan": "tan",
                     "light bluish gray": "gray", "dark bluish gray": "dark gray", "grey": "gray", "silver": "gray"}
PATRONES_CABELLO_TEXTO = [
    ("calvo", r"bald|shaved head|calv"),
    ("largo", r"long (\w+ ){0,2}hair|ponytail|braid|pelo largo"),
    ("rizado", r"curly|afro|rizad"),
    ("corto", r"short (\w+ ){0,2}hair|buzz cut|crew cut|pelo corto"),
]
PATRON_COLOR_PELO_TEXTO = r"\b(black|dark brown|light brown|brown|blonde?|red|ginger|auburn|gr[ae]y|white|silver)\b[\w ,-]{0,15}?\bhair"

# Rasgos a mano: mandan sobre los del dataset. Clave = nombre de archivo de la foto (o su id).
# Ej.: {"p00_00.jpg": {"lentes": True, "barba": False, "bigote": False, "expresion": "sonrisa",
#                      "cabello": "corto", "color_pelo": "black"}}
RASGOS_MANUALES = {}

# Estampas sin alfa: el trazo se separa del fondo como en el post-proceso
BORDE_FONDO = 0.05                   # 5 % exterior para estimar el fondo
UMBRAL_LAB_ESTAMPA = 25.0            # distancia Lab al fondo para ser trazo

# Tamaño final de la estampa (ancho, alto). None = el más común entre las estampas reales.
TAMANO_FINAL = None
TAMANO_POR_DEFECTO = (128, 118)      # (ancho, alto) medido en las 351 estampas de LegosPartsVae (100 %)
MARGEN_POR_DEFECTO = dict(arriba=0.10, abajo=0.10, izquierda=0.10, derecha=0.10)

# Selección de las 10 fotos de prueba
N_FOTOS = 10
SEMILLA = 1234
VARIEDAD = [("lentes", True), ("lentes", False), ("barba", True), ("bigote", True),
            ("expresion", "sonrisa"), ("expresion", "serio"),
            ("expresion", "sorpresa"), ("expresion", "neutral"),
            ("femenino", True), ("femenino", False)]
NOVEDAD = ("pieza", "edad")          # bonus por elegir una cara LEGO o una edad que aún no está entre las elegidas
FOTOS_FORZADAS = []                  # nombres de archivo que quieres sí o sí entre las 10

# ----------------------------------------------------------------- Etapa 1: FLUX.2-klein-4B
# Verificado en la ficha oficial (huggingface.co/black-forest-labs/FLUX.2-klein-4B, Apache-2.0):
#   model_index.json -> Flux2KleinPipeline (transformer Flux2Transformer2DModel, text_encoder Qwen3ForCausalLM),
#   "is_distilled": true; ejemplo oficial con guidance_scale=1.0 y num_inference_steps=4; la imagen de
#   referencia se pasa con image= (PIL o lista de PIL). Requiere diffusers >= 0.37.
# device_map="balanced": soportado a nivel de pipeline en diffusers (experimental; solo "balanced").
MODELO_ID = "black-forest-labs/FLUX.2-klein-4B"
DTYPE = "bfloat16"                   # el del ejemplo oficial. En T4 (sin bf16 nativo) va más lento; "float16" puede dar NaN
DEVICE_MAP = "balanced"              # reparte los componentes entre las 2 T4
MAX_MEMORY = None                    # p. ej. {0: "14GiB", 1: "14GiB"}; None = toda la memoria de cada GPU
PASOS = 4
GUIA = 1.0
ANCHO, ALTO = 512, 512
SEMILLA_FLUX = 42                    # semilla fija (igual para las 10 fotos)
GENERADOR_EN = "cpu"                 # torch.Generator en cpu: reproducible aunque el pipeline esté repartido
LADO_REFERENCIA = 512                # la foto de referencia se recorta al centro a este cuadrado

PROMPT_BASE = (
    "Flat 2D printed face decal of a LEGO minifigure, front view, on a plain solid bright yellow background "
    "that fills the whole image. It is the LEGO face of the person in the reference photo: {expresion}, "
    "{lentes}, {vello}, eyebrows in {color}. Simple printed strokes with sharp edges and flat solid colors, "
    "small black oval eyes, only the facial features. No head outline, no hair, no shading, no 3D, no shadows, "
    "no text, no realistic skin."
)
FRASES = {                           # tabla de rasgos -> frase (de la especificación)
    "lentes": {True: "wearing black rectangular glasses", False: "no glasses"},
    "barba": "short beard",
    "bigote": "moustache",
    "expresion": {"sonrisa": "a wide smile", "serio": "a closed straight mouth and flat eyebrows",
                  "sorpresa": "an open round mouth and raised eyebrows", "neutral": "a small calm smile"},
}
FRASE_SIN_VELLO = "no facial hair"   # supuesto: sin barba ni bigote
UNIR_VELLO = " and "                 # barba + bigote -> "short beard and moustache"
EXPRESION_POR_DEFECTO = "neutral"    # si la foto no tiene expresión (queda marcado en prompts.csv)
COLOR_CEJAS_POR_DEFECTO = "black"    # si no se leyó el color de cejas

# ----------------------------------------------------------------- Etapa 2: ajuste del prompt
# Juez automático de cada imagen (estimación; la grilla de cada variante queda para revisar a ojo).
USAR_CLIP = True                     # CLIP zero-shot para "¿es plana?", "¿tiene lentes/barba?", "¿solo rasgos?"
MODELO_CLIP = "openai/clip-vit-base-patch32"
CLIP_TEXTOS = {
    "plana": ["a flat 2D vector drawing of a cartoon face", "a 3D render of a toy head", "a realistic photo of a person"],
    "lentes": ["a cartoon face wearing glasses", "a cartoon face without glasses"],
    "barba": ["a cartoon face with a beard", "a cartoon face without a beard"],
    "solo_rasgos": ["eyes, eyebrows and mouth printed on a plain yellow background",
                    "a complete cartoon head with a face outline, ears and hair"],
    # Etapa 5 (elegir la cara de la minifig): "moustache" solo no separa; "facial hair" sí (corrida 2026-11-16:
    # con bigote 0.63–0.82, sin bigote 0.31–0.41, sin vello <= 0.35, con barba >= 0.89)
    "vello": ["a cartoon face with facial hair", "a clean-shaven cartoon face"],
}
UMBRAL_RASGO_CLIP = 0.5              # prob. del primer texto para decir "tiene lentes" / "tiene vello"
AMARILLO_COMPUESTO = (250, 215, 0)   # fondo sobre el que se juzga la estampa RGBA
# Fondo amarillo: mediana del borde (BORDE_FONDO) en HSV + que la mayoría del borde sea ese fondo
AMARILLO_H = (35, 75)                # tono en grados
AMARILLO_S_MIN, AMARILLO_V_MIN = 0.45, 0.55
# Plana (respaldo si no hay CLIP): fracción de píxeles del trazo con degradé suave (sombreado) en L*
GRADIENTE_SUAVE = (2.0, 12.0)
MAX_FRACCION_SUAVE = 0.20
REVISION_MANUAL = {}                 # {"v1_vector": {3: {"plana": False}}} manda sobre el juez automático
META_PLANAS_AMARILLAS = 8            # de 10
# 3 variantes por falla: la Etapa 2 detecta la falla más común de la Etapa 1 y prueba las 3 de esa falla.
VARIANTES = {
    "3d": {
        "v1_vector": "Flat vector illustration, like a printed sticker with zero depth. " + PROMPT_BASE
                     + " Pure 2D graphic: no gradients, no lighting, no volume.",
        "v2_tinta": "A simple black ink print on a flat bright yellow surface, seen straight on: the LEGO minifigure face "
                    "of the person in the reference photo, drawn as minimal graphic strokes: {expresion}, {lentes}, "
                    "{vello}, eyebrows in {color}, small black oval eyes. Flat solid colors only. No head shape, no hair, "
                    "no shading, no 3D, no shadows, no text, no realistic skin.",
        "v3_corto": "2D flat printed LEGO face decal on solid bright yellow: {expresion}, {lentes}, {vello}, eyebrows "
                    "in {color}, small black oval eyes. Flat colors, sharp edges. Not 3D, no shading, no hair, no head outline.",
    },
    "fondo": {
        "v1_fondo_hex": PROMPT_BASE + " The background is one flat uniform bright yellow color (#F2CD37) from edge to "
                        "edge, with nothing else in it.",
        "v2_fondo_primero": "Solid bright yellow background filling the entire image, edge to edge. On it: " + PROMPT_BASE,
        "v3_fondo_papel": "A flat sheet of bright yellow paper filling the whole frame, with a LEGO minifigure face printed "
                          "on it, based on the person in the reference photo: {expresion}, {lentes}, {vello}, eyebrows "
                          "in {color}, small black oval eyes. Flat solid colors, sharp edges. No head outline, no hair, "
                          "no shading, no 3D, no shadows, no text.",
    },
    "cara_completa": {
        "v1_solo_rasgos": PROMPT_BASE + " Draw ONLY the eyes, eyebrows, mouth (and glasses or facial hair if mentioned) "
                          "directly on the yellow background; do not draw the head shape, face contour, ears, neck or hair.",
        "v2_lista": "Bright solid yellow background. Printed on it, nothing but these facial marks of the person in the "
                    "reference photo: two small black oval eyes, eyebrows in {color}, {expresion}, {lentes}, {vello}. "
                    "No face outline, no head, no ears, no hair, no skin, no shading, no 3D.",
        "v3_recortado": "Close-up of a flat LEGO face print, only the printed features, cropped tight on a plain "
                        "bright yellow background: {expresion}, {lentes}, {vello}, eyebrows in {color}, small "
                        "black oval eyes. No head outline, no hair, no shading, no 3D, no shadows, no text.",
    },
}

# ----------------------------------------------------------------- Etapa 3: post-proceso a RGBA
UMBRAL_LAB = 25.0                    # distancia Lab al fondo para ser trazo
APERTURA = 3                         # apertura morfológica 3x3
MIN_COMPONENTE = 15                  # se borran componentes de menos de 15 px
ESTADISTICO_MARGEN = "mediana"       # "mediana" o "media" de las estampas reales (margenes.json)
MARGEN_LATERAL_MIN = 0.05            # el trazo se centra sin deformarlo; nunca más cerca del borde que esto
COBERTURA_MIN, COBERTURA_MAX = 0.02, 0.50   # guardrail: fracción del área que es trazo
BORDE_FONDO_MIN = 0.60               # guardrail: fracción del borde que debe ser fondo
# guardrail "cabeza dibujada": área de la silueta rellena más grande. Medido en la corrida del 2026-11-16:
# cabezas (contorno o piel) 0.39–0.51 · solo rasgos (incl. lentes y barba en U) <= 0.18
SILUETA_MAX = 0.30
SILUETA_CIERRE = 5                   # iteraciones de cierre 3x3 para tapar cortes chicos del contorno

# ----------------------------------------------------------------- Etapa 4: generación completa
N_CARAS = 5
SALTO_REINTENTO, MAX_REINTENTOS = 1000, 2   # semilla + 1000, máximo 2 reintentos
N_FOTOS_ETAPA4 = 3                   # cuántas de las 10 fotos pasan por la Etapa 4 (5 caras cada una)

# ----------------------------------------------------------------- Etapa 6: mosaico del Anexo A
# Ronda = una llamada que genera las N_CARAS caras de una foto, como en la app.
#   Ronda 1: rasgos de la foto, semillas SEMILLA_FLUX + k (las de la Etapa 4, se reutilizan)
#   Ronda 2: el usuario pide un cambio (CAMBIO_RONDA2), mismas semillas -> la diferencia es solo el cambio
#   Variar:  mismo pedido que la ronda 2, semillas SEMILLA_FLUX + SALTO_VARIAR + k
N_PERSONAS_MOSAICO = 3               # personas distintas (las primeras de las 10 elegidas); el Anexo A usa una
# Cambio pedido en la ronda 2. "alternar" invierte un rasgo sí/no (lentes, barba, bigote).
# También vale un valor fijo: {"expresion": "sorpresa"}, {"barba": True}, {"color_cejas": "brown"}.
CAMBIO_RONDA2 = {"lentes": "alternar"}
CAMBIOS_RONDA2_MANUAL = {}           # por foto, manda sobre CAMBIO_RONDA2: {"3626cp76_04.jpg": {"expresion": "sorpresa"}}
SALTO_VARIAR = 100                   # Variar -> semillas 142..146 (no debe chocar con SALTO_REINTENTO = 1000)
NOMBRE_PROPIO = "Modelo propio"      # etiqueta de las filas del modelo del equipo
CARPETA_PROPIO = None                # p. ej. "/kaggle/input/caras-propio": <foto>/{ronda1,ronda2,variar}/*.png

# ----------------------------------------------------------------- Etapa 5: LDraw
# Verificado en la librería oficial (complete.zip de library.ldraw.org):
#   3626c.dat "Minifig Head with Hollow Stud" = s\3626cs01.dat + 5 líneas de la mitad frontal;
#   3626cpx0.dat (cabeza oficial con textura) aplica la cara con
#   "0 !TEXMAP START PLANAR -13 0 10 13 0 10 -13 21 10 <png>" sobre esa mitad frontal (líneas "0 !:").
#   76382.dat "Minifig Torso with Arms and Hands"; 73200b-f1.dat "Minifig Hips and Legs (Standing)".
#   Pelo: piezas "Minifig Hair ..." con el mismo origen que la cabeza (cajas medidas en la librería).
# Especificación !TEXMAP: ldraw.org/texmap-spec.html (la textura se busca en textures/<png> y luego <png>).
LDRAW_URL = "https://library.ldraw.org/library/updates/complete.zip"
LDRAW_ZIP = Path(os.environ.get("FLUX_CARA_LDRAW_ZIP", "/tmp/ldraw/complete.zip"))   # fuera de /kaggle/working
LDRAW_USER_AGENT = "Mozilla/5.0 (compatible; flux-cara-ldraw/1.0)"   # el UA por defecto de Python recibió 403
LDRAW_BUSCAR_EN = ["/kaggle/input"]  # plan B: un complete.zip subido como Input se usa sin descargar
CABEZA = "3626c.dat"
TEXMAP_PLANAR = "-13 0 10 13 0 10 -13 21 10"
TORSO = "76382.dat"                  # se copian sus líneas para dar a las manos su propio color
PIERNAS = "73200b-f1.dat"
POS_CABEZA = (0, -24, 0)             # cabeza y -4..24 apoyada sobre el torso (y -12..32)
POS_PIERNAS = (0, 32, 0)             # caderas bajo el torso
COLOR_CABEZA = "Yellow"              # nombres de LDConfig.ldr (el código se lee de ese archivo)
COLOR_MANOS = "Yellow"
COLOR_TORSO = "Red"
COLOR_PIERNAS = "Blue"
# Catálogo de cabello: estilo -> descripciones a buscar en la librería (se usa la primera que exista)
CATALOGO_CABELLO = {
    "corto": ["Minifig Hair Short Tousled", "Minifig Hair Male"],
    "largo": ["Minifig Hair Female Long Straight", "Minifig Hair Long Straight"],
    "rizado": ["Minifig Hair Bubble Style (Afro)", "Minifig Hair Coiled"],
    "coleta": ["Minifig Hair Ponytail"],
    "bob": ["Minifig Hair Short Bob Cut"],
    "calvo": [],
}
# PairLegoFace no trae cabello: estilo por defecto según 'femenino' (supuesto) salvo que lo pases a mano
CABELLO_POR_DEFECTO = {True: "largo", False: "corto", None: "corto"}
CABELLO_MANUAL = {}                  # {"3626cp7a_04.jpg": "rizado"}
COLOR_PELO_LDRAW = {                 # color de cejas (texto) -> nombre en LDConfig.ldr
    "black": "Black", "dark brown": "Dark_Brown", "brown": "Reddish_Brown", "reddish brown": "Reddish_Brown",
    "light brown": "Medium_Nougat", "tan": "Tan", "blonde": "Tan", "yellow": "Bright_Light_Yellow",
    "white": "White", "gray": "Light_Bluish_Grey", "dark gray": "Dark_Bluish_Grey", "red": "Dark_Orange",
    "orange": "Dark_Orange", "ginger": "Dark_Orange", "auburn": "Reddish_Brown",
}
COLOR_PELO_POR_DEFECTO = "Black"
LADO_PREVIA = 600                    # vista previa frontal aproximada (no reemplaza el render)
