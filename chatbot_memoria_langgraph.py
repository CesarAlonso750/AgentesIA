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
    pregunta = input("Tú: ").strip()
    if pregunta.lower() == "salir":
        print("Saliendo...")
        break

    # Convierte la pregunta en un mensaje estructurado de usuario.
    # Esto permite que el modelo distinga claramente quién escribió el texto.
    mensaje_usuario = HumanMessage(content=pregunta)

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