"""Une las cuatro capturas de la Fig. 4 en un panel 2 x 2 con letras (a)-(d).

    python componer_fig4.py <carpeta_capturas> <salida.png>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NOMBRES = [("a_inicio", "(a) Inicio"), ("b_asesoria", "(b) Asesoría"),
           ("c_variaciones", "(c) Cinco variaciones"), ("d_resumen", "(d) Resumen verificado")]


def main():
    carpeta, salida = Path(sys.argv[1]), Path(sys.argv[2])
    ancho, alto, m, rotulo = 1200, 750, 16, 44
    try:
        f = ImageFont.truetype("segoeuib.ttf", 30)
    except OSError:
        f = ImageFont.load_default()
    panel = Image.new("RGB", (2 * ancho + 3 * m, 2 * (alto + rotulo) + 3 * m), "white")
    d = ImageDraw.Draw(panel)
    for i, (archivo, texto) in enumerate(NOMBRES):
        img = Image.open(carpeta / f"{archivo}.png").convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)
        x = m + (i % 2) * (ancho + m)
        y = m + (i // 2) * (alto + rotulo + m)
        d.text((x, y + 4), texto, font=f, fill="black")
        panel.paste(img, (x, y + rotulo))
        d.rectangle([x - 1, y + rotulo - 1, x + ancho, y + rotulo + alto], outline=(200, 200, 200), width=2)
    panel.save(salida)
    print("panel:", salida, panel.size)


if __name__ == "__main__":
    main()
