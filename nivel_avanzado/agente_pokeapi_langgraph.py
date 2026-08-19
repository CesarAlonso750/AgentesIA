import json  # Permite convertir los resultados de herramientas a texto JSON
import os  # Permite leer variables de entorno
import sys  # Permite terminar el programa si falta la clave

from dotenv import load_dotenv  # Carga las variables definidas en .env
from langchain.messages import (  # Proporciona mensajes estructurados
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain.tools import tool  # Convierte funciones Python en herramientas
from langchain_groq import ChatGroq  # Integra Groq con LangChain
from langgraph.graph import (  # Proporciona el estado, nodos y extremos del grafo
    END,
    START,
    MessagesState,
    StateGraph,
)

from pokeapi_tools import (  # Importa las funciones normales ya validadas
    consultar_item as consultar_item_api,
    consultar_pokemon as consultar_pokemon_api,
)


# Carga las variables del archivo .env.
load_dotenv()

# Obtiene la clave de Groq desde el entorno.
api_key = os.getenv("GROQ_API_KEY")

# Detiene el programa si falta la configuración necesaria.
if not api_key:
    print("Error: la variable GROQ_API_KEY no está definida.")
    sys.exit(1)

# Modelo recomendado para sustituir Llama 3.1 8B.
MODELO = "openai/gpt-oss-20b"

# Limita el número de pasos internos del grafo.
# Cinco rondas modelo-herramienta y una respuesta final
# necesitan como máximo unos once pasos.
LIMITE_RECURSION = 12

# Define las reglas y fuentes autorizadas del agente.
SYSTEM_PROMPT = (
    "Eres un asistente especializado en información de Pokémon. "
    "Responde siempre en español. "
    "Utiliza las herramientas disponibles cuando necesites datos de "
    "Pokémon u objetos. "
    "Los resultados de las herramientas son tu única fuente autorizada "
    "para afirmar datos sobre Pokémon y objetos. "
    "No añadas información procedente de tu memoria o entrenamiento. "
    "Responde únicamente con los datos solicitados por el usuario. "
    "Si la pregunta es general, resume solamente los campos devueltos "
    "por la herramienta correspondiente. "
    "No inventes tipos, evoluciones, generaciones, habilidades, precios "
    "ni otros campos que la herramienta no haya devuelto. "
    "Si el usuario solicita un dato que las herramientas no proporcionan, "
    "explica que ese dato no está disponible con las herramientas actuales. "
    "Si el usuario no identifica claramente el Pokémon o el objeto, "
    "pide una aclaración antes de solicitar una herramienta. "
    "Cuando el usuario proporcione un nombre o ID concreto y el dato no "
    "esté ya verificado en el historial, solicita siempre la herramienta "
    "correspondiente, aunque el nombre parezca inventado o incorrecto. "
    "Nunca afirmes que un Pokémon u objeto no existe salvo que una "
    "herramienta haya devuelto ese error. "
    "Si una herramienta devuelve un error, explícalo y pide al usuario "
    "que corrija el nombre o identificador."
)

@tool
def consultar_pokemon(identificador: str) -> dict:
    """Consulta nombre, altura y peso de un Pokémon por nombre oficial o ID."""

    # Delega la validación y la petición a la función normal ya probada.
    return consultar_pokemon_api(identificador)


@tool
def consultar_item(identificador: str) -> dict:
    """Consulta nombre, categoría y efecto de un objeto por nombre oficial o ID."""

    # Reutiliza la misma validación y comportamiento que la versión básica.
    return consultar_item_api(identificador)


# Agrupa las herramientas que se mostrarán al modelo.
HERRAMIENTAS = [
    consultar_pokemon,
    consultar_item,
]

# Relaciona exclusivamente los nombres permitidos con las funciones
# normales que contienen la validación y las peticiones HTTP.
FUNCIONES_DISPONIBLES = {
    "consultar_pokemon": consultar_pokemon_api,
    "consultar_item": consultar_item_api,
}

# Crea el modelo de chat sin herramientas todavía vinculadas.
llm = ChatGroq(
    api_key=api_key,
    model=MODELO,
    temperature=0,
)

# Entrega al modelo los esquemas generados por @tool.
modelo_con_herramientas = llm.bind_tools(HERRAMIENTAS)

def nodo_modelo(state: MessagesState) -> dict:
    """Permite que el modelo responda o solicite herramientas."""

    try:
        # Envía al modelo todos los mensajes acumulados en el estado.
        # El modelo también recibe los esquemas vinculados anteriormente.
        respuesta = modelo_con_herramientas.invoke(
            state["messages"],
        )

    except Exception as error:
        # Informa de que el fallo ocurrió durante la llamada al modelo.
        print(f"Error al llamar al modelo: {error}")

        # Propaga la excepción para que el nivel exterior pueda
        # detener el turno de manera controlada.
        raise

    # Devuelve únicamente el mensaje nuevo.
    # MessagesState se encargará de añadirlo al historial.
    return {
        "messages": [respuesta],
    }


def ejecutar_llamada_herramienta(llamada) -> dict:
    """Valida y ejecuta una llamada normalizada por LangChain."""

    # LangChain representa cada tool call mediante un diccionario.
    if not isinstance(llamada, dict):
        return {
            "ok": False,
            "error": "La llamada de herramienta tiene un formato inválido.",
        }

    # Obtiene el nombre solicitado por el modelo.
    nombre_funcion = llamada.get("name")

    # Rechaza nombres ausentes o con tipos inesperados.
    if not isinstance(nombre_funcion, str):
        return {
            "ok": False,
            "error": "La llamada no contiene un nombre de herramienta válido.",
        }

    # Busca la función únicamente en la lista blanca.
    funcion = FUNCIONES_DISPONIBLES.get(nombre_funcion)

    # Impide ejecutar nombres inventados por el modelo.
    if funcion is None:
        return {
            "ok": False,
            "error": f"La herramienta '{nombre_funcion}' no está permitida.",
        }

    # LangChain ya transforma el JSON de argumentos en un diccionario.
    argumentos = llamada.get("args")

    # No confiamos en que esa transformación siempre produzca
    # la estructura que espera nuestra función.
    if not isinstance(argumentos, dict):
        return {
            "ok": False,
            "error": "Los argumentos deben formar un objeto.",
        }

    # Comprueba que existe el único argumento obligatorio.
    if "identificador" not in argumentos:
        return {
            "ok": False,
            "error": "Falta el argumento obligatorio 'identificador'.",
        }

    # Detecta cualquier parámetro adicional inventado.
    argumentos_adicionales = set(argumentos) - {"identificador"}

    if argumentos_adicionales:
        # Ordena los nombres para obtener mensajes de error estables.
        nombres_adicionales = ", ".join(sorted(argumentos_adicionales))

        return {
            "ok": False,
            "error": (
                "La llamada contiene argumentos no permitidos: "
                f"{nombres_adicionales}."
            ),
        }

    try:
        # Entrega explícitamente el único argumento permitido.
        # La función normal vuelve a validar su tipo, formato y contenido.
        resultado = funcion(
            identificador=argumentos["identificador"],
        )

    except (TypeError, ValueError) as error:
        # Convierte los errores de validación en resultados estructurados.
        return {
            "ok": False,
            "error": str(error),
        }

    except Exception:
        # Evita exponer detalles internos de errores inesperados.
        return {
            "ok": False,
            "error": "La herramienta produjo un error interno inesperado.",
        }

    # Devuelve el diccionario generado por consultar_pokemon
    # o consultar_item.
    return resultado


def nodo_herramientas(state: MessagesState) -> dict:
    """Ejecuta todas las herramientas solicitadas por el último mensaje."""

    # Obtiene el último mensaje generado por el modelo.
    ultimo_mensaje = state["messages"][-1]

    # Obtiene las tool calls o utiliza una lista vacía.
    llamadas = ultimo_mensaje.tool_calls or []

    # Lista de resultados que se añadirá a MessagesState.
    mensajes_herramienta = []

    # Procesa todas las llamadas solicitadas en esta iteración.
    for llamada in llamadas:
        # El identificador relaciona la solicitud del modelo
        # con el ToolMessage que contiene su resultado.
        identificador_llamada = llamada.get("id")

        # No ejecutamos una herramienta si después no podemos
        # asociar su resultado con la solicitud original.
        if (
            not isinstance(identificador_llamada, str)
            or not identificador_llamada
        ):
            raise ValueError(
                "La llamada de herramienta no contiene un ID válido."
            )

        # Obtiene el nombre únicamente para mostrarlo y etiquetar el mensaje.
        nombre_funcion = llamada.get("name")

        # Utiliza un nombre seguro si el valor original no es texto.
        nombre_mensaje = (
            nombre_funcion
            if isinstance(nombre_funcion, str)
            else "herramienta_desconocida"
        )

        # Informa de la herramienta que se va a validar y ejecutar.
        print(f"Ejecutando herramienta: {nombre_mensaje}")

        # Ejecuta la llamada mediante todas las validaciones anteriores.
        resultado = ejecutar_llamada_herramienta(llamada)

        # ToolMessage requiere contenido textual.
        resultado_json = json.dumps(
            resultado,
            ensure_ascii=False,
        )

        # Crea un mensaje asociado al tool_call_id original.
        mensajes_herramienta.append(
            ToolMessage(
                content=resultado_json,
                tool_call_id=identificador_llamada,
                name=nombre_mensaje,
            )
        )

    # MessagesState añadirá todos los ToolMessage al historial.
    return {
        "messages": mensajes_herramienta,
    }


def decidir_siguiente_paso(state: MessagesState):
    """Decide si ejecutar herramientas o terminar el grafo."""

    # Obtiene el historial acumulado.
    mensajes = state.get("messages", [])

    # Termina de forma segura si el estado no contiene mensajes.
    if not mensajes:
        return END

    # Examina únicamente el último mensaje generado.
    ultimo_mensaje = mensajes[-1]

    # Obtiene las tool calls sin asumir que cualquier tipo
    # de mensaje tenga necesariamente ese atributo.
    llamadas = getattr(
        ultimo_mensaje,
        "tool_calls",
        None,
    )

    # Si el modelo solicitó una o varias herramientas,
    # dirige la ejecución al nodo correspondiente.
    if llamadas:
        return "herramientas"

    # Si no hay tool calls, el mensaje contiene la respuesta final.
    return END


# Construye un grafo cuyo estado acumula mensajes estructurados.
constructor = StateGraph(MessagesState)

# Registra el nodo que llama al modelo.
constructor.add_node(
    "modelo",
    nodo_modelo,
)

# Registra el nodo que valida y ejecuta herramientas.
constructor.add_node(
    "herramientas",
    nodo_herramientas,
)

# Cada ejecución comienza consultando al modelo.
constructor.add_edge(
    START,
    "modelo",
)

# Después del modelo, decide entre ejecutar herramientas o terminar.
constructor.add_conditional_edges(
    "modelo",
    decidir_siguiente_paso,
    [
        "herramientas",
        END,
    ],
)

# Después de entregar resultados, vuelve a consultar al modelo.
constructor.add_edge(
    "herramientas",
    "modelo",
)

# Valida la estructura y crea el grafo ejecutable.
graph = constructor.compile()


def main() -> None:
    """Mantiene una conversación de terminal usando el grafo."""

    # Crea el estado inicial con las reglas del agente.
    estado: MessagesState = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
        ]
    }

    # Informa de cómo terminar la conversación.
    print("Agente de PokeAPI con LangGraph iniciado.")
    print("Escribe 'salir' para terminar.")
    print("-" * 40)

    # Mantiene el agente activo durante varios turnos.
    while True:
        # Lee y limpia la entrada del usuario.
        pregunta = input("Tú: ").strip()

        # Finaliza sin añadir "salir" al historial.
        if pregunta.lower() == "salir":
            print("Saliendo...")
            break

        # Evita ejecutar el grafo con una entrada vacía.
        if not pregunta:
            print("Escribe una pregunta antes de continuar.")
            print("-" * 40)
            continue

        # Construye una entrada nueva sin modificar todavía el estado válido.
        # Si el grafo falla, conservaremos el historial anterior.
        estado_entrada: MessagesState = {
            "messages": [
                *estado["messages"],
                HumanMessage(content=pregunta),
            ]
        }

        try:
            # Ejecuta el ciclo modelo-herramientas-modelo
            # hasta alcanzar una respuesta final o el límite.
            nuevo_estado = graph.invoke(
                estado_entrada,
                config={
                    "recursion_limit": LIMITE_RECURSION,
                },
            )

        except Exception:
            # Evita cerrar el programa y no reemplaza el último
            # estado válido si el grafo produce un error.
            print("No se pudo completar este turno del agente.")
            print("-" * 40)
            continue

        # Sustituye el estado únicamente después de una ejecución correcta.
        estado = nuevo_estado

        # El último mensaje debe ser la respuesta final del modelo.
        ultimo_mensaje = estado["messages"][-1]
        contenido_final = ultimo_mensaje.content

        # Comprueba que la salida sea texto no vacío.
        if (
            not isinstance(contenido_final, str)
            or not contenido_final.strip()
        ):
            print("El modelo no generó una respuesta final válida.")
            print("-" * 40)
            continue

        # Muestra solo el contenido, sin metadatos de LangChain.
        print("Agente:", contenido_final.strip())
        print("-" * 40)


# Ejecuta el terminal únicamente al abrir este archivo directamente.
if __name__ == "__main__":
    main()