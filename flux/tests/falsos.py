"""Módulos falsos para correr el notebook sin GPU: IPython.display, torch, diffusers y transformers (CLIP).

El pipeline falso tiene la MISMA firma que Flux2KleinPipeline.__call__ (los parámetros que usamos) y registra cada
llamada en LLAMADAS. Para ejercitar las Etapas 2–4 su salida depende del prompt y de la semilla:
- fondo amarillo solo si el prompt dice "edge to edge" (el resto sale gris -> la falla más común es "fondo");
- semilla % 7 == 3 -> imagen sin trazo (el guardrail la descarta y se reintenta con semilla + 1000).
"""
import sys
import types
from contextlib import contextmanager

import numpy as np
from PIL import Image, ImageDraw

LLAMADAS = []
CARGAS = []


class _Generador:
    def __init__(self, dispositivo="cpu"):
        self.dispositivo, self.semilla = dispositivo, None

    def manual_seed(self, s):
        self.semilla = s
        return self


class _Pipe:
    hf_device_map = {"text_encoder": 0, "transformer": 1, "vae": 1}

    def set_progress_bar_config(self, **kw):
        pass

    def __call__(self, prompt=None, image=None, height=1024, width=1024, num_inference_steps=50,
                 guidance_scale=4.0, generator=None):
        LLAMADAS.append(dict(prompt=prompt, image=image, height=height, width=width, pasos=num_inference_steps,
                             guia=guidance_scale, semilla=generator.semilla, gen=generator.dispositivo))
        fondo = (242, 205, 55) if "edge to edge" in prompt else (150, 150, 150)
        im = Image.new("RGB", (width, height), fondo)
        if generator.semilla % 7 != 3:
            d = ImageDraw.Draw(im)
            d.rectangle([150, 150, 230, 165], fill=(60, 30, 10))            # cejas
            d.rectangle([290, 150, 370, 165], fill=(60, 30, 10))
            d.ellipse([175, 190, 205, 235], fill="black")                    # ojos
            d.ellipse([310, 190, 340, 235], fill="black")
            d.arc([180, 260, 340, 380], 20, 160, fill="black", width=12)    # boca
        return types.SimpleNamespace(images=[im])


class _DiffusionPipeline:
    @classmethod
    def from_pretrained(cls, modelo, **kw):
        CARGAS.append(dict(modelo=modelo, **{k: str(v) for k, v in kw.items()}))
        return _Pipe()


class _T:
    """Tensor mínimo para el camino de CLIP."""

    def __init__(self, a):
        self.a = np.asarray(a, float)

    def to(self, *_):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.a

    def softmax(self, dim=-1):
        e = np.exp(self.a - self.a.max(axis=dim, keepdims=True))
        return _T(e / e.sum(axis=dim, keepdims=True))


class _ClipModelo:
    @classmethod
    def from_pretrained(cls, nombre):
        return cls()

    def to(self, *_):
        return self

    def eval(self):
        return self

    def __call__(self, input_ids=None, pixel_values=None, **kw):
        n = input_ids.a.shape[0]
        return types.SimpleNamespace(logits_per_image=_T([[5.0] + [0.0] * (n - 1)]))   # siempre el 1er texto


class _ClipProc:
    @classmethod
    def from_pretrained(cls, nombre):
        return cls()

    def __call__(self, text=None, images=None, return_tensors=None, padding=None):
        return {"input_ids": _T(np.zeros((len(text), 4))), "pixel_values": _T(np.zeros((1, 3, 4, 4)))}


def instalar():
    ipy = types.ModuleType("IPython")
    ipy.display = types.ModuleType("IPython.display")
    ipy.display.display = lambda x: print("[display]", type(x).__name__, getattr(x, "shape", getattr(x, "size", "")))
    ipy.get_ipython = lambda: None
    sys.modules["IPython"], sys.modules["IPython.display"] = ipy, ipy.display

    torch = types.ModuleType("torch")
    torch.__version__ = "falso"
    torch.bfloat16, torch.float16 = "bfloat16", "float16"
    torch.Generator = _Generador
    torch.cuda = types.SimpleNamespace(is_available=lambda: False, device_count=lambda: 0)
    torch.no_grad = contextmanager(lambda: (yield))
    sys.modules["torch"] = torch

    diff = types.ModuleType("diffusers")
    diff.__version__ = "falso"
    diff.DiffusionPipeline = _DiffusionPipeline
    sys.modules["diffusers"] = diff

    tr = types.ModuleType("transformers")
    tr.CLIPModel, tr.CLIPProcessor = _ClipModelo, _ClipProc
    sys.modules["transformers"] = tr
    LLAMADAS.clear()
    CARGAS.clear()
