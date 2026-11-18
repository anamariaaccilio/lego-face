"""Contrato que cumple cualquier forma de generar caras.

Para agregar una forma nueva (por ejemplo una API img2img):
1. Crea un archivo en esta carpeta con una clase que herede de Generador.
2. Regístrala en generadores/__init__.py.
El servidor y la interfaz la muestran sin más cambios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import numpy as np


@dataclass
class Pedido:
    """Una de las 5 caras que se piden en una ronda."""
    id: str                          # "R2-3": ronda 2, cara 3
    seed: int
    mascara: np.ndarray | None = None  # forma heredada de una cara aprobada (128x128, 0/255)


@dataclass
class Resultado:
    id: str
    rgba: np.ndarray                 # 128x128x4 uint8, alfa 0 = piel
    mascara: np.ndarray | None = None
    datos: dict = field(default_factory=dict)  # seed real, cfg, etc. Se guarda en el registro.


class Generador:
    id: str = ""
    nombre: str = ""
    descripcion: str = ""
    # Opciones que la interfaz muestra. Tipos: "elegir" (valores) o "texto".
    opciones: list[dict] = []
    # True si puede conservar la forma de una cara aprobada y variar el resto.
    conserva_forma: bool = False
    # True si entiende pedidos en texto (la ficha de la asesoría y "¿qué le cambio?").
    acepta_texto: bool = False
    # False si puede generar sin foto (solo con la descripción).
    necesita_foto: bool = True

    def estado(self) -> dict:
        """{'disponible': bool, 'detalle': str}"""
        return {"disponible": True, "detalle": ""}

    def preparar(self) -> None:
        """Carga pesada (modelos). Se llama una vez en segundo plano al iniciar."""

    def generar(self, foto: np.ndarray, pedidos: list[Pedido], opciones: dict) -> Iterator[Resultado]:
        """foto: RGB uint8. Debe producir un Resultado por pedido, en orden, a medida que termina cada uno."""
        raise NotImplementedError

    def describir(self) -> dict:
        e = self.estado()
        return {
            "id": self.id, "nombre": self.nombre, "descripcion": self.descripcion,
            "opciones": self.opciones, "conserva_forma": self.conserva_forma,
            "acepta_texto": self.acepta_texto, "necesita_foto": self.necesita_foto,
            "disponible": e["disponible"], "detalle": e.get("detalle", ""),
        }
