import json  # Permite convertir y guardar el historial en formato JSON
import os  # Permite acceder a las variables de entorno
import sys  # Permite terminar el programa si falta la clave de la API
from datetime import datetime  # Permite obtener la fecha y hora actuales

from dotenv import load_dotenv  # Carga las variables definidas en el archivo .env
from groq import Groq  # Cliente oficial de Groq para hacer llamadas a la API

load_dotenv()  # Lee el archivo .env y carga las variables de entorno en el proceso
api_key = os.getenv("GROQ_API_KEY") # Obtiene la clave de API de Groq desde las variables de entorno
if not api_key:
    print("Error: variable de entorno GROQ_API_KEY no definida.")
    sys.exit(1)

client = Groq(api_key=api_key)  # Crea el cliente Groq, usando GROQ_API_KEY de la variable de entorno

# Define las instrucciones generales que seguirá el asistente.
# Lo guardamos en una variable separada para poder cambiarlo fácilmente
# cuando comparemos diferentes comportamientos.
SYSTEM_PROMPT = (
    "Eres un tutor de programación paciente. "
    "Responde siempre en español, explica los conceptos paso a paso "
    "y utiliza ejemplos sencillos."
)

# Crea el historial de la conversación.
# La lista se declara fuera del bucle para que no se reinicie
# cada vez que el usuario escriba una pregunta.
mensajes = [
    {
        # El rol "system" define el comportamiento general del asistente.
        "role": "system",

        # El contenido contiene las instrucciones declaradas anteriormente.
        "content": SYSTEM_PROMPT,
    }
]

def guardar_historial(historial):
    """Guarda el historial completo de la conversación en un archivo JSON."""

    # Obtiene la fecha y la hora actuales.
    # El formato evita caracteres no válidos en nombres de archivo,
    # como los dos puntos utilizados normalmente en las horas.
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Construye un nombre como:
    # conversacion_2026-08-12_18-30-45.json
    nombre_archivo = f"conversacion_{fecha_hora}.json"

    # Abre un archivo nuevo en modo escritura.
    # "with" se encarga de cerrarlo automáticamente al terminar.
    with open(nombre_archivo, "w", encoding="utf-8") as archivo:
        # Convierte la lista de mensajes a JSON y la escribe en el archivo.
        json.dump(
            historial,
            archivo,
            ensure_ascii=False,  # Conserva correctamente tildes y caracteres como la ñ
            indent=4,  # Organiza el JSON para que resulte fácil de leer
        )

    # Informa al usuario del nombre del archivo generado.
    print(f"Historial guardado en: {nombre_archivo}")

while True:  # Bucle infinito para mantener la conversación hasta que el usuario escriba "salir"
    # Informa al usuario de los dos comandos especiales disponibles.
    pregunta = input(
        "Escribe una pregunta, '/resumen' para resumir "
        "o 'salir' para terminar: "
    ).strip()
    # Lee la entrada del usuario y elimina espacios al principio y al final

    if pregunta.lower() == "salir":
        # Si el usuario escribe "salir", llama a la función
        # para guardar todos los mensajes acumulados.
        guardar_historial(mensajes)

        # Informa de que el programa va a terminar.
        print("Saliendo...")

        # Finaliza el bucle de conversación.
        break
    
    # Comprueba si el usuario ha utilizado el comando especial "/resumen".
    if pregunta.lower() == "/resumen":
        # Transforma el comando en una instrucción comprensible para el modelo.
        # El historial anterior ya está en la lista "mensajes", por lo que
        # el modelo podrá resumir la conversación mantenida hasta este momento.
        contenido_usuario = (
            "Resume la conversación mantenida hasta este momento. "
            "Incluye los temas principales y la información importante, "
            "pero no añadas información nueva."
        )
    else:
        # Si no es un comando especial, conserva la pregunta original.
        contenido_usuario = pregunta
    
    # Añade la pregunta actual al historial con el rol "user".
    # Al estar después de la comprobación anterior, la palabra "salir"
    # no se guardará como parte de la conversación.
    mensajes.append(
        {
            # Indica que este mensaje procede del usuario.
            "role": "user",

            # Guarda el texto introducido en la terminal.
            "content": contenido_usuario,
        }
    )

    try:
        # Realiza una petición al modelo utilizando toda la conversación.
        response = client.chat.completions.create(
        # Envía el historial completo, incluido el mensaje de sistema
        # y todas las preguntas almacenadas hasta este momento.
        messages=mensajes,

        # Indica el modelo de Groq que generará la respuesta.
        model="llama-3.1-8b-instant",
        temperature=0, # Reduce la aleatoriedad para producir respuestas más consistentes y facilitar las comparaciones.
        )
    except Exception as e:
        print(f"Error al llamar a la API de Groq: {e}")
        print("Asegúrate de que la variable de entorno GROQ_API_KEY esté definida correctamente.")
        continue  # Continuamos con la siguiente iteración del bucle para que el usuario pueda intentar de nuevo
    
    # Extrae el texto generado por el modelo y lo guarda en una variable.
    respuesta_asistente = response.choices[0].message.content

    # Añade la respuesta al historial con el rol "assistant".
    # De esta forma, Groq recibirá también esta respuesta en la próxima llamada.
    mensajes.append(
        {
            # Indica que este mensaje fue generado por el asistente.
            "role": "assistant",

            # Guarda el texto que devolvió el modelo.
            "content": respuesta_asistente,
        }
    )

    # Muestra un encabezado para distinguir la respuesta.
    print("Respuesta:")

    # Muestra la respuesta que también acabamos de guardar en el historial.
    print(respuesta_asistente)

    print("-" * 40)
    # Imprime una línea separadora para que el siguiente turno sea más legible