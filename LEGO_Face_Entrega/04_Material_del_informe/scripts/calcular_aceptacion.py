"""Aceptación por ronda, por método y por tipo de ronda, desde los registros reales de la interfaz.

    python calcular_aceptacion.py <carpeta_registros> [--salida aceptacion]

Lee los JSON que guarda interfaz/servidor/registros/ (uno por sesión). Lo mismo que /api/metricas,
pero sin servidor y con más cortes. Escribe aceptacion.csv y aceptacion.md.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("registros")
    ap.add_argument("--salida", default="aceptacion")
    a = ap.parse_args()
    regs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(a.registros).glob("*.json"))]
    if not regs:
        raise SystemExit("No hay registros en esa carpeta.")
    tablas = {"ronda": defaultdict(lambda: [0, 0]), "metodo": defaultdict(lambda: [0, 0]),
              "tipo_de_ronda": defaultdict(lambda: [0, 0])}
    resumenes = defaultdict(int)
    comentadas = total = 0
    for reg in regs:
        for r in reg["rondas"]:
            vs = [v for v in r["variaciones"] if v.get("decision")]
            if not vs:
                continue
            ac = sum(v["decision"] == "aceptada" for v in vs)
            tipo = ("variar" if any(str(v.get("origen", "")).startswith("forma de") for v in vs)
                    else "con pedido escrito" if r.get("instruccion") else "nueva")
            for clave, t in (("ronda", f"ronda {r['ronda']}"), ("metodo", r.get("generador", "?")), ("tipo_de_ronda", tipo)):
                tablas[clave][t][0] += ac
                tablas[clave][t][1] += len(vs)
            comentadas += sum(bool(v.get("comentario")) for v in vs)
            total += len(vs)
        if reg.get("resumen"):
            resumenes[reg["resumen"]["origen"]] += 1

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    filas = [{"corte": c, "grupo": g, "aceptadas": x, "total": n, "tasa": round(x / n, 3)}
             for c, t in tablas.items() for g, (x, n) in sorted(t.items())]
    with open(salida / "aceptacion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    md = [f"Sesiones: {len(regs)} · caras decididas: {total} · con comentario: {comentadas}", "",
          "| Corte | Grupo | Aceptadas | Total | Tasa |", "|---|---|---|---|---|"]
    md += [f"| {f['corte']} | {f['grupo']} | {f['aceptadas']} | {f['total']} | {f['tasa']:.0%} |" for f in filas]
    md += ["", "Origen de los resúmenes: " + (", ".join(f"{k} {v}" for k, v in resumenes.items()) or "ninguno")]
    (salida / "aceptacion.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
