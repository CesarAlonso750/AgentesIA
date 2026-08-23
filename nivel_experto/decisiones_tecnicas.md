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