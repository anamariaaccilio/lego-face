"""
Agente LLM de LEGO Face.

    interpretar(instruccion, llm)    pedido en texto libre a rasgos, con guardrail
    resumir(registro, llm)           resumen de la sesión, verificado contra el registro
    verificar(texto, registro)       (ok, errores) del resumen
    explicar_ronda(registro, ronda)  una o dos frases sobre por qué la ronda se ve así

`llm` es cualquier función llm(sistema, usuario, temperatura, max_tokens) que devuelve
texto (ver llms.py). Con llm=None, resumir usa la plantilla e interpretar usa reglas.
El formato del registro está en README.md.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Callable, Literal, Optional

from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Vocabulario de rasgos y cabello que usan el generador, la interfaz y el agente.
# ---------------------------------------------------------------------------
EXPRESIONES = ("feliz", "serio", "sorprendido", "enojado")
COLORES_CABELLO = ("negro", "castaño", "rubio", "pelirrojo", "gris", "blanco")
LARGOS_CABELLO = ("corto", "medio", "largo")
RASGOS_BOOL = ("lentes", "barba", "bigote")
# para escribir "expresión seria" en los textos
FEMENINO = {"feliz": "feliz", "serio": "seria", "sorprendido": "sorprendida", "enojado": "enojada"}

LLM = Callable[..., str]

# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return _sin_tildes((s or "").lower())


# Patrones sobre texto normalizado (minúsculas, sin tildes)
PATRON_RASGO = {
    "lentes": r"\b(lentes?|anteojos|gafas|lentitos)\b",
    "barba": r"\b(barbas?|barbudo|barbita)\b",
    "bigote": r"\b(bigotes?|bigotudo)\b",
}
PATRON_EXPRESION = {
    "feliz": r"\b(feliz|felices|sonrient\w*|sonrisa\w*|sonria|alegre\w*|content[oa]s?|se\s+ria|riendo|risuen[oa])\b",
    "serio": r"\b(seri[oa]s?|seriedad)\b",
    "sorprendido": r"\b(sorprendid[oa]s?|sorpresa)\b",
    "enojado": r"\b(enojad[oa]s?|enfadad[oa]s?|furios[oa]s?|brav[oa]s?|molest[oa]s?)\b",
}
PATRON_ID = re.compile(r"\bv(\d+)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Acceso al registro
# ---------------------------------------------------------------------------


def _variaciones(registro: dict) -> list[dict]:
    """Lista plana de variaciones con su número de ronda añadido."""
    salida = []
    for r in registro.get("rondas", []):
        for v in r.get("variaciones", []):
            item = dict(v)
            item["ronda"] = r.get("ronda")
            salida.append(item)
    return salida


def _por_id(registro: dict) -> dict[str, dict]:
    return {str(v["id"]).lower(): v for v in _variaciones(registro)}


def _tiene_rasgo(v: dict, rasgo: str) -> bool:
    return bool((v.get("rasgos_detectados") or {}).get(rasgo))


def _expresion(v: dict) -> Optional[str]:
    return (v.get("rasgos_detectados") or {}).get("expresion")


# ===========================================================================
# 1. RESUMEN DE PLANTILLA (correcto por construcción)
# ===========================================================================

APARTADOS = ("Aceptadas", "Rechazadas", "Preferencias observadas", "Cambios entre rondas")


def _motivo(v: dict) -> str:
    c = (v.get("comentario") or "").strip()
    return f'comentario "{c}"' if c else "sin comentario"


def resumen_plantilla(registro: dict) -> str:
    vs = _variaciones(registro)
    acep = [v for v in vs if v.get("decision") == "aceptada"]
    rech = [v for v in vs if v.get("decision") == "rechazada"]
    lineas = ["Aceptadas:"]
    lineas += [f"- {v['id']} (ronda {v['ronda']}): {_motivo(v)}." for v in acep] or ["- Ninguna."]
    lineas.append("Rechazadas:")
    lineas += [f"- {v['id']} (ronda {v['ronda']}): {_motivo(v)}." for v in rech] or ["- Ninguna."]

    lineas.append("Preferencias observadas:")
    prefs = []
    for rasgo in RASGOS_BOOL:
        a = sum(_tiene_rasgo(v, rasgo) for v in acep)
        r = sum(_tiene_rasgo(v, rasgo) for v in rech)
        if a or r:
            prefs.append(f"- Con {rasgo}: {a} de {len(acep)} aceptadas y {r} de {len(rech)} rechazadas.")
    for e in EXPRESIONES:
        a = sum(_expresion(v) == e for v in acep)
        r = sum(_expresion(v) == e for v in rech)
        if a or r:
            prefs.append(f"- Expresión {FEMENINO.get(e, e)}: {a} de {len(acep)} aceptadas y {r} de {len(rech)} rechazadas.")
    lineas += prefs or ["- No hay rasgos detectados para comparar."]

    lineas.append("Cambios entre rondas:")
    rondas = registro.get("rondas", [])
    if len(rondas) < 2:
        lineas.append("- Solo hubo una ronda.")
    for ant, sig in zip(rondas, rondas[1:]):
        na = sum(v.get("decision") == "aceptada" for v in ant.get("variaciones", []))
        ns = sum(v.get("decision") == "aceptada" for v in sig.get("variaciones", []))
        ins = (sig.get("instruccion") or "").strip()
        pedido = f'pediste "{ins}"' if ins else "no escribiste instrucción"
        lineas.append(
            f"- De la ronda {ant['ronda']} a la {sig['ronda']}: {pedido}; aceptaste "
            f"{na} de {len(ant.get('variaciones', []))} y luego {ns} de {len(sig.get('variaciones', []))}."
        )
    return "\n".join(lineas)


# ===========================================================================
# 2. VERIFICADOR
# ===========================================================================

_PATRON_APARTADO = re.compile(
    r"^\s*[#*\-\s]*(aceptadas|rechazadas|preferencias observadas|cambios entre rondas)\s*[*:]*\s*:?\s*(.*)$",
    re.IGNORECASE,
)


def separar_apartados(texto: str) -> dict[str, str]:
    """Divide el resumen en sus cuatro apartados (clave = nombre en minúsculas sin tildes)."""
    apartados: dict[str, list[str]] = {}
    actual = None
    for linea in (texto or "").splitlines():
        m = _PATRON_APARTADO.match(_norm(linea))
        if m:
            actual = m.group(1)
            apartados.setdefault(actual, [])
            if m.group(2).strip():
                apartados[actual].append(linea.split(":", 1)[-1])
        elif actual:
            apartados[actual].append(linea)
    return {k: "\n".join(v) for k, v in apartados.items()}


def _ids(texto: str) -> set[str]:
    return {f"v{n}" for n in PATRON_ID.findall(texto or "")}


def _frases(texto: str) -> list[str]:
    # Partimos por línea y por ; o . seguido de espacio (no rompe "v1.").
    partes = []
    for linea in texto.splitlines():
        partes += re.split(r";|\.\s|\.$", linea)
    return [p for p in partes if p.strip()]


def _mencion_positiva(frase_norm: str, patron: str) -> bool:
    """True si la frase menciona el rasgo sin negarlo justo antes ('sin lentes', 'ni bigote')."""
    for m in re.finditer(patron, frase_norm):
        previas = frase_norm[: m.start()].split()[-2:]
        if not any(p in ("sin", "no", "ni") for p in previas):
            return True
    return False


_COMILLAS = re.compile(r'"[^"]*"|“[^”]*”|«[^»]*»')


def _rasgos_mencionados(frase: str) -> list[tuple[str, str]]:
    """[(tipo, valor)] p.ej. [('bool','lentes'), ('expresion','serio')].
    Lo que está entre comillas es una cita (comentario o pedido) y no se cuenta."""
    f = _norm(_COMILLAS.sub(" ", frase))
    out = [("bool", r) for r, p in PATRON_RASGO.items() if _mencion_positiva(f, p)]
    out += [("expresion", e) for e, p in PATRON_EXPRESION.items() if _mencion_positiva(f, p)]
    return out


_GRUPO_IDS = re.compile(r"\(\s*v\d+(?:\s*(?:,|y)\s*v\d+)*\s*\)", re.IGNORECASE)


def _segmentos(frase: str) -> list[str]:
    """Si la frase trae grupos de ids entre paréntesis, la corta después de cada grupo
    para que cada rasgo se atribuya solo a los ids de su paréntesis:
    'feliz (v7, v8) y una sorprendida (v5)' da ['feliz (v7, v8)', ' y una sorprendida (v5)'].
    Un resto final sin ids se une al segmento anterior. Sin paréntesis: la frase entera."""
    cortes = [m.end() for m in _GRUPO_IDS.finditer(frase)]
    if not cortes:
        return [frase]
    segs, ini = [], 0
    for c in cortes:
        segs.append(frase[ini:c])
        ini = c
    resto = frase[ini:]
    if resto.strip():
        if _ids(resto):
            segs.append(resto)
        else:
            segs[-1] += resto
    return segs


def _respaldado(v: dict, tipo: str, valor: str) -> bool:
    comentario = _norm(v.get("comentario", ""))
    if tipo == "bool":
        return _tiene_rasgo(v, valor) or re.search(PATRON_RASGO[valor], comentario) is not None
    return _expresion(v) == valor or re.search(PATRON_EXPRESION[valor], comentario) is not None


def verificar(texto: str, registro: dict) -> tuple[bool, list[str]]:
    """Comprueba que el resumen no contradiga ni invente nada del registro."""
    errores: list[str] = []
    vs = _por_id(registro)
    apartados = separar_apartados(texto)

    for nombre in APARTADOS:
        if _norm(nombre) not in apartados:
            errores.append(f'Falta el apartado "{nombre}".')

    en_acep = _ids(apartados.get("aceptadas", ""))
    en_rech = _ids(apartados.get("rechazadas", ""))

    # 1) ids inventados
    for i in sorted(_ids(texto) - set(vs), key=lambda s: int(s[1:])):
        errores.append(f"{i} no existe en el registro.")

    # 2) cada variación en su apartado y en ninguno equivocado
    for i, v in vs.items():
        d = v.get("decision")
        if d == "aceptada":
            if i not in en_acep:
                errores.append(f"{i} (ronda {v['ronda']}) fue aceptada y no aparece en Aceptadas.")
            if i in en_rech:
                errores.append(f"{i} fue aceptada pero aparece en Rechazadas.")
        elif d == "rechazada":
            if i not in en_rech:
                errores.append(f"{i} (ronda {v['ronda']}) fue rechazada y no aparece en Rechazadas.")
            if i in en_acep:
                errores.append(f"{i} fue rechazada pero aparece en Aceptadas.")

    # 3) ronda correcta: "v3 (ronda 2)" / "v3, ronda 2" / "v3 de la ronda 2"
    for m in re.finditer(r"\bv(\d+)\b\W{0,3}(?:de la\s+)?ronda\s*(\d+)", _norm(texto)):
        i, ronda = f"v{m.group(1)}", int(m.group(2))
        if i in vs and vs[i]["ronda"] != ronda:
            errores.append(f"{i} es de la ronda {vs[i]['ronda']}, no de la ronda {ronda}.")

    pedidos = " ".join(_norm(r.get("instruccion") or "") for r in registro.get("rondas", []))

    # 4) rasgos: si una frase atribuye lentes/barba/bigote/expresión a una variación,
    #    tiene que estar en sus rasgos_detectados o en su comentario.
    for nombre, cuerpo in apartados.items():
        for frase in (s for f in _frases(cuerpo) for s in _segmentos(f)):
            ids_frase = [i for i in _ids(frase) if i in vs]
            rasgos = _rasgos_mencionados(frase)
            if nombre == "cambios entre rondas":  # ahí se habla de lo que pidió, no de lo que tenía
                rasgos = [(t, v) for t, v in rasgos
                          if not re.search((PATRON_RASGO if t == "bool" else PATRON_EXPRESION)[v], pedidos)]
            if not rasgos:
                continue
            if ids_frase:
                for i in ids_frase:
                    for tipo, valor in rasgos:
                        if not _respaldado(vs[i], tipo, valor):
                            errores.append(
                                f'{i} se describe con "{valor}" pero ese rasgo no está en sus '
                                f"rasgos_detectados ni en su comentario."
                            )
            elif nombre == "preferencias observadas":
                # preferencia general: el rasgo tiene que aparecer en alguna variación
                for tipo, valor in rasgos:
                    if not any(_respaldado(v, tipo, valor) for v in vs.values()):
                        errores.append(
                            f'Preferencias menciona "{valor}" pero ninguna variación lo tiene '
                            f"ni lo comenta."
                        )
    # 5) conteos en Preferencias: "Con lentes: 3 de 5 aceptadas y 1 de 4 rechazadas"
    #    (solo si la línea habla de un único rasgo; se cuenta sobre rasgos_detectados)
    grupos = {"aceptad": [v for v in vs.values() if v.get("decision") == "aceptada"],
              "rechazad": [v for v in vs.values() if v.get("decision") == "rechazada"]}
    for linea in apartados.get("preferencias observadas", "").splitlines():
        rasgos = _rasgos_mencionados(linea)
        if len(rasgos) != 1:
            continue
        tipo, valor = rasgos[0]
        for m in re.finditer(r"(\d+)\s+de\s+(\d+)\s+(aceptad|rechazad)", _norm(linea)):
            grupo = grupos[m.group(3)]
            real = sum((_tiene_rasgo(v, valor) if tipo == "bool" else _expresion(v) == valor) for v in grupo)
            if (int(m.group(1)), int(m.group(2))) != (real, len(grupo)):
                errores.append(
                    f'Preferencias dice "{valor}: {m.group(1)} de {m.group(2)} {m.group(3)}as" pero en el '
                    f"registro son {real} de {len(grupo)}."
                )
    errores = list(dict.fromkeys(errores))  # sin duplicados, mismo orden
    return (not errores, errores)


# ===========================================================================
# 3. RESUMIR (LLM, verificador, reintentos y plantilla)
# ===========================================================================

PROMPT_RESUMEN = """Eres el asistente de una app que convierte fotos de personas en caras de LEGO.
La persona vio varias rondas de variaciones y aceptó o rechazó cada una. Vas a recibir
el registro completo de la sesión en JSON y debes escribir un resumen en español.

REGLAS (obligatorias):
1. Afirma solo lo que está en el registro. No inventes rasgos, decisiones ni rondas.
2. Nombra cada variación por su id y su ronda, así: v3 (ronda 2).
3. No inventes motivos. El motivo de una decisión es solo el "comentario" de esa
   variación. Si el comentario está vacío, escribe "sin comentario".
4. Un rasgo (lentes, barba, bigote, expresión) solo se atribuye a una variación si
   está en sus "rasgos_detectados" o en su comentario.
5. Cada variación aceptada va SOLO en Aceptadas y cada rechazada SOLO en Rechazadas.

FORMATO (exactamente estos cuatro apartados, en este orden, sin texto antes ni después):
Aceptadas:
- vN (ronda R): motivo.
Rechazadas:
- vN (ronda R): motivo.
Preferencias observadas:
- Con lentes: A de N aceptadas y R de M rechazadas.
- Expresión seria: A de N aceptadas y R de M rechazadas.
  (una línea por rasgo, máximo 5 líneas. Cuenta sobre TODA la sesión, sumando todas
  las rondas: N = total de aceptadas, M = total de rechazadas, A y R = cuántas de ellas
  tienen ese rasgo en rasgos_detectados. Aquí NO listes ids)
Cambios entre rondas:
- De la ronda 1 a la 2: pidió "...", y cómo cambiaron sus decisiones (una línea por par
  de rondas; si hubo una sola ronda, dilo)

Sé breve: frases cortas, sin introducción ni conclusión; todo debe caber en 300 palabras.
Si un apartado no tiene elementos escribe "- Ninguna."."""


def _registro_para_llm(registro: dict) -> str:
    limpio = {k: v for k, v in registro.items() if k not in ("resumen",)}
    return json.dumps(limpio, ensure_ascii=False, indent=1)


def resumir(registro: dict, llm: Optional[LLM] = None, max_reintentos: int = 2) -> str:
    """Devuelve el resumen y deja en registro['resumen'] cómo se obtuvo.

    registro['resumen'] = {texto, origen: 'llm'|'plantilla', intentos, errores, llm}
    """
    meta = {"origen": "plantilla", "intentos": 0, "errores": [], "llm": getattr(llm, "nombre", None)}
    if llm is not None:
        usuario_base = "Registro de la sesión:\n" + _registro_para_llm(registro)
        usuario = usuario_base
        for intento in range(1 + max_reintentos):
            meta["intentos"] = intento + 1
            try:
                texto = llm(PROMPT_RESUMEN, usuario, temperatura=0.0, max_tokens=400).strip()
                meta["llm"] = getattr(llm, "ultimo_nombre", None) or meta["llm"]  # en una cadena: quién respondió
            except Exception as e:  # red caída o cuota: plantilla
                meta["errores"].append([f"Error llamando al LLM: {e}"])
                break
            ok, errores = verificar(texto, registro)
            meta["errores"].append(errores)
            if ok:
                meta["origen"] = "llm"
                registro["resumen"] = {"texto": texto, **meta}
                return texto
            usuario = (
                usuario_base
                + "\n\nTu resumen anterior fue:\n"
                + texto
                + "\n\nEl verificador encontró estos errores. Corrígelos y vuelve a escribir el resumen completo:\n"
                + "\n".join(f"- {e}" for e in errores)
            )
    texto = resumen_plantilla(registro)
    registro["resumen"] = {"texto": texto, **meta}
    return texto


# ===========================================================================
# 4. INTERPRETAR con guardrail en dos capas
# ===========================================================================


class Rasgos(BaseModel):
    lentes: Optional[bool] = None
    barba: Optional[bool] = None
    bigote: Optional[bool] = None
    expresion: Optional[Literal[EXPRESIONES]] = None  # type: ignore[valid-type]


class Cabello(BaseModel):
    color: Optional[Literal[COLORES_CABELLO]] = None  # type: ignore[valid-type]
    largo: Optional[Literal[LARGOS_CABELLO]] = None  # type: ignore[valid-type]


class Interpretacion(BaseModel):
    rasgos: Rasgos = Rasgos()
    cabello: Cabello = Cabello()
    permitido: bool = True
    motivo: Optional[str] = None


MOTIVOS = {
    "sexual": "No puedo hacer cambios de contenido sexual. Prueba pidiendo rasgos como lentes, barba, bigote, expresión o cabello.",
    "ofensivo": "No puedo generar contenido ofensivo. Prueba pidiendo rasgos como lentes, barba, bigote, expresión o cabello.",
    "persona_real": "No puedo hacer que la cara se parezca a una persona real específica. Describe los rasgos que quieres (lentes, barba, expresión, cabello).",
    "burla": "No puedo exagerar rasgos para burlarse de alguien. Puedo cambiar lentes, barba, bigote, expresión o cabello.",
}

# Capa 1: lista de palabras/patrones (texto normalizado, sin tildes)
BLOQUEO = {
    "sexual": [
        r"\bsex\w*", r"\bdesnud\w*", r"\bporno\w*", r"\berotic\w*", r"\bsensual\w*",
        r"\bcachond\w*", r"\bprovocativ\w*", r"\bxxx\b", r"\bseno\w*", r"\btetas?\b", r"\bnalg\w*",
    ],
    "ofensivo": [
        r"\bput[oa]s?\b", r"\bmierd\w*", r"\bcabr[oó]n\w*", r"\bmaric\w*", r"\bnazi\w*", r"\b(e?svastica|suastica)\w*",
        r"\bsimio\w*", r"\bmono\s+(negro|asqueroso)", r"\bterrorista\w*", r"\bestupid\w*", r"\bimbecil\w*",
        r"\bidiota\w*", r"\bretrasad\w*", r"\bmongol\w*", r"\bindio\s+feo", r"\bcholo\w*",
    ],
    "burla": [
        r"\bburl\w*", r"\bridicul\w*", r"\bhazl[oe]\s+(mas\s+)?fe[oa]", r"\bmas\s+fe[oa]\b",
        r"\bnarizon\w*", r"\bgordo\s+asqueroso", r"\borejon\w*", r"\bdientudo\w*", r"\bcara\s+de\s+tonto",
        r"\breirse\s+de\b", r"\bse\s+rian\b", r"\bpara\s+molestar\s+a\b", r"\bexager\w*\s+(su|la|el)\s+(nariz|orejas|dientes|papada)",
    ],
    "persona_real": [
        r"\bparezca\s+a\s+[a-z]", r"\bparecid[oa]\s+a\s+[a-z]", r"\bigualit[oa]\s+a\b",
        r"\bidentic[oa]\s+a\b", r"\bversion\s+lego\s+de\b",
        r"\b(messi|cristiano|ronaldo|shakira|trump|biden|obama|putin|bad\s*bunny|taylor\s+swift|"
        r"elon\s+musk|musk|maduro|boluarte|keiko|fujimori|guerrero|cueva|hitler|papa\s+francisco|"
        r"brad\s+pitt|beyonce|rosalia|karol\s+g|mbappe|neymar|zuckerberg)\b",
    ],
}
# frases que no son de una persona real aunque contengan "parezca a"
_EXCEPCION_PERSONA = re.compile(r"(parezca|parecid[oa])\s+a\s+(la|las|los|el|lo|una?|mi|mis|v\d+)\b")


def guardrail_lista(instruccion: str) -> Optional[str]:
    """Capa 1. Devuelve la categoría bloqueada o None."""
    t = _norm(instruccion)
    for categoria, patrones in BLOQUEO.items():
        for p in patrones:
            if re.search(p, t):
                if categoria == "persona_real" and p.startswith((r"\bparezca", r"\bparecid")) and _EXCEPCION_PERSONA.search(t):
                    continue
                return categoria
    return None


def interpretar_reglas(instruccion: str) -> dict:
    """Intérprete sin LLM (respaldo y línea base para la evaluación)."""
    t = _norm(instruccion)
    r = Interpretacion()
    neg = r"(sin|quita\w*|saca\w*|elimina\w*|borra\w*|no\s+(le\s+)?(pongas|quiero|tenga))\s+(\w+\s+){0,2}"
    for rasgo, p in PATRON_RASGO.items():
        if re.search(neg + p.replace(r"\b(", "(", 1), t):
            setattr(r.rasgos, rasgo, False)
        elif re.search(p, t):
            setattr(r.rasgos, rasgo, True)
    for e, p in PATRON_EXPRESION.items():
        if re.search(p, t) and not re.search(r"\bno\s+(se\s+vea\s+|este\s+)?(tan\s+)?" + p.replace(r"\b(", "(", 1), t):
            r.rasgos.expresion = e
            break
    # cabello
    hay_pelo = re.search(r"\b(pelo|cabello|melena|canas|canoso|rubi[oa]|pelirroj[oa]|rapad[oa])\b", t)
    if hay_pelo:
        colores = {
            "negro": r"\b(negro|oscuro)\b", "castaño": r"\b(castan[oa]|marron|cafe)\b",
            "rubio": r"\b(rubi[oa]|amarillo|dorado)\b", "pelirrojo": r"\b(pelirroj[oa]|rojo|naranja|colorad[oa])\b",
            "gris": r"\b(gris|canos[oa]|canas)\b", "blanco": r"\b(blanco|platinado)\b",
        }
        for c, p in colores.items():
            if re.search(p, t):
                r.cabello.color = c
                break
        if re.search(r"\b(largo|larga|melena)\b", t):
            r.cabello.largo = "largo"
        elif re.search(r"\b(corto|corta|rapad[oa])\b", t):
            r.cabello.largo = "corto"
        elif re.search(r"\b(medio|mediano|media\s+melena)\b", t):
            r.cabello.largo = "medio"
    return r.model_dump()


PROMPT_INTERPRETAR = f"""Eres el intérprete de instrucciones de una app que genera caras de LEGO.
La persona escribe en español qué quiere cambiar. Responde SOLO con un objeto JSON,
sin texto adicional y sin ```.

Esquema:
{{"rasgos": {{"lentes": true|false|null, "barba": true|false|null, "bigote": true|false|null,
             "expresion": {" | ".join(f'"{e}"' for e in EXPRESIONES)} | null}},
 "cabello": {{"color": {" | ".join(f'"{c}"' for c in COLORES_CABELLO)} | null,
             "largo": {" | ".join(f'"{l}"' for l in LARGOS_CABELLO)} | null}},
 "permitido": true|false,
 "motivo": null | "texto corto para mostrar a la persona"}}

Reglas:
- Deja en null todo lo que la persona NO mencionó. true = ponerlo, false = quitarlo.
- "más serio", "que no sonría" -> expresion "serio"; "sonriente", "contento" -> "feliz".
- permitido = false si el pedido es sexual u ofensivo, si pide parecerse a una persona
  real específica (famosos, políticos, conocidos con nombre) o si busca burlarse de
  rasgos de alguien. En ese caso pon todos los rasgos en null y explica en "motivo",
  en una frase amable, qué no se puede hacer y qué sí puede pedir.
- Si permitido = true, motivo = null.

Ejemplo: "ponle lentes y que se vea más serio" ->
{{"rasgos": {{"lentes": true, "barba": null, "bigote": null, "expresion": "serio"}}, "cabello": {{"color": null, "largo": null}}, "permitido": true, "motivo": null}}"""


def _extraer_json(texto: str) -> str:
    texto = re.sub(r"```(json)?", "", texto or "")
    ini, fin = texto.find("{"), texto.rfind("}")
    return texto[ini : fin + 1] if ini >= 0 and fin > ini else texto


def interpretar(instruccion: str, llm: Optional[LLM] = None) -> dict:
    """Convierte el pedido en un dict con rasgos, cabello, permitido y motivo.

    Deja en interpretar.ultimo = {'capa': 'lista'|'llm'|'reglas', 'intentos': n}
    """
    vacio = Interpretacion().model_dump()
    if not (instruccion or "").strip():
        interpretar.ultimo = {"capa": "vacio", "intentos": 0}
        return vacio

    # Capa 1: lista de bloqueo
    cat = guardrail_lista(instruccion)
    if cat:
        interpretar.ultimo = {"capa": "lista", "categoria": cat, "intentos": 0}
        return {**vacio, "permitido": False, "motivo": MOTIVOS[cat]}

    if llm is None:
        interpretar.ultimo = {"capa": "reglas", "intentos": 0}
        return interpretar_reglas(instruccion)

    # Capa 2: el LLM interpreta y decide
    usuario = f'Instrucción: "{instruccion}"'
    for intento in range(2):  # 1 intento + 1 reintento
        try:
            crudo = llm(PROMPT_INTERPRETAR, usuario, temperatura=0.0, max_tokens=200)
            res = Interpretacion.model_validate_json(_extraer_json(crudo))
        except ValidationError as e:
            usuario = (
                f'Instrucción: "{instruccion}"\n\nTu respuesta anterior no era JSON válido para el '
                f"esquema ({e.errors()[0]['msg']}). Responde solo con el JSON."
            )
            continue
        except Exception as e:  # red o cuota: intérprete por reglas
            interpretar.ultimo = {"capa": "reglas", "intentos": intento + 1, "error": str(e)}
            return interpretar_reglas(instruccion)
        if not res.permitido:
            res = Interpretacion(permitido=False, motivo=res.motivo or MOTIVOS["ofensivo"])
        else:
            res.motivo = None
        interpretar.ultimo = {"capa": "llm", "intentos": intento + 1}
        return res.model_dump()

    interpretar.ultimo = {"capa": "reglas", "intentos": 2}
    return interpretar_reglas(instruccion)


interpretar.ultimo = {}

# ===========================================================================
# 5. EXPLICACIÓN POR RONDA
# ===========================================================================


def _rasgos_comunes(vs: list[dict], minimo: float = 0.5) -> list[str]:
    """Rasgos presentes en más de `minimo` de las variaciones (en orden fijo)."""
    if not vs:
        return []
    out = [r for r in RASGOS_BOOL if sum(_tiene_rasgo(v, r) for v in vs) / len(vs) > minimo]
    exps = [_expresion(v) for v in vs if _expresion(v)]
    for e in EXPRESIONES:
        if exps and exps.count(e) / len(vs) > minimo:
            out.append(f"expresión {e}")
    return out


def objetivo_siguiente_ronda(registro: dict, pedido: Optional[dict] = None) -> dict:
    """Rasgos que debería traer la próxima ronda: lo que más aceptó en la última ronda,
    sobrescrito por lo que pidió explícitamente. La interfaz puede pasárselo al generador
    para que explicar_ronda sea cierto."""
    obj = Interpretacion().model_dump()
    rondas = registro.get("rondas", [])
    if rondas:
        acep = [v for v in rondas[-1].get("variaciones", []) if v.get("decision") == "aceptada"]
        for r in _rasgos_comunes(acep):
            if r.startswith("expresión "):
                obj["rasgos"]["expresion"] = r.split(" ", 1)[1]
            else:
                obj["rasgos"][r] = True
    if pedido and pedido.get("permitido", True):
        for k, v in (pedido.get("rasgos") or {}).items():
            if v is not None:
                obj["rasgos"][k] = v
        for k, v in (pedido.get("cabello") or {}).items():
            if v is not None:
                obj["cabello"][k] = v
    return obj


def _describir(obj: dict) -> list[str]:
    out = []
    for r in RASGOS_BOOL:
        if obj["rasgos"].get(r) is True:
            out.append(f"con {r}")
        elif obj["rasgos"].get(r) is False:
            out.append(f"sin {r}")
    if obj["rasgos"].get("expresion"):
        e = obj["rasgos"]["expresion"]
        out.append(f"con expresión {FEMENINO.get(e, e)}")
    c = obj.get("cabello") or {}
    if c.get("color") or c.get("largo"):
        out.append("con cabello " + " ".join(x for x in (c.get("largo"), c.get("color")) if x))
    return out


def _con(c: str) -> str:
    if c.startswith("expresión "):
        e = c.split(" ", 1)[1]
        return f"con expresión {FEMENINO.get(e, e)}"
    return f"con {c}"


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


_NUM = {1: "la", 2: "las dos", 3: "las tres", 4: "las cuatro", 5: "las cinco", 6: "las seis"}


def explicar_ronda(registro: dict, ronda: int) -> str:
    """Una o dos frases que conectan lo que decidió en la ronda anterior con lo que trae `ronda`."""
    rondas = {r["ronda"]: r for r in registro.get("rondas", [])}
    actual = rondas.get(ronda, {})
    pedido = actual.get("pedido")
    if pedido is None and actual.get("instruccion"):
        pedido = interpretar_reglas(actual["instruccion"])
    ins = (actual.get("instruccion") or "").strip()

    anterior = rondas.get(ronda - 1)
    if anterior is None:
        base = "Esta es la primera ronda: las variaciones salen directamente de tu foto"
        return base + (f' y de tu pedido "{ins}".' if ins else ".")

    vs = anterior.get("variaciones", [])
    acep = [v for v in vs if v.get("decision") == "aceptada"]
    rech = [v for v in vs if v.get("decision") == "rechazada"]
    comunes = _rasgos_comunes(acep)

    if not acep:
        f1 = f"En la ronda {ronda - 1} rechazaste las {len(vs)} variaciones"
        comunes_r = _rasgos_comunes(rech, minimo=0.99)
        f1 += f", {_NUM.get(len(rech), 'todas')} {_lista([_con(c) for c in comunes_r])}" if comunes_r else ""
    else:
        ids = _lista([v["id"] for v in acep])
        cuantas = f"{_NUM.get(len(acep), f'las {len(acep)}')} " if len(acep) > 1 else ""
        f1 = f"En la ronda {ronda - 1} aceptaste {len(acep)} de {len(vs)} ({ids})"
        todas = _rasgos_comunes(acep, minimo=0.99)
        if todas:
            f1 += f", {cuantas}{_lista([_con(c) for c in todas])}"
        elif comunes:
            f1 += f", la mayoría {_lista([_con(c) for c in comunes])}"

    obj = objetivo_siguiente_ronda({"rondas": [anterior]}, pedido)
    desc = _describir(obj)
    if ins and desc:
        f2 = f' y pediste "{ins}", así que esta ronda trae caras {_lista(desc)}.'
    elif desc:
        f2 = f", así que esta ronda trae más caras {_lista(desc)}."
    elif ins:
        f2 = f' y pediste "{ins}", así que esta ronda busca variaciones nuevas según tu pedido.'
    else:
        f2 = ", así que esta ronda prueba variaciones distintas."
    return f1 + f2


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ejemplo = {
        "sesion_id": "demo",
        "rondas": [
            {"ronda": 1, "instruccion": None, "variaciones": [
                {"id": "v1", "decision": "aceptada", "comentario": "yo uso lentes",
                 "rasgos_detectados": {"lentes": True, "barba": False, "bigote": False, "expresion": "feliz"}},
                {"id": "v2", "decision": "rechazada", "comentario": "",
                 "rasgos_detectados": {"lentes": False, "barba": True, "bigote": False, "expresion": "serio"}},
                {"id": "v3", "decision": "aceptada", "comentario": "",
                 "rasgos_detectados": {"lentes": True, "barba": False, "bigote": False, "expresion": "serio"}}]},
            {"ronda": 2, "instruccion": "ponle lentes y que se vea más serio", "variaciones": [
                {"id": "v4", "decision": "aceptada", "comentario": "muy serio",
                 "rasgos_detectados": {"lentes": True, "barba": False, "bigote": False, "expresion": "serio"}}]},
        ],
    }
    print(interpretar("ponle lentes y que se vea más serio"))
    print(interpretar("que se parezca a Messi"))
    print(explicar_ronda(ejemplo, 2))
    t = resumir(ejemplo)
    print(t)
    print(verificar(t, ejemplo))
