# Diario de decisiones técnicas

## DT-001: búsqueda y extracción de documentación oficial

**Fecha:** 23 de agosto de 2026

### Contexto

El tutor debe encontrar información actualizada en distintas documentaciones técnicas oficiales. El usuario indicará una tecnología y un tema, pero no tendrá que proporcionar la URL exacta de la página.

También necesitamos extraer el contenido útil de páginas con estructuras HTML diferentes. Construir y mantener un scraper propio para cada documentación aumentaría considerablemente la duración y complejidad del proyecto.

### Opciones consideradas

1. Crear un índice local de todas las documentaciones.
2. Utilizar el buscador propio de cada sitio.
3. Usar Tavily Search y construir un extractor HTML propio.
4. Usar Tavily Search junto con Tavily Extract.
5. Enviar el HTML completo directamente al modelo.

### Decisión

Se utilizará Tavily Search para localizar páginas dentro de una lista cerrada de dominios oficiales.

Después se utilizará Tavily Extract para obtener el contenido limpio de las páginas seleccionadas.

Tavily no generará la respuesta final. Los fragmentos extraídos se enviarán al agente tutor, que los utilizará como evidencias para explicar conceptos y generar preguntas.

### Configuración inicial

- Búsqueda con profundidad `basic`.
- Máximo de cinco resultados por búsqueda.
- Respuestas generadas por Tavily desactivadas.
- Extracción con profundidad `basic`.
- Formato de extracción Markdown.
- Máximo de tres fragmentos por fuente.
- Dominios obtenidos de un catálogo local.
- Máximo de tres búsquedas y tres extracciones por turno.

### Validaciones

El sistema deberá comprobar:

- Que la tecnología esté registrada.
- Que la consulta sea válida.
- Que las URLs pertenezcan a dominios autorizados.
- Que la URL extraída proceda de la búsqueda actual.
- Que la respuesta de Tavily tenga la estructura esperada.
- Que el contenido extraído no esté vacío.
- Que el contenido no supere el límite configurado.

### Consecuencias positivas

- Evita construir un scraper diferente para cada documentación.
- Reduce el tiempo necesario para completar el proyecto.
- Mantiene el encadenamiento de herramientas.
- Permite consultar documentación actualizada.
- Facilita añadir nuevas tecnologías mediante configuración.

### Consecuencias negativas

- Añade una dependencia externa.
- Requiere una variable `TAVILY_API_KEY`.
- El plan gratuito tiene un límite mensual.
- Los resultados de búsqueda pueden cambiar.
- Las pruebas deben simular las respuestas de Tavily.

### Alternativa futura

Si el proyecto necesitara funcionar sin servicios externos, se podría construir un índice local a partir de las documentaciones oficiales y utilizar un sistema de recuperación propio.

## DT-002: estado compartido y salida estructurada del coordinador

**Fecha:** 27 de agosto de 2026

### Contexto

Los tres agentes necesitan compartir información durante cada turno. Además,
las decisiones del coordinador controlan qué componentes se ejecutan y si se
consumen recursos externos, por lo que no pueden depender de texto libre.

El coordinador debe distinguir entre responder una consulta, generar un
ejercicio, evaluar una respuesta o pedir una aclaración.

### Opciones consideradas

1. Permitir que cada agente devuelva texto libre.
2. Solicitar JSON mediante instrucciones en el prompt.
3. Utilizar JSON Object Mode sin un esquema estricto.
4. Utilizar Structured Outputs con JSON Schema y validación local.
5. Utilizar únicamente clases Pydantic como estado completo del grafo.

### Decisión

Se utilizará `TypedDict` para describir el estado interno compartido por los
agentes. Este formato es sencillo, compatible con diccionarios normales y
adecuado para LangGraph.

Las salidas generadas por los modelos se validarán mediante clases Pydantic.
El coordinador utiliza `DecisionCoordinador` para producir una acción, una
tecnología, una consulta de documentación, un indicador de uso de fuentes y
un posible mensaje de aclaración.

La implementación manual utiliza Structured Outputs de Groq con JSON Schema
en modo estricto. La validación local de Pydantic se mantiene porque el JSON
Schema garantiza tipos y campos, pero no todas las relaciones semánticas entre
sus valores.

Si una salida cumple el JSON Schema pero no las reglas locales, el coordinador
puede realizar un único intento de corrección. El número total de intentos
queda limitado a dos.

### Reglas principales

- Los campos del JSON son obligatorios, aunque algunos admitan `null`.
- No se permiten propiedades adicionales.
- La tecnología debe existir en el catálogo local.
- Una consulta o un ejercicio requieren documentación oficial.
- Una aclaración no utiliza Tavily.
- Una evaluación reutiliza el ejercicio y las fuentes guardadas.
- Una consulta inválida nunca llega a las herramientas.
- El coordinador no puede realizar más de dos intentos.

### Consecuencias positivas

- Las decisiones pueden consumirse sin analizar texto libre.
- Los errores del modelo se detectan antes de ejecutar herramientas.
- Una salida incoherente puede corregirse de forma controlada.
- El límite de intentos evita bucles y consumo indefinido.
- El estado podrá reutilizarse en las versiones manual y LangGraph.
- Los componentes pueden probarse con clientes simulados.

### Consecuencias negativas

- Se añade código para esquemas, validadores y reintentos.
- Una corrección consume una segunda llamada a Groq.
- El JSON Schema no representa todas las reglas de `model_validator`.
- La calidad semántica de la clasificación necesita casos de evaluación.

### Evidencia inicial

En una prueba real, el coordinador seleccionó correctamente
`generar_ejercicio`, pero devolvió `consulta_documentacion` con valor `null`.
Structured Outputs aceptó la estructura y Pydantic rechazó la incoherencia
antes de consultar Tavily.

Después de añadir el reintento limitado, el coordinador produjo una consulta
válida relacionada con operaciones de listas de Python.