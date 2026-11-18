# Prueba de usabilidad de LEGO Face

Sirve para la sección VIII.D, el Anexo B y el video. Cada prueba dura unos 10 minutos por persona.

## Antes de empezar

- La persona es un docente de la UTEC o un estudiante de una carrera distinta de Ciencia de Datos o Ciencia de la Computación.
- Servidor encendido (`interfaz/servidor`, `python app.py`) y página abierta en http://127.0.0.1:8765, recargada con Ctrl+F5.
- Grabación de pantalla lista. Al inicio, la cámara apunta 10 segundos a la persona para el consentimiento.
- Un cronómetro (el del celular sirve) y `plantilla_respuestas.csv` abierta para anotar.

## Consentimiento (se lee al inicio del video, unos 10 segundos)

> "Hola, soy [nombre], [docente / estudiante de [carrera]] de la UTEC. Acepto participar en la prueba del proyecto LEGO Face, que me graben la pantalla y la voz, y que mi foto se use solo durante la prueba."

Después se le pide su foto dentro de la app. La app la usa solo en memoria y la borra al cerrar la sesión.

## Tareas

Solo se le lee la consigna. Si se traba más de 30 segundos, se anota y se le da una pista mínima. El tiempo corre desde que termina la consigna hasta que la tarea queda hecha.

| # | Consigna que se lee | Termina cuando |
|---|---|---|
| 1 | "Hazte una cara LEGO con tu foto y elige cuáles te gustan." | Aparece el mensaje de Tito después de pulsar **Listo** en el control de calidad |
| 2 | "Pide un cambio: por ejemplo, que tenga lentes o que se vea más serio, y genera otra ronda." | Termina la segunda ronda y decide las 5 caras |
| 3 | "Termina y lee el resumen de lo que elegiste." | El resumen se ve en el panel |

Se anota en la planilla el tiempo de cada tarea, si la completó sin ayuda (1) o no (0), y cualquier momento de duda.

## Al terminar

1. La persona completa el cuestionario SUS (`cuestionario_SUS.md`), 10 preguntas de 1 a 5.
2. Se le hacen tres preguntas cortas y se anota la respuesta tal cual:
   - "¿Qué te gustó más?"
   - "¿Qué te confundió o te costó?"
   - "¿Qué le cambiarías?"
3. Se descarga el registro (botón **Registro** en el resumen). También queda en `interfaz/servidor/registros/`.

## Con los datos

```
python calcular_sus.py plantilla_respuestas.csv
python ..\calcular_aceptacion.py ..\..\servidor\registros
```

El primer comando da el SUS de cada persona, el SUS medio, los tiempos por tarea y una tabla para el Anexo B. El segundo da la aceptación por ronda y por método para el Cuadro 3.

## Video (3 minutos o menos)

1. 10 s: la persona se presenta y da su consentimiento.
2. Foto y elección del método.
3. Las 5 variaciones y la persona aceptando o rechazando cada una.
4. El cambio escrito y la segunda ronda (se puede acelerar en la edición).
5. El resumen del agente.

Se cortan los tiempos muertos de generación.
