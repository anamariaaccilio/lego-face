### Resumir + verificar (30 sesiones)

| Métrica | local:Qwen2.5-7B-Instruct-4bit | sin LLM (plantilla/reglas) |
|---|---|---|
| pasa_primer_intento_% | 3.3 | 0.0 |
| necesita_reintento_% | 36.7 | 0.0 |
| plantilla_por_verificador_% | 60.0 | 0.0 |
| plantilla_por_red_cuota_% | 0.0 | 0.0 |
| plantilla_sin_llm_% | 0.0 | 100.0 |
| reejecuciones_por_red | 0 | 0 |
| tiempo_medio_s | 44.1 | 0.0 |
| tokens_entrada_total | 137958 | 0 |
| tokens_salida_total | 18669 | 0 |
| llamadas | 82 | 0 |
| n_registros | 30 | 30 |

### Interpretar (40 instrucciones, 10 prohibidas)

| Métrica | local:Qwen2.5-7B-Instruct-4bit | sin LLM (plantilla/reglas) |
|---|---|---|
| acierto_rasgos.lentes_% | 100.0 | 100.0 |
| acierto_rasgos.barba_% | 96.7 | 100.0 |
| acierto_rasgos.bigote_% | 96.7 | 100.0 |
| acierto_rasgos.expresion_% | 100.0 | 100.0 |
| acierto_cabello.color_% | 100.0 | 100.0 |
| acierto_cabello.largo_% | 93.3 | 100.0 |
| acierto_exacto_permitidas_% | 90.0 | 100.0 |
| no_bloquea_permitidas_% | 96.7 | 100.0 |
| rechaza_prohibidas_% | 100.0 | 100.0 |
| reglas_por_red_cuota | 0 | 0 |
| reejecuciones_por_red | 0 | 0 |

