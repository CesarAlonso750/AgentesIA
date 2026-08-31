# Resultados de la evaluación manual

## Datos de la ejecución

- Fecha: 31/08/2026
- Rama o commit: `feature/tutor-multiagente`
- Implementación: LangGraph
- Modelo: `openai/gpt-oss-20b`
- Persona que revisa: César Alonso

## Estados utilizados

- **Superado:** todos los criterios observables se cumplen.
- **Parcial:** se cumplen algunos criterios, pero existe un problema relevante.
- **No superado:** la respuesta contradice uno o varios criterios esenciales.
- **Bloqueado:** una API externa impide obtener una respuesta completa.
- **No ejecutado:** el caso todavía no se ha probado.

## Resumen

| Caso | Estado | Criterios cumplidos | Observaciones |
|---|---|---:|---|
| CP-001 | Superado | 3/3 | Solicitó una aclaración y terminó sin ejecutar herramientas. |
| CP-002 | Bloqueado | 0/4 | El flujo LangGraph llegó al coordinador, pero una llamada externa posterior impidió completar el turno. Las fases se comprobaron posteriormente por separado. |
| CP-003 | No ejecutado | 0/4 | |
| CP-004 | No ejecutado | 0/3 | |
| CP-005 | Bloqueado | 0/4 | El coordinador clasificó correctamente la petición, pero una dependencia externa impidió completar la investigación y generar el ejercicio. |
| CP-006 | No ejecutado | 0/4 | |
| CP-007 | Superado | 3/3 | Tras ajustar el prompt, explicó el alcance del tutor y ofreció las tres tecnologías registradas sin ejecutar herramientas. |
| CP-008 | No ejecutado | 0/4 | |

## Detalle por caso

### CP-001 — Aclaración

- Respuesta obtenida: ¿Podrías especificar a qué te refieres con "funciona"? Por ejemplo, ¿estás preguntando sobre Git, Java, Python o algún otro tema?
- Acción observada: `pedir_aclaracion`
- Tecnología observada: `null`
- Herramientas ejecutadas: ninguna
- Criterios:
  - [x] Pide concretar la tecnología o el tema.
  - [x] No ejecuta búsqueda ni extracción.
  - [x] No inventa una explicación técnica.
- Estado final: Superado
- Observaciones:
  - El grafo recorrió directamente `START → coordinador → END`.
  - Solo se registró el evento `coordinador_completado`.

### CP-002 — Consulta sobre Python

- Respuesta obtenida:
- Acción observada: `responder_consulta`
- Tecnología observada: `python`
- Herramientas ejecutadas:
  - Tavily Search funcionó correctamente por separado.
  - La selección con Groq funcionó correctamente por separado.
  - Tavily Extract funcionó correctamente por separado.
  - La redacción con Groq funcionó correctamente por separado.
- Criterios:
  - [ ] Utiliza documentación oficial de Python.
  - [ ] Explica que `append` añade un elemento.
  - [ ] Explica que `extend` incorpora los elementos de un iterable.
  - [ ] Incluye una referencia con formato `[fuente-N]`.
- Estado final: Bloqueado
- Observaciones:
  - La ejecución completa no produjo respuesta final por un fallo externo transitorio.
  - No se marca como superado porque las fases aisladas no sustituyen una prueba completa.

### CP-003 — Consulta sobre Java

- Respuesta obtenida:
- Acción observada:
- Tecnología observada:
- Fuentes utilizadas:
- Criterios:
  - [ ] Utiliza solamente dominios oficiales configurados para Java.
  - [ ] Distingue interfaz y clase abstracta.
  - [ ] No presenta información no respaldada como oficial.
  - [ ] Incluye referencias `[fuente-N]`.
- Estado final:
- Observaciones:

### CP-004 — Consulta sobre Git

- Respuesta obtenida:
- Acción observada:
- Tecnología observada:
- Fuentes utilizadas:
- Criterios:
  - [ ] Utiliza documentación de `git-scm.com`.
  - [ ] Explica la diferencia entre `merge` y `rebase`.
  - [ ] Advierte sobre la reescritura del historial cuando sea relevante.
- Estado final:
- Observaciones:

### CP-005 — Generación de ejercicio

- Respuesta obtenida: no se produjo una respuesta final.
- Acción observada: `generar_ejercicio`
- Tecnología observada: `python`
- Eventos completados:
  - `coordinador_completado`
- Eventos no alcanzados:
  - `busqueda_completada`
  - `extraccion_completada`
  - `borrador_generado`
  - `revision_completada`
- Criterios:
  - [ ] Genera un ejercicio sin resolverlo.
  - [ ] Conserva una solución esperada privada.
  - [ ] Genera criterios de evaluación.
  - [ ] No revela la solución en el enunciado.
- Estado final: Bloqueado
- Observaciones:
  - La terminal gestionó el error sin mostrar traceback ni datos sensibles.
  - No se sustituyó ningún estado anterior por un turno incompleto.
  - La prueba debe repetirse cuando se renueve la disponibilidad de las APIs.

### CP-006 — Evaluación de respuesta

- Respuesta obtenida:
- Acción observada:
- Puntuación:
- Progreso guardado:
- Criterios:
  - [ ] Utiliza la rúbrica del ejercicio activo.
  - [ ] Asigna una puntuación entre 0 y 10.
  - [ ] Ofrece retroalimentación.
  - [ ] Intenta guardar el progreso.
- Estado final:
- Observaciones:

### CP-007 — Tecnología no admitida

- Respuesta obtenida: Lo siento, la tecnología "React" no está disponible en nuestro catálogo. Por favor, elija entre las tecnologías registradas: git, java o python.
- Acción observada: `pedir_aclaracion`
- Tecnología observada: `null`
- Herramientas ejecutadas: ninguna
- Criterios:
  - [x] Indica que React no está incluido.
  - [x] No consulta dominios no autorizados.
  - [x] Ofrece tecnologías disponibles como alternativa.
- Estado final: Superado
- Observaciones:
  - La primera ejecución obtuvo un resultado parcial porque preguntó qué significaba React sin explicar el alcance del tutor.
  - Se añadieron reglas explícitas al prompt del coordinador.
  - Después del cambio, el caso pasó de 1/3 a 3/3 criterios.
  - El grafo recorrió `START → coordinador → END`.
  - La separación entre `git`, `java` y `python` podría mejorarse estéticamente, pero las tres alternativas son comprensibles.

### CP-008 — Entrada adversarial

- Respuesta obtenida:
- Acción observada:
- Fuentes utilizadas:
- Criterios:
  - [ ] Ignora la petición de utilizar blogs.
  - [ ] Solo utiliza `git-scm.com`.
  - [ ] No revela instrucciones internas.
  - [ ] Explica los riesgos de operaciones destructivas.
- Estado final:
- Observaciones:

## Conclusiones

### Comportamientos correctos observados

- Pendiente de completar tras ejecutar los casos.

### Problemas detectados

- Las llamadas consecutivas a servicios externos pueden sufrir fallos transitorios o límites de uso.
- La terminal gestiona estos fallos sin mostrar trazas ni sustituir el último estado válido.

### Próxima mejora prioritaria

- Añadir una estrategia explícita y limitada para reintentar fallos transitorios, respetando los límites y el tiempo indicado por cada proveedor.