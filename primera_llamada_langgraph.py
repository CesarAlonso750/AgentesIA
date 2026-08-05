import os  # Para acceso a variables de entorno si es necesario
from typing import TypedDict, List

from dotenv import load_dotenv  # Carga las variables de .env
from langchain_groq import ChatGroq  # Wrapper de LangChain para Groq
from langgraph.graph import StateGraph, START, END  # Grafo de estados de langgraph

load_dotenv()  # Carga GROQ_API_KEY u otras variables desde .env

# Definimos el estado compartido del workflow
# Aquí solo guardamos el historial de mensajes
class ChatState(TypedDict):
    messages: List[str]

# Inicializamos el modelo ChatGroq
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

# Nodo que genera la respuesta del agente en función del último mensaje del usuario
def answer_node(state: ChatState) -> ChatState:
    messages = state["messages"]
    user_message = messages[-1]  # El último mensaje es la pregunta actual del usuario

    response = llm.invoke(
        f"Responde en español de forma clara y breve:\n{user_message}"
    )
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
    state = graph.invoke(state)

    # Mostramos la respuesta generada por el modelo
    print("IA:", state["messages"][-1])
    print("-" * 40)