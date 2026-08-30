# Tutor técnico multiagente

Proyecto final del nivel experto. El sistema permite estudiar Python, Java y
Git utilizando exclusivamente documentación oficial.

## Estado actual

La implementación manual incluye:

- Coordinador con salida estructurada.
- Búsqueda oficial mediante Tavily Search.
- Selección de fuentes mediante Groq.
- Extracción mediante Tavily Extract.
- Redacción de explicaciones y ejercicios.
- Revisión independiente de borradores.
- Evaluación de respuestas mediante rúbricas privadas.
- Memoria entre turnos.
- Progreso local en JSON.
- Logging estructurado y rotativo.
- Pruebas automatizadas sin consumo de APIs.

La versión con LangGraph se añadirá posteriormente.

## Ejecutar la versión manual

Desde la raíz del repositorio y con el entorno virtual activado:

```powershell
python -m nivel_experto.tutor_multiagente.cli_manual

Comandos disponibles:
- Escribir una consulta sobre Python, Java o Git.
- Pedir un ejercicio.
- Responder al ejercicio pendiente.
- Escribir salir para terminar.
