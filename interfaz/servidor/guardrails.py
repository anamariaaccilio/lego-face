"""Controles antes de generar: archivo válido, tamaño razonable y exactamente una cara."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps

MAX_BYTES = 10 * 1024 * 1024
LADO_MAX = 1280
LADO_MIN = 160
FORMATOS = {"JPEG", "PNG", "WEBP"}

_detector = None


class FotoRechazada(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def leer_foto(datos: bytes) -> np.ndarray:
    if len(datos) > MAX_BYTES:
        raise FotoRechazada("archivo_grande", "La foto pesa más de 10 MB.")
    try:
        img = Image.open(io.BytesIO(datos))
        formato = img.format
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise FotoRechazada("archivo_invalido", "No pude abrir ese archivo como imagen.")
    if formato not in FORMATOS:
        raise FotoRechazada("archivo_invalido", "Usa una foto JPG, PNG o WEBP.")
    if min(img.size) < LADO_MIN:
        raise FotoRechazada("foto_chica", "La foto es muy pequeña.")
    img.thumbnail((LADO_MAX, LADO_MAX))
    return np.asarray(img).copy()


def contar_caras(rgb: np.ndarray) -> int:
    global _detector
    import cv2
    if _detector is None:
        _detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    h, w = rgb.shape[:2]
    gris = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    caras = _detector.detectMultiScale(gris, 1.1, 6, minSize=(max(48, min(h, w) // 8),) * 2)
    return len(caras)


def revisar_foto(rgb: np.ndarray) -> None:
    n = contar_caras(rgb)
    if n == 0:
        raise FotoRechazada("sin_cara", "No encuentro tu cara. Acércate un poco y mira de frente.")
    if n > 1:
        raise FotoRechazada("varias_caras", f"Veo {n} caras. Necesito que salga una sola persona.")
