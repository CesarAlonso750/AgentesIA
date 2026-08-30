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


## DT-003: tutor-investigador con herramientas encadenadas y fuentes verificables

**Fecha:** 28 de agosto de 2026

### Contexto

El segundo agente debe investigar documentación oficial y producir una
explicación o un ejercicio. Para hacerlo necesita ejecutar varios pasos:
buscar páginas, seleccionar las relevantes, extraer su contenido y redactar
un borrador.

No es seguro permitir que el modelo escriba directamente una URL o declare
libremente qué fuentes ha utilizado. Tampoco es suficiente confiar únicamente
en que Structured Outputs produzca un JSON con la forma correcta, porque una
respuesta estructuralmente válida todavía puede incluir una fuente inexistente
o una afirmación no respaldada.

### Opciones consideradas

1. Utilizar un único prompt que busque, seleccione y redacte a la vez.
2. Permitir que el modelo proporcione directamente las URL que quiere consultar.
3. Ejecutar siempre los primeros resultados devueltos por Tavily Search.
4. Separar selección y redacción dentro del mismo tutor-investigador.
5. Crear un agente independiente para cada llamada a una herramienta.

### Decisión

El tutor-investigador mantendrá una única responsabilidad general: producir
un borrador educativo basado en documentación oficial. Internamente realizará
dos tareas diferentes con el modelo:

1. Seleccionar hasta tres resultados relevantes mediante identificadores
   internos como `resultado-1`.
2. Redactar un `BorradorTutor` utilizando fuentes extraídas identificadas como
   `fuente-1`.

Entre ambas tareas se ejecutan de forma determinista Tavily Search y Tavily
Extract. El flujo completo es:

`buscar → seleccionar → extraer → redactar`

Las tareas de selección y redacción utilizan prompts y esquemas distintos.
No se crearán agentes adicionales para las herramientas, porque buscar y
extraer son operaciones deterministas, no decisiones autónomas.

### Seguridad y validación

- El selector solo puede devolver identificadores de la búsqueda actual.
- Las URL siempre se recuperan desde resultados validados; nunca desde texto
  generado por el modelo.
- Solo se extraen páginas pertenecientes a dominios oficiales autorizados.
- El contenido extraído se trata como información externa no confiable.
- El redactor debe utilizar citas con formato `[fuente-N]`.
- Toda fuente declarada debe estar citada.
- Toda fuente citada debe estar declarada.
- Los identificadores citados deben existir en la extracción actual.
- Una explicación no puede incluir solución ni criterios de evaluación.
- Un ejercicio debe guardar una solución privada y entre uno y cinco criterios.
- La acción del coordinador determina el tipo de borrador y el redactor no
  puede cambiarla.
- Selección y redacción permiten como máximo dos intentos cada una.
- Si una fase falla, las fases posteriores no se ejecutan.

### Estado compartido

El resultado interno del investigador se convierte en una actualización de
`EstadoTutor`.

Se conservan:

- Los resultados de búsqueda.
- Las fuentes extraídas.
- El texto completo del borrador.
- La solución y los criterios privados cuando se genera un ejercicio.

La selección intermedia y la lista temporal de URL no se incorporan al estado,
porque ya están representadas por los resultados y las fuentes finales.

### Cliente de Groq compartido

La creación del cliente y la lectura de su respuesta se trasladaron a
`cliente_groq.py`. El coordinador y el tutor-investigador reutilizan así el
mismo contrato, evitando mantener implementaciones duplicadas.

### Consecuencias positivas

- Cada fase puede probarse de manera independiente.
- Se puede demostrar qué resultado alimenta a cada herramienta posterior.
- Los errores detienen el flujo antes de consumir más créditos o tokens.
- Las URL y citas inventadas se rechazan localmente.
- El mismo investigador podrá reutilizarse en la orquestación manual y en
  LangGraph.
- Los clientes simulados permiten probar todo el recorrido sin utilizar APIs.

### Consecuencias negativas

- El flujo necesita más código que una única llamada al modelo.
- Una corrección puede consumir una segunda llamada a Groq.
- Tavily Search y Tavily Extract continúan siendo dependencias externas.
- La validación estructural no puede determinar por sí sola si cada afirmación
  está semánticamente respaldada por una fuente.

### Evidencia inicial

Una prueba real de redacción produjo correctamente una explicación sobre
`append` y `extend`, utilizó únicamente `[fuente-1]`, no inventó fuentes y
respetó todos los campos de `BorradorTutor`.

Sin embargo, también añadió la expresión técnica «se añade la referencia
completa», que no aparecía explícitamente en el fragmento proporcionado. Este
resultado confirma que las validaciones estructurales son necesarias pero no
suficientes.

Por este motivo, el tercer agente revisará durante la siguiente fase la
fidelidad semántica del borrador respecto a las fuentes antes de generar la
respuesta final.

## DT-004: evaluador independiente y ciclo limitado de corrección

**Fecha:** 30 de agosto de 2026

### Contexto

Los esquemas y validadores permiten comprobar la estructura de un borrador,
pero no garantizan que sus afirmaciones estén respaldadas por las fuentes
oficiales. Además, los ejercicios necesitan evaluar posteriormente la
respuesta del estudiante sin revelar la solución privada.

### Opciones consideradas

1. Mostrar directamente todos los borradores del tutor-investigador.
2. Pedir al propio redactor que revise su respuesta.
3. Utilizar un evaluador independiente con una única tarea.
4. Utilizar un evaluador independiente con dos tareas relacionadas.
5. Crear dos agentes evaluadores distintos.

### Decisión

Se utilizará un tercer agente evaluador independiente con dos tareas:

1. Revisar un borrador antes de mostrarlo.
2. Evaluar la respuesta del estudiante mediante la rúbrica privada.

Cada tarea utiliza un prompt y un esquema Pydantic diferente:
`RevisionBorrador` y `EvaluacionEjercicio`.

La revisión no permite al evaluador reescribir el borrador. Si detecta un
problema material, devuelve instrucciones al tutor-investigador. Solo se
permite una corrección y una segunda revisión.

La evaluación del estudiante clasifica todos los identificadores de la
rúbrica exactamente una vez como cumplidos o pendientes. El modelo no puede
inventar, omitir ni duplicar criterios.

### Seguridad y límites

- El evaluador utiliza únicamente las fuentes entregadas.
- No se ejecuta el código escrito por el estudiante.
- Una respuesta alternativa puede aceptarse si satisface la rúbrica.
- La solución esperada permanece privada.
- La retroalimentación no debe revelar la solución completa.
- Una aprobación no puede contener problemas pendientes.
- Una respuesta correcta debe obtener al menos 7 puntos.
- Una respuesta incorrecta no puede obtener 10 puntos.
- Cada llamada estructurada permite como máximo dos intentos.
- El ciclo de borrador permite dos revisiones y una corrección.

### Consecuencias positivas

- El contenido se revisa antes de mostrarse.
- Redactor y evaluador tienen responsabilidades separadas.
- Las evaluaciones pueden comprobarse objetivamente mediante criterios.
- Los ciclos están limitados y no pueden continuar indefinidamente.
- Todos los componentes pueden probarse con clientes simulados.

### Consecuencias negativas

- Cada revisión consume una llamada adicional al modelo.
- Una corrección puede necesitar dos llamadas más.
- La valoración semántica continúa dependiendo parcialmente del modelo.
- Un evaluador demasiado estricto puede rechazar contenido válido.

### Evidencia inicial

Una prueba real detectó correctamente que la expresión «append añade el
objeto como una referencia completa» no estaba respaldada por el fragmento
oficial proporcionado.

Después de ajustar el prompt, el evaluador dejó de exigir elementos
opcionales como encabezados, ejemplos, URL o citas literales cuando la
petición no los requería.


## DT-005: orquestación manual, progreso local y logging seguro

**Fecha:** 30 de agosto de 2026

### Contexto

Antes de construir la versión con LangGraph se necesita una implementación
manual que muestre explícitamente cómo pasan los datos entre coordinador,
herramientas, tutor-investigador y evaluador.

También es necesario guardar el progreso y registrar eventos técnicos sin
publicar datos personales o información privada.

### Decisión de orquestación

La implementación manual utiliza funciones Python explícitas y un
`EstadoTutor` compartido.

El flujo principal es:

`entrada → coordinador → ruta seleccionada → respuesta final`

Las rutas posibles son:

- `pedir_aclaracion`: termina sin utilizar herramientas.
- `responder_consulta`: investiga, redacta y revisa una explicación.
- `generar_ejercicio`: investiga, redacta y revisa un ejercicio.
- `evaluar_respuesta`: reutiliza ejercicio, rúbrica y fuentes anteriores.

El coordinador recibe un JSON mínimo con la entrada actual, la existencia de
un ejercicio activo, la tecnología de contexto y el número de mensajes
anteriores. No recibe la solución privada, las fuentes completas ni el
historial textual.

### Persistencia del progreso

El progreso se guarda localmente en un JSON versionado. Cada intento incluye:

- Fecha UTC.
- Tecnología.
- Título del ejercicio.
- Puntuación.
- Resultado correcto o incorrecto.
- Identificadores de criterios cumplidos y pendientes.

No se guardan la respuesta del estudiante, la solución esperada ni el
contenido de las fuentes.

La escritura es atómica: primero se genera un archivo temporal en el mismo
directorio y después se reemplaza el historial definitivo. Si el guardado
falla, la evaluación continúa mostrándose y el estado registra el error.

### Logging

Se utiliza el módulo estándar `logging` con:

- Salida de consola.
- Archivo rotativo de 1 MB.
- Tres copias anteriores.
- Eventos JSON estructurados.
- Lista cerrada de nombres y campos permitidos.

No se registran claves, prompts, respuestas del estudiante, soluciones,
contenido de fuentes ni mensajes internos de excepciones.

### Tratamiento de límites externos

Los reintentos automáticos del SDK de Groq se desactivan con
`max_retries=0`. Los agentes mantienen sus propios reintentos limitados para
errores de estructura, pero un límite HTTP 429 se comunica rápidamente como
un error controlado.

La terminal también captura `KeyboardInterrupt` durante una llamada externa
para cerrar sin mostrar un traceback.

### Consecuencias positivas

- El flujo completo puede seguirse paso a paso.
- Cada ruta puede probarse sin APIs mediante inyección de dependencias.
- El estado conserva el ejercicio necesario entre turnos.
- El progreso personal no se publica en Git.
- Los logs permiten observar el flujo sin almacenar contenido sensible.
- La implementación servirá como referencia para comparar con LangGraph.

### Consecuencias negativas

- La orquestación manual requiere más código propio.
- Las firmas contienen varios clientes opcionales para facilitar las pruebas.
- El progreso local no gestiona todavía múltiples estudiantes.
- Un límite temporal de una API obliga al usuario a reintentar más tarde.

### Evidencia inicial

La suite alcanzó 565 pruebas superadas.

La primera ejecución real recorrió coordinador, búsqueda, selección,
extracción, redacción y primera revisión. El evaluador solicitó una
corrección, pero Groq devolvió HTTP 429 durante esa llamada. El flujo previo
funcionó correctamente y el límite externo permitió detectar la necesidad de
desactivar los reintentos internos del SDK y controlar `Ctrl+C`.
