import json  # Permite guardar la conversación en formato JSON
import os  # Permite acceder a las variables de entorno
import sys  # Permite terminar el programa si falta la clave de API
from datetime import datetime  # Permite incluir fecha y hora en el archivo

from dotenv import load_dotenv  # Carga las variables definidas en .env
from langchain.messages import (  # Proporciona mensajes estructurados para el chat
    HumanMessage,  # Representa un mensaje escrito por el usuario
    SystemMessage,  # Representa las instrucciones generales del asistente
)
from langchain_groq import ChatGroq  # Integra los modelos de Groq con LangChain
from langgraph.graph import (  # Proporciona los elementos necesarios para el grafo
    END,  # Representa el final del recorrido por el grafo
    START,  # Representa el comienzo del recorrido por el grafo
    MessagesState,  # Estado preparado para acumular mensajes estructurados
    StateGraph,  # Permite construir un grafo basado en un estado compartido
)

load_dotenv()  # Carga GROQ_API_KEY u otras variables desde .env
api_key = os.getenv("GROQ_API_KEY") # Obtiene la clave de API de Groq desde las variables de entorno
if not api_key:
    print("Error: variable de entorno GROQ_API_KEY no definida.")
    sys.exit(1)

# Define el comportamiento general que mantendrá el asistente.
# Usamos el mismo prompt que en la versión sin LangGraph
# para que ambas implementaciones sean comparables.
SYSTEM_PROMPT = (
    "Eres un tutor de programación paciente. "
    "Responde siempre en español, explica los conceptos paso a paso "
    "y utiliza ejemplos sencillos."
)

def convertir_mensaje_a_diccionario(mensaje):
    """Convierte un mensaje de LangChain en un diccionario serializable."""

    # Relaciona los tipos utilizados por LangChain con los roles
    # habituales de una conversación.
    roles = {
        "system": "system",
        "human": "user",
        "ai": "assistant",
    }

    # Obtiene el rol equivalente.
    # Si aparece un tipo desconocido, conserva su nombre original
    # para no perder información.
    role = roles.get(mensaje.type, mensaje.type)

    # Devuelve únicamente los datos necesarios para reconstruir
    # y leer fácilmente la conversación.
    return {
        "role": role,
        "content": mensaje.content,
    }
    
def guardar_historial(historial):
    """Guarda el historial de LangGraph en un archivo JSON legible."""

    # Convierte cada objeto de mensaje en un diccionario sencillo.
    # La comprensión de lista aplica la función a todo el historial.
    historial_serializable = [
        convertir_mensaje_a_diccionario(mensaje)
        for mensaje in historial
    ]

    # Obtiene la fecha y hora actuales utilizando un formato
    # compatible con los nombres de archivo.
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Incluye "langgraph" para distinguir este historial
    # del generado por la versión básica.
    nombre_archivo = f"conversacion_langgraph_{fecha_hora}.json"

    # Abre el archivo en modo escritura y lo cierra automáticamente.
    with open(nombre_archivo, "w", encoding="utf-8") as archivo:
        # Guarda la lista convertida con un formato fácil de leer.
        json.dump(
            historial_serializable,
            archivo,
            ensure_ascii=False,  # Conserva tildes, eñes y otros caracteres
            indent=4,  # Organiza visualmente el contenido del JSON
        )

    # Muestra dónde se ha guardado la conversación.
    print(f"Historial guardado en: {nombre_archivo}")    


# Inicializamos el modelo ChatGroq
llm = ChatGroq(api_key=api_key, model="llama-3.1-8b-instant", temperature=0)


def answer_node(state: MessagesState) -> dict:
    """Genera una respuesta utilizando todos los mensajes del estado."""

    try:
        # Envía al modelo el historial completo.
        # Incluye las instrucciones, las preguntas del usuario
        # y las respuestas anteriores del asistente.
        response = llm.invoke(state["messages"])

    except Exception as error:
        # Informa del error concreto producido al llamar al modelo.
        print(f"Error al llamar a la API de Groq: {error}")

        # Vuelve a lanzar la misma excepción para que también pueda
        # gestionarla el try/except que rodea graph.invoke().
        raise

    # Devuelve únicamente la nueva respuesta del modelo.
    # MessagesState la añadirá al historial mediante su reductor.
    return {
        "messages": [response],
    }

# Construimos el grafo de estados
builder = StateGraph(MessagesState)

builder.add_node("answer_node", answer_node)
builder.add_edge(START, "answer_node")
builder.add_edge("answer_node", END)

graph = builder.compile()

# Crea el estado inicial con las instrucciones del asistente.
# SystemMessage identifica este texto como una instrucción general,
# no como una pregunta escrita por el usuario.
state: MessagesState = {
    "messages": [
        SystemMessage(content=SYSTEM_PROMPT),
    ]
}

# Bucle interactivo
while True:
    pregunta = input(
    "Tú ('/resumen' para resumir o 'salir' para terminar): "
    ).strip()
    
    if pregunta.lower() == "salir":
        # Extrae del estado la lista completa de objetos de mensaje
        # y la envía a la función de guardado.
        guardar_historial(state["messages"])

        # Informa de que el chatbot va a terminar.
        print("Saliendo...")

        # Finaliza el bucle de conversación.
        break

    # Comprueba si el usuario ha solicitado un resumen.
    if pregunta.lower() == "/resumen":
        # Convierte el comando especial en una instrucción detallada.
        # Cuando el nodo reciba el estado, tendrá acceso a todos los
        # mensajes anteriores y podrá resumirlos.
        contenido_usuario = (
            "Resume la conversación mantenida hasta este momento. "
            "Incluye los temas principales y la información importante, "
            "pero no añadas información nueva."
        )
    else:
        # Conserva el texto original cuando no es un comando especial.
        contenido_usuario = pregunta    

    # Crea el mensaje utilizando la pregunta normal o la instrucción
    # generada a partir del comando especial "/resumen".
    mensaje_usuario = HumanMessage(content=contenido_usuario)

    # Añade el mensaje del usuario al historial conservado en el estado.
    state["messages"].append(mensaje_usuario)

    # Ejecutamos el grafo con el estado actual
    try:
        state = graph.invoke(state)
    except Exception as e:
        print(f"Error al ejecutar el grafo: {e}")
        print("Intenta de nuevo.")
        continue

    # Obtiene el último objeto del historial, que será el AIMessage
    # devuelto por el nodo después de ejecutar correctamente el grafo.
    ultimo_mensaje = state["messages"][-1]

    # Muestra únicamente el contenido textual del mensaje.
    # Si imprimiéramos el objeto completo, aparecerían también metadatos.
    print("IA:", ultimo_mensaje.content)
    print("-" * 40) # Imprime una línea separadora para que el siguiente turno sea más legible