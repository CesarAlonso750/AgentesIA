# AgentesIA

Repositorio de ejercicios sobre modelos de lenguaje, memoria conversacional, herramientas y agentes construidos con y sin LangGraph.

## Estructura

- `nivel_basico`: primeras llamadas a un modelo de lenguaje.
- `nivel_intermedio`: chatbots con memoria e historial persistente.
- `nivel_avanzado`: agentes que utilizan PokeAPI mediante herramientas.
- `nivel_experto`: proyecto final multiagente.

Cada ejercicio dispone, cuando corresponde, de una versión construida manualmente y otra implementada con LangGraph.

## Ejecución

Los comandos deben ejecutarse desde la raíz del repositorio.

### Nivel básico

```powershell
# Ejecuta la primera llamada sin LangGraph
python .\nivel_basico\primera_llamada.py

# Ejecuta la primera llamada con LangGraph
python .\nivel_basico\primera_llamada_langgraph.py
```

### Nivel intermedio

```powershell
# Ejecuta el chatbot con memoria sin LangGraph
python .\nivel_intermedio\chatbot_memoria.py

# Ejecuta el chatbot con memoria y LangGraph
python .\nivel_intermedio\chatbot_memoria_langgraph.py
```

### Nivel avanzado

```powershell
# Ejecuta el agente de PokeAPI construido manualmente
python .\nivel_avanzado\agente_pokeapi.py

# Ejecuta el agente de PokeAPI construido con LangGraph
python .\nivel_avanzado\agente_pokeapi_langgraph.py
```

## Configuración

El proyecto utiliza la variable de entorno `GROQ_API_KEY`, definida en un archivo `.env` que no debe subirse al repositorio.