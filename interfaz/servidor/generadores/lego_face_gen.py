"""Forma 1: los modelos propios del equipo (Flow 1 + DiTo + Flow 2 + VAE color)."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import numpy as np

from .base import Generador, Pedido, Resultado

RAIZ = Path(__file__).resolve().parents[3]  # raíz del repo lego-face
CODIGO = Path(os.environ.get("LEGO_FACE_CODIGO", RAIZ / "LegoFace_Local"))
PESOS = Path(os.environ.get("LEGO_FACE_PESOS", RAIZ / "Face"))
if not PESOS.exists() and (RAIZ / "Face.zip").exists():
    PESOS = RAIZ / "Face.zip"

# Cuánto se guía cada flow por la foto. Los valores por defecto (2.0 y 1.5) vienen de los checkpoints.
ESTILOS = {
    "parecido":   {"cfg_flow1": 3.0, "cfg_flow2": 2.0},
    "equilibrado": {"cfg_flow1": None, "cfg_flow2": None},
    "libre":      {"cfg_flow1": 1.0, "cfg_flow2": 1.0},
}


class LegoFace(Generador):
    id = "lego_face"
    nombre = "Modelo entrenado"
    descripcion = "Flow 1 dibuja la forma de los rasgos y Flow 2 les pone color. Entrenados por el grupo."
    conserva_forma = True
    opciones = [{
        "id": "estilo", "nombre": "Estilo", "tipo": "elegir", "defecto": "equilibrado",
        "valores": [
            {"id": "parecido", "nombre": "Parecido", "descripcion": "Se pega más a tu foto"},
            {"id": "equilibrado", "nombre": "Equilibrado", "descripcion": "Como fue entrenado"},
            {"id": "libre", "nombre": "Libre", "descripcion": "Más variedad entre caras"},
        ],
    }]

    def __init__(self):
        self.modelos = None
        self.error = None
        self.cargando = False
        self.lock = threading.Lock()

    def estado(self):
        if self.modelos is not None:
            return {"disponible": True, "detalle": f"listo en {self.modelos.device}"}
        if self.error:
            return {"disponible": False, "detalle": self.error}
        return {"disponible": False, "detalle": "cargando modelos"}

    def preparar(self):
        self.cargando = True
        try:
            sys.path.insert(0, str(CODIGO))
            import torch
            from lego_face import cargar_modelos
            if not torch.cuda.is_available():
                torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
            t = time.time()
            m = cargar_modelos(str(PESOS), device=os.environ.get("LEGO_FACE_DEVICE", "auto"))
            m.cargar_dino()  # descarga DINOv2 la primera vez
            self.modelos = m
            print(f"[lego_face] modelos listos en {m.device} ({time.time() - t:.1f} s)")
        except Exception as e:  # se muestra en la interfaz como no disponible
            self.error = f"{type(e).__name__}: {e}"
            print("[lego_face] error al cargar:", self.error)
        finally:
            self.cargando = False

    def generar(self, foto, pedidos: list[Pedido], opciones: dict):
        estilo = ESTILOS.get(opciones.get("estilo", "equilibrado"), ESTILOS["equilibrado"])
        m = self.modelos
        with self.lock:
            # DINO se calcula una vez por ronda y se reutiliza en las 5 caras.
            cond = m.extraer_condiciones(foto, True)
            original = m.extraer_condiciones
            m.extraer_condiciones = lambda *_a, **_k: cond
            try:
                for p in pedidos:
                    yield self._una(m, foto, p, estilo)
            finally:
                m.extraer_condiciones = original

    def _una(self, m, foto, p: Pedido, estilo):
        seed = p.seed
        for _ in range(4):
            try:
                r = m.generar(foto, mascara=p.mascara, seed=seed, **estilo)
                break
            except ValueError as e:
                if "vacía" not in str(e):
                    raise
                seed += 7919  # Flow 1 dio una máscara vacía: otra semilla
        else:
            raise RuntimeError("No salió una cara válida tras 4 intentos")
        return Resultado(
            id=p.id, rgba=r["rgba"], mascara=r["mascara"],
            datos={"seed": seed, "cfg_flow1": r["cfg_flow1"] if p.mascara is None else None,
                   "cfg_flow2": r["cfg_flow2"], "cara_detectada": bool(r["cara_detectada"])},
        )
