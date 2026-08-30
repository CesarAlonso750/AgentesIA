from typing import Protocol  # Define contratos mediante tipado estructural.

from groq import Groq  # Cliente oficial utilizado en la versión manual.

from nivel_experto.tutor_multiagente.config import (
    MAX_REINTENTOS_SDK_GROQ,
    obtener_variable_entorno,
)


class CreadorCompletions(Protocol):
    """
    Define el método utilizado para solicitar una respuesta al modelo.
    """

    def create(self, **parametros: object) -> object:
        """Crea una respuesta de chat."""
        ...


class RecursoChat(Protocol):
    """
    Representa el atributo chat del cliente de Groq.
    """

    completions: CreadorCompletions


class ClienteGroq(Protocol):
    """
    Define la parte del cliente utilizada por los agentes.

    Groq cumple este contrato y los tests pueden proporcionar clientes
    simulados con la misma estructura.
    """

    chat: RecursoChat


def crear_cliente_groq() -> Groq:
    """
    Crea el cliente real utilizando la clave almacenada en el entorno.

    Returns:
        Cliente oficial de Groq configurado.
    """
    # Recupera la clave sin imprimirla ni incorporarla al código fuente.
    api_key = obtener_variable_entorno("GROQ_API_KEY")

    # Evita esperas automáticas largas ante límites o fallos temporales.
    # Cada agente convierte después esos errores en RuntimeError controlados.
    return Groq(
        api_key=api_key,
        max_retries=MAX_REINTENTOS_SDK_GROQ,
    )

def obtener_contenido_respuesta(respuesta: object) -> str:
    """
    Recupera el contenido textual de una respuesta de Groq.

    Args:
        respuesta: Objeto externo devuelto por el SDK.

    Returns:
        Contenido textual no vacío.

    Raises:
        RuntimeError: Si la estructura recibida no es válida.
    """
    # Una respuesta de chat debe contener una colección choices.
    choices = getattr(respuesta, "choices", None)

    if not isinstance(choices, list) or not choices:
        raise RuntimeError(
            "Groq devolvió una respuesta sin alternativas."
        )

    # Utiliza únicamente la primera alternativa.
    primera_alternativa = choices[0]

    # La alternativa debe contener un mensaje.
    mensaje = getattr(primera_alternativa, "message", None)

    if mensaje is None:
        raise RuntimeError(
            "La respuesta de Groq no contiene un mensaje."
        )

    # El JSON estructurado se recibe en el campo content.
    contenido = getattr(mensaje, "content", None)

    if not isinstance(contenido, str) or not contenido.strip():
        raise RuntimeError(
            "La respuesta de Groq no contiene contenido válido."
        )

    return contenido.strip()

def extraer_generacion_json_fallida(
    error: object,
) -> str | None:
    """
    Recupera el JSON rechazado por Structured Outputs de Groq.

    Args:
        error: Excepción recibida desde el SDK de Groq.

    Returns:
        JSON generado y rechazado, o None si el error tiene otra causa.
    """
    # El SDK conserva normalmente la respuesta estructurada en body.
    cuerpo = getattr(
        error,
        "body",
        None,
    )

    if not isinstance(cuerpo, dict):
        return None

    # Según la versión del SDK, el contenido puede estar anidado.
    datos_error = cuerpo.get(
        "error",
        cuerpo,
    )

    if not isinstance(datos_error, dict):
        return None

    codigo = datos_error.get(
        "code"
    )

    if codigo != "json_validate_failed":
        return None

    generacion_fallida = datos_error.get(
        "failed_generation"
    )

    if not isinstance(generacion_fallida, str):
        return None

    generacion_normalizada = (
        generacion_fallida.strip()
    )

    if not generacion_normalizada:
        return None

    return generacion_normalizada
