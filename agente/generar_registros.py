"""Genera 30 sesiones sintéticas con el formato de registro descrito en README.md.

    python generar_registros.py                 # escribe registros_sinteticos/sesion_01.json ...
    python generar_registros.py --n 30 --semilla 0 --por-ronda 4
"""
import argparse
import json
import random
from pathlib import Path
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
AQUI = Path(__file__).resolve().parent

from agente import COLORES_CABELLO, EXPRESIONES, LARGOS_CABELLO, interpretar_reglas

COMENTARIOS = [
    "yo uso lentes", "muy serio", "me gusta el pelo", "no me parezco", "demasiado feliz",
    "me gusta la barba", "sin bigote se ve mejor", "el color de pelo no es el mío", "me encanta",
    "se ve raro", "parece mi hermano", "los ojos están bien",
]
INSTRUCCIONES = [
    "ponle lentes y que se vea más serio", "quítale la barba", "que sonría más", "ponle bigote",
    "pelo más largo", "pelo negro y corto", "sin lentes", "que se vea sorprendido",
    "ponle barba", "que esté más contento", "cabello castaño", None,
]


def rasgos_al_azar(rng: random.Random) -> dict:
    return {
        "lentes": rng.random() < 0.4,
        "barba": rng.random() < 0.3,
        "bigote": rng.random() < 0.25,
        "expresion": rng.choice(EXPRESIONES),
        "cabello": {"color": rng.choice(COLORES_CABELLO), "largo": rng.choice(LARGOS_CABELLO)},
    }


def sesion(i: int, rng: random.Random, por_ronda: int) -> dict:
    rondas, n = [], 0
    for r in range(1, rng.randint(1, 3) + 1):
        ins = rng.choice(INSTRUCCIONES) if r > 1 else None
        variaciones = []
        for _ in range(por_ronda):
            n += 1
            variaciones.append({
                "id": f"v{n}",
                "decision": rng.choice(["aceptada", "rechazada"]),
                "comentario": rng.choice(COMENTARIOS) if rng.random() < 0.5 else "",
                "rasgos_detectados": rasgos_al_azar(rng),
            })
        rondas.append({
            "ronda": r,
            "instruccion": ins,
            "pedido": interpretar_reglas(ins) if ins else None,
            "variaciones": variaciones,
        })
    return {"sesion_id": f"sint_{i:02d}", "origen": "sintetico", "rondas": rondas}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--semilla", type=int, default=0)
    p.add_argument("--por-ronda", type=int, default=4)
    p.add_argument("--salida", default=str(AQUI / "registros_sinteticos"))
    a = p.parse_args()
    rng = random.Random(a.semilla)
    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    for i in range(1, a.n + 1):
        (out / f"sesion_{i:02d}.json").write_text(
            json.dumps(sesion(i, rng, a.por_ronda), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{a.n} registros en {out.resolve()}")


if __name__ == "__main__":
    main()
