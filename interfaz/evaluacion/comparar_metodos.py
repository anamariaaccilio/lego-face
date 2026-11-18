"""Compara los dos métodos con las mismas fotos: parecido (CLIP), diversidad (LPIPS) y tiempo.

    python comparar_metodos.py <carpeta_fotos> <carpeta_salida> [--repo ../lego-face]

Por cada foto, cada método genera una ronda de 5 caras (semillas fijas) sin ficha ni pedidos,
igual que la primera ronda de la interfaz. Se mide:
  - CLIP: similitud coseno entre la foto (recortada a la cara) y cada estampa sobre amarillo.
    Se compara con la similitud contra las fotos de las otras personas (margen) y se cuenta
    cuántas estampas reconoce CLIP como de su propia persona entre todas las fotos (top-1).
  - LPIPS (AlexNet): distancia media entre los 10 pares de estampas de la misma ronda.
  - Segundos por ronda en esta máquina.
Sirve igual con fotos reales: basta cambiar la carpeta de fotos.
"""
import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

AMARILLO = (242, 205, 55)


def sobre_amarillo(rgba: np.ndarray, lado=224) -> Image.Image:
    fondo = Image.new("RGBA", (128, 128), AMARILLO + (255,))
    fondo.alpha_composite(Image.fromarray(rgba))
    return fondo.convert("RGB").resize((lado, lado), Image.Resampling.BICUBIC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fotos")
    ap.add_argument("salida")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]), help="raíz del repo lego-face")
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()
    serv = Path(a.repo) / "interfaz" / "servidor"
    sys.path.insert(0, str(serv))
    import guardrails
    from generadores.base import Pedido
    from generadores.flux_gen import FluxKlein, recortar_cara
    from generadores.lego_face_gen import LegoFace

    salida = Path(a.salida)
    (salida / "caras").mkdir(parents=True, exist_ok=True)
    fotos = sorted(p for p in Path(a.fotos).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    metodos = {"modelo_propio": LegoFace(), "flux": FluxKlein()}
    for g in metodos.values():
        g.preparar()
        print(g.id, g.estado(), flush=True)

    filas, estampas, recortes = [], {}, {}
    for f in fotos:
        pid = f.stem
        rgb = np.asarray(Image.open(f).convert("RGB"))
        n_caras = guardrails.contar_caras(rgb)
        recortes[pid] = recortar_cara(rgb)
        for nombre, g in metodos.items():
            pedidos = [Pedido(id=f"{pid}_{k}", seed=a.semilla + k) for k in range(5)]
            t = time.time()
            res = list(g.generar(rgb, pedidos, {}))
            seg = time.time() - t
            estampas[(pid, nombre)] = [r.rgba for r in res]
            for k, r in enumerate(res):
                Image.fromarray(r.rgba).save(salida / "caras" / f"{pid}_{nombre}_{k + 1}.png")
                if r.mascara is not None and nombre == "modelo_propio":
                    Image.fromarray(r.mascara).save(salida / "caras" / f"{pid}_{nombre}_{k + 1}_mascara.png")
            filas.append({"persona": pid, "metodo": nombre, "caras_detectadas": n_caras, "segundos_ronda": round(seg, 1)})
            print(f"{pid} {nombre}: {seg:.1f} s", flush=True)

    # libera la GPU para CLIP y LPIPS
    del metodos
    torch.cuda.empty_cache()
    from transformers import CLIPModel, CLIPProcessor
    import lpips

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(dev).eval()
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    @torch.no_grad()
    def emb(imgs):
        x = proc(images=imgs, return_tensors="pt").to(dev)
        e = clip.get_image_features(**x)
        return torch.nn.functional.normalize(e, dim=-1).cpu()

    personas = sorted(recortes)
    e_fotos = emb([recortes[p] for p in personas])  # P x D
    dist = lpips.LPIPS(net="alex", verbose=False).to(dev)

    def a_tensor(rgba):
        x = torch.from_numpy(np.asarray(sobre_amarillo(rgba, 128))).permute(2, 0, 1).float() / 127.5 - 1
        return x[None].to(dev)

    for fila in filas:
        p, m = fila["persona"], fila["metodo"]
        caras = estampas[(p, m)]
        e_caras = emb([sobre_amarillo(c) for c in caras])  # 5 x D
        sims = e_caras @ e_fotos.T  # 5 x P
        i = personas.index(p)
        propia = sims[:, i]
        ajenas = torch.cat([sims[:, :i], sims[:, i + 1:]], 1)
        fila["clip_propia"] = round(float(propia.mean()), 4)
        fila["clip_ajena"] = round(float(ajenas.mean()), 4)
        fila["clip_margen"] = round(float((propia - ajenas.mean(1)).mean()), 4)
        fila["clip_top1"] = int((sims.argmax(1) == i).sum())  # de 5
        with torch.no_grad():
            pares = [float(dist(a_tensor(caras[x]), a_tensor(caras[y]))) for x, y in itertools.combinations(range(5), 2)]
        fila["lpips_medio"] = round(float(np.mean(pares)), 4)

    with open(salida / "por_persona.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

    resumen = {}
    for m in ("modelo_propio", "flux"):
        fs = [f for f in filas if f["metodo"] == m]
        def ms(k):
            v = np.array([f[k] for f in fs], float)
            return {"media": round(float(v.mean()), 4), "desv": round(float(v.std(ddof=1)), 4)}
        resumen[m] = {
            "personas": len(fs),
            "clip_propia": ms("clip_propia"), "clip_ajena": ms("clip_ajena"), "clip_margen": ms("clip_margen"),
            "clip_top1": f"{sum(f['clip_top1'] for f in fs)} de {5 * len(fs)}",
            "clip_top1_tasa": round(sum(f["clip_top1"] for f in fs) / (5 * len(fs)), 3),
            "lpips_medio": ms("lpips_medio"), "segundos_ronda": ms("segundos_ronda"),
        }
    resumen["azar_top1"] = round(1 / len(personas), 3)
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
