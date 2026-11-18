# Entrega: material para completar el informe

Aquí van datos, figuras y herramientas. **La redacción del informe es de ustedes**: el enunciado exige que esté escrito íntegramente por los alumnos. Por eso no hay párrafos para copiar, solo cifras y observaciones.

| Pendiente del informe | Qué hay aquí | Estado |
|---|---|---|
| Fig. 3 (foto publicable) | `fig3_cascada.png`: la cascada sobre un retrato **sintético** (no es una persona real) | Listo |
| Fig. 4 | `fig4_interfaz.png` (panel a–d) y las 4 capturas sueltas en `fig4/` | Listo |
| Cuadro 3: parecido y diversidad; VIII.B | `comparacion/` (CLIP, LPIPS y tiempo con los dos métodos) | Listo con retratos sintéticos; repetir con fotos reales |
| Cuadro 3: respuesta a decisiones (aceptación) | `scripts/calcular_aceptacion.py` | Falta: sale de las sesiones con personas |
| Cuadro 3: coherencia; VIII.C | `agente_eval/` (Qwen2.5-7B local y sin LLM) | Ver más abajo; falta Groq (necesita `GROQ_API_KEY`) |
| VIII.D y Anexo B | `usabilidad/` (guía, SUS, planilla y calculadora) | Falta: la prueba con personas |
| Anexo A | `anexo_a_mosaico.png` | Listo con retratos sintéticos |
| Portada | — | El borrador ya trae "Ruben Aaron Coorahua Peña (202110086)" |

## Retratos sintéticos (`retratos/`)

Son 10 personas que no existen, generadas con FLUX.2 klein (`scripts/generar_retratos.py`, semillas fijas): 6 con rasgos peruanos y 4 de otros orígenes, igual que la proporción de los datos de entrenamiento. Varían edad, lentes, barba y expresión, y las descripciones están en `retratos.json`. No se usaron para entrenar, y como no son personas reales se pueden publicar.

## Comparación de los métodos (`comparacion/`)

Cada retrato pasa por los dos métodos: una ronda de 5 caras, sin ficha ni pedidos, igual que la primera ronda de la interfaz. Medido en la RTX 3070 laptop de 8 GB.

| | Modelo propio | FLUX.2 klein |
|---|---|---|
| CLIP foto-cara (propia) | 0,562 ± 0,048 | 0,567 ± 0,032 |
| CLIP con fotos de las otras 9 personas | 0,535 ± 0,024 | 0,556 ± 0,005 |
| Margen (propia − ajena) | +0,027 ± 0,044 | +0,011 ± 0,034 |
| CLIP reconoce la persona correcta (top-1 entre 10) | 10 de 50 (20 %) | 8 de 50 (16 %) |
| Azar | 10 % | 10 % |
| LPIPS medio entre las 5 caras de la ronda | 0,143 ± 0,063 | 0,299 ± 0,050 |
| Segundos por ronda | 18,6 ± 2,3 | 102,1 ± 4,6 |

Observaciones:

- **Parecido.** La similitud CLIP entre una foto y una estampa LEGO es baja en los dos métodos (~0,56) y casi igual a la que da contra fotos de otras personas. El modelo propio queda un poco por encima del azar (20 % frente a 10 %), pero con 10 personas esa diferencia no alcanza para afirmar nada. CLIP no fue entrenado para comparar retratos con estampas, así que mide parecido de manera muy gruesa.
- **Diversidad.** FLUX varía el doble entre las 5 caras de una ronda (0,30 frente a 0,14). El modelo propio da caras muy parecidas entre sí: con p05, por ejemplo, el LPIPS medio fue 0,06.
- **Tiempo.** Aquí FLUX tardó unos **100 s por ronda**, no los 25–35 s que dice el borrador. Hay dos razones, y conviene corregir la cifra:
  1. Los dos modelos comparten la GPU, así que FLUX sube a la GPU por partes.
  2. Con una foto y sin ficha, FLUX dibuja a menudo el contorno de la cabeza; el filtro lo detecta y reintenta con otra semilla (hasta 3 veces por cara).
- **Restos de contorno.** En la ronda 1 de FLUX, varias caras conservan trozos del contorno que el filtro no borra del todo (se ven en el Anexo A y en la Fig. 4c). Con un pedido concreto, en la ronda 2, salen limpias. Puede ir en Limitaciones.

`por_persona.csv` trae las cifras por retrato y `caras/` las 100 estampas, más las máscaras del modelo propio.

### Repetir con fotos reales

Pongan las fotos de amigos o familiares (con su permiso) en una carpeta y corran:

```powershell
cd entrega\scripts
..\..\lego-face\interfaz\servidor\.venv\Scripts\python comparar_metodos.py ..\fotos_reales ..\comparacion_reales
```

Sale el mismo `resumen.json`. Cada foto debe tener una sola cara de frente: el script anota cuántas detectó.

## Anexo A (`anexo_a_mosaico.png`)

El mosaico muestra tres retratos (p01, p04 y p07) y los dos métodos.
- **Ronda 1:** las mismas caras de la comparación.
- **Ronda 2, modelo propio:** Variar con las caras 1 y 2.
- **Ronda 2, FLUX:** el pedido "ponle lentes y que se vea más serio", interpretado por el agente con sus reglas (lentes y expresión seria).

Las caras "aceptadas" (borde verde) las fija el script, no una persona; el pie de la figura del informe debe decirlo.

Se nota que Variar conserva la forma y cambia el color, y que FLUX cumple el pedido en las 5 caras.

Para regenerarlo: `scripts/mosaico_y_fig3.py`.

## Fig. 3 (`fig3_cascada.png`)

Muestra la foto, la máscara (Flow 1 + codec de forma) y la estampa (Flow 2 + codec de color) del retrato sintético p01. Reemplaza a la foto actual, cuyo origen había que confirmar.

## Fig. 4 (`fig4_interfaz.png`)

Son capturas reales de la app con el retrato p09:
- (a) el inicio;
- (b) la asesoría, con el maniquí probando "Medio despeinado";
- (c) las 5 variaciones, tres aceptadas y dos rechazadas, una con motivo;
- (d) el resumen verificado.

Para regenerarlas: `scripts/capturas_fig4.mjs` y `scripts/componer_fig4.py`.

## Usabilidad (`usabilidad/`)

- **`guia_prueba.md`:** el texto del consentimiento para el video, las 3 tareas con su criterio de término, las preguntas finales y la estructura del video de 3 minutos.
- **`cuestionario_SUS.md`:** las 10 preguntas en español, para imprimir.
- **`plantilla_respuestas.csv`:** una fila por persona (tiempos, éxito por tarea, respuestas SUS y comentarios).
- **`calcular_sus.py`:** calcula el SUS de cada persona, la media y los tiempos por tarea, y escribe `anexo_b.md` con la tabla del anexo.

## Aceptación por ronda y por método

Después de las sesiones reales:

```powershell
python scripts\calcular_aceptacion.py ..\lego-face\interfaz\servidor\registros --salida aceptacion
```

Corta por ronda, por método y por tipo de ronda (nueva, Variar o con pedido escrito), y cuenta los resúmenes por origen.

## Cambio en la interfaz

El borrador dice que al rechazar se puede escribir un comentario de hasta 200 caracteres, pero la interfaz no lo tenía. Ya está agregado en `lego-face/interfaz` (aparece en la Fig. 4c). Si se marcan motivos y además se escribe, el registro guarda los dos.
