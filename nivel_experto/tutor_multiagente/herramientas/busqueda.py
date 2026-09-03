from typing import Protocol  # Permite definir el comportamiento esperado del cliente.

from tavily import (
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    TavilyClient,
    UsageLimitExceededError,
)
from tavily.errors import (
    ForbiddenError,
    TimeoutError as TavilyTimeoutError,
)

from nivel_experto.tutor_multiagente.config import (
    MAX_RESULTADOS_BUSQUEDA,
    PROFUNDIDAD_BUSQUEDA,
    obtener_variable_entorno,
)
from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    obtener_fuente_oficial,
)
from nivel_experto.tutor_multiagente.validadores import (
    validar_consulta,
    validar_url_oficial,
)


class ClienteBusqueda(Protocol):
    """
    Define el método que debe ofrecer cualquier cliente de búsqueda.

    TavilyClient cumple este contrato. En las pruebas utilizaremos objetos
    simulados con el mismo método para evitar consumir créditos.
    """

    def search(self, query: str, **parametros: object) -> dict:
        """Realiza una búsqueda y devuelve una respuesta estructurada."""
        ...


def _crear_cliente_tavily() -> TavilyClient:
    """
    Crea el cliente real utilizando la clave almacenada en el entorno.
    """
    # Obtiene la clave sin imprimirla ni incorporarla a mensajes de error.
    api_key = obtener_variable_entorno("TAVILY_API_KEY")

    # Entrega la clave directamente al cliente oficial de Tavily.
    return TavilyClient(api_key=api_key)


def _crear_resultado_error(mensaje: str) -> dict[str, object]:
    """
    Construye la respuesta uniforme utilizada ante errores externos.
    """
    return {
        "ok": False,
        "error": mensaje,
        "resultados": [],
    }

def _procesar_resultados(
    respuesta: object,
    dominios_permitidos: list[str],
) -> list[dict[str, object]]:
    """
    Valida, filtra y simplifica los resultados devueltos por Tavily.

    Args:
        respuesta: Respuesta externa que podría tener un formato inesperado.
        dominios_permitidos: Dominios oficiales obtenidos del catálogo.

    Returns:
        Lista de resultados seguros con identificadores internos.

    Raises:
        RuntimeError: Si la estructura principal de Tavily no es válida.
    """
    # La respuesta principal debe ser un objeto JSON convertido a diccionario.
    if not isinstance(respuesta, dict):
        raise RuntimeError(
            "Tavily devolvió una respuesta con formato inválido."
        )

    resultados_originales = respuesta.get("results")

    # El campo results debe existir y contener una lista.
    if not isinstance(resultados_originales, list):
        raise RuntimeError(
            "La respuesta de Tavily no contiene una lista de resultados."
        )

    resultados_validos = []

    # Permite detectar páginas repetidas sin recorrer toda la lista cada vez.
    urls_incluidas = set()

    for resultado in resultados_originales:
        # Ignora elementos que no sean objetos.
        if not isinstance(resultado, dict):
            continue

        titulo = resultado.get("title")
        url = resultado.get("url")
        resumen = resultado.get("content", "")
        puntuacion = resultado.get("score")

        # El título y la URL son obligatorios.
        if (
            not isinstance(titulo, str)
            or not titulo.strip()
            or not isinstance(url, str)
        ):
            continue

        try:
            # Vuelve a validar la URL aunque Tavily ya filtre por dominio.
            url_validada = validar_url_oficial(
                url,
                dominios_permitidos,
            )
        except (TypeError, ValueError):
            # Una página insegura no se entrega al agente.
            continue

        # Evita incluir dos veces la misma página.
        if url_validada in urls_incluidas:
            continue

        urls_incluidas.add(url_validada)

        # El resumen es opcional, pero se limita para controlar el contexto.
        resumen_normalizado = (
            resumen.strip()[:1_000]
            if isinstance(resumen, str)
            else ""
        )

        # bool hereda de int en Python, por eso se rechaza explícitamente.
        puntuacion_normalizada = (
            float(puntuacion)
            if isinstance(puntuacion, (int, float))
            and not isinstance(puntuacion, bool)
            else None
        )

        # El identificador se genera después de descartar resultados inválidos.
        identificador = f"resultado-{len(resultados_validos) + 1}"

        resultados_validos.append(
            {
                "id": identificador,
                "titulo": titulo.strip()[:300],
                "url": url_validada,
                "resumen": resumen_normalizado,
                "puntuacion": puntuacion_normalizada,
            }
        )

    return resultados_validos

def buscar_documentacion(
    tecnologia: object,
    consulta: object,
    cliente: ClienteBusqueda | None = None,
) -> dict[str, object]:
    """
    Busca documentación en los dominios oficiales de una tecnología.

    Args:
        tecnologia: Identificador de la tecnología registrada.
        consulta: Tema que se quiere investigar.
        cliente: Cliente alternativo utilizado en las pruebas.

    Returns:
        Diccionario con resultados oficiales o un error controlado.

    Raises:
        TypeError: Si las entradas tienen tipos incorrectos.
        ValueError: Si la tecnología o la consulta no son válidas.
        RuntimeError: Si falta una variable de entorno obligatoria.
    """
    # Valida el identificador y confirma que existe en el catálogo.
    fuente = obtener_fuente_oficial(tecnologia)

    # Normaliza la consulta antes de enviarla al servicio externo.
    consulta_normalizada = validar_consulta(consulta)

    # El catálogo ya ha comprobado que este campo sea una lista de textos.
    dominios_permitidos = list(fuente["dominios_permitidos"])

    # Usa el cliente simulado de los tests o crea el cliente real.
    cliente_busqueda = (
        cliente
        if cliente is not None
        else _crear_cliente_tavily()
    )

    # Añade el nombre de la tecnología para mejorar la búsqueda principal.
    consulta_tavily = f"{fuente['nombre']} {consulta_normalizada}"

    # La búsqueda avanzada es el intento principal. Si Tavily no devuelve
    # ninguna página oficial utilizable, se realiza un único intento básico
    # con una consulta más directa.
    intentos_busqueda = (
        (
            consulta_tavily,
            PROFUNDIDAD_BUSQUEDA,
            3,
        ),
        (
            consulta_normalizada,
            "basic",
            1,
        ),
    )

    for (
        consulta_intento,
        profundidad_intento,
        fragmentos_intento,
    ) in intentos_busqueda:
        try:
            # Tavily solo encuentra páginas; no genera la respuesta.
            respuesta = cliente_busqueda.search(
                query=consulta_intento,
                search_depth=profundidad_intento,
                chunks_per_source=fragmentos_intento,
                topic="general",
                max_results=MAX_RESULTADOS_BUSQUEDA,
                include_domains=dominios_permitidos,
                include_answer=False,
                include_raw_content=False,
                include_images=False,
                auto_parameters=False,
                include_usage=True,
                timeout=10,
            )
        except (
            MissingAPIKeyError,
            InvalidAPIKeyError,
            ForbiddenError,
        ):
            return _crear_resultado_error(
                "No se pudo autenticar la petición con Tavily."
            )
        except UsageLimitExceededError:
            return _crear_resultado_error(
                "Se ha alcanzado el límite de uso de Tavily."
            )
        except TavilyTimeoutError:
            return _crear_resultado_error(
                "Tavily tardó demasiado tiempo en responder."
            )
        except BadRequestError:
            return _crear_resultado_error(
                "Tavily rechazó los parámetros de la búsqueda."
            )
        except Exception:
            # Impide que un fallo inesperado cierre toda la sesión.
            return _crear_resultado_error(
                "No se pudo completar la búsqueda por un "
                "error externo."
            )

        try:
            # Filtra URLs, duplicados y estructuras incompletas.
            resultados = _procesar_resultados(
                respuesta,
                dominios_permitidos,
            )
        except RuntimeError as error:
            return _crear_resultado_error(str(error))

        # Detiene los intentos en cuanto encuentra resultados seguros.
        if resultados:
            return {
                "ok": True,
                "tecnologia": fuente["id"],
                "consulta": consulta_normalizada,
                "resultados": resultados,
            }

    # Los dos intentos terminaron sin páginas oficiales utilizables.
    return _crear_resultado_error(
        "No se encontró documentación oficial para la consulta."
    )