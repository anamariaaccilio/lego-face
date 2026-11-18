"""Servidor de la Fábrica de caras.

    python app.py                 # http://127.0.0.1:8765
    LEGO_DEMO=1 python app.py     # agrega un generador simulado
    FLUX=0 python app.py          # sin FLUX.2 (solo el modelo entrenado)

El agente del equipo (../../agente) interpreta los pedidos, explica cada ronda y resume la sesión.
Sin GROQ_API_KEY trabaja con reglas y plantilla.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os
import random
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

import guardrails
from generadores import Pedido, crear_generadores

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "agente"))
from agente import explicar_ronda, interpretar, objetivo_siguiente_ronda, resumir, verificar  # noqa: E402
from llms import crear_llm  # noqa: E402

REGISTROS = AQUI / "registros"
WEB = AQUI.parent / "web" / "dist"
CARAS_POR_RONDA = 5
VIDA_SESION = 30 * 60
MOTIVOS = ["No se parece", "Expresión", "Colores", "Defecto"]

generadores = crear_generadores()
llm = crear_llm()
sesiones: dict[str, dict] = {}
lock = threading.Lock()


@asynccontextmanager
async def vida(_app):
    def cargar():  # en orden, para no juntar dos cargas pesadas en la RAM
        for g in generadores.values():
            g.preparar()
    threading.Thread(target=cargar, daemon=True).start()
    print("[agente] LLM:", getattr(llm, "nombre", None) or "ninguno (reglas y plantilla)")
    yield


app = FastAPI(title="Fábrica de caras LEGO", lifespan=vida)


# ---------- utilidades ----------

def png_dataurl(a: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def limpiar_viejas():
    limite = time.time() - VIDA_SESION
    with lock:
        for sid in [s for s, v in sesiones.items() if v["tocada"] < limite]:
            sesiones.pop(sid, None)  # la foto vive solo en memoria y se va con la sesión


def sesion(sid: str) -> dict:
    limpiar_viejas()
    s = sesiones.get(sid)
    if not s:
        raise HTTPException(404, "La sesión expiró. Empieza de nuevo.")
    s["tocada"] = time.time()
    return s


def guardar(s: dict):
    REGISTROS.mkdir(exist_ok=True)
    (REGISTROS / f"{s['registro']['sesion_id']}.json").write_text(
        json.dumps(s["registro"], ensure_ascii=False, indent=1), encoding="utf-8")


def variaciones(reg: dict) -> list[dict]:
    return [v for r in reg["rondas"] for v in r["variaciones"]]


def para_agente(reg: dict) -> dict:
    """Copia del registro sin lo que no le sirve al LLM (prompts en inglés, tiempos, semillas)."""
    limpio = copy.deepcopy(reg)
    limpio.pop("resumen", None)
    for r in limpio["rondas"]:
        r.pop("prompt", None)
        for v in r["variaciones"]:
            for k in ("seed", "ms", "rasgos_fuente", "cfg_flow1", "cfg_flow2", "cara_detectada"):
                v.pop(k, None)
    return limpio


def fusionar_ficha(base: dict, objetivo: dict | None) -> dict:
    """La ficha de la asesoría, con lo que pida el objetivo de la ronda encima."""
    ficha = copy.deepcopy(base or {})
    ficha.setdefault("rasgos", {})
    ficha.setdefault("cabello", {})
    for grupo in ("rasgos", "cabello"):
        for k, v in ((objetivo or {}).get(grupo) or {}).items():
            if v is not None:
                ficha[grupo][k] = v
    return ficha


# ---------- API ----------

@app.get("/api/estado")
def estado():
    return {
        "generadores": [g.describir() for g in generadores.values()],
        "agente": {"llm": getattr(llm, "nombre", None)},
        "motivos": MOTIVOS,
        "caras_por_ronda": CARAS_POR_RONDA,
    }


class NuevaSesion(BaseModel):
    consentimiento: bool
    modo: str = "maquina"  # "maquina" o "asesoria"


@app.post("/api/sesion")
def crear_sesion(body: NuevaSesion):
    if not body.consentimiento:
        raise HTTPException(400, "Sin consentimiento no se puede usar la foto.")
    limpiar_viejas()
    sid = uuid.uuid4().hex[:12]
    sesiones[sid] = {
        "tocada": time.time(), "foto": None, "mascaras": {}, "imagenes": {},
        "registro": {"sesion_id": f"s_{datetime.now():%Y-%m-%d}_{sid}", "origen": "real", "modo": body.modo,
                     "inicio": ahora(), "consentimiento": True, "foto_guardada": False,
                     "asesoria": {"conversacion": [], "ficha": None} if body.modo == "asesoria" else None,
                     "rondas": [], "favorita": None},
    }
    return {"sesion": sid}


@app.post("/api/sesion/{sid}/foto")
async def subir_foto(sid: str, foto: UploadFile = File(...)):
    s = sesion(sid)
    try:
        rgb = guardrails.leer_foto(await foto.read())
        guardrails.revisar_foto(rgb)
    except guardrails.FotoRechazada as e:
        return JSONResponse({"ok": False, "codigo": e.codigo, "mensaje": e.mensaje}, status_code=422)
    s["foto"] = rgb
    s["registro"]["foto_revisada"] = {"caras": 1, "hora": ahora()}
    return {"ok": True}


class Texto(BaseModel):
    texto: str
    pregunta: str | None = None


@app.post("/api/sesion/{sid}/interpretar")
def interpretar_texto(sid: str, body: Texto):
    """Pedido en texto libre -> rasgos, con el guardrail del agente."""
    s = sesion(sid)
    texto = body.texto.strip()[:300]
    r = interpretar(texto, llm)
    capa = dict(interpretar.ultimo)
    if s["registro"].get("asesoria") is not None:
        s["registro"]["asesoria"]["conversacion"].append(
            {"pregunta": body.pregunta, "texto": texto, "permitido": r["permitido"], "capa": capa.get("capa")})
    return {**r, "capa": capa.get("capa")}


class PedidoRonda(BaseModel):
    generador: str
    opciones: dict = {}
    modo: str = "nueva"            # "nueva" o "variar" (conserva la forma de las aprobadas)
    instruccion: str | None = None  # "¿qué le cambio?" antes de esta ronda


@app.post("/api/sesion/{sid}/ronda")
def ronda(sid: str, body: PedidoRonda):
    s = sesion(sid)
    reg = s["registro"]
    g = generadores.get(body.generador)
    if not g or not g.estado()["disponible"]:
        raise HTTPException(409, "Ese método no está disponible ahora.")
    if g.necesita_foto and s["foto"] is None:
        raise HTTPException(409, "Este método necesita tu foto.")
    if reg["rondas"] and any(v["decision"] is None for v in reg["rondas"][-1]["variaciones"]):
        raise HTTPException(409, "Primero decide todas las caras de la ronda anterior.")

    instruccion = (body.instruccion or "").strip()[:300] or None
    pedido = None
    if instruccion:
        if not g.acepta_texto:
            raise HTTPException(409, "Este método no entiende pedidos en texto.")
        pedido = interpretar(instruccion, llm)
        if not pedido["permitido"]:
            return JSONResponse({"ok": False, "mensaje": pedido["motivo"]}, status_code=422)

    opciones = {k: v for k, v in body.opciones.items() if k != "peinado"}
    if g.acepta_texto:
        if opciones.get("ficha") is not None and reg.get("asesoria") is not None:
            reg["asesoria"]["ficha"] = opciones["ficha"]
        base = (reg.get("asesoria") or {}).get("ficha") or opciones.get("ficha") or {}
        objetivo = objetivo_siguiente_ronda(para_agente(reg), pedido) if reg["rondas"] else pedido
        opciones["ficha"] = fusionar_ficha(base, objetivo)

    n = len(reg["rondas"]) + 1
    base_seed = random.randrange(1, 2**31 - 100)
    aprobadas = []
    if body.modo == "variar":
        if not g.conserva_forma:
            raise HTTPException(409, "Este método no puede conservar formas.")
        aprobadas = [v["id"] for v in (reg["rondas"][-1]["variaciones"] if reg["rondas"] else [])
                     if v["decision"] == "aceptada" and v["id"] in s["mascaras"]]
        if not aprobadas:
            raise HTTPException(409, "No hay caras aprobadas para variar.")

    primero = len(variaciones(reg)) + 1
    pedidos, vs = [], []
    for i in range(CARAS_POR_RONDA):
        vid = f"v{primero + i}"
        de = aprobadas[i % len(aprobadas)] if aprobadas else None
        pedidos.append(Pedido(id=vid, seed=base_seed + i, mascara=s["mascaras"][de] if de else None))
        vs.append({"id": vid, "decision": None, "comentario": "", "rasgos_detectados": {},
                   "origen": f"forma de {de}" if de else "nueva"})

    nombres = {}
    for op in g.opciones:
        v = body.opciones.get(op["id"], op.get("defecto"))
        if op["tipo"] == "elegir":
            v = next((x["nombre"] for x in op["valores"] if x["id"] == v), v)
        if v:
            nombres[op["nombre"]] = v
    r = {"ronda": n, "instruccion": instruccion, "pedido": pedido, "generador": g.nombre,
         "opciones": nombres, "inicio": ahora(), "variaciones": vs}
    peinado = body.opciones.get("peinado")
    if peinado:  # pieza de cabello de LDraw que se encajó en las 5 cabezas
        r["peinado"] = {"pieza_ldraw": peinado.get("id"), "nombre": peinado.get("nombre"), "color": peinado.get("color")}
    explicacion = explicar_ronda({"rondas": para_agente(reg)["rondas"] + [copy.deepcopy(r)]}, n)
    r["explicacion"] = explicacion

    def flujo():
        yield json.dumps({"tipo": "inicio", "ronda": n, "caras": [{"id": v["id"], "origen": v["origen"]} for v in vs],
                          "explicacion": explicacion}, ensure_ascii=False) + "\n"
        t = time.time()
        try:
            for res in g.generar(s["foto"], pedidos, opciones):
                ms = round((time.time() - t) * 1000)
                t = time.time()
                v = next(x for x in vs if x["id"] == res.id)
                datos = dict(res.datos)
                if "prompt" in datos:
                    r["prompt"] = datos.pop("prompt")
                v.update(ms=ms, **datos)
                img = png_dataurl(res.rgba)
                s["imagenes"][res.id] = img
                if res.mascara is not None:
                    s["mascaras"][res.id] = res.mascara
                yield json.dumps({"tipo": "cara", "id": res.id, "imagen": img, "origen": v["origen"], "ms": ms}) + "\n"
            reg["rondas"].append(r)
            yield json.dumps({"tipo": "fin", "ronda": n}) + "\n"
        except Exception as e:
            print("[ronda] error:", repr(e))
            yield json.dumps({"tipo": "error", "mensaje": "La máquina se trabó al fabricar. Prueba otra vez."}) + "\n"

    return StreamingResponse(flujo(), media_type="application/x-ndjson")


class Decision(BaseModel):
    id: str
    decision: str  # "aceptada" | "rechazada"
    motivos: list[str] = []
    comentario: str = ""


class Decisiones(BaseModel):
    ronda: int
    decisiones: list[Decision]
    por_paquete: bool = False


@app.post("/api/sesion/{sid}/decisiones")
def decidir(sid: str, body: Decisiones):
    s = sesion(sid)
    reg = s["registro"]
    if not reg["rondas"] or reg["rondas"][-1]["ronda"] != body.ronda:
        raise HTTPException(409, "Ronda equivocada.")
    vs = {v["id"]: v for v in reg["rondas"][-1]["variaciones"]}
    if {d.id for d in body.decisiones} != set(vs):
        raise HTTPException(400, f"Hay que decidir las {CARAS_POR_RONDA} caras.")
    for d in body.decisiones:
        if d.decision not in ("aceptada", "rechazada"):
            raise HTTPException(400, "Decisión inválida.")
        motivos = [m for m in d.motivos if m in MOTIVOS] if d.decision == "rechazada" else []
        comentario = "; ".join(x for x in (", ".join(m.lower() for m in motivos), d.comentario.strip()[:200]) if x)
        vs[d.id].update(decision=d.decision, comentario=comentario)
    reg["rondas"][-1].update(decidida=ahora(), por_paquete=body.por_paquete)
    guardar(s)
    return {"ok": True}


class PedidoResumen(BaseModel):
    favorita: str | None = None


@app.post("/api/sesion/{sid}/resumen")
def resumir_sesion(sid: str, body: PedidoResumen):
    s = sesion(sid)
    reg = s["registro"]
    if not reg["rondas"] or any(v["decision"] is None for v in variaciones(reg)):
        raise HTTPException(409, "Faltan decisiones.")
    if body.favorita:
        if next((v for v in variaciones(reg) if v["id"] == body.favorita), {}).get("decision") != "aceptada":
            raise HTTPException(400, "La favorita tiene que ser una cara aceptada.")
        reg["favorita"] = body.favorita
    t = time.time()
    limpio = para_agente(reg)
    texto = resumir(limpio, llm)
    meta = limpio["resumen"]
    ok, errores = verificar(texto, limpio)
    reg["resumen"] = {**meta, "ms": round((time.time() - t) * 1000), "hora": ahora()}
    guardar(s)
    return {"texto": texto, "origen": meta["origen"], "llm": meta.get("llm"), "intentos": meta["intentos"],
            "ms": reg["resumen"]["ms"], "verificacion": {"ok": ok, "errores": errores}}


@app.get("/api/sesion/{sid}/registro")
def registro(sid: str):
    s = sesion(sid)
    return JSONResponse(s["registro"], headers={
        "Content-Disposition": f'attachment; filename="{s["registro"]["sesion_id"]}.json"'})


@app.post("/api/sesion/{sid}/cerrar")
def cerrar(sid: str):
    with lock:
        sesiones.pop(sid, None)
    return {"ok": True}


@app.get("/api/metricas")
def metricas():
    """Agrega los registros guardados: aceptación por ronda y por método, y origen de los resúmenes."""
    regs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REGISTROS.glob("*.json"))] if REGISTROS.exists() else []
    por_ronda, por_metodo, origen = {}, {}, {}
    for reg in regs:
        for r in reg["rondas"]:
            dec = [v["decision"] for v in r["variaciones"] if v["decision"]]
            if not dec:
                continue
            for clave, tabla in ((f"ronda {r['ronda']}", por_ronda),
                                 (" · ".join([r["generador"], *r.get("opciones", {}).values()]), por_metodo)):
                a = tabla.setdefault(clave, [0, 0])
                a[0] += dec.count("aceptada")
                a[1] += len(dec)
        if reg.get("resumen"):
            o = reg["resumen"]["origen"]
            origen[o] = origen.get(o, 0) + 1
    tasa = lambda t: {k: {"aceptadas": a, "total": n, "tasa": round(a / n, 3)} for k, (a, n) in t.items()}
    return {"sesiones": len(regs), "aceptacion_por_ronda": tasa(por_ronda),
            "aceptacion_por_metodo": tasa(por_metodo), "origen_resumen": origen}


if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8765")))
