"""Genera retratos sintéticos (personas que no existen) para evaluar y para las figuras.

    python generar_retratos.py <carpeta_salida>

Usa FLUX.2 [klein] 4B en 4 bits. 60 % con rasgos peruanos y 40 % de otros orígenes,
la misma proporción que los datos de entrenamiento. Semillas fijas: el resultado se puede repetir.
"""
import json
import sys
import time
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline
from diffusers.quantizers import PipelineQuantizationConfig

ESTILO = ("Frontal head-and-shoulders photo portrait, looking straight at the camera, plain light gray wall behind, "
          "soft natural window light, sharp focus, realistic smartphone photo, no text, no watermark.")
PERSONAS = [
    ("p01", "A 24-year-old Peruvian woman from Lima with long black hair, smiling."),
    ("p02", "A 45-year-old Andean Peruvian man from Cusco with short black hair and a neutral expression."),
    ("p03", "A 19-year-old Peruvian student with wavy dark brown hair and round black glasses, slight smile."),
    ("p04", "A 62-year-old Peruvian man with short gray hair and a gray mustache, smiling."),
    ("p05", "A 33-year-old Peruvian woman from the Amazon region with long straight black hair, serious expression."),
    ("p06", "A 28-year-old Peruvian man with a short black beard and short curly hair, smiling."),
    ("p07", "A 38-year-old Black woman with short natural curly hair, smiling."),
    ("p08", "A 52-year-old East Asian man with thin rectangular glasses and short black hair, neutral expression."),
    ("p09", "A 26-year-old white woman with shoulder-length red hair and freckles, smiling."),
    ("p10", "A 41-year-old South Asian man with a full dark beard and short black hair, slight smile."),
]


def main():
    salida = Path(sys.argv[1])
    salida.mkdir(parents=True, exist_ok=True)
    q = PipelineQuantizationConfig(
        quant_backend="bitsandbytes_4bit",
        quant_kwargs={"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": torch.bfloat16},
        components_to_quantize=["transformer", "text_encoder"],
    )
    pipe = Flux2KleinPipeline.from_pretrained("black-forest-labs/FLUX.2-klein-4B", torch_dtype=torch.bfloat16, quantization_config=q)
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    meta = []
    for i, (pid, desc) in enumerate(PERSONAS):
        t = time.time()
        img = pipe(prompt=f"{desc} {ESTILO}", num_inference_steps=4, guidance_scale=1.0, height=768, width=768,
                   generator=torch.Generator("cpu").manual_seed(1000 + i)).images[0]
        img.save(salida / f"{pid}.png")
        meta.append({"id": pid, "descripcion": desc, "semilla": 1000 + i, "modelo": "FLUX.2-klein-4B (4 bits), 4 pasos"})
        print(f"{pid} {time.time() - t:.1f} s", flush=True)
    (salida / "retratos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
