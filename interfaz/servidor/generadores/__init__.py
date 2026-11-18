"""Registro de formas de generar. Para sumar una nueva, impórtala y agrégala a la lista."""
import os

from .base import Generador, Pedido, Resultado
from .lego_face_gen import LegoFace


def crear_generadores() -> dict[str, Generador]:
    lista: list[Generador] = [LegoFace()]
    if os.environ.get("FLUX", "1") != "0":
        from .flux_gen import FluxKlein
        lista.append(FluxKlein())
    if os.environ.get("LEGO_DEMO") == "1":
        from .simulado import Simulado
        lista.append(Simulado())
    return {g.id: g for g in lista}
