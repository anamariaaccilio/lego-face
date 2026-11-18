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

Después de subir o tomar una foto, elige **Desde mi foto** en **Peinado** en el panel de la máquina o en la pregunta de peinado en la asesoría. DINOv2 Small, el predictor directo Flow 1 y la VAE 1 producen una ocupación 3D que se convierte en una malla. La malla se puede previsualizar, pintar con la paleta y exportar en GLB, incluida en la cabeza. La geometría se reutiliza para todas las caras de una ronda.

También puedes elegir una de las 11 piezas LDraw, o **Sin cabello**. Las piezas del catálogo están en `web/public/cabello/`; ver sus créditos y `herramientas/ldraw_a_json.py`.

Los pesos de cabello vienen en `interfaz/modelos_cabello/`. Se incluye el checkpoint `flow1_v2_best.pt` de la corrida de 305 pares, con 271 pares de entrenamiento, 16 de validación y 18 de prueba. Está guardado como `flow1_best.pt`. Para usar otro checkpoint directo de la misma arquitectura, define `LEGO_CABELLO_FLOW` con la ruta al archivo. El servidor comprueba la compatibilidad con la VAE y la grilla.

Por defecto el cabello corre en CPU y DINOv2 se descarga en la primera solicitud. Usa `LEGO_CABELLO_DEVICE=cuda:0` para correrlo en una GPU, o `LEGO_CABELLO_DINO` para apuntar a una copia local del mismo DINOv2 Small. La forma se genera desde la foto. El color se elige con la paleta y empieza en castaño si no has elegido otro.

En una ronda nueva del generador **Modelo entrenado**, la máquina calcula cinco cabellos desde ruido gaussiano con semillas distintas. Usa el checkpoint generativo de cabello `flow1_ruido.pt`, con 25 pasos, y luego genera cinco caras con el Flow de caras. El indicador circular estima el tiempo y ajusta la estimación después de cada ronda. La pasarela recibe las parejas 1–1 a 5–5 conforme llegan las caras. En el control de calidad, **Ver las 25 combinaciones** cruza las cinco caras con los cinco cabellos. Las decisiones de la ronda se aplican a las cinco parejas de la pasarela.

## Cómo correrlo

Para usar el generador de **caras** entrenado, recupera el `Face.zip` real del repositorio con Git LFS y descomprímelo junto a `LegoFace_Local_Completo.zip` en la raíz, así quedan `Face/` y `LegoFace_Local/`. El `Face.zip` de la distribución original es un puntero LFS. Para abrir la máquina y generar, pintar y exportar únicamente la cabeza con cabello, puedes arrancar con `FLUX=0` sin esos archivos de cara. En PowerShell usa `$env:FLUX="0"` antes de ejecutar el servidor.

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
