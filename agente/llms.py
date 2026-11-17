"""
Backends de LLM del agente. Todos tienen la misma interfaz:

    llm(sistema, usuario, temperatura=0.0, max_tokens=400) -> str

Cada uno guarda .nombre, .ultimo (tokens y segundos de la última llamada) y
.total (acumulado) para la evaluación.

    from llms import LLMAPI, crear_llm, cargar_local
    api   = LLMAPI("groq")                 # clave en GROQ_API_KEY o secreto de Kaggle
    app   = crear_llm()                    # cadena de respaldo para la app, o None sin claves
    local = cargar_local()                 # Qwen2.5-7B 4 bits; si no entra, 3B
"""
from __future__ import annotations

import os
import time

import requests

PROVEEDORES = {
    # Groq: OpenAI-compatible. Los Llama 3.x de Groq fueron retirados en 2026.
    # Elegido qwen3.8-27b sin razonamiento: en 10 sesiones con máx. 400 tokens resolvió 9/10
    # con el LLM; gpt-oss-20b (reasoning_effort="low", su mínimo) cayó 3/10 a plantilla porque
    # el razonamiento se come los 400 tokens. Para usarlo: LLMAPI('groq', modelo='openai/gpt-oss-20b',
    # reasoning_effort='low'). Ver modelos activos: LLMAPI('groq').modelos()
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "modelo": "qwen/qwen3.8-27b",
        "clave": "GROQ_API_KEY",
        "reasoning_effort": "none",  # Qwen3 razona por defecto; "none" deja los 400 tokens para la respuesta
    },
    # Endpoint compatible con OpenAI; solo se usa como último respaldo de crear_llm() si hay clave.
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "modelo": "gemini-2.5-flash",
        "clave": "GEMINI_API_KEY",
        "reasoning_effort": "none",
    },
}


def _cargar_env():
    """Lee agente/.env (líneas CLAVE=valor) sin pisar variables ya definidas."""
    from pathlib import Path

    for ruta in (Path(__file__).with_name(".env"), Path.cwd() / ".env"):
        if ruta.exists():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                if "=" in linea and not linea.strip().startswith("#"):
                    k, v = linea.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _leer_clave(nombre: str) -> str | None:
    _cargar_env()
    if os.environ.get(nombre):
        return os.environ[nombre]
    try:  # Kaggle: Add-ons > Secrets
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret(nombre)
    except Exception:
        return None


class _Contador:
    def _registrar(self, entrada: int, salida: int, segundos: float):
        self.ultimo = {"tokens_entrada": entrada, "tokens_salida": salida, "segundos": segundos}
        for k, v in self.ultimo.items():
            self.total[k] = self.total.get(k, 0) + v
        self.total["llamadas"] = self.total.get("llamadas", 0) + 1

    def reiniciar(self):
        self.ultimo, self.total = {}, {}


class LLMAPI(_Contador):
    def __init__(self, proveedor: str = "groq", modelo: str | None = None, api_key: str | None = None,
                 base_url: str | None = None, reasoning_effort: str | None = "auto", timeout: int = 60,
                 esperar_cuota: bool = True):
        cfg = PROVEEDORES.get(proveedor, {})
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.modelo = modelo or cfg["modelo"]
        self.api_key = api_key or _leer_clave(cfg.get("clave", ""))
        if not self.api_key:
            raise ValueError(f"Falta la clave: define {cfg.get('clave')} (variable de entorno o secreto de Kaggle).")
        self.reasoning_effort = cfg.get("reasoning_effort") if reasoning_effort == "auto" else reasoning_effort
        self.timeout = timeout
        self.esperar_cuota = esperar_cuota  # False: ante un 429 falla enseguida (para la cadena)
        self.nombre = f"api:{self.modelo}"
        self.reiniciar()

    def modelos(self) -> list[str]:
        r = requests.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30)
        r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))

    def __call__(self, sistema: str, usuario: str, temperatura: float = 0.0, max_tokens: int = 400) -> str:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "temperature": temperatura,
            "max_tokens": max_tokens,
        }
        if self.reasoning_effort:
            cuerpo["reasoning_effort"] = self.reasoning_effort
        t0 = time.time()
        for espera in (0, 5, 15, 30) if self.esperar_cuota else (0,):  # reintentos ante 429 o 5xx
            time.sleep(espera)
            r = requests.post(f"{self.base_url}/chat/completions", json=cuerpo, timeout=self.timeout,
                              headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code == 400 and "reasoning_effort" in cuerpo and "reasoning" in r.text.lower():
                cuerpo.pop("reasoning_effort")  # el modelo no acepta ese parámetro
                self.reasoning_effort = None
                r = requests.post(f"{self.base_url}/chat/completions", json=cuerpo, timeout=self.timeout,
                                  headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code == 429 and _segundos_espera(r) > 30:
                break  # cuota agotada por un buen rato (p. ej. límite diario): no tiene sentido esperar
            if r.status_code != 429 and r.status_code < 500:
                break
        r.raise_for_status()
        datos = r.json()
        uso = datos.get("usage") or {}
        self._registrar(uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0), time.time() - t0)
        texto = datos["choices"][0]["message"].get("content") or ""
        if not texto.strip():
            raise RuntimeError("El LLM devolvió texto vacío (¿se gastó max_tokens razonando?).")
        return texto


def _segundos_espera(r) -> float:
    try:
        return float(r.headers.get("retry-after", 0))
    except ValueError:
        return 0.0


class CadenaLLM(_Contador):
    """Prueba los LLM en orden. Ante un 429 o un error de red pasa al siguiente de inmediato
    y salta el que falló durante `pausa` segundos. Si todos fallan, relanza el último error
    (resumir usa entonces la plantilla e interpretar las reglas)."""

    def __init__(self, llms: list, pausa: float = 300):
        self.llms, self.pausa = list(llms), pausa
        self.nombre = "cadena:" + "|".join(l.nombre for l in self.llms)
        self.ultimo_nombre = None  # qué modelo respondió la última llamada
        self._saltar_hasta = {l.nombre: 0.0 for l in self.llms}
        self.reiniciar()

    def __call__(self, sistema: str, usuario: str, temperatura: float = 0.0, max_tokens: int = 400) -> str:
        error = RuntimeError("Todos los LLM de la cadena están en pausa.")
        for llm in self.llms:
            if time.time() < self._saltar_hasta[llm.nombre]:
                continue
            try:
                texto = llm(sistema, usuario, temperatura, max_tokens)
            except requests.RequestException as e:  # 429, red caída, etc.
                self._saltar_hasta[llm.nombre] = time.time() + self.pausa
                error = e
                continue
            except Exception as e:  # p. ej. texto vacío: probar el siguiente sin pausar este
                error = e
                continue
            self.ultimo_nombre = llm.nombre
            u = llm.ultimo or {}
            self._registrar(u.get("tokens_entrada", 0), u.get("tokens_salida", 0), u.get("segundos", 0.0))
            return texto
        raise error


def crear_llm(pausa: float = 300):
    """LLM para la app: cadena Groq qwen3.8-27b, Groq gpt-oss-20b (otra cuota) y gemini-2.5-flash
    si hay GEMINI_API_KEY. Los que no tienen clave se saltan. Sin ninguna clave devuelve None."""
    opciones = [
        ("groq", {}),
        ("groq", {"modelo": "openai/gpt-oss-20b", "reasoning_effort": "low"}),
        ("gemini", {}),
    ]
    llms = []
    for proveedor, kwargs in opciones:
        try:
            llms.append(LLMAPI(proveedor, esperar_cuota=False, **kwargs))
        except ValueError:  # falta la clave
            pass
    return CadenaLLM(llms, pausa) if llms else None


class LLMLocal(_Contador):
    """Qwen2.5-Instruct con transformers. En 4 bits (bitsandbytes) necesita una GPU."""

    def __init__(self, modelo: str = "Qwen/Qwen2.5-7B-Instruct", cuantizar_4bit: bool = True, device_map="auto"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kwargs = {"device_map": device_map}
        if cuantizar_4bit:
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
            )
        else:
            kwargs["torch_dtype"] = "auto"
        self.tok = AutoTokenizer.from_pretrained(modelo)
        self.model = AutoModelForCausalLM.from_pretrained(modelo, **kwargs).eval()
        self.nombre = f"local:{modelo.split('/')[-1]}" + ("-4bit" if cuantizar_4bit else "")
        self.reiniciar()

    def __call__(self, sistema: str, usuario: str, temperatura: float = 0.0, max_tokens: int = 400) -> str:
        import torch

        mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]
        enc = self.tok.apply_chat_template(mensajes, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        ids = enc["input_ids"].to(self.model.device)
        mascara = enc["attention_mask"].to(self.model.device)
        t0 = time.time()
        gen = {"max_new_tokens": max_tokens, "pad_token_id": self.tok.eos_token_id}
        if temperatura > 0:
            gen.update(do_sample=True, temperature=temperatura)
        else:
            gen.update(do_sample=False, temperature=None, top_p=None, top_k=None)
        with torch.no_grad():
            out = self.model.generate(input_ids=ids, attention_mask=mascara, **gen)
        nuevos = out[0, ids.shape[1]:]
        self._registrar(int(ids.shape[1]), int(nuevos.shape[0]), time.time() - t0)
        return self.tok.decode(nuevos, skip_special_tokens=True)


def cargar_local(preferido: str = "Qwen/Qwen2.5-7B-Instruct", respaldo: str = "Qwen/Qwen2.5-3B-Instruct") -> LLMLocal:
    """Intenta el 7B en 4 bits; si no hay memoria (junto con FLUX y los flows), usa el 3B."""
    try:
        return LLMLocal(preferido)
    except (RuntimeError, ValueError, MemoryError) as e:  # torch.OutOfMemoryError hereda de RuntimeError
        print(f"No cupo {preferido} ({type(e).__name__}); uso {respaldo}.")
        import gc

        import torch

        gc.collect()
        torch.cuda.empty_cache()
        return LLMLocal(respaldo)


class LLMFalso(_Contador):
    """Para pruebas sin red: devuelve las respuestas de una lista, o llama a una función."""

    def __init__(self, respuestas=None, funcion=None, nombre="falso"):
        self.respuestas, self.funcion, self.nombre = list(respuestas or []), funcion, nombre
        self.reiniciar()

    def __call__(self, sistema, usuario, temperatura=0.0, max_tokens=400):
        texto = self.funcion(sistema, usuario) if self.funcion else self.respuestas.pop(0)
        self._registrar(len(sistema + usuario) // 4, len(texto) // 4, 0.0)
        return texto
