from typing import Protocol  # Permite describir el contrato del cliente externo.

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
    FORMATO_EXTRACCION,
    MAX_CARACTERES_EXTRAIDOS,
    MAX_EXTRACCIONES_POR_TURNO,
    MAX_FRAGMENTOS_POR_FUENTE,
    PROFUNDIDAD_EXTRACCION,
    obtener_variable_entorno,
)
from nivel_experto.tutor_multiagente.herramientas.fuentes import (
    obtener_fuente_oficial,
)
from nivel_experto.tutor_multiagente.validadores import (
    validar_consulta,
    validar_url_oficial,
)


class ClienteExtraccion(Protocol):
    """
    Define el comportamiento que debe tener el cliente de extracción.

    TavilyClient dispone del método extract. En los tests podremos sustituirlo
    por un cliente simulado para no realizar conexiones ni consumir créditos.
    """

    def extract(
        self,
        urls: str | list[str],
        **parametros: object,
    ) -> dict:
        """Extrae contenido de una URL o de una lista de URL."""
        ...


def _crear_cliente_tavily() -> TavilyClient:
    """
    Crea el cliente real de Tavily utilizando la variable de entorno.
    """
    # Recupera la clave sin mostrarla ni guardarla en el código fuente.
    api_key = obtener_variable_entorno("TAVILY_API_KEY")

    # Devuelve el cliente oficial configurado.
    return TavilyClient(api_key=api_key)


def _crear_resultado_error(mensaje: str) -> dict[str, object]:
    """
    Construye una respuesta uniforme cuando la extracción falla.
    """
    return {
        "ok": False,
        "error": mensaje,
        "fuentes": [],
    }

def _validar_urls_extraccion(
    urls: object,
    dominios_permitidos: list[str],
) -> list[str]:
    """
    Valida las URL que se enviarán posteriormente a Tavily Extract.

    Args:
        urls: Lista recibida desde el agente o desde otra parte del programa.
        dominios_permitidos: Dominios oficiales definidos para la tecnología.

    Returns:
        Lista de URL oficiales, normalizadas y sin duplicados.

    Raises:
        TypeError: Si urls no es una lista.
        ValueError: Si la lista está vacía, supera el límite o contiene
            alguna URL no autorizada.
    """
    # Una llamada de herramienta representa las URL mediante un array JSON,
    # que Python convierte en una lista.
    if not isinstance(urls, list):
        raise TypeError("Las URL deben proporcionarse dentro de una lista.")

    # No tendría sentido llamar a Tavily sin ninguna página que extraer.
    if not urls:
        raise ValueError("Debe proporcionarse al menos una URL.")

    # Limita el consumo y evita que el modelo solicite demasiadas extracciones.
    if len(urls) > MAX_EXTRACCIONES_POR_TURNO:
        raise ValueError(
            "No se pueden extraer más de "
            f"{MAX_EXTRACCIONES_POR_TURNO} URL por turno."
        )

    urls_validadas = []

    # Permite detectar URL repetidas de manera eficiente.
    urls_incluidas = set()

    for url in urls:
        # Comprueba HTTPS, dominio, puerto, credenciales y otros aspectos
        # de seguridad mediante el validador que ya hemos probado.
        url_validada = validar_url_oficial(
            url,
            dominios_permitidos,
        )

        # Evita pagar y procesar dos veces la misma página.
        if url_validada in urls_incluidas:
            continue

        urls_incluidas.add(url_validada)
        urls_validadas.append(url_validada)

    # Esta comprobación es defensiva. Normalmente ya existirá al menos una URL,
    # pero garantiza que nunca se haga una extracción con una lista vacía.
    if not urls_validadas:
        raise ValueError("No queda ninguna URL válida para extraer.")

    return urls_validadas

def _procesar_extracciones(
    respuesta: object,
    dominios_permitidos: list[str],
    urls_solicitadas: list[str],
) -> list[dict[str, str]]:
    """
    Valida y simplifica los resultados devueltos por Tavily Extract.

    Args:
        respuesta: Respuesta externa que podría estar mal formada.
        dominios_permitidos: Dominios oficiales de la tecnología.
        urls_solicitadas: URL que nuestro programa pidió extraer.

    Returns:
        Lista de fuentes oficiales con su contenido extraído.

    Raises:
        RuntimeError: Si la estructura principal de la respuesta no es válida.
    """
    # La respuesta JSON principal debe haberse convertido en un diccionario.
    if not isinstance(respuesta, dict):
        raise RuntimeError(
            "Tavily devolvió una respuesta de extracción con formato inválido."
        )

    resultados_originales = respuesta.get("results")

    # El campo results es obligatorio y debe contener una lista.
    if not isinstance(resultados_originales, list):
        raise RuntimeError(
            "La respuesta de Tavily no contiene una lista de extracciones."
        )

    # Solo se admitirán resultados correspondientes a páginas que solicitamos.
    urls_solicitadas_set = set(urls_solicitadas)

    # Evita aceptar dos veces el contenido de la misma página.
    urls_incluidas = set()

    fuentes_extraidas = []
    caracteres_acumulados = 0

    for resultado in resultados_originales:
        # Ignora elementos externos que no tengan estructura de objeto.
        if not isinstance(resultado, dict):
            continue

        url = resultado.get("url")
        contenido = resultado.get("raw_content")

        # Ambos campos son obligatorios y deben contener texto.
        if (
            not isinstance(url, str)
            or not isinstance(contenido, str)
            or not contenido.strip()
        ):
            continue

        try:
            # Comprueba otra vez que la página pertenezca a un dominio oficial.
            url_validada = validar_url_oficial(
                url,
                dominios_permitidos,
            )
        except (TypeError, ValueError):
            # Una URL insegura o mal formada no se entrega al agente.
            continue

        # Tavily solo debe devolver páginas que nosotros hayamos solicitado.
        if url_validada not in urls_solicitadas_set:
            continue

        # Evita procesar dos veces una misma página.
        if url_validada in urls_incluidas:
            continue

        contenido_normalizado = contenido.strip()

        # Calcula cuánto espacio queda dentro del límite global.
        caracteres_disponibles = (
            MAX_CARACTERES_EXTRAIDOS - caracteres_acumulados
        )

        # Detiene el procesamiento cuando se ha agotado el límite.
        if caracteres_disponibles <= 0:
            break

        # Recorta el contenido para no desbordar el contexto del futuro agente.
        contenido_limitado = contenido_normalizado[:caracteres_disponibles]

        urls_incluidas.add(url_validada)
        caracteres_acumulados += len(contenido_limitado)

        # El identificador se crea después de descartar elementos inválidos.
        identificador = f"fuente-{len(fuentes_extraidas) + 1}"

        fuentes_extraidas.append(
            {
                "id": identificador,
                "url": url_validada,
                "contenido": contenido_limitado,
            }
        )

    return fuentes_extraidas

def extraer_documentacion(
    tecnologia: object,
    consulta: object,
    urls: object,
    cliente: ClienteExtraccion | None = None,
) -> dict[str, object]:
    """
    Extrae fragmentos relevantes de páginas oficiales.

    Args:
        tecnologia: Identificador de una tecnología registrada.
        consulta: Información concreta que se quiere localizar.
        urls: Lista de páginas oficiales que se quieren procesar.
        cliente: Cliente alternativo utilizado en las pruebas.

    Returns:
        Diccionario con las fuentes extraídas o un error controlado.

    Raises:
        TypeError: Si las entradas tienen tipos incorrectos.
        ValueError: Si la tecnología, consulta o lista de URL no es válida.
        RuntimeError: Si falta una variable de entorno obligatoria.
    """
    # Comprueba que la tecnología exista en el catálogo local.
    fuente = obtener_fuente_oficial(tecnologia)

    # Normaliza la consulta antes de enviarla al servicio externo.
    consulta_normalizada = validar_consulta(consulta)

    # El catálogo ya ha validado que este campo sea una lista de dominios.
    dominios_permitidos = list(fuente["dominios_permitidos"])

    # Valida todas las URL antes de crear o utilizar el cliente externo.
    urls_validadas = _validar_urls_extraccion(
        urls,
        dominios_permitidos,
    )

    # Utiliza el cliente simulado de los tests o crea el cliente real.
    cliente_extraccion = (
        cliente
        if cliente is not None
        else _crear_cliente_tavily()
    )

    # Añade el nombre de la tecnología para orientar mejor la selección
    # de fragmentos relevantes realizada por Tavily.
    consulta_tavily = f"{fuente['nombre']} {consulta_normalizada}"

    try:
        # Solicita únicamente fragmentos relacionados con la consulta.
        respuesta = cliente_extraccion.extract(
            urls=urls_validadas,
            query=consulta_tavily,
            chunks_per_source=MAX_FRAGMENTOS_POR_FUENTE,
            extract_depth=PROFUNDIDAD_EXTRACCION,
            format=FORMATO_EXTRACCION,
            include_images=False,
            include_favicon=False,
            include_usage=True,
            timeout=10,
        )
    except (MissingAPIKeyError, InvalidAPIKeyError, ForbiddenError):
        return _crear_resultado_error(
            "No se pudo autenticar la petición con Tavily."
        )
    except UsageLimitExceededError:
        return _crear_resultado_error(
            "Se ha alcanzado el límite de uso de Tavily."
        )
    except TavilyTimeoutError:
        return _crear_resultado_error(
            "Tavily tardó demasiado tiempo en extraer el contenido."
        )
    except BadRequestError:
        return _crear_resultado_error(
            "Tavily rechazó los parámetros de la extracción."
        )
    except Exception:
        # Un error externo inesperado no debe cerrar toda la aplicación.
        return _crear_resultado_error(
            "No se pudo completar la extracción por un error externo."
        )

    try:
        # Valida las URL y limita el contenido antes de entregarlo al agente.
        fuentes_extraidas = _procesar_extracciones(
            respuesta,
            dominios_permitidos,
            urls_validadas,
        )
    except RuntimeError as error:
        # Convierte una respuesta externa mal formada en un error controlado.
        return _crear_resultado_error(str(error))

    # Impide que el agente intente contestar sin documentación extraída.
    if not fuentes_extraidas:
        return _crear_resultado_error(
            "No se pudo extraer contenido de las páginas oficiales."
        )

    # Devuelve únicamente información que ha superado las validaciones.
    return {
        "ok": True,
        "tecnologia": fuente["id"],
        "consulta": consulta_normalizada,
        "fuentes": fuentes_extraidas,
    }