import os  # Importa el módulo para trabajar con variables de entorno si se necesitara
from dotenv import load_dotenv  # Carga las variables definidas en el archivo .env
from groq import Groq  # Cliente oficial de Groq para hacer llamadas a la API

load_dotenv()  # Lee el archivo .env y carga las variables de entorno en el proceso
client = Groq()  # Crea el cliente Groq, usando GROQ_API_KEY de la variable de entorno

while True:  # Bucle infinito para mantener la conversación hasta que el usuario escriba "salir"
    pregunta = input("Escribe una pregunta (o 'salir' para terminar): ").strip()
    # Lee la entrada del usuario y elimina espacios al principio y al final

    if pregunta.lower() == "salir":
        # Si el usuario escribe "salir" en cualquier combinación de mayúsculas/minúsculas...
        print("Saliendo...")
        break  # ...salimos del bucle y terminamos el programa

    response = client.chat.completions.create(
        # Hace la llamada a la API de Groq para generar una respuesta de chat
        messages=[
            {"role": "user", "content": pregunta}
            # Enviamos un mensaje de tipo usuario con el texto que escribió el usuario
        ],
        model="llama-3.1-8b-instant",
        # Modelo de Groq que se usará para generar la respuesta
    )

    print("Respuesta:")
    # Imprime el encabezado para la respuesta del modelo

    print(response.choices[0].message.content)
    # Muestra el contenido de la primera opción devuelta por el modelo
    # `response.choices` es la lista de resultados,
    # `choices[0]` es el primer resultado,
    # `message.content` es el texto generado.

    print("-" * 40)
    # Imprime una línea separadora para que el siguiente turno sea más legible