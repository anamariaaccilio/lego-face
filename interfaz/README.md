# Interfaz: Fábrica de caras

Tito, un LEGO operario, te recibe en una fábrica 3D y te ofrece dos caminos:

- **Fabricar con la máquina**: foto, estilo (Parecido, Equilibrado o Libre) y 5 caras con el modelo entrenado (Flow 1 + DiTo + Flow 2 + VAE color).
- **Quiero asesoría**: Tito te lleva a la oficina de diseño, te pide una foto (opcional) y te hace 6 preguntas (expresión, lentes, barba o bigote, cabello, ojos, detalles). Puedes responder con botones o escribiendo libre. Con esa ficha, FLUX.2 [klein] 4B fabrica 5 caras.

En los dos caminos aceptas o rechazas cada cara, pides otra ronda y puedes pasar al otro modelo sin perder la sesión. Al terminar, el agente resume la sesión.

```
interfaz/servidor/   FastAPI: generadores, guardrails, registro; usa ../../agente
interfaz/web/        Three.js + Vite
```

## Cabello

El cabello no lo dibuja ningún modelo: es una pieza 3D de LDraw (11 peinados) que se encaja en la cabeza y se pinta del color elegido, incluidos rosa, azul, morado y verde.
- En la asesoría se elige con dos preguntas y se ve en el maniquí de la oficina. En la máquina se elige en el panel.
- Si el texto libre habla del pelo, eso va a la pieza y no a FLUX. A FLUX solo le llega el color, para las cejas.

Las piezas están en `web/public/cabello/`. Salen de la biblioteca oficial de LDraw (CC BY 2.0; ver `CREDITOS.txt`) y se convierten con `herramientas/ldraw_a_json.py`. Para agregar un peinado, suma su número de pieza a `PEINADOS` en ese script y vuelve a correrlo con el `complete.zip` de ldraw.org.

## Cómo correrlo

Primero descomprime `Face.zip` y `LegoFace_Local_Completo.zip` en la raíz del repo, así quedan `Face/` y `LegoFace_Local/`.

```powershell
cd interfaz\servidor
python -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\pip install -r requirements.txt

cd ..\web
npm install
npm run build

cd ..\servidor
.venv\Scripts\python app.py      # http://127.0.0.1:8765
```

La primera vez se descargan DINOv2 (unos 350 MB) y FLUX.2 klein (unos 16 GB). Al arrancar, FLUX se cuantiza a 4 bits y tarda unos 30 s en cargar.

Para usar el LLM del agente, pon `GROQ_API_KEY` en `agente/.env` (y `GEMINI_API_KEY` como respaldo, si tienes). Sin claves, el agente usa sus reglas para interpretar y su plantilla para resumir.

Variables útiles:
- `FLUX=0`: arranca sin FLUX.
- `FLUX_GPU=1` / `0`: fuerza a FLUX a quedarse entero en la GPU, o a subir por partes.
- `LEGO_DEMO=1`: agrega un generador simulado.

## Tiempos en la RTX 3070 laptop (8 GB)

| | Por ronda de 5 |
|---|---|
| Modelo entrenado | ~20 s; ~8 s si conserva la forma de las aceptadas |
| FLUX.2 klein, por partes (junto al modelo entrenado) | ~25–35 s |

Con los dos modelos cargados no cabe todo en 8 GB, así que FLUX sube a la GPU por partes. Si quedan 6,5 GB libres o más, se queda entero en la GPU (~3 s por cara).

## Cómo usa el agente

| Momento | Función de `agente/` |
|---|---|
| Respuesta escrita en la asesoría | `interpretar` (con su guardrail: bloquea pedidos sexuales, ofensivos, de parecerse a una persona real o de burla) |
| "¿Qué le cambio?" antes de otra ronda | `interpretar` + `objetivo_siguiente_ronda` |
| Inicio de cada ronda (lo dice Tito) | `explicar_ronda` |
| Terminar | `resumir` + `verificar` |

El registro sigue el formato de `agente/README.md` (`v1, v2…`, `aceptada`/`rechazada`, `comentario`, `rasgos_detectados`). Se guarda en `interfaz/servidor/registros/` y también se puede descargar.

Para FLUX, `rasgos_detectados` registra lo que se le pidió (la ficha), porque no hay un detector de rasgos. Para el modelo entrenado queda vacío.

## Agregar otra forma de generar

Crea una clase en `servidor/generadores/` que herede de `Generador` y regístrala en `generadores/__init__.py`. Con `acepta_texto = True` recibe la ficha y los pedidos escritos. Con `necesita_foto = False` puede generar sin foto.
