import os  # Permite consultar variables de entorno.
from pathlib import Path  # Permite construir rutas independientes del sistema operativo.

from dotenv import load_dotenv  # Permite cargar las variables guardadas en .env.


# Obtiene la carpeta que contiene este archivo: tutor_multiagente.
DIRECTORIO_PAQUETE = Path(__file__).resolve().parent

# Obtiene la carpeta principal del proyecto final: nivel_experto.
DIRECTORIO_PROYECTO = DIRECTORIO_PAQUETE.parent

# Obtiene la raíz del repositorio, donde está guardado el archivo .env.
DIRECTORIO_REPOSITORIO = DIRECTORIO_PROYECTO.parent

# Construye explícitamente la ruta del archivo .env compartido.
RUTA_ENV = DIRECTORIO_REPOSITORIO / ".env"

# Carga las variables sin depender del directorio desde el que se ejecute Python.
load_dotenv(dotenv_path=RUTA_ENV)


# Rutas utilizadas por los distintos módulos del proyecto.
RUTA_CATALOGO_FUENTES = (
    DIRECTORIO_PROYECTO / "datos" / "fuentes_oficiales.json"
)
RUTA_DIRECTORIO_PROGRESO = DIRECTORIO_PROYECTO / "datos" / "progreso"
RUTA_DIRECTORIO_LOGS = DIRECTORIO_PROYECTO / "logs"
# Archivo que contiene los casos utilizados para evaluar el agente.
RUTA_CASOS_EVALUACION = (
    DIRECTORIO_PROYECTO / "evaluacion" / "casos_prueba.json"
)


# Modelo que utilizarán los tres agentes en Groq.
MODELO_GROQ = "openai/gpt-oss-20b"

# Tiempo máximo de espera para una llamada al modelo.
TIMEOUT_GROQ = 30

# Desactiva los reintentos automáticos internos del SDK.
# Nuestros agentes ya controlan sus ciclos y errores explícitamente.
MAX_REINTENTOS_SDK_GROQ = 0

# Número máximo de reintentos cuando Groq devuelve HTTP 429.
# Permite varias esperas consecutivas, pero evita un bucle infinito.
MAX_REINTENTOS_LIMITE_GROQ = 3

# Evita bloquear la terminal si el proveedor solicita una espera excesiva.
# Dos minutos permiten recuperarse de límites temporales del plan gratuito.
MAX_ESPERA_REINTENTO_GROQ = 120

# Límite máximo para la salida y el razonamiento del coordinador.
MAX_TOKENS_COORDINADOR = 1_000

# Número total de intentos permitidos para obtener una decisión válida.
MAX_INTENTOS_COORDINADOR = 2

# Máximo de tokens para seleccionar resultados de búsqueda.
MAX_TOKENS_SELECCION = 1_000

# Número total de intentos para obtener una selección válida.
MAX_INTENTOS_SELECCION = 2

# Tokens máximos para redactar una explicación o ejercicio completo.
# El borrador necesita más espacio que una decisión o selección breve.
MAX_TOKENS_BORRADOR = 4_000

# Permite una llamada inicial y una única corrección del borrador.
# Evita ciclos indefinidos y controla el consumo de tokens.
MAX_INTENTOS_BORRADOR = 2

# Tokens máximos para revisar un borrador documentado.
# La revisión es más breve que el borrador, pero debe justificar su decisión.
MAX_TOKENS_REVISION = 1_500

# Permite corregir una salida de evaluación mal formada o incoherente.
MAX_INTENTOS_REVISION = 2

# Permite evaluar el borrador inicial y una única versión corregida.
# Este límite controla el ciclo entre redactor y evaluador.
MAX_REVISIONES_BORRADOR = 2

# Tokens máximos para evaluar la respuesta de un estudiante.
# La evaluación necesita justificar la nota sin generar textos extensos.
MAX_TOKENS_EVALUACION = 1_500

# Permite una llamada inicial y una corrección si la salida es inválida.
MAX_INTENTOS_EVALUACION = 2

# Límites para controlar el consumo y evitar bucles infinitos.
MAX_RESULTADOS_BUSQUEDA = 5
MAX_BUSQUEDAS_POR_TURNO = 3
MAX_EXTRACCIONES_POR_TURNO = 3
MAX_FRAGMENTOS_POR_FUENTE = 3
MAX_CARACTERES_EXTRAIDOS = 12_000

# Conserva como máximo diez intercambios usuario-asistente.
# Evita que el estado y los futuros prompts crezcan indefinidamente.
MAX_MENSAJES_HISTORIAL = 20

# Número máximo de pasos internos permitidos en un turno de LangGraph.
# El recorrido más largo previsto utiliza seis nodos, por lo que diez
# permite completarlo sin aceptar un posible bucle infinito.
MAX_PASOS_LANGGRAPH = 10

# Configuración de bajo consumo para Tavily.

# Prioriza resultados precisos para que el investigador pueda
# identificar documentación directamente relacionada con la consulta.
PROFUNDIDAD_BUSQUEDA = "advanced"

# La extracción básica es suficiente para recuperar texto y Markdown.
PROFUNDIDAD_EXTRACCION = "basic"
FORMATO_EXTRACCION = "markdown"


def obtener_variable_entorno(nombre: str) -> str:
    """
    Obtiene una variable de entorno obligatoria.

    Args:
        nombre: Nombre exacto de la variable que se quiere recuperar.

    Returns:
        Valor de la variable, sin espacios exteriores.

    Raises:
        ValueError: Si el nombre recibido está vacío.
        RuntimeError: Si la variable no existe o no contiene un valor.
    """
    # Evita consultar variables utilizando nombres vacíos o inválidos.
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("El nombre de la variable de entorno no puede estar vacío.")

    # Recupera la variable utilizando el nombre ya normalizado.
    nombre_normalizado = nombre.strip()
    valor = os.getenv(nombre_normalizado)

    # Detiene la operación si falta una configuración obligatoria.
    if valor is None or not valor.strip():
        raise RuntimeError(
            f"La variable de entorno obligatoria '{nombre_normalizado}' no está definida."
        )

    # Devuelve el valor sin espacios accidentales al principio o al final.
    return valor.strip()
