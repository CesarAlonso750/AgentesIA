import re  # Permite validar nombres mediante expresiones regulares

import requests  # Permite realizar peticiones HTTP a PokeAPI


# Patrón permitido para nombres oficiales de PokeAPI.
# Acepta ejemplos como "pikachu", "mr-mime" y "porygon-z".
# Rechaza espacios, barras, URLs, guiones dobles y caracteres especiales.
PATRON_NOMBRE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Dirección base de la versión 2 de PokeAPI.
POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

# Tiempo máximo que esperaremos una respuesta de la API.
TIMEOUT_SEGUNDOS = 10


def validar_identificador(identificador: str | int) -> str:
    """Valida y normaliza un identificador recibido por una herramienta."""

    # Los booleanos son subclases de int en Python.
    # Sin esta comprobación, True podría convertirse accidentalmente en el ID 1.
    if isinstance(identificador, bool):
        raise ValueError("El identificador no puede ser un booleano.")

    # Si recibimos un entero, debe ser positivo.
    if isinstance(identificador, int):
        if identificador <= 0:
            raise ValueError("El identificador numérico debe ser mayor que cero.")

        # La URL se construirá siempre con texto.
        return str(identificador)

    # Rechaza listas, diccionarios, valores None y otros tipos inesperados.
    if not isinstance(identificador, str):
        raise TypeError("El identificador debe ser un nombre o un número entero.")

    # Elimina espacios exteriores y normaliza las mayúsculas.
    identificador_normalizado = identificador.strip().lower()

    # Rechaza cadenas vacías o compuestas únicamente por espacios.
    if not identificador_normalizado:
        raise ValueError("El identificador no puede estar vacío.")

    # Limita el tamaño para evitar entradas absurdamente grandes
    # generadas accidentalmente por el modelo.
    if len(identificador_normalizado) > 100:
        raise ValueError("El identificador es demasiado largo.")

    # Una cadena numérica también representa un ID.
    if identificador_normalizado.isdigit():
        numero = int(identificador_normalizado)

        # Rechaza valores como "0" o "000".
        if numero <= 0:
            raise ValueError("El identificador numérico debe ser mayor que cero.")

        # Elimina ceros iniciales; por ejemplo, "0025" se convierte en "25".
        return str(numero)

    # Comprueba el formato de un nombre oficial.
    if not PATRON_NOMBRE.fullmatch(identificador_normalizado):
        raise ValueError(
            "El nombre solo puede contener letras minúsculas, "
            "números y guiones simples."
        )

    # Devuelve el valor limpio y preparado para construir la URL.
    return identificador_normalizado


def consultar_pokemon(identificador: str | int) -> dict:
    """Consulta un Pokémon y devuelve únicamente sus datos principales."""

    # Valida el parámetro antes de construir la URL o realizar
    # cualquier petición externa.
    identificador_normalizado = validar_identificador(identificador)

    # Construye una URL segura utilizando el valor ya validado.
    url = f"{POKEAPI_BASE_URL}/pokemon/{identificador_normalizado}/"

    try:
        # Realiza la petición con un tiempo máximo de espera.
        respuesta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)

    except requests.Timeout:
        # Devuelve un error controlado si la API tarda demasiado.
        return {
            "ok": False,
            "error": "PokeAPI tardó demasiado en responder.",
        }

    except requests.RequestException:
        # Controla errores de conexión, DNS y otros fallos de red
        # sin exponer detalles internos al modelo.
        return {
            "ok": False,
            "error": "No se pudo conectar con PokeAPI.",
        }

    # Un 404 indica que el nombre o ID tiene un formato válido,
    # pero el recurso solicitado no existe.
    if respuesta.status_code == 404:
        return {
            "ok": False,
            "error": (
                f"No existe ningún Pokémon con el identificador "
                f"'{identificador_normalizado}'."
            ),
        }

    try:
        # Convierte otros estados HTTP de error en excepciones controlables.
        respuesta.raise_for_status()

    except requests.HTTPError:
        return {
            "ok": False,
            "error": (
                "PokeAPI devolvió un error HTTP "
                f"con código {respuesta.status_code}."
            ),
        }

    try:
        # Convierte la respuesta JSON en estructuras de Python.
        datos = respuesta.json()

    except ValueError:
        # Controla una respuesta que no contenga JSON válido.
        return {
            "ok": False,
            "error": "PokeAPI devolvió una respuesta JSON no válida.",
        }

    # La respuesta principal del endpoint debe ser un diccionario.
    if not isinstance(datos, dict):
        return {
            "ok": False,
            "error": "PokeAPI devolvió una estructura inesperada.",
        }

    # Extrae únicamente los tres campos que necesita nuestra herramienta.
    nombre = datos.get("name")
    altura_decimetros = datos.get("height")
    peso_hectogramos = datos.get("weight")

    # Comprueba que el nombre recibido sea realmente texto.
    if not isinstance(nombre, str):
        return {
            "ok": False,
            "error": "La respuesta no contiene un nombre válido.",
        }

    # Comprueba los tipos antes de realizar operaciones matemáticas.
    # También rechazamos booleanos porque Python los considera enteros.
    if (
        not isinstance(altura_decimetros, (int, float))
        or isinstance(altura_decimetros, bool)
        or not isinstance(peso_hectogramos, (int, float))
        or isinstance(peso_hectogramos, bool)
    ):
        return {
            "ok": False,
            "error": "La respuesta no contiene una altura o un peso válidos.",
        }

    # Convierte los decímetros de la API a metros.
    altura_metros = altura_decimetros / 10

    # Convierte los hectogramos de la API a kilogramos.
    peso_kilogramos = peso_hectogramos / 10

    # Devuelve una estructura pequeña, estable y fácil de entregar al modelo.
    return {
        "ok": True,
        "nombre": nombre,
        "altura_m": altura_metros,
        "peso_kg": peso_kilogramos,
    }


def consultar_item(identificador: str | int) -> dict:
    """Consulta un objeto de Pokémon y devuelve sus datos principales."""

    # Valida el parámetro antes de construir la URL o realizar
    # cualquier petición externa.
    identificador_normalizado = validar_identificador(identificador)

    # Construye la URL del endpoint de objetos utilizando
    # exclusivamente el identificador validado.
    url = f"{POKEAPI_BASE_URL}/item/{identificador_normalizado}/"

    try:
        # Realiza la petición con un tiempo máximo de espera.
        respuesta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)

    except requests.Timeout:
        # Controla las peticiones que superan el tiempo permitido.
        return {
            "ok": False,
            "error": "PokeAPI tardó demasiado en responder.",
        }

    except requests.RequestException:
        # Controla errores de conexión sin mostrar detalles internos.
        return {
            "ok": False,
            "error": "No se pudo conectar con PokeAPI.",
        }

    # Distingue un objeto inexistente de otros errores HTTP.
    if respuesta.status_code == 404:
        return {
            "ok": False,
            "error": (
                f"No existe ningún objeto con el identificador "
                f"'{identificador_normalizado}'."
            ),
        }

    try:
        # Detecta otros códigos HTTP que representen un error.
        respuesta.raise_for_status()

    except requests.HTTPError:
        return {
            "ok": False,
            "error": (
                "PokeAPI devolvió un error HTTP "
                f"con código {respuesta.status_code}."
            ),
        }

    try:
        # Convierte el cuerpo JSON en estructuras de Python.
        datos = respuesta.json()

    except ValueError:
        # Controla una respuesta que no sea JSON válido.
        return {
            "ok": False,
            "error": "PokeAPI devolvió una respuesta JSON no válida.",
        }

    # El endpoint debe devolver un objeto JSON, representado por un diccionario.
    if not isinstance(datos, dict):
        return {
            "ok": False,
            "error": "PokeAPI devolvió una estructura inesperada.",
        }

    # Extrae el nombre, la categoría y la lista de efectos.
    nombre = datos.get("name")
    categoria = datos.get("category")
    efectos = datos.get("effect_entries")

    # Comprueba que el nombre sea texto.
    if not isinstance(nombre, str):
        return {
            "ok": False,
            "error": "La respuesta no contiene un nombre válido.",
        }

    # La categoría debe ser un diccionario con un nombre.
    if (
        not isinstance(categoria, dict)
        or not isinstance(categoria.get("name"), str)
    ):
        return {
            "ok": False,
            "error": "La respuesta no contiene una categoría válida.",
        }

    # La colección de efectos debe ser una lista.
    if not isinstance(efectos, list):
        return {
            "ok": False,
            "error": "La respuesta no contiene una lista de efectos válida.",
        }

    # Valor utilizado cuando el objeto no tenga una descripción
    # breve disponible en inglés.
    efecto_breve = "No hay un efecto breve disponible en inglés."

    # Recorre las distintas traducciones del efecto.
    for efecto in efectos:
        # Ignora entradas con una estructura inesperada.
        if not isinstance(efecto, dict):
            continue

        idioma = efecto.get("language")
        texto_breve = efecto.get("short_effect")

        # Selecciona únicamente la descripción inglesa.
        if (
            isinstance(idioma, dict)
            and idioma.get("name") == "en"
            and isinstance(texto_breve, str)
            and texto_breve.strip()
        ):
            # Elimina espacios exteriores del texto recibido.
            efecto_breve = texto_breve.strip()
            break

    # Devuelve únicamente los tres datos que necesita el agente.
    return {
        "ok": True,
        "nombre": nombre,
        "categoria": categoria["name"],
        "efecto_breve": efecto_breve,
    }