"""Forma 2: FLUX.2 [klein] 4B (preentrenado, Apache 2.0) guiado por la asesoría.

Recibe la foto (opcional) y la ficha que arma Tito con el agente: expresión, lentes, barba,
bigote, color de cabello (para las cejas), color de ojos y detalles en texto libre.
Devuelve la estampa con la piel transparente, igual que el modelo del equipo.
"""
from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .base import Generador, Pedido, Resultado

MODELO = os.environ.get("FLUX_MODELO", "black-forest-labs/FLUX.2-klein-4B")
LADO = 512

ESTILO = ("only the eyes, eyebrows and mouth printed flat on a plain yellow background, with the same simple "
          "shapes and line thickness as the LEGO reference. No head outline, no circle or border around the face, "
          "no hair, no ears, no nose, no neck, no skin color, no shading, no text.")
CON_FOTO = "Draw the face of the person in image 1 as a LEGO minifigure face print in exactly the same style as image 2: "
SIN_FOTO = "Draw a new LEGO minifigure face print in exactly the same style as image 1: "
REFERENCIA = Path(__file__).resolve().parents[3] / "LegoFace_Local" / "pruebas" / "lego_prueba.png"


def imagen_estilo() -> Image.Image:
    """Estampa real del modelo del equipo sobre amarillo: le marca a FLUX el estilo exacto."""
    e = Image.open(REFERENCIA).convert("RGBA").resize((384, 384), Image.Resampling.LANCZOS)
    fondo = Image.new("RGBA", (LADO, LADO), (242, 205, 55, 255))
    fondo.alpha_composite(e, (64, 64))
    return fondo.convert("RGB")

EXPRESION = {
    "feliz": "a happy smiling expression",
    "serio": "a serious expression with a straight mouth",
    "sorprendido": "a surprised expression with a small open round mouth",
    "enojado": "an angry expression with frowning eyebrows",
}
COLOR = {"negro": "black", "castaño": "brown", "rubio": "dark blond", "pelirrojo": "orange-red",
         "gris": "gray", "blanco": "white", "rosa": "pink", "azul": "blue", "morado": "purple", "verde": "green"}
# El pelo es una pieza 3D aparte (LDraw): si el texto libre habla de pelo, eso no va a FLUX.
PELO = re.compile(r"\b(pelo|cabello|peinado|melena|cerquillo|flequillo|rulos|rizos|rizado|calv[oa]|rapad[oa]|trenza\w*|moño)\b", re.I)


def sin_pelo(texto: str) -> str:
    partes = [p.strip() for p in re.split(r"[.;,]| y ", texto or "")]
    return ", ".join(p for p in partes if p and not PELO.search(p))
OJOS = {"verdes": "green irises", "azules": "blue irises", "cafe": "brown irises", "grises": "gray irises"}


def armar_prompt(ficha: dict, con_foto: bool) -> str:
    rasgos = ficha.get("rasgos") or {}
    cabello = ficha.get("cabello") or {}
    color = COLOR.get(cabello.get("color") or "", "")
    partes = []
    if rasgos.get("expresion") in EXPRESION:
        partes.append(EXPRESION[rasgos["expresion"]])
    if color:
        partes.append(f"{color} eyebrows")
    if rasgos.get("lentes") is True:
        partes.append("black rectangular glasses")
    vello = color or "brown"
    if rasgos.get("barba") is True:
        partes.append(f"a short {vello} beard printed around the jaw")
    if rasgos.get("bigote") is True:
        partes.append(f"a {vello} mustache")
    if ficha.get("ojos") in OJOS:
        partes.append(OJOS[ficha["ojos"]])
    texto = (CON_FOTO if con_foto else SIN_FOTO) + ESTILO
    if partes:
        texto += " The face has " + ", ".join(partes) + "."
    sin = [r for r in ("lentes", "barba", "bigote") if rasgos.get(r) is False]
    if sin:
        texto += " No " + ", no ".join({"lentes": "glasses", "barba": "beard", "bigote": "mustache"}[r] for r in sin) + "."
    detalles = sin_pelo(ficha.get("detalles") or "")
    if detalles:
        texto += f' Extra details requested by the person (in Spanish): "{detalles}".'
    return texto


def recortar_cara(rgb: np.ndarray) -> Image.Image:
    """Recorte cuadrado alrededor de la cara (mismo criterio que lego_face)."""
    import cv2
    h, w = rgb.shape[:2]
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    caras = det.detectMultiScale(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 1.1, 5, minSize=(max(16, w // 6),) * 2)
    if len(caras):
        x, y, cw, ch = max(caras, key=lambda q: q[2] * q[3])
        cx, cy, s = x + cw / 2, y + ch / 2, max(cw, ch) * 1.8
    else:
        cx, cy, s = w / 2, h * 0.45, min(w, h) * 0.75
    x0, y0 = max(0, int(cx - s / 2)), max(0, int(cy - s / 2))
    x1, y1 = min(w, int(cx + s / 2)), min(h, int(cy + s / 2))
    return Image.fromarray(rgb[y0:y1, x0:x1]).resize((LADO, LADO), Image.Resampling.BICUBIC)


def sin_contorno(alfa: np.ndarray) -> tuple[np.ndarray, bool]:
    """Borra el contorno de cabeza si FLUX lo dibuja: una línea fina que encierra casi toda la cara.

    Se quitan los píxeles delgados del borde de la región (la barba, rellena, se conserva) y
    después las líneas finas y altas que hayan quedado sueltas. Devuelve (alfa, había_contorno).
    """
    import cv2
    m = (alfa > 0.5).astype(np.uint8)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    h, w = m.shape
    habia = False
    for k in range(1, n):
        x, y, cw, ch, area = stats[k]
        if cw > 0.45 * w and ch > 0.45 * h:
            habia = True
            comp = (etiquetas == k).astype(np.uint8)
            # lo que sobrevive a una apertura de 9 px es relleno (barba, lentes gruesos); lo demás es línea
            relleno = cv2.morphologyEx(comp, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
            interior = cv2.dilate(relleno, np.ones((5, 5), np.uint8))
            # el anillo exterior: componente menos el relleno, solo cerca del borde de su caja
            anillo = (comp == 1) & (interior == 0)
            yy, xx = np.nonzero(anillo)
            borde = (np.minimum.reduce([xx - x, x + cw - 1 - xx, yy - y, y + ch - 1 - yy]) < 0.18 * min(cw, ch))
            alfa[yy[borde], xx[borde]] = 0
    # restos: trazos finos y altos (lados del contorno). Cejas, boca y lentes son anchos y bajos.
    m = (alfa > 0.5).astype(np.uint8)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    for k in range(1, n):
        x, y, cw, ch, area = stats[k]
        comp = (etiquetas == k).astype(np.uint8)
        relleno = cv2.morphologyEx(comp, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)).sum()
        if ch > 0.28 * h and relleno < 0.1 * area:
            alfa[etiquetas == k] = 0
            habia = True
    return alfa, habia


def a_estampa(img: Image.Image, lado: int = 128, ocupa: float = 0.74) -> tuple[np.ndarray, bool]:
    """Quita el fondo y la piel amarilla; centra los rasgos y devuelve (RGBA lado x lado, había_contorno)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    borde = np.concatenate([a[:10].reshape(-1, 3), a[-10:].reshape(-1, 3),
                            a[:, :10].reshape(-1, 3), a[:, -10:].reshape(-1, 3)])
    fondo = np.median(borde, 0)
    dist = np.linalg.norm(a - fondo, axis=2)
    alfa = np.clip((dist - 45) / 45, 0, 1)
    # piel: amarillo saturado y claro
    hsv = np.asarray(img.convert("RGB").convert("HSV")).astype(np.float32)
    tono, sat, val = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    piel = (tono > 38) & (tono < 66) & (sat > 0.42) & (val > 0.62)
    alfa[piel] = 0
    alfa, habia = sin_contorno(alfa)
    ys, xs = np.where(alfa > 0.5)
    if len(ys) < 200:
        raise ValueError("La imagen no trae rasgos reconocibles")
    lo_y, hi_y = np.percentile(ys, [0.5, 99.5])
    lo_x, hi_x = np.percentile(xs, [0.5, 99.5])
    cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
    s = max(hi_x - lo_x, hi_y - lo_y) / ocupa
    rgba = np.dstack([a, alfa * 255]).clip(0, 255).astype(np.uint8)
    caja = (int(cx - s / 2), int(cy - s / 2), int(cx + s / 2), int(cy + s / 2))
    recorte = Image.fromarray(rgba, "RGBA").crop(caja).resize((lado, lado), Image.Resampling.LANCZOS)
    out = np.asarray(recorte).copy()
    out[..., 3] = np.where(out[..., 3] > 110, 255, 0)  # bordes nítidos, como las estampas reales
    return out, habia


class FluxKlein(Generador):
    id = "flux_klein"
    nombre = "Asesoría con FLUX.2"
    descripcion = "Modelo preentrenado FLUX.2 klein. Usa tu foto si la diste y lo que le contaste a Tito."
    conserva_forma = False
    acepta_texto = True
    necesita_foto = False
    opciones = []

    def __init__(self):
        self.pipe = None
        self.error = None
        self.lock = threading.Lock()
        self.modo = None

    def estado(self):
        if self.pipe is not None:
            return {"disponible": True, "detalle": f"listo ({self.modo})"}
        if self.error:
            return {"disponible": False, "detalle": self.error}
        return {"disponible": False, "detalle": "cargando FLUX.2"}

    def preparar(self):
        try:
            import torch
            from diffusers import Flux2KleinPipeline
            from diffusers.quantizers import PipelineQuantizationConfig
            t = time.time()
            q = PipelineQuantizationConfig(
                quant_backend="bitsandbytes_4bit",
                quant_kwargs={"load_in_4bit": True, "bnb_4bit_quant_type": "nf4",
                              "bnb_4bit_compute_dtype": torch.bfloat16},
                components_to_quantize=["transformer", "text_encoder"],
            )
            pipe = Flux2KleinPipeline.from_pretrained(MODELO, torch_dtype=torch.bfloat16, quantization_config=q)
            pipe.set_progress_bar_config(disable=True)
            # Todo en la GPU necesita ~6 GB libres. Con menos (p. ej. junto al modelo entrenado en 8 GB),
            # cada parte sube a la GPU solo mientras se usa: más lento, pero no se llena la VRAM.
            libre = torch.cuda.mem_get_info()[0] / 2**30
            if os.environ.get("FLUX_GPU") == "1" or (libre >= 6.5 and os.environ.get("FLUX_GPU") != "0"):
                pipe.to("cuda")
                self.modo = "GPU"
            else:
                pipe.enable_model_cpu_offload()
                self.modo = "GPU por partes"
            self.pipe = pipe
            print(f"[flux] listo ({self.modo}) en {time.time() - t:.0f} s")
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            print("[flux] error al cargar:", self.error)

    def generar(self, foto, pedidos: list[Pedido], opciones: dict):
        import torch
        ficha = opciones.get("ficha") or {}
        estilo = imagen_estilo()
        refs = [recortar_cara(foto), estilo] if foto is not None else [estilo]
        prompt = armar_prompt(ficha, foto is not None)
        with self.lock:
            for p in pedidos:
                seed, rgba, intentos = p.seed, None, 0
                while intentos < 3:
                    intentos += 1
                    img = self.pipe(image=refs, prompt=prompt, num_inference_steps=4, guidance_scale=1.0,
                                    height=LADO, width=LADO,
                                    generator=torch.Generator("cpu").manual_seed(seed)).images[0]
                    try:
                        rgba, contorno = a_estampa(img)
                    except ValueError:
                        seed += 7919
                        continue
                    if not contorno:
                        break
                    seed += 7919  # dibujó contorno: probar otra semilla; si se acaban, queda la versión limpiada
                if rgba is None:
                    raise RuntimeError("FLUX no dio una estampa usable tras 3 intentos")
                yield Resultado(id=p.id, rgba=rgba, mascara=rgba[..., 3].copy(), datos={
                    "seed": seed, "prompt": prompt,
                    # sin detector de rasgos: se registra lo que se pidió en el prompt
                    "rasgos_detectados": rasgos_de_ficha(ficha), "rasgos_fuente": "pedido al generador",
                })


def rasgos_de_ficha(ficha: dict) -> dict:
    r = ficha.get("rasgos") or {}
    out = {k: bool(r.get(k)) for k in ("lentes", "barba", "bigote")}
    if r.get("expresion"):
        out["expresion"] = r["expresion"]
    c = ficha.get("cabello") or {}
    if c.get("color") or c.get("largo"):
        out["cabello"] = {"color": c.get("color"), "largo": c.get("largo")}
    return out
