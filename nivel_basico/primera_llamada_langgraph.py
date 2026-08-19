import os  # Para acceso a variables de entorno si es necesario
import sys
from typing import TypedDict, List

from dotenv import load_dotenv  # Carga las variables de .env
from langchain_groq import ChatGroq  # Wrapper de LangChain para Groq
from langgraph.graph import StateGraph, START, END  # Grafo de estados de langgraph

load_dotenv()  # Carga GROQ_API_KEY u otras variables desde .env
api_key = os.getenv("GROQ_API_KEY") # Obtiene la clave de API de Groq desde las variables de entorno
if not api_key:
    print("Error: variable de entorno GROQ_API_KEY no definida.")
    sys.exit(1)

# Definimos el estado compartido del workflow
# Aquí solo guardamos el historial de mensajes
class ChatState(TypedDict):
    messages: List[str]

# Inicializamos el modelo ChatGroq
llm = ChatGroq(api_key=api_key, model="openai/gpt-oss-20b", temperature=0)

# Nodo que genera la respuesta del agente en función del último mensaje del usuario
def answer_node(state: ChatState) -> ChatState:
    messages = state["messages"]
    user_message = messages[-1]  # El último mensaje es la pregunta actual del usuario

    try:
        response = llm.invoke(
            f"Responde en español de forma clara y breve:\n{user_message}"
        )
    except Exception as e:
        print(f"Error al llamar a la API de Groq: {e}")
        print("Asegúrate de que la variable de entorno GROQ_API_KEY esté definida correctamente.")
        return {"messages": messages + ["[Error: no se pudo generar respuesta]"]}

    # Añadimos la respuesta generada al historial de mensajes
    return {"messages": messages + [response.content]}

# Construimos el grafo de estados
builder = StateGraph(ChatState)

builder.add_node("answer_node", answer_node)
builder.add_edge(START, "answer_node")
builder.add_edge("answer_node", END)

graph = builder.compile()

# Estado inicial vacío
state: ChatState = {"messages": []}

# Bucle interactivo
while True:
    pregunta = input("Tú: ").strip()
    if pregunta.lower() == "salir":
        print("Saliendo...")
        break

    # Añadimos el mensaje del usuario al estado
    state["messages"].append(pregunta)

    # Ejecutamos el grafo con el estado actual
    try:
        state = graph.invoke(state)
    except Exception as e:
        print(f"Error al ejecutar el grafo: {e}")
        print("Intenta de nuevo.")
        continue

    # Mostramos la respuesta generada por el modelo
    print("IA:", state["messages"][-1])
    print("-" * 40)