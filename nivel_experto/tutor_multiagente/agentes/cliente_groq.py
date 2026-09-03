import logging  # Registra de forma segura cuándo se reintentará.
import math  # Redondea la espera para no reintentar antes de tiempo.
import time  # Realiza la espera indicada por Groq.
from collections.abc import (
    Callable,
    Mapping,
)
from typing import Protocol  # Define contratos mediante tipado estructural.

from groq import (
    Groq,
    RateLimitError,
)

from nivel_experto.tutor_multiagente.config import (
    MAX_ESPERA_REINTENTO_GROQ,
    MAX_REINTENTOS_LIMITE_GROQ,
    MAX_REINTENTOS_SDK_GROQ,
    obtener_variable_entorno,
)

# Registra el reintento sin incluir respuestas, prompts ni cabeceras.
from nivel_experto.tutor_multiagente.logging_config import (
    NOMBRE_LOGGER,
    registrar_evento,
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

def obtener_espera_reintento_groq(
    error: object,
) -> int | None:
    """
    Recupera una espera segura desde la cabecera retry-after.

    Args:
        error: Excepción RateLimitError producida por el SDK.

    Returns:
        Segundos enteros de espera o None si no debe reintentarse.
    """
    # El SDK conserva la respuesta HTTP dentro de la excepción.
    respuesta = getattr(
        error,
        "response",
        None,
    )
    cabeceras = getattr(
        respuesta,
        "headers",
        None,
    )

    # No inventa una espera cuando el proveedor no la proporciona.
    if not isinstance(cabeceras, Mapping):
        return None

    valor_retry_after = cabeceras.get(
        "retry-after"
    )

    # bool debe rechazarse aunque sea una subclase de int.
    if isinstance(valor_retry_after, bool):
        return None

    try:
        segundos_originales = float(
            valor_retry_after
        )
    except (TypeError, ValueError):
        return None

    # Rechaza NaN, infinito, cero y valores negativos.
    if (
        not math.isfinite(segundos_originales)
        or segundos_originales <= 0
    ):
        return None

    # Espera hasta el siguiente segundo completo para no adelantarse.
    segundos = math.ceil(
        segundos_originales
    )

    # Si la espera es excesiva, devuelve el control al usuario.
    if segundos > MAX_ESPERA_REINTENTO_GROQ:
        return None

    return segundos


def solicitar_completion_groq(
    cliente: ClienteGroq,
    pausa: Callable[[float], None] = time.sleep,
    **parametros: object,
) -> object:
    """
    Solicita una respuesta y aplica reintentos limitados ante un 429 recuperable.

    Args:
        cliente: Cliente real o simulado con chat.completions.create.
        pausa: Función de espera sustituible durante las pruebas.
        parametros: Parámetros enviados a Groq.

    Returns:
        Respuesta producida por Groq.

    Raises:
        TypeError: Si pausa no es invocable.
        RateLimitError: Si no hay espera válida o se agotan los reintentos.
    """
    if not callable(pausa):
        raise TypeError(
            "La función de pausa debe ser invocable."
        )

    reintentos_realizados = 0

    while True:
        try:
            return cliente.chat.completions.create(
                **parametros
            )
        except RateLimitError as error:
            espera_segundos = obtener_espera_reintento_groq(
                error
            )

            # No inventa una espera cuando la cabecera está ausente,
            # es inválida o supera el máximo local.
            if espera_segundos is None:
                registrar_evento(
                    logging.getLogger(
                        NOMBRE_LOGGER
                    ),
                    "reintento_descartado",
                    nivel=logging.WARNING,
                    resultado="espera_no_admitida",
                    iteracion=reintentos_realizados,
                )
                raise

            # Detiene el ciclo cuando ya se utilizaron todos los
            # reintentos permitidos por la configuración.
            if (
                reintentos_realizados
                >= MAX_REINTENTOS_LIMITE_GROQ
            ):
                registrar_evento(
                    logging.getLogger(
                        NOMBRE_LOGGER
                    ),
                    "reintento_descartado",
                    nivel=logging.WARNING,
                    resultado="reintentos_agotados",
                    iteracion=reintentos_realizados,
                )
                raise

            reintentos_realizados += 1

            # Informa de la espera sin registrar las cabeceras completas.
            registrar_evento(
                logging.getLogger(
                    NOMBRE_LOGGER
                ),
                "reintento_programado",
                nivel=logging.WARNING,
                resultado="limite_groq",
                iteracion=reintentos_realizados,
                espera_segundos=espera_segundos,
            )

            pausa(
                espera_segundos
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
