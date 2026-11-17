"""Compara los LLM en resumir (con verificar) e interpretar.

    python evaluar.py --llms groq,local,ninguno
    python evaluar.py --llms groq --reales registros_reales/   # añade las sesiones de usabilidad

Salidas (carpeta resultados/):
    metricas_agente.csv      una fila por (llm, función, métrica)
    tabla_agente.md          las dos tablas para el informe
    resumenes_ciegos.csv     10 resúmenes por LLM barajados, para puntuar a ciegas de 1 a 5
    clave_ciega.csv          qué LLM escribió cada resumen (no se la muestres a los evaluadores)
    resumenes_<llm>.jsonl    todos los resúmenes con sus metadatos
"""
import argparse
import copy
import csv
import json
import random
import time
from pathlib import Path
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
AQUI = Path(__file__).resolve().parent

from agente import interpretar, resumir

CAMPOS = [("rasgos", "lentes"), ("rasgos", "barba"), ("rasgos", "bigote"), ("rasgos", "expresion"),
          ("cabello", "color"), ("cabello", "largo")]


def construir_llm(nombre: str):
    if nombre == "ninguno":
        return None
    if nombre == "local":
        from llms import cargar_local
        return cargar_local()
    from llms import LLMAPI
    return LLMAPI(nombre)


def cargar_registros(*carpetas):
    regs = []
    for c in carpetas:
        if c and Path(c).exists():
            regs += [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(c).glob("*.json"))]
    return regs


class Pausado:
    """Envuelve un LLM por API para no pasar su límite de tokens por minuto: antes de cada
    llamada espera max(pausa, 60 * tokens de la llamada anterior / tpm) segundos."""

    def __init__(self, llm, pausa: float, tpm: float):
        self.llm, self.pausa, self.tpm, self.dormido = llm, pausa, tpm, 0.0
        self.nombre = llm.nombre

    def __call__(self, *args, **kwargs):
        u = self.llm.ultimo or {}
        usados = u.get("tokens_entrada", 0) + u.get("tokens_salida", 0)
        espera = max(self.pausa, 60 * usados / self.tpm) if self.tpm else self.pausa
        time.sleep(espera)
        self.dormido += espera
        return self.llm(*args, **kwargs)


def _error_de_red(meta: dict) -> bool:
    return any(e.startswith("Error llamando al LLM") for intento in meta["errores"] for e in intento)


def _dormido(llm) -> float:
    return getattr(llm, "dormido", 0.0)


def evaluar_resumen(llm, nombre, registros, salida: Path, reintentos_red: int, espera_red: float):
    n = len(registros)
    primer = reint = plantilla_verif = plantilla_red = plantilla_sin = reejecuciones = 0
    tiempos = []
    if llm is not None:
        getattr(llm, "llm", llm).reiniciar()
    with open(salida / f"resumenes_{nombre}.jsonl", "w", encoding="utf-8") as fh:
        for reg in registros:
            for vez in range(1 + (reintentos_red if llm is not None else 0)):
                r = copy.deepcopy(reg)
                t0, d0 = time.time(), _dormido(llm)
                texto = resumir(r, llm)
                segundos = time.time() - t0 - (_dormido(llm) - d0)
                m = r["resumen"]
                if not _error_de_red(m):
                    break
                if vez < reintentos_red:  # 429 o red caída: no es un fallo del LLM, se repite
                    reejecuciones += 1
                    print(f"  {r.get('sesion_id')}: error de red/cuota, se repite en {espera_red:.0f} s", flush=True)
                    time.sleep(espera_red)
            tiempos.append(segundos)
            if m["origen"] == "plantilla":
                if m["intentos"] == 0:
                    plantilla_sin += 1
                elif _error_de_red(m):
                    plantilla_red += 1
                else:
                    plantilla_verif += 1
            elif m["intentos"] == 1:
                primer += 1
            else:
                reint += 1
            fh.write(json.dumps({"sesion_id": r.get("sesion_id"), "texto": texto, **m}, ensure_ascii=False) + "\n")
    tot = getattr(llm, "llm", llm).total if llm is not None else {}
    return {
        "pasa_primer_intento_%": 100 * primer / n,
        "necesita_reintento_%": 100 * reint / n,
        "plantilla_por_verificador_%": 100 * plantilla_verif / n,
        "plantilla_por_red_cuota_%": 100 * plantilla_red / n,
        "plantilla_sin_llm_%": 100 * plantilla_sin / n,
        "reejecuciones_por_red": reejecuciones,
        "tiempo_medio_s": sum(tiempos) / n,
        "tokens_entrada_total": tot.get("tokens_entrada", 0),
        "tokens_salida_total": tot.get("tokens_salida", 0),
        "llamadas": tot.get("llamadas", 0),
        "n_registros": n,
    }


def evaluar_interpretar(llm, csv_path, reintentos_red: int, espera_red: float):
    filas = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    aciertos = {f"{a}.{b}": 0 for a, b in CAMPOS}
    ok_permitidas = n_permitidas = ok_rechazo = n_rechazo = exactas = reglas_red = reejecuciones = 0
    detalle = []
    for f in filas:
        esp = json.loads(f["esperado_json"])
        for vez in range(1 + (reintentos_red if llm is not None else 0)):
            out = interpretar(f["instruccion"], llm)
            if "error" not in interpretar.ultimo:
                break
            if vez < reintentos_red:
                reejecuciones += 1
                print(f"  interpretar: error de red/cuota, se repite en {espera_red:.0f} s", flush=True)
                time.sleep(espera_red)
        reglas_red += "error" in interpretar.ultimo
        if int(f["debe_rechazarse"]):
            n_rechazo += 1
            ok_rechazo += (not out["permitido"]) and bool(out["motivo"])
        else:
            n_permitidas += 1
            ok_permitidas += out["permitido"]
            todo = True
            for a, b in CAMPOS:
                bien = out[a][b] == esp[a][b]
                aciertos[f"{a}.{b}"] += bien
                todo &= bien
            exactas += todo and out["permitido"]
        detalle.append({"instruccion": f["instruccion"], "salida": out, **interpretar.ultimo})
    res = {f"acierto_{k}_%": 100 * v / n_permitidas for k, v in aciertos.items()}
    res["acierto_exacto_permitidas_%"] = 100 * exactas / n_permitidas
    res["no_bloquea_permitidas_%"] = 100 * ok_permitidas / n_permitidas
    res["rechaza_prohibidas_%"] = 100 * ok_rechazo / n_rechazo
    res["reglas_por_red_cuota"] = reglas_red
    res["reejecuciones_por_red"] = reejecuciones
    return res, detalle


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--llms", default="ninguno", help="lista separada por comas: groq, local, ninguno")
    p.add_argument("--sinteticos", default=str(AQUI / "registros_sinteticos"))
    p.add_argument("--reales", default=str(AQUI / "registros_reales"))
    p.add_argument("--instrucciones", default=str(AQUI / "instrucciones_prueba.csv"))
    p.add_argument("--n-ciego", type=int, default=10)
    p.add_argument("--salida", default=str(AQUI / "resultados"))
    p.add_argument("--pausa", type=float, default=3, help="segundos mínimos entre llamadas a la API")
    p.add_argument("--tpm", type=float, default=8000, help="tokens por minuto de la API (0 = sin límite)")
    p.add_argument("--reintentos-red", type=int, default=5, help="veces que se repite un caso con error de red/cuota")
    p.add_argument("--espera-red", type=float, default=60, help="segundos antes de repetir un caso con error de red/cuota")
    a = p.parse_args()
    salida = Path(a.salida)
    salida.mkdir(exist_ok=True)
    registros = cargar_registros(a.sinteticos, a.reales)

    filas, tabla_res, tabla_int, ciegos = [], {}, {}, []
    for nombre in a.llms.split(","):
        nombre = nombre.strip()
        llm = construir_llm(nombre)
        if hasattr(llm, "base_url"):  # LLM por API: respetar su límite de tokens por minuto
            llm = Pausado(llm, a.pausa, a.tpm)
        etiqueta = getattr(llm, "nombre", "sin LLM (plantilla/reglas)")
        print(f"== {etiqueta}")
        r = evaluar_resumen(llm, nombre, registros, salida, a.reintentos_red, a.espera_red)
        i, det = evaluar_interpretar(llm, a.instrucciones, a.reintentos_red, a.espera_red)
        json.dump(det, open(salida / f"interpretar_{nombre}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        tabla_res[etiqueta], tabla_int[etiqueta] = r, i
        filas += [{"llm": etiqueta, "funcion": "resumir", "metrica": k, "valor": round(v, 3)} for k, v in r.items()]
        filas += [{"llm": etiqueta, "funcion": "interpretar", "metrica": k, "valor": round(v, 3)} for k, v in i.items()]
        if llm is not None:  # muestra ciega: solo resúmenes escritos por el LLM
            lineas = [json.loads(l) for l in open(salida / f"resumenes_{nombre}.jsonl", encoding="utf-8")]
            lineas = [l for l in lineas if l["origen"] == "llm"] or lineas
            for l in random.Random(1).sample(lineas, min(a.n_ciego, len(lineas))):
                ciegos.append({"llm": etiqueta, "sesion_id": l["sesion_id"], "texto": l["texto"]})
        print(json.dumps({**r, **i}, indent=1, ensure_ascii=False))

    with open(salida / "metricas_agente.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["llm", "funcion", "metrica", "valor"])
        w.writeheader()
        w.writerows(filas)

    if ciegos:
        random.Random(7).shuffle(ciegos)
        with open(salida / "resumenes_ciegos.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["codigo", "texto", "claridad_evaluador_1", "claridad_evaluador_2"])
            for k, c in enumerate(ciegos, 1):
                w.writerow([f"R{k:02d}", c["texto"], "", ""])
        with open(salida / "clave_ciega.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["codigo", "llm", "sesion_id"])
            for k, c in enumerate(ciegos, 1):
                w.writerow([f"R{k:02d}", c["llm"], c["sesion_id"]])

    def tabla(d, titulo):
        if not d:
            return ""
        cols = list(next(iter(d.values())).keys())
        s = f"### {titulo}\n\n| Métrica | " + " | ".join(d) + " |\n|---|" + "---|" * len(d) + "\n"
        for c in cols:
            s += f"| {c} | " + " | ".join(f"{d[k][c]:.1f}" if isinstance(d[k][c], float) else str(d[k][c]) for k in d) + " |\n"
        return s + "\n"

    (salida / "tabla_agente.md").write_text(
        tabla(tabla_res, f"Resumir + verificar ({len(registros)} sesiones)")
        + tabla(tabla_int, "Interpretar (40 instrucciones, 10 prohibidas)"), encoding="utf-8")
    print(f"Listo: {salida.resolve()}")


if __name__ == "__main__":
    main()
