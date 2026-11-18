"""Anexo A (mosaico de caras de ambos métodos) y Fig. 3 (cascada del modelo propio).

    python mosaico_y_fig3.py <carpeta_retratos> <carpeta_comparacion> <carpeta_entrega>

Usa las rondas 1 que dejó comparar_metodos.py y genera las rondas 2:
  - modelo propio: ronda con Variar, conservando la forma de las caras 1 y 2;
  - FLUX: ronda con el pedido "ponle lentes y que se vea más serio", interpretado por el agente.
Las caras 1 y 2 hacen de aceptadas: las fija el script, no una persona.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PERSONAS = ["p01", "p04", "p07"]
PEDIDO = "ponle lentes y que se vea más serio"
AMARILLO = (242, 205, 55)
T = 104  # lado de cada cara


def fuente(tam, negrita=False):
    for nombre in (("segoeuib.ttf" if negrita else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def ficha_cara(rgba, borde=None):
    t = Image.new("RGBA", (128, 128), AMARILLO + (255,))
    t.alpha_composite(Image.fromarray(rgba) if isinstance(rgba, np.ndarray) else rgba)
    t = t.convert("RGB").resize((T, T), Image.Resampling.LANCZOS)
    if borde:
        ImageDraw.Draw(t).rectangle([0, 0, T - 1, T - 1], outline=borde, width=5)
    return t


def main():
    retratos, comp, entrega = map(Path, sys.argv[1:4])
    repo = Path(__file__).resolve().parents[2]  # raíz del repo lego-face
    sys.path.insert(0, str(repo / "interfaz" / "servidor"))
    sys.path.insert(0, str(repo / "agente"))
    from agente import interpretar
    from generadores.base import Pedido
    from generadores.flux_gen import FluxKlein, recortar_cara
    from generadores.lego_face_gen import LegoFace

    caras = comp / "caras"
    leer = lambda p, m, k: np.asarray(Image.open(caras / f"{p}_{m}_{k}.png").convert("RGBA"))
    propio, flux = LegoFace(), FluxKlein()
    propio.preparar()
    flux.preparar()
    pedido = interpretar(PEDIDO, None)  # mismas reglas que usa la app sin LLM
    ficha = {"rasgos": {k: v for k, v in pedido["rasgos"].items() if v is not None},
             "cabello": {k: v for k, v in pedido["cabello"].items() if v is not None}}
    print("pedido interpretado:", ficha, flush=True)

    filas = []
    for p in PERSONAS:
        rgb = np.asarray(Image.open(retratos / f"{p}.png").convert("RGB"))
        r1p = [leer(p, "modelo_propio", k) for k in range(1, 6)]
        r1f = [leer(p, "flux", k) for k in range(1, 6)]
        mascaras = [np.asarray(Image.open(caras / f"{p}_modelo_propio_{k}_mascara.png")) for k in (1, 2)]
        r2p = [r.rgba for r in propio.generar(rgb, [Pedido(id=f"v{k}", seed=4000 + k, mascara=mascaras[k % 2]) for k in range(5)], {})]
        r2f = [r.rgba for r in flux.generar(rgb, [Pedido(id=f"v{k}", seed=5000 + k) for k in range(5)], {"ficha": ficha})]
        filas.append((p, recortar_cara(rgb), r1p, r2p, r1f, r2f))
        print(p, "listo", flush=True)

    # ---------- mosaico ----------
    m, sep, ancho_foto = 14, 26, 150
    bloque = 5 * T + 4 * 6
    W = m + ancho_foto + m + 110 + bloque + sep + bloque + m
    alto_persona = 2 * T + 6 + 34
    H = 70 + len(filas) * alto_persona + 62
    lienzo = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(lienzo)
    x1 = m + ancho_foto + m + 110
    x2 = x1 + bloque + sep
    d.text((x1, 18), "Ronda 1", font=fuente(22, True), fill="black")
    d.text((x2, 18), "Ronda 2", font=fuente(22, True), fill="black")
    y = 70
    verde = (35, 120, 65)
    for p, foto, r1p, r2p, r1f, r2f in filas:
        lienzo.paste(foto.resize((ancho_foto, ancho_foto)), (m, y + (2 * T + 6 - ancho_foto) // 2))
        for fila_i, (nombre, r1, r2) in enumerate((("Modelo\npropio", r1p, r2p), ("FLUX.2\nklein", r1f, r2f))):
            yy = y + fila_i * (T + 6)
            d.multiline_text((m + ancho_foto + m, yy + 28), nombre, font=fuente(17, True), fill="black", spacing=2)
            for k in range(5):
                borde = verde if k < 2 else None
                lienzo.paste(ficha_cara(r1[k], borde), (x1 + k * (T + 6), yy))
                lienzo.paste(ficha_cara(r2[k]), (x2 + k * (T + 6), yy))
        y += alto_persona
    d.text((m, H - 54), "Ronda 2: el modelo propio usa Variar con las caras 1 y 2; FLUX recibe el pedido «" + PEDIDO + "».",
           font=fuente(15), fill=(90, 90, 90))
    d.text((m, H - 30), "Borde verde: caras tomadas como aceptadas (las fija el script, no una persona). "
           "Retratos sintéticos generados con FLUX.2 klein.", font=fuente(15), fill=(90, 90, 90))
    lienzo.save(entrega / "anexo_a_mosaico.png")
    print("mosaico:", entrega / "anexo_a_mosaico.png")

    # ---------- Fig. 3: cascada del modelo propio sobre un retrato ----------
    p = PERSONAS[0]
    rgb = np.asarray(Image.open(retratos / f"{p}.png").convert("RGB"))
    foto = recortar_cara(rgb).resize((300, 300))
    mascara = Image.open(caras / f"{p}_modelo_propio_1_mascara.png").convert("L").resize((300, 300), Image.Resampling.NEAREST)
    estampa = ficha_cara(leer(p, "modelo_propio", 1)).resize((300, 300), Image.Resampling.NEAREST)
    fig = Image.new("RGB", (900, 336), (245, 246, 248))
    d = ImageDraw.Draw(fig)
    for i, (img, txt) in enumerate(((foto, "Foto (retrato sintético)"), (mascara.convert("RGB"), "Flow 1 + codec de forma"),
                                    (estampa, "Flow 2 + codec de color"))):
        d.text((i * 300 + 10, 8), txt, font=fuente(16), fill="black")
        fig.paste(img, (i * 300, 36))
    fig.save(entrega / "fig3_cascada.png")
    print("fig3:", entrega / "fig3_cascada.png")


if __name__ == "__main__":
    main()
