# LEGO Face

Convierte la foto de una persona en caras de minifigura LEGO, con dos métodos (modelo propio y FLUX.2 klein), una interfaz 3D y un agente LLM que resume cada sesión.

## Estructura

| Carpeta / archivo | Qué hay |
|---|---|
| `modelo/` | Notebooks del modelo propio en cascada (VAE, Flow 1 de forma, Flow 2 de color) y su guía. |
| `Face.zip` | Pesos entrenados del modelo propio (`flow1.pt`, `flow2.pt`, `vae1.pt`, `vae2.pt`). **Se queda en la raíz**: la interfaz lo busca aquí. |
| `LegoFace_Local_Completo.zip` | Código para correr el modelo propio en local. **Se queda en la raíz**: la interfaz lo busca aquí. |
| `flux/` | Parte FLUX: cara LEGO con FLUX.2 klein + minifig LDraw + cabello y render. Ver `flux/README.md`. |
| `agente/` | Agente LLM que resume la sesión y su evaluación. |
| `interfaz/` | App web (servidor FastAPI + escena Three.js) y scripts de evaluación. |
| `LEGO_Face_Entrega/` | Paquete final de entrega: informe (PDF + LaTeX), presentación, video, material del informe y usabilidad. Lo que falta está en `LEGO_Face_Entrega/PENDIENTES.txt`. |

Para correr la interfaz, primero descomprime `Face.zip` y `LegoFace_Local_Completo.zip` aquí mismo (ver `interfaz/README.md`).
