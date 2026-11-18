"""Cabello de las minifigs parecido al de la foto (después de la Etapa 5, antes del render).

La Etapa 5 pone un estilo por defecto (corto / largo según `femenino`) y el color de las cejas. Aquí:
    f = cabello.foto(CARPETA_ENTREGAR, "3626bp39_09")        # la foto original (o su miniatura de las grillas)
    s = cabello.estimar(f, femenino=False)                     # sugerencia: color LDraw + estilo (heurística)
    hoja = cabello.galeria(lib, carpeta, ESTILOS, s["color"])  # cabeza + cada peinado, para elegir a ojo
    cabello.aplicar(lib, carpeta, "peinado_atras", "Dark_Bluish_Grey")   # reescribe minifig_<foto>.ldr
    cabello.restaurar(carpeta)                                 # vuelve al .ldr de la Etapa 5

Las piezas de pelo de LDraw comparten el origen de la cabeza, así que van en la misma posición que ella.
"""
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import render

CRLF = "\r\n"

# Estilo -> pieza oficial (descripción entre paréntesis). Agrega más con buscar(lib, "texto").
ESTILOS = {
    "calvo": None,
    "corto": "40233.dat",            # Short Tousled
    "corto_liso": "21788.dat",       # Short Smooth
    "corto_lado": "15500.dat",       # Short Combed Sideways Part Right
    "clasico": "3901.dat",           # Male (el clásico)
    "tupe": "21787.dat",             # Short Quiff
    "peinado_atras": "64798.dat",    # Backslick
    "atras_abultado": "28551.dat",   # Bushy Swept Back
    "atras_despeinado": "61183.dat", # Swept Back Tousled
    "ondulado_corto": "3277.dat",    # Short Wavy Parted on Right
    "rizado": "87995.dat",           # Bubble Style (Afro)
    "rizado_largo": "29634.dat",     # Female Very Curly - Parted in Middle
    "bob": "62711.dat",              # Short Bob Cut
    "media_melena": "2632.dat",      # Female Mid-Length, Wavy, Parted in Center
    "media_oreja": "36037.dat",      # Female Mid-Length Combed Behind Ear
    "largo": "12890.dat",            # Female Long Straight
    "largo_ondulado": "40251.dat",   # Long Wavy
    "largo_raya": "95225.dat",       # Long Wavy Parted in Center
    "coleta": "6093a.dat",           # Ponytail
    "mono": "99240.dat",             # Swept Back Into Bun
}

# Colores de pelo (nombres de LDConfig.ldr) entre los que elige estimar().
COLORES_PELO = ["Black", "Dark_Brown", "Reddish_Brown", "Medium_Nougat", "Dark_Tan", "Tan",
                "Bright_Light_Yellow", "Dark_Orange", "Dark_Bluish_Grey", "Light_Bluish_Grey", "White"]


# ===================================================================== fotos
def foto(carpeta_entregar, nombre, fotos_originales=None):
    """Foto de la persona. Prioridad: carpeta con los originales (p. ej. bajados de Kaggle) >
    miniatura de datos/grilla_10.jpg (200 px) > miniatura de etapa4/tira_<foto>.jpg (160 px)."""
    carpeta_entregar = Path(carpeta_entregar)
    if fotos_originales:
        for r in Path(fotos_originales).rglob(f"{nombre}.*"):
            if r.suffix.lower() in (".jpg", ".jpeg", ".png"):
                return Image.open(r).convert("RGB")
    csv, grilla = carpeta_entregar / "datos" / "fotos_elegidas.csv", carpeta_entregar / "datos" / "grilla_10.jpg"
    if csv.exists() and grilla.exists():
        df = pd.read_csv(csv)
        fila = df[df["id"] == nombre]
        if len(fila) and int(fila.iloc[0]["idx"]) < 10:          # grilla de 5 pares (foto | estampa) por fila
            i = int(fila.iloc[0]["idx"])
            x, y = (i % 5) * 400, (i // 5) * 230
            return Image.open(grilla).convert("RGB").crop((x, y, x + 200, y + 200))
    tira = carpeta_entregar / "etapa4" / f"tira_{nombre}.jpg"
    if tira.exists():
        return Image.open(tira).convert("RGB").crop((0, 0, 160, 160))
    return None


def datos_foto(carpeta_entregar, nombre):
    """Fila de datos/fotos_elegidas.csv (femenino, edad, color de cejas…) o {}."""
    csv = Path(carpeta_entregar) / "datos" / "fotos_elegidas.csv"
    if not csv.exists():
        return {}
    df = pd.read_csv(csv)
    fila = df[df["id"] == nombre]
    return fila.iloc[0].to_dict() if len(fila) else {}


# ===================================================================== estimación (heurística)
def _lab(rgb):
    c = np.asarray(rgb, float) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]])
    xyz = xyz / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _piel(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 95) & (r > g) & (g > b) & (r - b > 25)


def color_ldraw(lib, rgb, candidatos=None):
    """Color de LDConfig.ldr más cercano (ΔE en Lab) a un RGB de la foto."""
    candidatos = [c for c in (candidatos or COLORES_PELO) if c in lib.colores]
    hexes = np.array([[int(lib.colores[c][1][k:k + 2], 16) for k in (1, 3, 5)] for c in candidatos])
    d = np.linalg.norm(_lab(hexes) - _lab(np.asarray(rgb, float)), axis=1)
    return candidatos[int(d.argmin())]


def estimar(img, lib, femenino=None):
    """Sugerencia a partir de la foto (retrato de frente, pared clara detrás):
    - color: mediana de los píxeles de pelo de la franja superior (ni pared ni piel) -> color LDraw más cercano;
    - estilo: calvo si casi no hay pelo arriba; largo si hay pelo a los lados de la cara; si no, corto
      (o media_melena si femenino). Es una heurística: mira la galería y corrige con ELECCION."""
    a = np.asarray(img.convert("RGB").resize((200, 200)), float)
    esquinas = np.concatenate([a[:15, :15].reshape(-1, 3), a[:15, -15:].reshape(-1, 3)])
    fondo = np.median(esquinas, 0)
    no_fondo = np.linalg.norm(a - fondo, axis=-1) > 45
    arriba = (slice(4, 36), slice(60, 140))
    pelo = no_fondo[arriba] & ~_piel(a[arriba])
    frac_arriba = float(pelo.mean())
    rgb = np.median(a[arriba][pelo], 0) if pelo.sum() > 30 else np.array([40.0, 40, 40])
    parecido = (np.linalg.norm(a - rgb, axis=-1) < 55) & no_fondo
    lados = np.concatenate([parecido[100:145, 8:40].ravel(), parecido[100:145, 160:192].ravel()])
    frac_lados = float(lados.mean())
    if frac_arriba < 0.15:
        estilo = "calvo"
    elif frac_lados > 0.15:
        estilo = "largo"
    else:
        estilo = "media_melena" if femenino else "corto"
    return dict(color=color_ldraw(lib, rgb), foto=hex_de(rgb), estilo=estilo, rgb=tuple(int(v) for v in rgb),
                pelo_arriba=round(frac_arriba, 2), pelo_lados=round(frac_lados, 2))


def muestra(rgb, hex_ldraw, lado=40):
    """Dos cuadritos: color medido en la foto | color LDraw elegido."""
    im = Image.new("RGB", (2 * lado, lado))
    im.paste(tuple(rgb), (0, 0, lado, lado))
    im.paste(tuple(int(hex_ldraw[k:k + 2], 16) for k in (1, 3, 5)), (lado, 0, 2 * lado, lado))
    return im


# ===================================================================== catálogo
def buscar(lib, texto=""):
    """Piezas 'Minifig Hair' de la librería cuya descripción contiene `texto` (sin distinguir mayúsculas)."""
    filas = [(p, d) for p, d in lib.descripciones().items()
             if d.startswith("Minifig Hair") and texto.lower() in d.lower()]
    return pd.DataFrame(sorted(filas, key=lambda x: x[1]), columns=["pieza", "descripcion"])


def catalogo(lib, estilos=None):
    estilos = estilos or ESTILOS
    desc = lib.descripciones()
    return pd.DataFrame([dict(estilo=e, pieza=p or "(sin pelo)", descripcion=desc.get(p, "—") if p else "—")
                         for e, p in estilos.items()])


# ===================================================================== .ldr
def _es_pelo(lib, linea):
    p = linea.split()
    if len(p) < 15 or p[0] != "1":
        return False
    return lib.descripciones().get(p[14].lower(), "").startswith("Minifig Hair")


def _linea_cabeza(texto):
    for l in texto.splitlines():
        p = l.split()
        if len(p) >= 15 and p[0] == "1" and p[14].lower().startswith("cabeza_"):
            return l.strip()
    raise ValueError("El .ldr no tiene la línea de la cabeza (cabeza_<foto>.dat)")


def _pieza(estilo_o_pieza, estilos):
    if estilo_o_pieza in estilos:
        return estilos[estilo_o_pieza]
    if estilo_o_pieza in (None, "", "calvo"):
        return None
    return estilo_o_pieza if estilo_o_pieza.lower().endswith(".dat") else estilo_o_pieza + ".dat"


def hex_de(color):
    """(r, g, b) o "#rrggbb" -> "#rrggbb" (None si es un nombre de LDConfig)."""
    if isinstance(color, (tuple, list, np.ndarray)):
        return "#" + "".join(f"{int(v):02x}" for v in color[:3])
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        return color.lower()
    return None


def codigo_color(lib, color):
    """Texto del color para la línea LDraw: código de LDConfig.ldr o color directo 0x2RRGGBB (exacto)."""
    h = hex_de(color)
    return f"0x2{h[1:].upper()}" if h else str(lib.codigo(color))


def hex_color(lib, color):
    return hex_de(color) or lib.colores[color][1]


def linea_pelo(lib, linea_cabeza, pieza, color):
    """La pieza de pelo con la misma posición y rotación que la cabeza."""
    p = linea_cabeza.split()
    return " ".join(["1", codigo_color(lib, color)] + p[2:14] + [pieza])


def ldr_actual(carpeta):
    return next(Path(carpeta).glob("minifig_*.ldr"))


def cabello_actual(lib, carpeta):
    """(pieza, nombre del color) del .ldr, o (None, None) si no tiene pelo."""
    nombres = {str(c): n for n, (c, _) in lib.colores.items()}
    for l in ldr_actual(carpeta).read_text(encoding="utf-8").splitlines():
        if _es_pelo(lib, l):
            p = l.split()
            if p[1].lower().startswith("0x2"):
                return p[14], "#" + p[1][3:].lower()
            return p[14], nombres.get(p[1], p[1])
    return None, None


def aplicar(lib, carpeta, estilo_o_pieza, color, estilos=None, nota="elegido en cabello_minifigs.ipynb"):
    """Reescribe minifig_<foto>.ldr con el pelo nuevo. La primera vez guarda el original en .ldr.orig."""
    estilos = estilos or ESTILOS
    ruta = ldr_actual(carpeta)
    orig = ruta.with_suffix(".ldr.orig")
    if not orig.exists():
        shutil.copy2(ruta, orig)
    texto = ruta.read_text(encoding="utf-8")
    pieza = _pieza(estilo_o_pieza, estilos)
    if pieza and lib.ruta(pieza) is None:
        raise FileNotFoundError(f"La pieza {pieza} no está en la librería")
    codigo_color(lib, color)                                  # falla si el color no existe
    lineas = [l for l in texto.splitlines()
              if not l.startswith("0 // Cabello") and not _es_pelo(lib, l)]
    while lineas and not lineas[-1].strip():
        lineas.pop()
    estilo = next((e for e, p in estilos.items() if p == pieza), pieza or "calvo")
    desc = lib.descripciones().get(pieza, "") if pieza else "sin pelo"
    comentario = f"0 // Cabello: {estilo} ({nota}) - {desc} - color {color}"
    i = next((k + 1 for k, l in enumerate(lineas) if l.startswith("0 // Foto:")), 3)
    lineas.insert(i, comentario)
    if pieza:
        lineas += ["0 // Cabello", linea_pelo(lib, _linea_cabeza(texto), pieza, color)]
    ruta.write_bytes((CRLF.join(lineas) + CRLF).encode("utf-8"))
    return dict(ldr=ruta, estilo=estilo, pieza=pieza, color=color)


def restaurar(carpeta):
    """Vuelve al .ldr que dejó la Etapa 5."""
    ruta = ldr_actual(carpeta)
    orig = ruta.with_suffix(".ldr.orig")
    if orig.exists():
        shutil.copy2(orig, ruta)
        return True
    return False


# ===================================================================== renders
def _modelo_temporal(lib, carpeta, lineas):
    """Modelo de render a partir de líneas sueltas (se escribe junto al .ldr para que encuentre la cara)."""
    tmp = Path(carpeta) / "_cabello_prueba.ldr"
    tmp.write_text(CRLF.join(["0 prueba de cabello", *lineas]) + CRLF, encoding="utf-8")
    try:
        return render.Modelo(lib, tmp)
    finally:
        tmp.unlink(missing_ok=True)


def cabeza_con(lib, carpeta, estilo_o_pieza, color, estilos=None, lado=220, yaw=-25, pitch=12, ss=2):
    """Render de solo la cabeza con ese pelo (RGBA)."""
    estilos = estilos or ESTILOS
    cab = _linea_cabeza(ldr_actual(carpeta).read_text(encoding="utf-8"))
    pieza = _pieza(estilo_o_pieza, estilos)
    lineas = [cab] + ([linea_pelo(lib, cab, pieza, color)] if pieza else [])
    m = _modelo_temporal(lib, carpeta, lineas)
    return render.render(m, lado, lado, yaw=yaw, pitch=pitch, ss=ss, distancia=5.0)


def _rotulo(img, texto, alto=34, fondo=(255, 255, 255)):
    hoja = Image.new("RGB", (img.width, img.height + alto), fondo)
    hoja.paste(img.convert("RGB") if img.mode != "RGBA" else render.sobre_fondo(img), (0, 0))
    d = ImageDraw.Draw(hoja)
    for k, t in enumerate(texto.split("\n")[:2]):
        d.text((6, img.height + 4 + 14 * k), t, fill=(40, 40, 40))
    return hoja


def galeria(lib, carpeta, estilos, color, img_foto=None, columnas=6, lado=200, **kw):
    """Hoja: la foto y la cabeza con cada estilo (todos en `color`). Devuelve la imagen RGB."""
    celdas = []
    if img_foto is not None:
        celdas.append(_rotulo(img_foto.resize((lado, lado)), "FOTO\n" + Path(carpeta).name))
    for e in estilos:
        im = cabeza_con(lib, carpeta, e, color, lado=lado, **kw)
        celdas.append(_rotulo(im, f"{e}\n{_pieza(e, ESTILOS) or 'sin pelo'}"))
    filas = (len(celdas) + columnas - 1) // columnas
    w, h = celdas[0].size
    hoja = Image.new("RGB", (columnas * w, filas * h), (255, 255, 255))
    for k, c in enumerate(celdas):
        hoja.paste(c, ((k % columnas) * w, (k // columnas) * h))
    return hoja


def comparar(lib, carpeta, img_foto, lado=300, ss=2):
    """Foto | antes (Etapa 5, de .ldr.orig) | después (frente) | después (3/4)."""
    m = render.Modelo(lib, ldr_actual(carpeta))
    alto = round(lado * 1.3)
    orig = ldr_actual(carpeta).with_suffix(".ldr.orig")
    antes = render.render(render.Modelo(lib, orig), lado, alto, yaw=0, pitch=10, ss=ss) if orig.exists() else None
    frente = render.render(m, lado, alto, yaw=0, pitch=10, ss=ss)
    tres = render.render(m, lado, alto, yaw=-35, pitch=15, ss=ss)
    paneles = [(img_foto.resize((lado, lado)) if img_foto else Image.new("RGB", (lado, lado), "white"), "foto")]
    if antes is not None:
        paneles.append((antes, "antes (Etapa 5)"))
    paneles += [(frente, "despues - frente"), (tres, "despues - 3/4")]
    hoja = Image.new("RGB", (len(paneles) * lado, alto + 30), (255, 255, 255))
    d = ImageDraw.Draw(hoja)
    for k, (im, t) in enumerate(paneles):
        im = render.sobre_fondo(im) if im.mode == "RGBA" else im
        hoja.paste(im, (k * lado, (alto - im.height) // 2))
        d.text((k * lado + 8, alto + 8), t, fill=(60, 60, 60))
    return hoja, frente
