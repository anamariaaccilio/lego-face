# Evaluación

Scripts que producen las cifras y figuras del informe. Se corren con el venv de `interfaz/servidor`, que ya tiene los modelos instalados, más `pip install lpips torchvision` para LPIPS.

| Script | Qué hace |
|---|---|
| `generar_retratos.py <salida>` | 10 retratos sintéticos con FLUX.2 klein (6 con rasgos peruanos y 4 de otros orígenes; semillas fijas) |
| `comparar_metodos.py <fotos> <salida>` | Corre los dos métodos sobre las mismas fotos y mide CLIP (foto-cara, margen y top-1), LPIPS entre las 5 caras y segundos por ronda |
| `mosaico_y_fig3.py <retratos> <comparacion> <salida>` | Anexo A (rondas 1 y 2, Variar y un pedido escrito) y Fig. 3 (cascada del modelo propio) |
| `capturas_fig4.mjs <url> <foto> <salida>` y `componer_fig4.py` | Capturas de la app para la Fig. 4 (necesita `npm i playwright-core` y el servidor encendido) |
| `calcular_aceptacion.py <registros>` | Aceptación por ronda, por método y por tipo de ronda, a partir de `interfaz/servidor/registros/` |
| `usabilidad/` | Guía de la prueba, cuestionario SUS, planilla y `calcular_sus.py` |

Para comparar con fotos reales (con permiso de cada persona, una sola cara de frente por foto):

```powershell
cd interfaz\evaluacion
..\servidor\.venv\Scripts\python comparar_metodos.py C:\ruta\fotos_reales C:\ruta\comparacion_reales
```

Las fotos y los resultados no se suben al repo.
