"""SUS por persona, SUS medio y tiempos por tarea, a partir de plantilla_respuestas.csv.

    python calcular_sus.py plantilla_respuestas.csv

Imprime el resumen y escribe anexo_b.md con la tabla para el informe.
"""
import csv
import statistics as st
import sys
from pathlib import Path


def sus(f: dict) -> float:
    q = [int(f[f"q{i}"]) for i in range(1, 11)]
    if any(not 1 <= x <= 5 for x in q):
        raise ValueError(f"{f['persona']}: las respuestas SUS van de 1 a 5")
    return 2.5 * sum((x - 1) if i % 2 == 0 else (5 - x) for i, x in enumerate(q))


def media(v):
    v = [x for x in v if x is not None]
    if not v:
        return "—"
    return f"{st.mean(v):.1f}" + (f" ± {st.stdev(v):.1f}" if len(v) > 1 else "")


def main():
    ruta = Path(sys.argv[1] if len(sys.argv) > 1 else "plantilla_respuestas.csv")
    filas = [f for f in csv.DictReader(open(ruta, encoding="utf-8-sig")) if f.get("persona", "").strip()]
    if not filas:
        sys.exit("La planilla no tiene personas todavía.")
    for f in filas:
        f["sus"] = sus(f)
    num = lambda f, k: float(f[k]) if f.get(k, "").strip() else None
    print(f"Personas: {len(filas)}")
    print(f"SUS medio: {media([f['sus'] for f in filas])}")
    for t in (1, 2, 3):
        hechas = sum(f.get(f"tarea{t}_sin_ayuda", "").strip() == "1" for f in filas)
        print(f"Tarea {t}: {media([num(f, f'tarea{t}_seg') for f in filas])} s, sin ayuda {hechas} de {len(filas)}")

    lineas = ["| Persona | Carrera o cargo | Fecha | Consentimiento | Método | SUS | Comentarios |", "|---|---|---|---|---|---|---|"]
    for f in filas:
        coment = " / ".join(x for x in (f.get("gusto"), f.get("confundio"), f.get("cambiaria")) if x and x.strip())
        lineas.append(f"| {f['persona']} | {f['carrera_o_cargo']} | {f['fecha']} | {f['consentimiento']} | "
                      f"{f.get('metodo', '')} | {f['sus']:.1f} | {coment} |")
    lineas.append("")
    lineas.append(f"SUS medio: {media([f['sus'] for f in filas])} (n = {len(filas)}).")
    (ruta.parent / "anexo_b.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Tabla para el Anexo B en {ruta.parent / 'anexo_b.md'}")


if __name__ == "__main__":
    main()
