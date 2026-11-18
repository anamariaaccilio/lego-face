"""Etapa 5: minifig en LDraw con la cara generada aplicada por !TEXMAP.

Todo sale de la librería oficial (complete.zip, se lee sin descomprimir):
    lib = ldraw.Libreria(ldraw.descargar())
    cat = ldraw.catalogo_cabello(lib)                 # estilo -> número de pieza (buscado por descripción)
    rutas = ldraw.escribir_minifig(carpeta, "nombre", rgba, fila, lib, cat)
    ldraw.verificar(rutas, lib) ; ldraw.vista_previa(rutas["ldr"], lib)

La cabeza con cara es un archivo propio (cabeza_<nombre>.dat) armado igual que la cabeza oficial con textura
3626cpx0.dat: s\\3626cs01.dat + la mitad frontal de 3626c.dat dentro de "0 !TEXMAP START PLANAR ..." con
FALLBACK (los visores sin !TEXMAP dibujan la cabeza lisa).
"""
import functools
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import config as C

CRLF = "\r\n"                           # la especificación pide CR/LF (y acepta LF)


# ===================================================================== librería
def _es_libreria(ruta):
    """True si el zip trae ldraw/LDConfig.ldr (la librería oficial completa)."""
    try:
        with zipfile.ZipFile(ruta) as z:
            return any(n.lower().endswith("ldconfig.ldr") for n in z.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


def _buscar_en_inputs():
    """Un complete.zip subido como Input de Kaggle (plan B si la descarga está bloqueada)."""
    for raiz in C.LDRAW_BUSCAR_EN:
        raiz = Path(raiz)
        if not raiz.exists():
            continue
        for r in sorted(raiz.rglob("*.zip")):
            if r.stat().st_size > 10 * 2**20 and _es_libreria(r):
                return r
    return None


def _bajar(url, tmp):
    """urllib con User-Agent explícito; si falla, curl y luego wget. Devuelve el método que funcionó."""
    errores = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": C.LDRAW_USER_AGENT, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        return "urllib"
    except Exception as e:
        errores.append(f"urllib: {e}")
    for cmd in (["curl", "-fL", "--retry", "3", "-A", C.LDRAW_USER_AGENT, "-o", str(tmp), url],
                ["wget", "-q", "-U", C.LDRAW_USER_AGENT, "-O", str(tmp), url]):
        if shutil.which(cmd[0]) is None:
            errores.append(f"{cmd[0]}: no instalado")
            continue
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0 and tmp.exists() and tmp.stat().st_size > 10 * 2**20:
            return cmd[0]
        errores.append(f"{cmd[0]}: código {p.returncode} {p.stderr.strip()[-200:]}")
    raise RuntimeError("No se pudo descargar la librería LDraw:\n  " + "\n  ".join(errores))


def descargar(destino=None):
    destino = Path(destino or C.LDRAW_ZIP)
    if destino.exists() and destino.stat().st_size > 10 * 2**20:
        print(f"Librería LDraw ya descargada: {destino} ({destino.stat().st_size / 2**20:.0f} MB)")
        return destino
    local = _buscar_en_inputs()
    if local is not None:
        print(f"Librería LDraw tomada de los Inputs: {local} ({local.stat().st_size / 2**20:.0f} MB)")
        return local
    destino.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    tmp = destino.with_suffix(".part")
    try:
        metodo = _bajar(C.LDRAW_URL, tmp)
    except RuntimeError as e:
        raise RuntimeError(
            f"{e}\n\nPlan B: descarga {C.LDRAW_URL} en tu PC, súbelo a Kaggle como Dataset "
            "(Add Input → Upload) y vuelve a correr desde la Etapa 5; se detecta solo en /kaggle/input.") from None
    if not _es_libreria(tmp):
        raise RuntimeError(f"Lo descargado de {C.LDRAW_URL} no es la librería LDraw (sin LDConfig.ldr).")
    tmp.rename(destino)
    print(f"Librería LDraw descargada ({metodo}) de {C.LDRAW_URL}: "
          f"{destino.stat().st_size / 2**20:.0f} MB en {time.time() - t:.0f} s")
    return destino


class Libreria:
    """Acceso de solo lectura a complete.zip (búsqueda: parts/, p/, como dice la especificación)."""

    def __init__(self, ruta_zip):
        self.z = zipfile.ZipFile(ruta_zip)
        self.nombres = {n.lower(): n for n in self.z.namelist()}
        self._desc = None
        lic = self.leer_raiz("LDConfig.ldr")
        self.colores = {m.group(1): (int(m.group(2)), m.group(3))
                        for m in re.finditer(r"!COLOUR\s+(\S+)\s+CODE\s+(\d+)\s+VALUE\s+(#[0-9A-Fa-f]{6})", lic)}
        self.hex_por_codigo = {c: h for c, h in self.colores.values()}
        print(f"Librería: {len(self.nombres)} archivos · {len(self.colores)} colores en LDConfig.ldr")

    def leer_raiz(self, nombre):
        return self.z.read(self.nombres["ldraw/" + nombre.lower()]).decode("utf-8", "replace")

    def ruta(self, nombre):
        n = nombre.replace("\\", "/").lower()
        for base in ("ldraw/parts/", "ldraw/p/"):
            if base + n in self.nombres:
                return self.nombres[base + n]
        return None

    def leer(self, nombre):
        r = self.ruta(nombre)
        return None if r is None else self.z.read(r).decode("utf-8", "replace")

    def textura(self, nombre):
        r = self.nombres.get("ldraw/parts/textures/" + nombre.lower())
        return None if r is None else self.z.read(r)

    def descripciones(self):
        """{pieza.dat: descripción} de las piezas de parts/ (primera línea)."""
        if self._desc is None:
            self._desc = {}
            for n in self.z.namelist():
                if n.startswith("ldraw/parts/") and n.endswith(".dat") and n.count("/") == 2:
                    with self.z.open(n) as h:
                        self._desc[n[12:]] = h.readline().decode("utf-8", "replace")[2:].strip()
        return self._desc

    def por_descripcion(self, texto):
        for pieza, d in self.descripciones().items():
            if d == texto:
                return pieza
        return None

    def codigo(self, nombre_color):
        if nombre_color not in self.colores:
            raise KeyError(f"El color '{nombre_color}' no está en LDConfig.ldr")
        return self.colores[nombre_color][0]


# ===================================================================== catálogo de cabello
def catalogo_cabello(lib):
    filas = []
    for estilo, descs in C.CATALOGO_CABELLO.items():
        pieza = desc = None
        for d in descs:
            pieza = lib.por_descripcion(d)
            if pieza:
                desc = d
                break
        filas.append(dict(estilo=estilo, pieza=pieza, descripcion=desc,
                          buscadas=" | ".join(descs) if descs else "(sin pelo)"))
    cat = pd.DataFrame(filas)
    faltan = cat[(cat["pieza"].isna()) & (cat["buscadas"] != "(sin pelo)")]
    if len(faltan):
        print(f"⚠ Estilos sin pieza en la librería: {faltan['estilo'].tolist()} (revisa config.CATALOGO_CABELLO)")
    total = sum(1 for d in lib.descripciones().values() if d.startswith("Minifig Hair"))
    print(f"Catálogo de cabello: {len(cat)} estilos (de {total} piezas 'Minifig Hair' en la librería)")
    return cat


def elegir_cabello(fila, cat):
    nombre = str(fila.get("nombre"))
    estilo = C.CABELLO_MANUAL.get(nombre)
    fuente = "manual"
    if estilo is None and isinstance(fila.get("cabello"), str) and fila.get("cabello") in C.CATALOGO_CABELLO:
        estilo, fuente = fila.get("cabello"), "dataset"
    if estilo is None:
        fem = fila.get("femenino")
        fem = None if fem is None or (isinstance(fem, float) and np.isnan(fem)) else bool(fem)
        estilo, fuente = C.CABELLO_POR_DEFECTO[fem], "por defecto (femenino=" + str(fem) + ")"
    color_txt = fila.get("color_cejas")
    color_txt = color_txt if isinstance(color_txt, str) else None
    color = C.COLOR_PELO_LDRAW.get(color_txt, C.COLOR_PELO_POR_DEFECTO)
    pieza = cat.set_index("estilo").loc[estilo, "pieza"] if estilo in set(cat["estilo"]) else None
    return dict(estilo=estilo, pieza=pieza if isinstance(pieza, str) else None, color=color,
                fuente=fuente, color_de=color_txt or "defecto")


# ===================================================================== escribir
def _linea1(color, pos, pieza, mat="1 0 0 0 1 0 0 0 1"):
    x, y, z = pos
    return f"1 {color} {x:g} {y:g} {z:g} {mat} {pieza}"


def cabeza_texturizada(lib, nombre_dat, png):
    """Cabeza propia: igual que 3626cpx0.dat pero con nuestra cara y la geometría tomada de 3626c.dat."""
    base = lib.leer(C.CABEZA)
    if base is None:
        raise FileNotFoundError(f"{C.CABEZA} no está en la librería")
    tipo1 = [l.strip() for l in base.splitlines() if l.strip().startswith("1 ")]
    sub = [l for l in tipo1 if l.lower().endswith("3626cs01.dat")]
    frente = [l for l in tipo1 if l not in sub]
    if len(sub) != 1 or not frente:
        raise ValueError(f"{C.CABEZA} no tiene la estructura esperada (s\\3626cs01.dat + frente): {tipo1}")
    texto = [f"0 Minifig Head with Generated Face {nombre_dat[:-4]}", f"0 Name: {nombre_dat}", "0 Author: flux_cara",
             "0 // Basado en 3626c.dat y en la cabeza oficial con textura 3626cpx0.dat", "",
             "0 BFC CERTIFY CCW", "", sub[0], "", "0 // Cara (mitad frontal) con textura",
             f"0 !TEXMAP START PLANAR {C.TEXMAP_PLANAR} {png}"]
    texto += ["0 !: " + l for l in frente]
    texto += ["0 !TEXMAP FALLBACK"] + frente + ["0 !TEXMAP END", ""]
    return CRLF.join(texto)


def lineas_torso(lib, color_torso, color_manos):
    """Líneas de 76382.dat (torso + brazos + manos) con colores propios: manos (3820) aparte."""
    t = lib.leer(C.TORSO)
    if t is None:
        raise FileNotFoundError(f"{C.TORSO} no está en la librería")
    out = []
    for l in t.splitlines():
        p = l.split()
        if p and p[0] == "1" and len(p) >= 15:
            col = color_manos if p[14].lower() == "3820.dat" else color_torso
            out.append(" ".join(["1", str(col)] + p[2:]))
    return out


def escribir_minifig(carpeta, nombre, rgba, fila, lib, cat):
    carpeta = Path(carpeta)
    (carpeta / "textures").mkdir(parents=True, exist_ok=True)
    png, dat, ldr = f"cara_{nombre}.png", f"cabeza_{nombre}.dat", f"minifig_{nombre}.ldr"
    rgba.save(carpeta / "textures" / png)              # la especificación busca textures/<png> y luego <png>
    rgba.save(carpeta / png)
    (carpeta / dat).write_bytes(cabeza_texturizada(lib, dat, png).encode("utf-8"))
    pelo = elegir_cabello(fila, cat)
    c_cab, c_torso = lib.codigo(C.COLOR_CABEZA), lib.codigo(C.COLOR_TORSO)
    lineas = [f"0 Minifig {nombre}", f"0 Name: {ldr}", "0 Author: flux_cara",
              f"0 // Foto: {fila.get('nombre')} - cara FLUX.2-klein-4B + piezas oficiales LDraw",
              f"0 // Cabello: {pelo['estilo']} ({pelo['fuente']}) - color {pelo['color']} (de cejas: {pelo['color_de']})", "",
              "0 // Torso con brazos y manos (lineas de " + C.TORSO + ")"]
    lineas += lineas_torso(lib, c_torso, lib.codigo(C.COLOR_MANOS))
    lineas += ["0 // Caderas y piernas", _linea1(lib.codigo(C.COLOR_PIERNAS), C.POS_PIERNAS, C.PIERNAS),
               "0 // Cabeza con la cara generada (!TEXMAP)", _linea1(c_cab, C.POS_CABEZA, dat)]
    if pelo["pieza"]:
        lineas += ["0 // Cabello", _linea1(lib.codigo(pelo["color"]), C.POS_CABEZA, pelo["pieza"])]
    (carpeta / ldr).write_bytes((CRLF.join(lineas) + CRLF).encode("utf-8"))
    return dict(ldr=carpeta / ldr, dat=carpeta / dat, png=carpeta / "textures" / png, pelo=pelo)


# ===================================================================== verificación
PATRON_TEXMAP = re.compile(r"^0 !TEXMAP START PLANAR( -?\d+(\.\d+)?){9} \S+\.png$")


def verificar(rutas, lib):
    carpeta = rutas["ldr"].parent
    chequeos = []
    faltan = []
    for archivo in (rutas["ldr"], rutas["dat"]):
        for l in archivo.read_text(encoding="utf-8").splitlines():
            l = l[5:] if l.startswith("0 !: ") else l
            p = l.split()
            if p and p[0] == "1":
                pieza = " ".join(p[14:])
                if lib.ruta(pieza) is None and not (carpeta / pieza).exists():
                    faltan.append(pieza)
    chequeos.append(("todas las piezas existen (librería oficial o carpeta)", not faltan, faltan))
    dat = rutas["dat"].read_text(encoding="utf-8").splitlines()
    tex = [l for l in dat if l.startswith("0 !TEXMAP")]
    chequeos.append(("sintaxis START PLANAR (9 números + png)", bool(tex) and bool(PATRON_TEXMAP.match(tex[0])), tex[:1]))
    chequeos.append(("orden START → FALLBACK → END", [t.split()[2] for t in tex] == ["START", "FALLBACK", "END"], tex))
    chequeos.append(("líneas '0 !:' con la geometría texturizada", any(l.startswith("0 !: 1 ") for l in dat), None))
    png = Image.open(rutas["png"])
    chequeos.append(("PNG con alfa en textures/", png.mode == "RGBA" and png.getextrema()[3][0] == 0, png.size))
    chequeos.append(("CR/LF", b"\r\n" in rutas["ldr"].read_bytes(), None))
    for texto, ok, extra in chequeos:
        print(("✅ " if ok else "❌ ") + texto + (f" · {extra}" if extra and not ok else ""))
    return all(ok for _, ok, _ in chequeos)


# ===================================================================== vista previa (aproximada)
class _Escena:
    """Triángulos de un archivo LDraw (recursivo) con color (16 = heredado) y si están texturizados."""

    def __init__(self, lib, carpeta):
        self.lib, self.carpeta = lib, Path(carpeta)
        self.cache = {}

    def _texto(self, nombre):
        local = self.carpeta / nombre
        if local.exists():
            return local.read_text(encoding="utf-8", errors="replace")
        return self.lib.leer(nombre)

    def cargar(self, nombre):
        if nombre in self.cache:
            return self.cache[nombre]
        tris, cols, tex, texdefs = [], [], [], []
        t = self._texto(nombre)
        activo, fallback, planar = False, False, None
        for l in (t or "").splitlines():
            p = l.split()
            if not p:
                continue
            if p[0] == "0":
                if len(p) >= 3 and p[1] == "!TEXMAP":
                    if p[2] == "START" and len(p) >= 13 and p[3] == "PLANAR":
                        activo, fallback = True, False
                        v = np.array(list(map(float, p[4:13]))).reshape(3, 3)
                        texdefs.append((v, " ".join(p[13:])))
                    elif p[2] == "FALLBACK":
                        fallback = True
                    elif p[2] == "END":
                        activo, fallback = False, False
                    continue
                if len(p) > 1 and p[1] == "!:" and activo and not fallback:
                    p = p[2:]
                else:
                    continue
            if fallback:
                continue
            if p[0] == "1" and len(p) >= 15:
                v = list(map(float, p[2:14]))
                M, o = np.array(v[3:]).reshape(3, 3), np.array(v[:3])
                ct, cc, cx, cd = self.cargar(" ".join(p[14:]))
                if len(ct):
                    tris.append(ct @ M.T + o)
                    c = int(p[1])
                    cols.append(np.where(cc == 16, c, cc))
                    tex.append(cx | activo)
                for (tv, png) in cd:
                    texdefs.append((tv @ M.T + o, png))
            elif p[0] in ("3", "4"):
                k = int(p[0])
                pts = np.array(list(map(float, p[2:2 + 3 * k]))).reshape(k, 3)
                caras = [pts[[0, 1, 2]]] + ([pts[[0, 2, 3]]] if k == 4 else [])
                tris.append(np.array(caras))
                cols.append(np.full(len(caras), int(p[1])))
                tex.append(np.full(len(caras), activo))
        r = (np.concatenate(tris) if tris else np.zeros((0, 3, 3)),
             np.concatenate(cols) if cols else np.zeros(0, int),
             np.concatenate(tex) if tex else np.zeros(0, bool), texdefs)
        self.cache[nombre] = r
        return r


def vista_previa(ruta_ldr, lib, lado=None):
    """Vista frontal ortográfica aproximada (no es el render final): sirve para ver que todo encaja."""
    lado = lado or C.LADO_PREVIA
    esc = _Escena(lib, Path(ruta_ldr).parent)
    tris, cols, tex, texdefs = esc.cargar(Path(ruta_ldr).name)
    xy = tris[..., :2]
    mn, mx = xy.reshape(-1, 2).min(0), xy.reshape(-1, 2).max(0)
    s = (lado * 0.9) / (mx - mn).max()
    off = (lado - (mx - mn) * s) / 2 - mn * s
    a = lambda p: p[..., :2] * s + off
    img = Image.new("RGB", (lado, lado), (255, 255, 255))
    masc = Image.new("L", (lado, lado), 0)
    d, dm = ImageDraw.Draw(img), ImageDraw.Draw(masc)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    luz = np.array([0.3, -0.5, -1.0])
    luz /= np.linalg.norm(luz)
    inten = 0.45 + 0.55 * np.abs(n @ luz)
    orden = np.argsort(-tris[..., 2].mean(1))                 # cámara en -Z: primero lo más lejano
    for i in orden:
        h = lib.hex_por_codigo.get(int(cols[i]), "#808080")
        rgb = tuple(int(int(h[k:k + 2], 16) * inten[i]) for k in (1, 3, 5))
        pol = [tuple(q) for q in a(tris[i])]
        d.polygon(pol, fill=rgb)
        dm.polygon(pol, fill=255 if tex[i] else 0)
    for v, png in texdefs:                                    # PLANAR de frente: la textura es un rectángulo en pantalla
        p1, p2, p3 = a(v)
        x0, x1 = sorted((p1[0], p2[0]))
        y0, y1 = sorted((p1[1], p3[1]))
        ruta = Path(ruta_ldr).parent / "textures" / png
        if not ruta.exists():
            continue
        t = Image.open(ruta).convert("RGBA")
        if p2[0] < p1[0]:
            t = t.transpose(Image.FLIP_LEFT_RIGHT)
        if p3[1] < p1[1]:
            t = t.transpose(Image.FLIP_TOP_BOTTOM)
        w, h = max(1, round(x1 - x0)), max(1, round(y1 - y0))
        t = t.resize((w, h), Image.BOX)
        caja = (round(x0), round(y0))
        m = Image.fromarray((np.asarray(t)[..., 3].astype(float) * np.asarray(masc.crop((*caja, caja[0] + w, caja[1] + h))) / 255).astype(np.uint8))
        img.paste(t.convert("RGB"), caja, m)
    return img


# ===================================================================== README de render
README = """# Render de la minifig ({nombre})

Archivos (deja todos juntos en la misma carpeta):
- `{ldr}`: modelo principal (piezas oficiales de LDraw + la cabeza con cara).
- `{dat}`: cabeza con la cara aplicada con `!TEXMAP START PLANAR` (igual que la cabeza oficial con textura `3626cpx0.dat`).
- `textures/{png}` (y una copia `{png}` al lado): la cara RGBA. El estándar busca primero en `textures/`.
- `vista_previa_{nombre}.png`: vista frontal aproximada hecha en Python, solo para comprobar que las piezas encajan.

Necesitas la librería oficial de piezas: https://library.ldraw.org/library/updates/complete.zip (descomprímela, p. ej. en `C:\\LDraw`).

## LDView
1. Instala LDView. Usa la 4.4 o una más nueva: la 4.4 agregó las texturas CYLINDRICAL/SPHERICAL y arregló varios errores de texturas; la 4.6 y la 4.7 trajeron más arreglos.
2. La primera vez te pide la carpeta de la librería LDraw: elige la carpeta `ldraw` descomprimida.
3. Abre `{ldr}`. Si no ves la cara, revisa que `textures/{png}` esté junto al `.ldr`.
4. Imagen desde la línea de comandos: `LDView {ldr} -SaveSnapshot=render.png` (las demás opciones están en la ayuda de LDView).

## Blender (complemento ImportLDraw de TobyLobster)
1. Instala el complemento desde https://github.com/TobyLobster/ImportLDraw (Blender 4.0 o más nuevo).
   Su README dice que importa las piezas con `!TEXMAP` (planar, cilíndrico y esférico) junto con sus imágenes.
2. *File → Import → LDraw*, elige `{ldr}` y, en las opciones, la carpeta de la librería LDraw.
3. Deja marcada la opción *Import textures*.
4. Renderiza con Cycles o EEVEE.

Visores sin `!TEXMAP` dibujan la cabeza lisa (sección FALLBACK); no es un error del archivo.
"""


def escribir_readme(rutas, nombre):
    texto = README.format(nombre=nombre, ldr=rutas["ldr"].name, dat=rutas["dat"].name, png=rutas["png"].name)
    destino = rutas["ldr"].parent / "README_render.md"
    destino.write_text(texto, encoding="utf-8")
    return destino
