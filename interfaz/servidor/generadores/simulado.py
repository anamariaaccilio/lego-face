"""Generador falso para trabajar la interfaz sin PyTorch. Solo aparece con LEGO_DEMO=1."""
from __future__ import annotations

import time

import numpy as np
from PIL import Image

from .base import Generador, Pedido, Resultado
from .lego_face_gen import CODIGO


class Simulado(Generador):
    id = "simulado"
    nombre = "Simulado"
    descripcion = "Recolorea una cara de prueba. Solo para desarrollo."
    conserva_forma = True
    opciones = []

    def __init__(self):
        img = Image.open(CODIGO / "pruebas" / "lego_prueba.png").convert("RGBA")
        self.base = np.asarray(img.resize((128, 128))).copy()

    def generar(self, foto, pedidos: list[Pedido], opciones):
        for p in pedidos:
            time.sleep(1.2)
            rng = np.random.default_rng(p.seed)
            rgba = self.base.copy()
            if p.mascara is None and rng.random() < 0.5:
                rgba = rgba[:, ::-1].copy()
            mask = rgba[..., 3] > 0
            tinte = rng.uniform(0.4, 1.0, 3)
            rgba[..., :3][mask] = (rgba[..., :3][mask] * tinte).astype(np.uint8)
            if p.mascara is not None:
                rgba[..., 3] = p.mascara
            yield Resultado(id=p.id, rgba=rgba, mascara=rgba[..., 3].copy(), datos={"seed": p.seed})
