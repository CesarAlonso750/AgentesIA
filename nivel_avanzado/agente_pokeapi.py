import json  # Permite analizar los argumentos JSON generados por el modelo
import os  # Permite leer variables de entorno
import sys  # Permite terminar el programa si falta la clave

from dotenv import load_dotenv  # Carga las variables definidas en .env
from groq import Groq  # Cliente oficial para llamar a los modelos de Groq

from pokeapi_tools import (  # Importa las funciones locales ya probadas
    consultar_item,
    consultar_pokemon,
)


# Carga las variables del archivo .env.
load_dotenv()

# Obtiene la clave sin escribirla directamente en el código.
api_key = os.getenv("GROQ_API_KEY")

# Detiene el programa si la clave no está configurada.
if not api_key:
    print("Error: la variable GROQ_API_KEY no está definida.")
    sys.exit(1)

# Modelo actual recomendado por Groq para sustituir Llama 3.1 8B.
MODELO = "openai/gpt-oss-20b"

# Evita que el modelo solicite herramientas indefinidamente.
MAX_ITERACIONES_HERRAMIENTAS = 5

# Crea el cliente que se comunicará con Groq.
client = Groq(api_key=api_key)


# Define las reglas, límites y fuentes autorizadas del agente.
SYSTEM_PROMPT = (
    # Establece el rol y el idioma de respuesta.
    "Eres un asistente especializado en información de Pokémon. "
    "Responde siempre en español. "

    # Indica cuándo debe utilizar las herramientas.
    "Utiliza las herramientas disponibles cuando necesites datos de "
    "Pokémon u objetos. "

    # Impide complementar los resultados con conocimiento interno.
    "Los resultados de las herramientas son tu única fuente autorizada "
    "para afirmar datos sobre Pokémon y objetos. "
    "No añadas información procedente de tu memoria o entrenamiento. "

    # Limita la respuesta a los campos solicitados.
    "Responde únicamente con los datos solicitados por el usuario. "
    "Si la pregunta es general, resume solamente los campos devueltos "
    "por la herramienta correspondiente. "

    # Prohíbe inventar información que nuestras funciones no devuelven.
    "No inventes tipos, evoluciones, generaciones, habilidades, precios "
    "ni otros campos que la herramienta no haya devuelto. "

    # Explica la limitación cuando el usuario pide campos no disponibles.
    "Si el usuario solicita un dato que las herramientas no proporcionan, "
    "explica que ese dato no está disponible con las herramientas actuales. "

    # Evita ejecutar herramientas si falta el recurso concreto.
    "Si el usuario no identifica claramente el Pokémon o el objeto, "
    "pide una aclaración antes de solicitar una herramienta. "

    # Obliga a comprobar nombres o identificadores posiblemente inventados.
    "Cuando el usuario proporcione un nombre o ID concreto y el dato no "
    "esté ya verificado en el historial, solicita siempre la herramienta "
    "correspondiente, aunque el nombre parezca inventado o incorrecto. "
    "Nunca afirmes que un Pokémon u objeto no existe salvo que una "
    "herramienta haya devuelto ese error. "

    # Indica cómo actuar ante errores controlados de las herramientas.
    "Si una herramienta devuelve un error, explícalo y pide al usuario "
    "que corrija el nombre o identificador."
)

# Lista de herramientas que el modelo podrá solicitar.
# Estas definiciones describen las funciones, pero no las ejecutan.
HERRAMIENTAS = [
    {
        # Indica que la herramienta representa una función local.
        "type": "function",
        "function": {
            # Debe coincidir exactamente con el nombre de la función Python.
            "name": "consultar_pokemon",

            # Ayuda al modelo a decidir cuándo debe utilizarla.
            "description": (
                "Consulta un Pokémon en PokeAPI por su nombre oficial "
                "o ID y devuelve su nombre, altura en metros y peso "
                "en kilogramos."
            ),

            # Define los argumentos que el modelo puede proporcionar.
            "parameters": {
                "type": "object",
                "properties": {
                    "identificador": {
                        # Pedimos texto para simplificar el esquema.
                        # Un ID se representará como texto, por ejemplo "25".
                        "type": "string",
                        "description": (
                            "Nombre oficial del Pokémon en minúsculas, "
                            "como 'pikachu' o 'mr-mime', o su ID positivo "
                            "escrito como texto, como '25'. No debe ser una URL."
                        ),
                    }
                },

                # El modelo debe proporcionar obligatoriamente este argumento.
                "required": ["identificador"],

                # Declara que no existen otros argumentos admitidos.
                "additionalProperties": False,
            },
        },
    },
    {
        # Esta segunda herramienta representa una función distinta.
        "type": "function",
        "function": {
            # Debe coincidir con consultar_item() en pokeapi_tools.py.
            "name": "consultar_item",

            # Explica cuándo utilizar el endpoint de objetos.
            "description": (
                "Consulta un objeto de Pokémon en PokeAPI por su nombre "
                "oficial o ID y devuelve su nombre, categoría y efecto breve."
            ),

            # Esta herramienta tiene su propio esquema independiente.
            "parameters": {
                "type": "object",
                "properties": {
                    "identificador": {
                        "type": "string",
                        "description": (
                            "Nombre oficial del objeto en minúsculas, "
                            "como 'master-ball' o 'potion', o su ID positivo "
                            "escrito como texto. No debe ser una URL."
                        ),
                    }
                },
                "required": ["identificador"],
                "additionalProperties": False,
            },
        },
    },
]

# Relaciona exclusivamente los nombres permitidos con funciones reales.
# No utilizamos eval() ni globals(), porque permitirían ejecutar
# nombres que no hubiéramos autorizado expresamente.
FUNCIONES_DISPONIBLES = {
    "consultar_pokemon": consultar_pokemon,
    "consultar_item": consultar_item,
}


def ejecutar_llamada_herramienta(llamada) -> dict:
    """Valida y ejecuta una llamada de herramienta solicitada por el modelo."""

    # Obtiene el nombre propuesto por el modelo.
    nombre_funcion = llamada.function.name

    # Rechaza nombres ausentes o con un tipo inesperado.
    if not isinstance(nombre_funcion, str):
        return {
            "ok": False,
            "error": "La llamada no contiene un nombre de herramienta válido.",
        }

    # Busca el nombre únicamente dentro de la lista permitida.
    funcion = FUNCIONES_DISPONIBLES.get(nombre_funcion)

    # Impide ejecutar herramientas inventadas por el modelo.
    if funcion is None:
        return {
            "ok": False,
            "error": f"La herramienta '{nombre_funcion}' no está permitida.",
        }

    # Los argumentos llegan desde Groq como una cadena JSON.
    argumentos_json = llamada.function.arguments

    # Comprueba el tipo antes de intentar analizar el contenido.
    if not isinstance(argumentos_json, str):
        return {
            "ok": False,
            "error": "Los argumentos de la herramienta no son texto JSON.",
        }

    try:
        # Convierte el texto JSON en un valor de Python.
        argumentos = json.loads(argumentos_json)

    except json.JSONDecodeError:
        # Un modelo puede generar JSON incompleto o mal formado.
        return {
            "ok": False,
            "error": "Los argumentos de la herramienta no contienen JSON válido.",
        }

    # El esquema exige un objeto JSON, no una lista ni un valor simple.
    if not isinstance(argumentos, dict):
        return {
            "ok": False,
            "error": "Los argumentos deben formar un objeto JSON.",
        }

    # Comprueba explícitamente la presencia del único argumento obligatorio.
    if "identificador" not in argumentos:
        return {
            "ok": False,
            "error": "Falta el argumento obligatorio 'identificador'.",
        }

    # Detecta parámetros adicionales aunque el esquema indique
    # additionalProperties=False.
    argumentos_adicionales = set(argumentos) - {"identificador"}

    if argumentos_adicionales:
        # Ordena los nombres para generar un error estable y fácil de leer.
        nombres_adicionales = ", ".join(sorted(argumentos_adicionales))

        return {
            "ok": False,
            "error": (
                "La llamada contiene argumentos no permitidos: "
                f"{nombres_adicionales}."
            ),
        }

    try:
        # Pasa explícitamente el único argumento permitido.
        # No usamos **argumentos para evitar ejecutar parámetros inesperados.
        resultado = funcion(
            identificador=argumentos["identificador"],
        )

    except (TypeError, ValueError) as error:
        # Captura los errores generados por validar_identificador().
        return {
            "ok": False,
            "error": str(error),
        }

    except Exception:
        # Evita que un fallo imprevisto cierre el agente o revele
        # detalles internos al modelo.
        return {
            "ok": False,
            "error": "La herramienta produjo un error interno inesperado.",
        }

    # Las funciones normales ya devuelven diccionarios estructurados.
    return resultado


def solicitar_respuesta_modelo(mensajes):
    """Envía la conversación y las herramientas disponibles al modelo."""

    # Realiza una llamada permitiendo que el modelo decida
    # si necesita utilizar cero, una o varias herramientas.
    return client.chat.completions.create(
        # Utiliza el modelo configurado al comienzo del programa.
        model=MODELO,

        # Envía todos los mensajes acumulados hasta este momento.
        messages=mensajes,

        # Describe las funciones locales que el modelo puede solicitar.
        tools=HERRAMIENTAS,

        # Permite que el modelo responda directamente o solicite herramientas.
        tool_choice="auto",

        # Reduce la variación al generar argumentos estructurados.
        temperature=0,
    )


def procesar_llamadas_herramienta(
    mensajes,
    mensaje_asistente,
) -> int:
    """Ejecuta todas las herramientas solicitadas y añade sus resultados."""

    # Obtiene la lista de llamadas. Si el modelo no solicitó ninguna,
    # utilizamos una lista vacía.
    llamadas = mensaje_asistente.tool_calls or []

    # Esta función solo debe procesar mensajes que contengan herramientas.
    if not llamadas:
        return 0

    # Añade primero el mensaje del asistente que contiene las solicitudes.
    # Los resultados posteriores deben hacer referencia a estas llamadas.
    mensajes.append(mensaje_asistente)

    # Recorre todas las herramientas solicitadas.
    # No asumimos que siempre habrá solamente una.
    for llamada in llamadas:
        # Muestra qué función ha pedido ejecutar el modelo.
        print(f"Ejecutando herramienta: {llamada.function.name}")

        # Valida y ejecuta la llamada mediante el ejecutor seguro.
        resultado = ejecutar_llamada_herramienta(llamada)

        # Convierte el diccionario en texto JSON.
        # El campo content de un mensaje tool debe ser texto.
        resultado_json = json.dumps(
            resultado,
            ensure_ascii=False,
        )

        # Añade el resultado asociado al identificador exacto
        # de la llamada que produjo el modelo.
        mensajes.append(
            {
                "role": "tool",
                "tool_call_id": llamada.id,
                "name": llamada.function.name,
                "content": resultado_json,
            }
        )

    # Devuelve cuántas herramientas se han procesado.
    return len(llamadas)


def ejecutar_turno_agente(
    mensajes,
    pregunta: str,
) -> str:
    """Procesa un turno hasta obtener una respuesta final del modelo."""

    # Valida la entrada recibida antes de enviarla al modelo.
    if not isinstance(pregunta, str):
        return "Error: la pregunta debe ser texto."

    # Elimina espacios exteriores.
    pregunta_normalizada = pregunta.strip()

    # Impide enviar una pregunta vacía.
    if not pregunta_normalizada:
        return "Error: la pregunta no puede estar vacía."

    # Añade la pregunta al historial de la conversación.
    mensajes.append(
        {
            "role": "user",
            "content": pregunta_normalizada,
        }
    )

    # Limita el número total de rondas de herramientas.
    for _ in range(MAX_ITERACIONES_HERRAMIENTAS):
        try:
            # Envía al modelo el historial y los esquemas de herramientas.
            respuesta = solicitar_respuesta_modelo(mensajes)

        except Exception:
            # Evita cerrar el programa o mostrar información interna
            # si Groq devuelve un error.
            return "No se pudo obtener una respuesta del modelo."

        # Extrae el mensaje generado en esta iteración.
        mensaje_asistente = respuesta.choices[0].message

        # Si existen tool_calls, las ejecuta todas y continúa el bucle.
        if mensaje_asistente.tool_calls:
            procesar_llamadas_herramienta(
                mensajes,
                mensaje_asistente,
            )
            continue

        # Si no hay herramientas, esperamos una respuesta textual final.
        contenido_final = mensaje_asistente.content

        # Controla una respuesta vacía o con un tipo inesperado.
        if not isinstance(contenido_final, str) or not contenido_final.strip():
            return "El modelo no generó una respuesta final válida."

        # Conserva la respuesta final para los siguientes turnos.
        mensajes.append(mensaje_asistente)

        # Devuelve únicamente el texto limpio al usuario.
        return contenido_final.strip()

    # Si se alcanza el límite, detenemos el ciclo de forma controlada.
    return (
        "El agente alcanzó el límite de iteraciones "
        "sin generar una respuesta final."
    )


def main() -> None:
    """Mantiene una conversación de terminal con el agente."""

    # Crea el historial inicial con las reglas del agente.
    # La lista se mantiene fuera del bucle para conservar el contexto.
    mensajes = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Informa de los comandos disponibles.
    print("Agente de PokeAPI iniciado.")
    print("Escribe 'salir' para terminar.")
    print("-" * 40)

    # Mantiene la conversación hasta recibir el comando de salida.
    while True:
        # Lee la pregunta y elimina espacios exteriores.
        pregunta = input("Tú: ").strip()

        # Finaliza sin enviar la palabra "salir" al modelo.
        if pregunta.lower() == "salir":
            print("Saliendo...")
            break

        # Evita procesar entradas vacías.
        if not pregunta:
            print("Escribe una pregunta antes de continuar.")
            print("-" * 40)
            continue

        # Ejecuta todas las rondas de herramientas necesarias
        # hasta obtener una respuesta final.
        respuesta_final = ejecutar_turno_agente(
            mensajes,
            pregunta,
        )

        # Muestra la respuesta final en lenguaje natural.
        print("Agente:", respuesta_final)

        # Separa visualmente los turnos.
        print("-" * 40)


# Ejecuta el chatbot solo cuando abrimos este archivo directamente.
# Evita iniciar el bucle al importarlo desde pruebas u otros módulos.
if __name__ == "__main__":
    main()