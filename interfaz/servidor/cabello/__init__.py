"""Inferencia de cabello 3D a partir de retratos."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
from threading import Lock

import numpy as np

MODELOS = Path(__file__).resolve().parents[2] / "modelos_cabello"
FORMA_LATENTE = (8, 6, 7, 6)
VAE_ORIGINAL = "6431af8b0dfea768899f4e631ffc7cfb4c68b2bb948cebdf62f1cfd59dc778af"


class CabelloVacio(ValueError):
    pass


def superficie(ocupado, origen, paso):
    from skimage.measure import marching_cubes

    if not ocupado.any():
        raise CabelloVacio("El modelo no encontró una forma de cabello. Prueba el catálogo.")
    # Cierra la superficie también cuando la ocupación toca el borde del volumen.
    volumen = np.pad(ocupado, 1)
    vertices, caras, _, _ = marching_cubes(volumen, level=0.5, gradient_direction="ascent", allow_degenerate=False)
    vertices = np.round((vertices - 1) * paso + origen, 3)
    return {"pos": vertices.ravel().tolist(), "indices": caras.ravel().tolist()}


class CabelloFoto:
    def __init__(self, carpeta=MODELOS, *, desde_ruido=False):
        self.carpeta = Path(carpeta)
        self.desde_ruido = desde_ruido
        self.flow_path = (self.carpeta / "flow1_ruido.pt" if desde_ruido else
                          Path(os.environ.get("LEGO_CABELLO_FLOW", self.carpeta / "flow1_best.pt")))
        self.lock = Lock()
        self.modelos = None

    def disponible(self):
        return (self.flow_path.is_file()
                and (self.carpeta / "vae1_v3_best.pt").is_file()
                and (self.carpeta / "grilla.npz").is_file())

    def _cargar(self):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        from .redes import Flow1, VAE1

        device = torch.device(os.environ.get("LEGO_CABELLO_DEVICE", "cpu"))
        raw = (self.carpeta / "vae1_v3_best.pt").read_bytes()
        vae_hash = hashlib.sha256(raw).hexdigest()
        if vae_hash != VAE_ORIGINAL:
            raise ValueError("La VAE 1 no coincide con el checkpoint de la integración.")
        ck = torch.load(self.flow_path, weights_only=True, map_location="cpu")
        if ck.get("vae_sha256") != vae_hash:
            raise ValueError("El checkpoint es incompatible con esta VAE 1.")
        pasos = ck.get("pasos", 0) if self.desde_ruido else 0
        if (self.desde_ruido and not pasos) or (not self.desde_ruido and ck.get("modo") != "directo"):
            raise ValueError("El checkpoint no corresponde al modo de generación solicitado.")
        with np.load(self.carpeta / "grilla.npz", allow_pickle=False) as grilla:
            cabeza = grilla["cabeza"]
            origen, paso = grilla["origen"], float(grilla["paso_ldu"])
            if ck.get("base_sha256") != str(grilla["base_sha256"].item()):
                raise ValueError("El checkpoint de cabello pertenece a otra grilla.")
        # El archivo original, identificado por su hash, incluye estado NumPy del entrenamiento.
        pesos = torch.load(io.BytesIO(raw), weights_only=False, map_location="cpu")
        vae = VAE1(cabeza)
        vae.load_state_dict(pesos["model"], strict=True)
        flow = Flow1(ck["dim_foto"])
        flow.load_state_dict(ck["modelo"], strict=True)
        dino_repo = ck["dino"]
        if dino_repo != "facebook/dinov2-small":
            raise ValueError("Este modelo usa DINOv2 Small.")
        fuente = os.environ.get("LEGO_CABELLO_DINO", dino_repo)
        procesador = AutoImageProcessor.from_pretrained(fuente)
        dino = AutoModel.from_pretrained(fuente)
        for modelo in (dino, flow, vae):
            modelo.to(device).eval().requires_grad_(False)
        return (device, dino, flow, vae, procesador,
                ck["media"].to(device), ck["escala"].to(device), origen, paso, pasos)

    def generar(self, foto):
        return self._generar(foto, [None])[0]

    def generar_variantes(self, foto, semillas):
        return self._generar(foto, semillas)

    def _generar(self, foto, semillas):
        import torch
        from PIL import Image, ImageOps
        from torch.nn import functional as F

        with self.lock, torch.inference_mode():
            if self.modelos is None:
                self.modelos = self._cargar()
            device, dino, flow, vae, procesador, media, escala, origen, paso, pasos = self.modelos
            imagen = ImageOps.pad(Image.fromarray(foto).convert("RGB"), (224, 224), color="gray")
            opciones = {} if self.desde_ruido else {"do_resize": False, "do_center_crop": False}
            batch = procesador(images=[imagen], return_tensors="pt", **opciones).to(device)
            alto, ancho = (v // dino.config.patch_size for v in batch["pixel_values"].shape[-2:])
            parches = dino(**batch).last_hidden_state[:, -alto * ancho:]
            mapa = parches.transpose(1, 2).reshape(1, parches.shape[-1], alto, ancho)
            tokens = F.adaptive_avg_pool2d(mapa, (8, 8)).flatten(2).transpose(1, 2).float()
            resultados = []
            for semilla in semillas:
                if pasos:
                    generador = torch.Generator(device=device).manual_seed(semilla)
                    latente = torch.randn((1, *FORMA_LATENTE), generator=generador, device=device)
                    for k in range(pasos):
                        tiempo = tokens.new_full((1,), k / pasos)
                        latente = latente + flow(latente, tiempo, tokens) / pasos
                else:
                    latente = flow(tokens.new_zeros((1, *FORMA_LATENTE)), tokens.new_ones(1), tokens)
                ocupado = (vae.decode(latente * escala + media)[0, 0] > 0).cpu().numpy()
                resultados.append(superficie(ocupado, origen, paso))
        return resultados
