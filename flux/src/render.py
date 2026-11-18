"""Render 3D local de las minifigs (.ldr) sin programas externos: rasterizador numpy con perspectiva, z-buffer,
luz de plástico, la cara por !TEXMAP PLANAR (proyección de la especificación LDraw) y aristas (líneas tipo 2).

    lib = ldraw.Libreria(ruta_complete_zip)
    m = render.Modelo(lib, ruta_ldr)                  # triángulos, colores, texturas y aristas (recursivo)
    img = render.render(m, yaw=-30, pitch=15)         # PIL RGBA con fondo transparente
    render.lamina(m, nombre)                          # varias vistas en una hoja

Convención LDraw: y hacia abajo, el frente de la minifig mira a -Z (la cámara está en -Z).
"""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

GRIS = "#808080"


DIRECTO = 0x2000000           # colores directos de LDraw: 0x2RRGGBB


def codigo(tok):
    """Código de color de una línea LDraw: número de LDConfig o color directo 0x2RRGGBB."""
    return int(tok, 16) if tok.lower().startswith("0x") else int(tok)


def _arista_directa(h):
    """Arista de un color directo: algo más clara si es oscuro, más oscura si es claro (como LDConfig)."""
    v = _hex(h)
    v = v + 0.07 if v.mean() < 0.3 else v * 0.6
    return "#" + "".join(f"{int(round(min(max(x, 0), 1) * 255)):02x}" for x in v)


def _hex(h):
    return np.array([int(h[k:k + 2], 16) for k in (1, 3, 5)], float) / 255


class Modelo:
    """Geometría aplanada de un .ldr: tris (N,3,3), col (N), tex (N, -1 = sin textura), texturas [(P1,P2,P3,png)],
    lineas (M,2,3), col_lineas (M). Los colores 16 (heredado) y 24 (arista) se resuelven al bajar por la jerarquía."""

    def __init__(self, lib, ruta_ldr):
        self.lib, self.ruta = lib, Path(ruta_ldr)
        self.carpeta = self.ruta.parent
        cfg = lib.leer_raiz("LDConfig.ldr")
        self.valor, self.arista = {}, {}
        for m in re.finditer(r"!COLOUR\s+\S+\s+CODE\s+(\d+)\s+VALUE\s+(#[0-9A-Fa-f]{6})\s+EDGE\s+(#[0-9A-Fa-f]{6})", cfg):
            self.valor[int(m.group(1))], self.arista[int(m.group(1))] = m.group(2), m.group(3)
        self._cache = {}
        t, c, x, defs, l, lc = self._cargar(self.ruta.name)
        self.tris, self.lineas = t, l
        self.col = self._resolver(c, 7)
        self.col_lineas = self._resolver(lc, 7)
        self.tex = x
        self.texturas = [(P, self._imagen(png)) for P, png in defs]

    # ----------------------------------------------------------------- lectura
    def _texto(self, nombre):
        local = self.carpeta / nombre
        if local.exists():
            return local.read_text(encoding="utf-8", errors="replace")
        return self.lib.leer(nombre)

    def _imagen(self, png):
        for r in (self.carpeta / "textures" / png, self.carpeta / png):
            if r.exists():
                return np.asarray(Image.open(r).convert("RGBA"), float) / 255
        b = self.lib.textura(png)
        if b is None:
            raise FileNotFoundError(f"No encontré la textura {png} (ni en textures/ ni junto al .ldr)")
        import io
        return np.asarray(Image.open(io.BytesIO(b)).convert("RGBA"), float) / 255

    def _cargar(self, nombre):
        """Devuelve (tris, colores, idx textura, texdefs, lineas, colores lineas) en el espacio del archivo.
        Colores: código LDraw; 16 y 24 quedan sin resolver para que los resuelva el padre."""
        key = nombre.lower().replace("\\", "/")
        if key in self._cache:
            return self._cache[key]
        T, Cc, X, D, L, LC = [], [], [], [], [], []
        activo, fallback = -1, False
        for linea in (self._texto(nombre) or "").splitlines():
            p = linea.split()
            if not p:
                continue
            if p[0] == "0":
                if len(p) >= 3 and p[1] == "!TEXMAP":
                    if p[2] == "START" and len(p) >= 13 and p[3] == "PLANAR":
                        D.append((np.array(list(map(float, p[4:13]))).reshape(3, 3), " ".join(p[13:])))
                        activo, fallback = len(D) - 1, False
                    elif p[2] == "FALLBACK":
                        fallback = True
                    elif p[2] == "END":
                        activo, fallback = -1, False
                    continue
                if len(p) > 2 and p[1] == "!:" and activo >= 0 and not fallback:
                    p = p[2:]
                else:
                    continue
            elif fallback:
                continue
            tipo = p[0]
            if tipo == "1" and len(p) >= 15:
                v = list(map(float, p[2:14]))
                M, o = np.array(v[3:]).reshape(3, 3), np.array(v[:3])
                ct, cc, cx, cd, cl, clc = self._cargar(" ".join(p[14:]))
                c = codigo(p[1])
                base = len(D)
                D += [(P @ M.T + o, png) for P, png in cd]
                if len(ct):
                    T.append(ct @ M.T + o)
                    Cc.append(self._heredar(cc, c))
                    x = np.where(cx >= 0, cx + base, -1)
                    X.append(np.where(x < 0, activo, x) if activo >= 0 else x)
                if len(cl):
                    L.append(cl @ M.T + o)
                    LC.append(self._heredar(clc, c))
            elif tipo in ("3", "4"):
                k = int(tipo)
                pts = np.array(list(map(float, p[2:2 + 3 * k]))).reshape(k, 3)
                caras = [pts[[0, 1, 2]]] + ([pts[[0, 2, 3]]] if k == 4 else [])
                T.append(np.array(caras))
                Cc.append(np.full(len(caras), codigo(p[1])))
                X.append(np.full(len(caras), activo))
            elif tipo == "2" and len(p) >= 8:
                L.append(np.array(list(map(float, p[2:8]))).reshape(1, 2, 3))
                LC.append(np.array([codigo(p[1])]))
        r = (np.concatenate(T) if T else np.zeros((0, 3, 3)), np.concatenate(Cc) if Cc else np.zeros(0, int),
             np.concatenate(X) if X else np.zeros(0, int), D,
             np.concatenate(L) if L else np.zeros((0, 2, 3)), np.concatenate(LC) if LC else np.zeros(0, int))
        self._cache[key] = r
        return r

    @staticmethod
    def _heredar(cc, c):
        """16 -> color del padre; 24 -> arista del padre (se guarda como -(c+1) hasta resolverla)."""
        if c == 16:
            return cc
        if c == 24:
            return np.where((cc == 16) | (cc == 24), 24, cc)
        out = np.where(cc == 16, c, cc)
        return np.where(cc == 24, -(c + 1), out)

    def _resolver(self, cc, defecto):
        """Código -> RGB (0..1). Negativos = arista del color -(x)-1; 16/24 sin padre = color por defecto."""
        rgb = np.zeros((len(cc), 3))
        for c in np.unique(cc):
            if c <= -DIRECTO - 1:
                h = _arista_directa(f"#{(-c - 1) & 0xFFFFFF:06x}")
            elif c >= DIRECTO:
                h = f"#{c & 0xFFFFFF:06x}"
            elif c < 0:
                h = self.arista.get(-c - 1, "#333333")
            elif c in (16, 24):
                h = self.valor.get(defecto, GRIS) if c == 16 else self.arista.get(defecto, "#333333")
            else:
                h = self.valor.get(int(c), GRIS)
            rgb[cc == c] = _hex(h)
        return rgb

    def __repr__(self):
        return f"Modelo({self.ruta.name}: {len(self.tris)} triángulos, {len(self.lineas)} aristas, {len(self.texturas)} texturas)"


# ===================================================================== cámara
def _rotacion(yaw, pitch):
    b, a = np.radians(yaw), np.radians(pitch)
    Ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    return Rx @ Ry


def render(m, ancho=600, alto=760, yaw=0.0, pitch=12.0, ss=3, aristas=True, distancia=6.0, ancho_arista=1.0):
    """Imagen RGBA (fondo transparente). yaw: giro en grados (negativo = se ve el lado izquierdo de la minifig);
    pitch: cámara por encima (positivo). ss: supermuestreo para antialias. distancia: en radios del modelo."""
    W, H = ancho * ss, alto * ss
    todo = m.tris.reshape(-1, 3)
    centro = (todo.min(0) + todo.max(0)) / 2
    radio = np.linalg.norm(todo - centro, axis=1).max()
    R = _rotacion(yaw, pitch)
    D = distancia * radio

    def a_camara(p):
        q = (p - centro) @ R.T
        return q, q[..., 2] + D                               # profundidad w (> 0)

    q, w = a_camara(m.tris)
    xs, ys = q[..., 0] / w, q[..., 1] / w
    # encuadre: el modelo (en esta vista) ocupa el 88 % del lado limitante
    mnx, mxx, mny, mxy = xs.min(), xs.max(), ys.min(), ys.max()
    f = 0.88 * min(W / (mxx - mnx), H / (mxy - mny))
    ox, oy = W / 2 - f * (mnx + mxx) / 2, H / 2 - f * (mny + mxy) / 2
    sx, sy = xs * f + ox, ys * f + oy

    zbuf = np.full((H, W), np.inf)
    ids = np.full((H, W), -1, np.int64)
    for i in range(len(sx)):
        x0, y0 = int(max(0, np.floor(sx[i].min()))), int(max(0, np.floor(sy[i].min())))
        x1, y1 = int(min(W - 1, np.ceil(sx[i].max()))), int(min(H - 1, np.ceil(sy[i].max())))
        if x1 < x0 or y1 < y0:
            continue
        (ax, bx, cx), (ay, by, cy) = sx[i], sy[i]
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(area) < 1e-9:
            continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((bx - px) * (cy - py) - (cx - px) * (by - py)) / area
        l1 = ((cx - px) * (ay - py) - (ax - px) * (cy - py)) / area
        l2 = 1 - l0 - l1
        dentro = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not dentro.any():
            continue
        wi = w[i]
        prof = 1 / (l0 / wi[0] + l1 / wi[1] + l2 / wi[2])     # profundidad con corrección de perspectiva
        zb = zbuf[y0:y1 + 1, x0:x1 + 1]
        gana = dentro & (prof < zb)
        zb[gana] = prof[gana]
        ids[y0:y1 + 1, x0:x1 + 1][gana] = i

    hay = ids >= 0
    yy, xx = np.nonzero(hay)
    tid = ids[hay]
    wpx = zbuf[hay]
    # punto 3D de cada píxel (desproyección) en espacio cámara y en espacio modelo
    qc = np.stack([(xx + 0.5 - ox) / f * wpx, (yy + 0.5 - oy) / f * wpx, wpx - D], 1)
    pm = qc @ R + centro
    # normal de cada triángulo, mirando a la cámara
    tri_c = q
    n = np.cross(tri_c[:, 1] - tri_c[:, 0], tri_c[:, 2] - tri_c[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    nn = n[tid]
    vista = np.array([0, 0, -D]) - qc
    vista /= np.linalg.norm(vista, axis=1, keepdims=True)
    nn *= np.sign((nn * vista).sum(1, keepdims=True) + 1e-12)

    base = m.col[tid].copy()
    for k, (P, img) in enumerate(m.texturas):                 # !TEXMAP PLANAR: U sobre P1→P2, V sobre P1→P3
        sel = m.tex[tid] == k
        if not sel.any():
            continue
        p1, p2, p3 = P
        d = pm[sel] - p1
        u = d @ (p2 - p1) / np.dot(p2 - p1, p2 - p1)
        v = d @ (p3 - p1) / np.dot(p3 - p1, p3 - p1)
        dentro = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        mu = _muestrear(img, u.clip(0, 1), v.clip(0, 1))
        alfa = mu[:, 3:4] * dentro[:, None]
        base[sel] = base[sel] * (1 - alfa) + mu[:, :3] * alfa

    luces = [(np.array([-0.55, -0.75, -1.0]), 0.75), (np.array([0.8, -0.2, -0.6]), 0.30), (np.array([0.0, 0.6, 0.4]), 0.15)]
    difusa = np.full(len(tid), 0.30)
    brillo = np.zeros(len(tid))
    for L, k in luces:
        L = L / np.linalg.norm(L)
        nl = (nn * L).sum(1)
        difusa += k * nl.clip(0)
        h = L + vista
        h /= np.linalg.norm(h, axis=1, keepdims=True)
        brillo += k * (nn * h).sum(1).clip(0) ** 48
    color = (base * difusa[:, None] + 0.35 * brillo[:, None]).clip(0, 1)

    out = np.zeros((H, W, 4))
    out[yy, xx, :3] = color
    out[yy, xx, 3] = 1

    if aristas and len(m.lineas):
        ql, wl = a_camara(m.lineas)
        lx, ly = ql[..., 0] / wl * f + ox, ql[..., 1] / wl * f + oy
        grosor = max(1, int(round(ancho_arista * ss)))
        tol = 0.004 * D
        for j in range(len(lx)):
            largo = np.hypot(lx[j, 1] - lx[j, 0], ly[j, 1] - ly[j, 0])
            n_pts = int(largo * 1.5) + 2
            t = np.linspace(0, 1, n_pts)
            px = lx[j, 0] + t * (lx[j, 1] - lx[j, 0])
            py = ly[j, 0] + t * (ly[j, 1] - ly[j, 0])
            pw = 1 / ((1 - t) / wl[j, 0] + t / wl[j, 1])
            for dx in range(grosor):
                for dy in range(grosor):
                    ix, iy = (px + dx - grosor / 2).astype(int), (py + dy - grosor / 2).astype(int)
                    ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
                    ix, iy, pwk = ix[ok], iy[ok], pw[ok]
                    vis = pwk <= zbuf[iy, ix] + tol
                    out[iy[vis], ix[vis], :3] = m.col_lineas[j]
                    out[iy[vis], ix[vis], 3] = 1

    img = Image.fromarray((out * 255).round().astype(np.uint8), "RGBA")
    # premultiplicar antes de reducir para que el borde no se ensucie de negro
    pre = np.asarray(img, float)
    pre[..., :3] *= pre[..., 3:4] / 255
    chica = np.asarray(Image.fromarray(pre.astype(np.uint8), "RGBA").resize((ancho, alto), Image.LANCZOS), float)
    a = chica[..., 3:4]
    chica[..., :3] = np.where(a > 0, chica[..., :3] * 255 / np.maximum(a, 1), 0)
    return Image.fromarray(chica.clip(0, 255).astype(np.uint8), "RGBA")


def _muestrear(img, u, v):
    """Bilineal: u de izquierda a derecha, v de arriba abajo (como la imagen)."""
    h, w = img.shape[:2]
    x, y = u * (w - 1), v * (h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy)
            + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


# ===================================================================== hojas
def sobre_fondo(rgba, color=(245, 245, 247)):
    f = Image.new("RGBA", rgba.size, (*color, 255))
    f.alpha_composite(rgba)
    return f.convert("RGB")


VISTAS = {"frente": (0, 10), "3/4 izquierda": (-35, 15), "3/4 derecha": (35, 15), "perfil": (-90, 5), "espalda": (180, 10)}


def lamina(m, titulo, vistas=None, ancho=420, alto=540, cara=None, **kw):
    """Hoja con varias vistas (y la estampa de la cara a la izquierda, si se pasa). Devuelve (hoja RGB, {vista: RGBA})."""
    vistas = vistas or VISTAS
    imgs = {n: render(m, ancho, alto, yaw=y, pitch=p, **kw) for n, (y, p) in vistas.items()}
    extra = 1 if cara is not None else 0
    hoja = Image.new("RGB", ((len(imgs) + extra) * ancho, alto + 60), (255, 255, 255))
    d = ImageDraw.Draw(hoja)
    d.text((10, 8), titulo, fill=(20, 20, 20))
    if cara is not None:
        c = cara.convert("RGBA")
        esc = (ancho - 60) / c.width
        c = c.resize((round(c.width * esc), round(c.height * esc)), Image.NEAREST)
        fondo = Image.new("RGBA", c.size, (250, 215, 0, 255))
        fondo.alpha_composite(c)
        hoja.paste(fondo.convert("RGB"), (30, 60 + (alto - c.height) // 2))
        d.text((30, alto + 36), "estampa (textura)", fill=(90, 90, 90))
    for k, (n, im) in enumerate(imgs.items(), start=extra):
        hoja.paste(sobre_fondo(im), (k * ancho, 30))
        d.text((k * ancho + 10, alto + 36), n, fill=(90, 90, 90))
    return hoja, imgs
