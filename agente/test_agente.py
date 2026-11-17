"""Pruebas sin red:  python -m pytest -q test_agente.py   (o  python test_agente.py)"""
import copy
import json
from pathlib import Path
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
AQUI = Path(__file__).resolve().parent

from agente import explicar_ronda, interpretar, resumen_plantilla, resumir, verificar
from llms import LLMFalso

REGS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((AQUI / "registros_sinteticos").glob("*.json"))]

REG = {
    "sesion_id": "t",
    "rondas": [
        {"ronda": 1, "instruccion": None, "variaciones": [
            {"id": "v1", "decision": "aceptada", "comentario": "yo uso lentes",
             "rasgos_detectados": {"lentes": True, "barba": False, "bigote": False, "expresion": "feliz"}},
            {"id": "v2", "decision": "rechazada", "comentario": "",
             "rasgos_detectados": {"lentes": False, "barba": True, "bigote": False, "expresion": "serio"}}]},
        {"ronda": 2, "instruccion": "que sonría más", "variaciones": [
            {"id": "v3", "decision": "aceptada", "comentario": "",
             "rasgos_detectados": {"lentes": False, "barba": False, "bigote": False, "expresion": "feliz"}}]},
    ],
}

BUENO = """**Aceptadas:**
- v1 (ronda 1): la persona comentó "yo uso lentes".
- v3 (ronda 2): sin comentario; tiene expresión feliz.
**Rechazadas:**
- v2 (ronda 1): sin comentario.
**Preferencias observadas:**
- Las dos aceptadas son felices y la rechazada tenía barba.
**Cambios entre rondas:**
- En la ronda 2 pidió que sonría más y aceptó v3."""


def test_plantilla_pasa_siempre():
    for r in REGS + [REG]:
        ok, err = verificar(resumen_plantilla(r), r)
        assert ok, (r["sesion_id"], err)


def test_resumen_bueno_con_markdown():
    assert verificar(BUENO, REG) == (True, [])


def test_detecta_errores():
    casos = {
        "apartado equivocado": BUENO.replace("- v2 (ronda 1)", "- v9 (ronda 1)"),
        "ronda equivocada": BUENO.replace("v3 (ronda 2)", "v3 (ronda 1)"),
        "rasgo inventado": BUENO.replace("sin comentario; tiene expresión feliz", "tiene bigote"),
        "preferencia inventada": BUENO.replace("son felices", "tienen bigote"),
        "conteo equivocado": BUENO.replace("- Las dos aceptadas son felices y la rechazada tenía barba.",
                                           "- Expresión feliz: 1 de 2 aceptadas y 0 de 1 rechazadas."),
        "rasgo inventado en grupo": BUENO.replace("- Las dos aceptadas son felices y la rechazada tenía barba.",
                                                  "- Aceptó caras con lentes (v1, v3) y rechazó una con barba (v2)."),
        "falta apartado": BUENO.split("**Cambios")[0],
        "aceptada en rechazadas": BUENO.replace("- v2 (ronda 1): sin comentario.", "- v2 (ronda 1): sin comentario.\n- v1 (ronda 1)."),
    }
    for nombre, texto in casos.items():
        ok, err = verificar(texto, REG)
        assert not ok, nombre
        print(f"  {nombre}: {err}")


def test_sin_falsos_positivos():
    variantes = [
        BUENO.replace("**Cambios entre rondas:**\n- En la ronda 2 pidió que sonría más y aceptó v3.",
                      "Cambios entre rondas:\n- Entre la ronda 1 y la 2 pidió \"ponle lentes\" y aceptó v3 (ronda 2)."),
        BUENO.replace("- v1 (ronda 1): la persona comentó \"yo uso lentes\".", "1. v1 (ronda 1): motivo: \"yo uso lentes\"."),
        BUENO.replace("**Aceptadas:**", "## Aceptadas").replace("**Rechazadas:**", "## Rechazadas"),
        BUENO.replace("- Las dos aceptadas son felices y la rechazada tenía barba.", "- Prefiere caras sin bigote ni barba."),
        # rasgos distintos para grupos de ids distintos en la misma frase (caso real de gpt-oss-20b)
        BUENO.replace("- Las dos aceptadas son felices y la rechazada tenía barba.",
                      "- Aceptó caras con expresión feliz (v1, v3) y rechazó una con barba (v2)."),
        BUENO.replace("- Las dos aceptadas son felices y la rechazada tenía barba.",
                      "- Expresión feliz: 2 de 2 aceptadas y 0 de 1 rechazadas.\n- Con barba: 0 de 2 aceptadas y 1 de 1 rechazadas."),
    ]
    for t in variantes:
        assert verificar(t, REG) == (True, []), (t, verificar(t, REG))


def test_reintento_y_respaldo():
    malo = BUENO.replace("sin comentario; tiene expresión feliz", "tiene bigote")
    r = copy.deepcopy(REG)
    assert resumir(r, LLMFalso([BUENO])) == BUENO and r["resumen"]["intentos"] == 1
    r = copy.deepcopy(REG)
    llm = LLMFalso([malo, BUENO])
    resumir(r, llm)
    assert r["resumen"]["origen"] == "llm" and r["resumen"]["intentos"] == 2
    r = copy.deepcopy(REG)
    texto = resumir(r, LLMFalso([malo, malo, malo]))
    assert r["resumen"]["origen"] == "plantilla" and r["resumen"]["intentos"] == 3
    assert verificar(texto, r)[0]


def test_reintento_lleva_errores_al_prompt():
    vistos = []

    def f(sistema, usuario):
        vistos.append(usuario)
        return "nada"

    resumir(copy.deepcopy(REG), LLMFalso(funcion=f))
    assert len(vistos) == 3 and "errores" in vistos[1] and "Falta el apartado" in vistos[1]


def test_interpretar():
    assert interpretar("ponle lentes y que se vea más serio")["rasgos"] == {
        "lentes": True, "barba": None, "bigote": None, "expresion": "serio"}
    for t in ["que se parezca a Messi", "hazlo sexy", "hazlo más feo para reírnos de él"]:
        out = interpretar(t, LLMFalso(["{}"]))  # la lista lo bloquea antes de llamar al LLM
        assert out["permitido"] is False and out["motivo"]
    # LLM devuelve basura y luego JSON válido
    ok = '{"rasgos": {"lentes": true, "barba": null, "bigote": null, "expresion": "serio"}, "cabello": {"color": null, "largo": null}, "permitido": true, "motivo": null}'
    out = interpretar("ponle lentes y serio", LLMFalso(["no sé", "```json\n" + ok + "\n```"]))
    assert out["rasgos"]["lentes"] is True and interpretar.ultimo == {"capa": "llm", "intentos": 2}
    # segunda capa: el LLM bloquea algo que la lista no vio
    out = interpretar("que se parezca a mi profesor de física, el ingeniero Ramírez", LLMFalso(
        ['{"rasgos": {"lentes": true}, "permitido": false, "motivo": "No puedo copiar a una persona real."}']))
    assert out["permitido"] is False and out["rasgos"]["lentes"] is None
    # LLM inválido dos veces: intérprete por reglas
    out = interpretar("ponle barba", LLMFalso(["x", "y"]))
    assert out["rasgos"]["barba"] is True and interpretar.ultimo["capa"] == "reglas"


def test_cadena_pasa_al_siguiente_ante_429():
    import requests
    from llms import CadenaLLM

    def cuota_agotada(sistema, usuario):
        resp = requests.Response()
        resp.status_code = 429
        raise requests.HTTPError("429 Too Many Requests", response=resp)

    primero = LLMFalso(funcion=cuota_agotada, nombre="api:primero")
    segundo = LLMFalso([BUENO, BUENO], nombre="api:segundo")
    cadena = CadenaLLM([primero, segundo])
    r = copy.deepcopy(REG)
    assert resumir(r, cadena) == BUENO
    assert r["resumen"]["origen"] == "llm" and r["resumen"]["llm"] == "api:segundo"
    assert cadena._saltar_hasta["api:primero"] > 0  # el que falló queda en pausa
    assert cadena("s", "u") == BUENO and primero.total == {}  # no se vuelve a intentar
    # si todos fallan, resumir no se cae: plantilla
    r = copy.deepcopy(REG)
    resumir(r, CadenaLLM([LLMFalso(funcion=cuota_agotada, nombre="api:x")]))
    assert r["resumen"]["origen"] == "plantilla"


def test_explicar():
    assert explicar_ronda(REG, 1).startswith("Esta es la primera ronda")
    e = explicar_ronda(REG, 2)
    assert "v1" in e and "que sonría más" in e and "feliz" in e
    for r in REGS:
        for ronda in r["rondas"]:
            assert explicar_ronda(r, ronda["ronda"])


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
